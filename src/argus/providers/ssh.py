from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass

from argus.config import SourceConfig, SshConnectionConfig
from argus.models import LogFile
from argus.providers.base import LogReadError, is_safe_file_name, resolve_log_source

_REMOTE_SCRIPT = """\
set -eu
path={path}
max_bytes={max_file_bytes}
allow_directory={allow_directory}

fail() {{
  echo "$1" >&2
  exit 1
}}

emit_file() {{
  file="$1"
  if [ ! -f "$file" ]; then
    fail "Configured log source is unavailable"
  fi
  size=$(wc -c < "$file" | tr -d ' ')
  if [ "$size" -gt "$max_bytes" ]; then
    fail "Configured log source exceeds the read limit"
  fi
  cat -- "$file"
}}

if [ -f "$path" ]; then
  emit_file "$path"
elif [ "$allow_directory" = "1" ] && [ -d "$path" ]; then
  total=0
  found=0
  find "$path" -maxdepth 1 -type f -name '*.log' -print | sort | while IFS= read -r file; do
    found=1
    size=$(wc -c < "$file" | tr -d ' ')
    total=$((total + size))
    if [ "$total" -gt "$max_bytes" ]; then
      fail "Configured log source exceeds the read limit"
    fi
    cat -- "$file"
  done
else
  fail "Configured log source is unavailable"
fi
"""

_REMOTE_LIST_FILES_SCRIPT = """\
set -eu
path={path}
max_extract_bytes={max_extract_bytes}

fail() {{
  echo "$1" >&2
  exit 1
}}

emit_file() {{
  file="$1"
  if [ ! -f "$file" ]; then
    fail "Configured log source is unavailable"
  fi
  size=$(wc -c < "$file" | tr -d ' ')
  modified=$(stat -c %Y "$file")
  basename=$(basename -- "$file")
  kind=other
  archive_status=not_archive
  archive_error=
  case "$basename" in
    *.log|*.LOG) kind=log ;;
    *.zip|*.ZIP)
      kind=zip
      if ! command -v unzip >/dev/null 2>&1; then
        archive_status=unavailable
        archive_error=missing_unzip
      elif ! unzip -tqq "$file" >/dev/null 2>&1; then
        archive_status=unavailable
        archive_error=invalid_zip
      elif ! zip_entries_are_safe "$file"; then
        archive_status=unavailable
        archive_error=unsafe_archive
      else
        uncompressed=$(unzip -l "$file" | awk 'END {{ print $1 }}')
        case "$uncompressed" in
          ''|*[!0-9]*)
            archive_status=unavailable
            archive_error=invalid_zip
            ;;
          *)
            if [ "$uncompressed" -gt "$max_extract_bytes" ]; then
              archive_status=unavailable
              archive_error=archive_too_large
            else
              archive_status=extractable
            fi
            ;;
        esac
      fi
      ;;
  esac
  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \
    "$basename" "$size" "$modified" "$kind" "$archive_status" "$archive_error"
}}

zip_entries_are_safe() {{
  unzip -Z1 "$1" | awk '
    /^\\// || /^\\.\\.$/ || /^\\.\\.\\// || /\\/\\.\\.\\// || /\\/\\.\\.$/ {{ unsafe = 1 }}
    END {{ exit unsafe }}
  ' || return 1
  unzip -Z -l "$1" | awk 'substr($1, 1, 1) == "l" {{ unsafe = 1 }} END {{ exit unsafe }}'
}}

if [ -f "$path" ]; then
  emit_file "$path"
elif [ -d "$path" ]; then
  find "$path" -maxdepth 1 -type f -print | sort | while IFS= read -r file; do
    emit_file "$file"
  done
else
  fail "Configured log source is unavailable"
fi
"""

