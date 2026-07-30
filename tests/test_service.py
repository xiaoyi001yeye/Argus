import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from argus.cache import LogFileCache
from argus.config import EnvironmentConfig, SourceConfig
from argus.providers.local import LocalFileProvider
from argus.service import LogService


class LogServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        log = Path(self.temp_directory.name) / "app.log"
        log.write_text(
            "\n".join(
                [
                    "2026-07-28T09:03:20+08:00 WARN pool low",
                    "2026-07-28T09:03:21+08:00 ERROR Database timed out token=secret",
                    "2026-07-28T09:03:22+08:00 INFO request failed",
                ]
            ),
            encoding="utf-8",
        )
        environment = EnvironmentConfig(
            provider="local",
            sources={"orders": SourceConfig(path=log, description="Orders")},
        )
        self.service = LogService(environment, LocalFileProvider(environment.sources))

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_lists_only_configured_sources(self) -> None:
        self.assertEqual([source.id for source in self.service.list_sources()], ["orders"])

    def test_lists_files_for_source(self) -> None:
        listing = self.service.list_files("orders")

        self.assertEqual([file.name for file in listing.files], ["app.log"])

    def test_lists_all_files_extracts_confirmed_zip_and_persists_cache(self) -> None:
        root = Path(self.temp_directory.name)
        log_directory = root / "logs"
        log_directory.mkdir()
        (log_directory / "current.log").write_text("INFO current\n", encoding="utf-8")
        (log_directory / "notes.txt").write_text("notes\n", encoding="utf-8")
        (log_directory / "broken.zip").write_text("not a zip\n", encoding="utf-8")
        with ZipFile(log_directory / "archive.zip", "w") as archive:
            archive.writestr("archived.log", "ERROR archived\n")

        environment = EnvironmentConfig(
            provider="local",
            sources={"appserver": SourceConfig(path=log_directory, description="Appserver")},
        )
        cache = LogFileCache(root / "cache")
        service = LogService(
            environment,
            LocalFileProvider(environment.sources),
            environment_name="production",
            file_cache=cache,
        )

        discovered = service.list_files("appserver")

        self.assertEqual(
            [file.name for file in discovered.files],
            ["archive.zip", "broken.zip", "current.log", "notes.txt"],
        )
        archive_file = next(file for file in discovered.files if file.name == "archive.zip")
        self.assertEqual(archive_file.archive_status, "extractable")
        broken_archive = next(file for file in discovered.files if file.name == "broken.zip")
        self.assertEqual(broken_archive.archive_status, "unavailable")
        self.assertEqual(broken_archive.archive_error, "invalid_zip")
        self.assertFalse((log_directory / "archived.log").exists())
        self.assertTrue(discovered.to_dict()["requires_extraction_confirmation"])

        extracted = service.list_files("appserver", extract_archives=True)

        self.assertEqual(extracted.extracted_archives, ["archive.zip"])
        self.assertTrue((log_directory / "archived.log").is_file())
        self.assertEqual(
            next(file for file in extracted.files if file.name == "archive.zip").archive_status,
            "extracted",
        )
        self.assertIsNotNone(extracted.cache)
        self.assertEqual(extracted.cache.key, "production/appserver")

        restarted_service = LogService(
            environment,
            LocalFileProvider(environment.sources),
            environment_name="production",
            file_cache=LogFileCache(root / "cache"),
        )
        refreshed = restarted_service.list_files("appserver")

        self.assertEqual(
            next(file for file in refreshed.files if file.name == "archive.zip").archive_status,
            "extracted",
        )
        self.assertFalse(refreshed.to_dict()["requires_extraction_confirmation"])

    def test_rejects_zip_path_traversal_before_extracting(self) -> None:
        root = Path(self.temp_directory.name)
        log_directory = root / "logs"
        log_directory.mkdir()
        with ZipFile(log_directory / "unsafe.zip", "w") as archive:
            archive.writestr("../outside.log", "secret\n")
        environment = EnvironmentConfig(
            provider="local",
            sources={"appserver": SourceConfig(path=log_directory)},
        )
        service = LogService(environment, LocalFileProvider(environment.sources))

        discovered = service.list_files("appserver")

        unsafe_archive = next(file for file in discovered.files if file.name == "unsafe.zip")
        self.assertEqual(unsafe_archive.archive_status, "unavailable")
        self.assertEqual(unsafe_archive.archive_error, "unsafe_archive")
        service.list_files("appserver", extract_archives=True)
        self.assertFalse((root / "outside.log").exists())

    def test_searches_single_file_under_directory_source(self) -> None:
        log_directory = Path(self.temp_directory.name) / "logs"
        log_directory.mkdir()
        (log_directory / "insight-appserver.log").write_text(
            "2026-07-28T09:03:20+08:00 INFO ok\n",
            encoding="utf-8",
        )
        (log_directory / "insight-appserver-error.log").write_text(
            "2026-07-28T09:03:21+08:00 ERROR NullPointerException\n",
            encoding="utf-8",
        )
        environment = EnvironmentConfig(
            provider="local",
            sources={"appserver": SourceConfig(path=log_directory, description="Appserver")},
        )
        service = LogService(environment, LocalFileProvider(environment.sources))

        matches, truncated = service.search(
            "appserver/insight-appserver-error.log",
            "NullPointerException",
        )

        self.assertFalse(truncated)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].source, "appserver/insight-appserver-error.log")
        self.assertEqual(matches[0].cursor, "appserver/insight-appserver-error.log:1")
        context = service.context(
            "appserver/insight-appserver-error.log",
            matches[0].cursor,
            before=0,
            after=0,
        )
        self.assertEqual(context[0].message, "2026-07-28T09:03:21+08:00 ERROR NullPointerException")

    def test_search_returns_cursor_and_redacts_secret(self) -> None:
        matches, truncated = self.service.search("orders", "timeout OR timed out")

        self.assertFalse(truncated)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].cursor, "orders:2")
        self.assertEqual(matches[0].level, "ERROR")
        self.assertTrue(matches[0].message.endswith("token=[REDACTED]"))

    def test_context_marks_matching_line(self) -> None:
        lines = self.service.context("orders", "orders:2", before=1, after=1)

        self.assertEqual(len(lines), 3)
        self.assertEqual([line.is_match for line in lines], [False, True, False])

    def test_rejects_cursor_from_another_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.service.context("orders", "payments:2")


if __name__ == "__main__":
    unittest.main()
