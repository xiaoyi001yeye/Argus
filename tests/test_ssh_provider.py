import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from argus.config import SourceConfig, SshConnectionConfig
from argus.providers.base import LogReadError
from argus.providers.ssh import SshLogProvider


class SshLogProviderTest(unittest.TestCase):
    def test_reads_lines_with_non_interactive_ssh(self) -> None:
        provider = SshLogProvider(
            "insight-appserver",
            {"appserver": SourceConfig(path=Path("/var/log/app/app.log"))},
        )
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="2026-07-29 INFO ok\n2026-07-29 ERROR failed\n",
            stderr="",
        )

        with patch("argus.providers.ssh.subprocess.run", return_value=completed) as run:
            lines = provider.read_lines("appserver")

        self.assertEqual(lines, ["2026-07-29 INFO ok", "2026-07-29 ERROR failed"])
        command = run.call_args.args[0]
        self.assertEqual(command[:5], ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15"])
        self.assertEqual(command[-3:], ["insight-appserver", "sh", "-s"])
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertIn("path=/var/log/app/app.log", run.call_args.kwargs["input"])

    def test_directory_sources_read_current_log_files(self) -> None:
        provider = SshLogProvider(
            "insight-appserver",
            {"appserver": SourceConfig(path=Path("/var/log/app"))},
        )
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        with patch("argus.providers.ssh.subprocess.run", return_value=completed) as run:
            provider.read_lines("appserver")

        script = run.call_args.kwargs["input"]
        self.assertIn("allow_directory=1", script)
        self.assertIn('elif [ "$allow_directory" = "1" ] && [ -d "$path" ]; then', script)
        self.assertIn("find \"$path\" -maxdepth 1 -type f -name '*.log' -print", script)

    def test_reads_single_file_under_directory_source(self) -> None:
        provider = SshLogProvider(
            "insight-appserver",
            {"appserver": SourceConfig(path=Path("/var/log/app"))},
        )
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="2026-07-29 ERROR failed\n",
            stderr="",
        )

        with patch("argus.providers.ssh.subprocess.run", return_value=completed) as run:
            lines = provider.read_lines("appserver/insight-appserver-error.log")

        self.assertEqual(lines, ["2026-07-29 ERROR failed"])
        script = run.call_args.kwargs["input"]
        self.assertIn("path=/var/log/app/insight-appserver-error.log", script)
        self.assertIn("allow_directory=0", script)

    def test_rejects_directory_source_path_traversal_without_ssh(self) -> None:
        provider = SshLogProvider(
            "insight-appserver",
            {"appserver": SourceConfig(path=Path("/var/log/app"))},
        )

        with (
            patch("argus.providers.ssh.subprocess.run") as run,
            self.assertRaisesRegex(LogReadError, "Unknown log source"),
        ):
            provider.read_lines("appserver/../secret.log")

        run.assert_not_called()

    def test_lists_log_files_without_reading_contents(self) -> None:
        provider = SshLogProvider(
            "insight-appserver",
            {"appserver": SourceConfig(path=Path("/var/log/app"))},
        )
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "app.log\t123\t1722326400\tlog\tnot_archive\t\n"
                "archive.zip\t456\t1722326500\tzip\textractable\t\n"
                "notes.txt\t10\t1722326600\tother\tnot_archive\t\n"
            ),
            stderr="",
        )

        with patch("argus.providers.ssh.subprocess.run", return_value=completed) as run:
            files = provider.list_files("appserver")

        self.assertEqual([file.name for file in files], ["app.log", "archive.zip", "notes.txt"])
        self.assertEqual([file.size_bytes for file in files], [123, 456, 10])
        self.assertEqual(files[1].archive_status, "extractable")
        script = run.call_args.kwargs["input"]
        self.assertIn("basename -- \"$file\"", script)
        self.assertNotIn("cat -- \"$file\"", script)
        self.assertIn('-type f -print', script)
        self.assertNotIn("-name '*.log'", script)
        self.assertIn("command -v unzip", script)

    def test_extracts_explicit_zip_archives_in_place(self) -> None:
        provider = SshLogProvider(
            "insight-appserver",
            {"appserver": SourceConfig(path=Path("/var/log/app"))},
        )
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="archive.zip\n",
            stderr="",
        )

        with patch("argus.providers.ssh.subprocess.run", return_value=completed) as run:
            extracted = provider.extract_archives("appserver", ["archive.zip"])

        self.assertEqual(extracted, ["archive.zip"])
        script = run.call_args.kwargs["input"]
        self.assertIn("set -- archive.zip", script)
        self.assertIn('unzip -tqq "$archive"', script)
        self.assertIn('zip_entries_are_safe "$archive"', script)
        self.assertIn('unzip -oq "$archive" -d "$directory"', script)

    def test_rejects_unsafe_zip_name_without_ssh(self) -> None:
        provider = SshLogProvider(
            "insight-appserver",
            {"appserver": SourceConfig(path=Path("/var/log/app"))},
        )

        with (
            patch("argus.providers.ssh.subprocess.run") as run,
            self.assertRaisesRegex(LogReadError, "Unsafe ZIP archive name"),
        ):
            provider.extract_archives("appserver", ["../archive.zip"])

        run.assert_not_called()

    def test_reads_lines_with_password_ssh_config(self) -> None:
        ssh_config = SshConnectionConfig(
            host="172.17.162.104",
            username="root",
            password="secret",
            connect_timeout=7,
        )
        provider = SshLogProvider(
            "172.17.162.104",
            {"appserver": SourceConfig(path=Path("/var/log/app/app.log"))},
            ssh_config=ssh_config,
        )
        fake_paramiko, fake_client = _fake_paramiko(stdout="INFO ok\n")

        with (
            patch.dict(sys.modules, {"paramiko": fake_paramiko}),
            patch("argus.providers.ssh.subprocess.run") as run,
        ):
            lines = provider.read_lines("appserver")

        self.assertEqual(lines, ["INFO ok"])
        run.assert_not_called()
        self.assertEqual(fake_client.connect_kwargs["hostname"], "172.17.162.104")
        self.assertEqual(fake_client.connect_kwargs["username"], "root")
        self.assertEqual(fake_client.connect_kwargs["password"], "secret")
        self.assertFalse(fake_client.connect_kwargs["look_for_keys"])
        self.assertFalse(fake_client.connect_kwargs["allow_agent"])
        self.assertEqual(fake_client.exec_command_args, ("sh -s",))
        self.assertIn("path=/var/log/app/app.log", fake_client.stdin.written)

    def test_rejects_unknown_source_without_ssh(self) -> None:
        provider = SshLogProvider("insight-appserver", {})

        with (
            patch("argus.providers.ssh.subprocess.run") as run,
            self.assertRaisesRegex(LogReadError, "Unknown log source"),
        ):
            provider.read_lines("missing")

        run.assert_not_called()

    def test_raises_read_error_for_remote_failure(self) -> None:
        provider = SshLogProvider(
            "insight-appserver",
            {"appserver": SourceConfig(path=Path("/var/log/app/app.log"))},
        )
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="Configured log source is unavailable\n",
        )

        with (
            patch("argus.providers.ssh.subprocess.run", return_value=completed),
            self.assertRaisesRegex(LogReadError, "unavailable"),
        ):
            provider.read_lines("appserver")

    def test_raises_friendly_error_for_ssh_authentication_failure(self) -> None:
        provider = SshLogProvider(
            "root@172.17.162.104",
            {"appserver": SourceConfig(path=Path("/var/log/app/app.log"))},
        )
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=255,
            stdout="",
            stderr=(
                "root@172.17.162.104: Permission denied "
                "(publickey,password,keyboard-interactive).\n"
            ),
        )

        with (
            patch("argus.providers.ssh.subprocess.run", return_value=completed),
            self.assertRaisesRegex(LogReadError, "SSH authentication failed"),
        ):
            provider.read_lines("appserver")

