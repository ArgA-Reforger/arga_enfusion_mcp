"""Thin wrapper around the ``enfusion`` CLI (https://github.com/landaire/enfusion_tools).

The CLI is always run without a shell, with a timeout, and its output is bounded.
Positional arguments go after ``--`` so a pattern such as ``-rf`` is never parsed
as an option.
"""

import codecs
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from arga_enfusion_mcp.process import bounded_run

DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_OUTPUT_BYTES = 40_000
MAX_ERROR_CHARS = 2000

Runner = Callable[..., subprocess.CompletedProcess[bytes]]


class CliError(RuntimeError):
    """Raised when the enfusion CLI fails, times out or cannot be started."""


@dataclass(frozen=True)
class CliResult:
    text: str
    truncated: bool


class EnfusionCli:
    def __init__(
        self,
        exe: Path,
        *,
        runner: Runner = bounded_run,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        self._exe = exe
        self._runner = runner
        self._timeout = timeout
        self._max_output_bytes = max_output_bytes

    def glob(self, pattern: str, archives: Sequence[Path], *, long: bool = False) -> CliResult:
        options = ["--long"] if long else []
        return self._run("glob", options, [pattern], archives)

    def cat(self, path: str, archives: Sequence[Path]) -> CliResult:
        return self._run("cat", ["--path", path], [], archives)

    def grep(
        self,
        pattern: str,
        archives: Sequence[Path],
        *,
        ignore_case: bool = False,
        glob: str | None = None,
        extensions: Sequence[str] | None = None,
        files_only: bool = False,
        context: int = 0,
    ) -> CliResult:
        options: list[str] = []
        if ignore_case:
            options.append("--ignore-case")
        if glob:
            options += ["--glob", glob]
        if extensions:
            options += ["--extensions", ",".join(extensions)]
        if files_only:
            options.append("--files-only")
        if context:
            options += ["--context", str(context)]
        return self._run("grep", options, [pattern], archives)

    def list(
        self,
        archives: Sequence[Path],
        *,
        glob: str | None = None,
        long: bool = False,
    ) -> CliResult:
        options = ["--flat"]
        if glob:
            options += ["--glob", glob]
        if long:
            options.append("--long")
        return self._run("list", options, [], archives)

    def info(self, archives: Sequence[Path]) -> CliResult:
        return self._run("info", [], [], archives)

    def extract(
        self,
        pattern: str,
        archives: Sequence[Path],
        output_dir: Path,
        *,
        flat: bool = False,
    ) -> CliResult:
        options = ["--output", str(output_dir)]
        if flat:
            options.append("--flat")
        return self._run("extract", options, [pattern], archives)

    def _run(
        self,
        command: str,
        options: Sequence[str],
        positionals: Sequence[str],
        archives: Sequence[Path],
    ) -> CliResult:
        if not archives:
            raise ValueError("at least one archive is required")

        argv = [str(self._exe), command, *options, "--", *positionals]
        argv += [str(archive) for archive in archives]

        try:
            completed = self._runner(
                argv,
                timeout=self._timeout,
                max_output_bytes=self._max_output_bytes,
            )
        except subprocess.TimeoutExpired as error:
            raise CliError(f"enfusion {command} timed out after {self._timeout:g}s") from error
        except OSError as error:
            raise CliError(f"cannot run enfusion CLI: {error}") from error

        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            if len(stderr) > MAX_ERROR_CHARS:
                stderr = stderr[: MAX_ERROR_CHARS - len("...")] + "..."
            raise CliError(f"enfusion {command} failed ({completed.returncode}): {stderr}")

        truncated = len(completed.stdout) > self._max_output_bytes
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        text = decoder.decode(completed.stdout[: self._max_output_bytes], final=not truncated)
        return CliResult(text, truncated=truncated)