_REMOTE_EXTRACT_ARCHIVES_SCRIPT = """\
set -eu
path={path}
max_extract_bytes={max_extract_bytes}
set -- {archive_names}

fail() {{
  echo "$1" >&2
  exit 1
}}

zip_entries_are_safe() {{
  unzip -Z1 "$1" | awk '
    /^\\// || /^\\.\\.$/ || /^\\.\\.\\// || /\\/\\.\\.\\// || /\\/\\.\\.$/ {{ unsafe = 1 }}
    END {{ exit unsafe }}
  ' || return 1
  unzip -Z -l "$1" | awk 'substr($1, 1, 1) == "l" {{ unsafe = 1 }} END {{ exit unsafe }}'
}}

if [ -d "$path" ]; then
  directory="$path"
elif [ -f "$path" ]; then
  directory=$(dirname -- "$path")
else
  fail "Configured log source is unavailable"
fi

command -v unzip >/dev/null 2>&1 || fail "The remote host does not provide unzip"

for archive_name do
  archive="$directory/$archive_name"
  [ -f "$archive" ] || fail "ZIP archive is unavailable: $archive_name"
  unzip -tqq "$archive" >/dev/null 2>&1 || fail "ZIP archive is invalid: $archive_name"
  zip_entries_are_safe "$archive" || fail "ZIP archive is unsafe: $archive_name"
  uncompressed=$(unzip -l "$archive" | awk 'END {{ print $1 }}')
  case "$uncompressed" in
    ''|*[!0-9]*) fail "Unable to determine ZIP extraction size: $archive_name" ;;
  esac
  [ "$uncompressed" -le "$max_extract_bytes" ] \
    || fail "ZIP archive exceeds the extraction limit: $archive_name"
done

for archive_name do
  archive="$directory/$archive_name"
  unzip -oq "$archive" -d "$directory"
  printf '%s\\n' "$archive_name"
done
"""


@dataclass(frozen=True, slots=True)
class _SshResult:
    stdout: str
    stderr: str
    returncode: int


