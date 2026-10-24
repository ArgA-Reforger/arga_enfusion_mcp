"""Run a child process without a shell, with bounded output and a timeout."""

import os
import subprocess
import threading
from collections.abc import Sequence
from typing import IO

READ_CHUNK_BYTES = 64 * 1024


def bounded_run(
    argv: Sequence[str],
    *,
    timeout: float,
    max_output_bytes: int,
    max_stderr_bytes: int = 8192,
) -> subprocess.CompletedProcess[bytes]:
    """Run ``argv`` and collect its output within hard limits.

    Stdout is read until it exceeds ``max_output_bytes``. At that point the child is killed on
    purpose and stdout is cut to ``max_output_bytes + 1`` bytes, so the caller can detect the
    truncation. Because that stop was deliberate, the returned returncode is 0. Stderr is drained
    in a background thread so the child never blocks on a full pipe, and only its first
    ``max_stderr_bytes`` are kept.

    Raises ``subprocess.TimeoutExpired`` when the child is still running after ``timeout``
    seconds, after killing and reaping it. Raises ``OSError`` when the child cannot be started.
    """
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_pipe, stderr_pipe = process.stdout, process.stderr
    assert stdout_pipe is not None and stderr_pipe is not None

    expired = threading.Event()
    stderr_head = bytearray()
    stderr_reader = threading.Thread(
        target=_keep_head,
        args=(stderr_pipe, max_stderr_bytes, stderr_head),
        daemon=True,
    )
    timer = threading.Timer(timeout, _expire, args=(process, expired))

    stderr_reader.start()
    timer.start()
    try:
        stdout = _read_up_to(stdout_pipe, max_output_bytes)
        capped = len(stdout) > max_output_bytes
        if capped:
            process.kill()
        process.wait()
    finally:
        timer.cancel()
        timer.join()
        if process.poll() is None:
            process.kill()
            process.wait()
        stderr_reader.join()
        stdout_pipe.close()
        stderr_pipe.close()

    if expired.is_set():
        raise subprocess.TimeoutExpired(list(argv), timeout)
    returncode = 0 if capped else process.returncode
    return subprocess.CompletedProcess(list(argv), returncode, stdout, bytes(stderr_head))


def _expire(process: subprocess.Popen[bytes], expired: threading.Event) -> None:
    expired.set()
    process.kill()


def _read_up_to(pipe: IO[bytes], limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while total <= limit:
        chunk = os.read(pipe.fileno(), READ_CHUNK_BYTES)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)[: limit + 1]


def _keep_head(pipe: IO[bytes], limit: int, head: bytearray) -> None:
    while chunk := os.read(pipe.fileno(), READ_CHUNK_BYTES):
        if len(head) < limit:
            head.extend(chunk[: limit - len(head)])
