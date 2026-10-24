import subprocess
import sys
import time

import pytest

from arga_enfusion_mcp.process import bounded_run


def run(
    code: str,
    *,
    timeout: float = 10,
    max_output_bytes: int = 1000,
    max_stderr_bytes: int | None = None,
) -> subprocess.CompletedProcess[bytes]:
    kwargs: dict[str, int] = {}
    if max_stderr_bytes is not None:
        kwargs["max_stderr_bytes"] = max_stderr_bytes
    return bounded_run(
        [sys.executable, "-c", code],
        timeout=timeout,
        max_output_bytes=max_output_bytes,
        **kwargs,
    )


def test_returns_stdout_and_zero_returncode() -> None:
    completed = run("import sys; sys.stdout.buffer.write(b'hello')")

    assert completed.returncode == 0
    assert completed.stdout == b"hello"


def test_output_within_cap_is_returned_whole() -> None:
    completed = run("import sys; sys.stdout.buffer.write(b'x' * 1000)", max_output_bytes=1000)

    assert completed.stdout == b"x" * 1000


def test_nonzero_exit_returns_returncode_and_stderr() -> None:
    completed = run("import sys; sys.stderr.buffer.write(b'boom'); sys.exit(3)")

    assert completed.returncode == 3
    assert completed.stderr == b"boom"


def test_stdout_cap_stops_child_and_returns_one_extra_byte() -> None:
    started = time.monotonic()

    completed = run("import sys; sys.stdout.buffer.write(b'x' * 5_000_000)", max_output_bytes=1000)

    assert completed.stdout == b"x" * 1001
    assert completed.returncode == 0
    assert time.monotonic() - started < 5


def test_stderr_is_drained_and_only_its_head_is_kept() -> None:
    completed = run(
        "import sys; sys.stderr.buffer.write(b'e' * 1_000_000); sys.exit(1)",
        max_stderr_bytes=100,
    )

    assert completed.returncode == 1
    assert completed.stderr == b"e" * 100


def test_timeout_kills_child_and_raises() -> None:
    started = time.monotonic()

    with pytest.raises(subprocess.TimeoutExpired):
        run("import time; time.sleep(30)", timeout=0.5)

    assert time.monotonic() - started < 10


def test_missing_executable_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        bounded_run(["arga-enfusion-missing-executable"], timeout=5, max_output_bytes=1000)
