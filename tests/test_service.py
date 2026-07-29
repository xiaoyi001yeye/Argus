import tempfile
import unittest
from pathlib import Path

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