def _fake_paramiko(*, stdout: str = "", stderr: str = "", returncode: int = 0):
    fake_client = _FakeSshClient(stdout=stdout, stderr=stderr, returncode=returncode)

    class FakeSshException(Exception):
        pass

    fake_paramiko = types.SimpleNamespace(
        AuthenticationException=FakeSshException,
        RejectPolicy=lambda: object(),
        SSHClient=lambda: fake_client,
        SSHException=FakeSshException,
    )
    return fake_paramiko, fake_client


class _FakeSshClient:
    def __init__(self, *, stdout: str, stderr: str, returncode: int) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStream(stdout, returncode)
        self.stderr = _FakeStream(stderr, returncode)
        self.connect_kwargs = {}
        self.exec_command_args = ()

    def load_system_host_keys(self) -> None:
        pass

    def load_host_keys(self, filename: str) -> None:
        self.host_keys_filename = filename

    def set_missing_host_key_policy(self, policy: object) -> None:
        self.missing_host_key_policy = policy

    def connect(self, **kwargs: object) -> None:
        self.connect_kwargs = kwargs

    def exec_command(self, *args: object, **kwargs: object):
        self.exec_command_args = args
        self.exec_command_kwargs = kwargs
        return self.stdin, self.stdout, self.stderr

    def close(self) -> None:
        self.closed = True


class _FakeStdin:
    def __init__(self) -> None:
        self.written = ""
        self.channel = types.SimpleNamespace(shutdown_write=lambda: None)

    def write(self, value: str) -> None:
        self.written += value


class _FakeStream:
    def __init__(self, value: str, returncode: int) -> None:
        self._value = value
        self.channel = types.SimpleNamespace(recv_exit_status=lambda: returncode)

    def read(self) -> bytes:
        return self._value.encode()


if __name__ == "__main__":
    unittest.main()