class SshLogProvider:
    """Read allow-listed log sources over OpenSSH."""

    def __init__(
        self,
        ssh_alias: str,
        sources: dict[str, SourceConfig],
        *,
        ssh_config: SshConnectionConfig | None = None,
        max_file_bytes: int = 10_000_000,
        max_extract_bytes: int = 100_000_000,
        timeout_seconds: int = 15,
    ) -> None:
        self._ssh_alias = ssh_alias
        self._ssh_config = ssh_config
        self._sources = sources
        self._max_file_bytes = max_file_bytes
        self._max_extract_bytes = max_extract_bytes
        self._timeout_seconds = ssh_config.connect_timeout if ssh_config else timeout_seconds

    def read_lines(self, source_id: str) -> list[str]:
        source = resolve_log_source(self._sources, source_id)

        script = _REMOTE_SCRIPT.format(
            path=shlex.quote(str(source.path)),
            max_file_bytes=self._max_file_bytes,
            allow_directory="0" if source.is_virtual_file else "1",
        )
        completed = self._run_ssh_script(source_id, script, action="reading")
        return completed.stdout.splitlines()

    def list_files(self, source_id: str) -> list[LogFile]:
        source = resolve_log_source(self._sources, source_id)

        script = _REMOTE_LIST_FILES_SCRIPT.format(
            path=shlex.quote(str(source.path)),
            max_extract_bytes=self._max_extract_bytes,
        )
        completed = self._run_ssh_script(source_id, script, action="listing")
        files: list[LogFile] = []
        for line in completed.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) != 6:
                raise LogReadError(f"Unable to parse SSH log file listing for '{source_id}'")
            name, size, modified, kind, archive_status, archive_error = fields
            if not name or not size.isdigit() or not modified.isdigit():
                raise LogReadError(f"Unable to parse SSH log file listing for '{source_id}'")
            files.append(
                LogFile(
                    name=name,
                    size_bytes=int(size),
                    modified_at_ns=int(modified) * 1_000_000_000,
                    kind=kind,
                    archive_status=archive_status,
                    archive_error=archive_error or None,
                )
            )
        return files

    def extract_archives(self, source_id: str, archive_names: list[str]) -> list[str]:
        if not archive_names:
            return []
        for archive_name in archive_names:
            if not is_safe_file_name(archive_name) or not archive_name.lower().endswith(".zip"):
                raise LogReadError(f"Unsafe ZIP archive name: {archive_name}")

        source = resolve_log_source(self._sources, source_id)
        script = _REMOTE_EXTRACT_ARCHIVES_SCRIPT.format(
            path=shlex.quote(str(source.path)),
            max_extract_bytes=self._max_extract_bytes,
            archive_names=" ".join(shlex.quote(name) for name in archive_names),
        )
        completed = self._run_ssh_script(source_id, script, action="extracting")
        extracted = completed.stdout.splitlines()
        if extracted != archive_names:
            raise LogReadError(f"Unable to verify extracted ZIP archives for '{source_id}'")
        return extracted

    def _run_ssh_script(
        self,
        source_id: str,
        script: str,
        *,
        action: str,
    ) -> _SshResult | subprocess.CompletedProcess[str]:
        if self._ssh_config is not None:
            completed = self._run_paramiko_script(script)
        else:
            completed = self._run_openssh_script(script)

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown SSH error"
            raise LogReadError(
                f"Unable to {action.removesuffix('ing')} SSH log source "
                f"'{source_id}': {_friendly_ssh_error(detail)}"
            )

        return completed

    def _run_openssh_script(self, script: str) -> subprocess.CompletedProcess[str]:
        command = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={self._timeout_seconds}",
            self._ssh_alias,
            "sh",
            "-s",
        ]
        try:
            completed = subprocess.run(
                command,
                input=script,
                text=True,
                capture_output=True,
                timeout=self._timeout_seconds + 5,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LogReadError("Timed out running SSH log command") from exc

        return completed

    def _run_paramiko_script(self, script: str) -> _SshResult:
        try:
            import paramiko
        except ImportError as exc:
            raise LogReadError(
                "Password SSH authentication requires the 'paramiko' dependency."
            ) from exc

        if self._ssh_config is None:
            raise LogReadError("SSH connection config is missing")

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if self._ssh_config.known_hosts is not None:
            client.load_host_keys(str(self._ssh_config.known_hosts))
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

        try:
            client.connect(
                hostname=self._ssh_config.host,
                port=self._ssh_config.port,
                username=self._ssh_config.username,
                password=self._ssh_config.password,
                timeout=self._timeout_seconds,
                auth_timeout=self._timeout_seconds,
                banner_timeout=self._timeout_seconds,
                look_for_keys=False,
                allow_agent=False,
            )
            stdin, stdout, stderr = client.exec_command("sh -s", timeout=self._timeout_seconds)
            stdin.write(script)
            stdin.channel.shutdown_write()
            stdout_text = stdout.read().decode("utf-8", errors="replace")
            stderr_text = stderr.read().decode("utf-8", errors="replace")
            return _SshResult(
                stdout=stdout_text,
                stderr=stderr_text,
                returncode=stdout.channel.recv_exit_status(),
            )
        except TimeoutError as exc:
            raise LogReadError("Timed out running SSH log command") from exc
        except paramiko.AuthenticationException as exc:
            raise LogReadError(
                "SSH authentication failed. Check ssh.username and ssh.password."
            ) from exc
        except paramiko.SSHException as exc:
            raise LogReadError(f"SSH connection failed: {exc}") from exc
        except OSError as exc:
            raise LogReadError(f"SSH connection failed: {exc}") from exc
        finally:
            client.close()


def _friendly_ssh_error(detail: str) -> str:
    if "Permission denied" in detail and (
        "publickey" in detail or "password" in detail or "keyboard-interactive" in detail
    ):
        return (
            "SSH authentication failed. Configure ssh_alias to use a non-interactive "
            "account/key, or configure ssh.host, ssh.username, and ssh.password."
        )
    return detail
