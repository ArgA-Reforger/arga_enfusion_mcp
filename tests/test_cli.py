import subprocess
from pathlib import Path

import pytest

from arga_enfusion_mcp.cli import CliError, EnfusionCli

EXE = Path("enfusion.exe")
PAK = Path("data007.pak")


class FakeRunner:
    def __init__(self, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0) -> None:
        self.calls: list[list[str]] = []
        self.kwargs: dict[str, object] = {}
        self._result = subprocess.CompletedProcess([], returncode, stdout, stderr)

    def __call__(self, argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(argv)
        self.kwargs = kwargs
        return self._result


def make(runner: FakeRunner, **kwargs: object) -> EnfusionCli:
    return EnfusionCli(EXE, runner=runner, **kwargs)  # type: ignore[arg-type]


def test_glob_builds_argv() -> None:
    runner = FakeRunner(b"/a.c\n")

    result = make(runner).glob("**/*.c", [PAK])

    assert runner.calls == [[str(EXE), "glob", "--", "**/*.c", str(PAK)]]
    assert result.text == "/a.c\n"
    assert result.truncated is False


def test_glob_long_flag() -> None:
    runner = FakeRunner()

    make(runner).glob("**/*.c", [PAK], long=True)

    assert runner.calls[0][:3] == [str(EXE), "glob", "--long"]


def test_cat_uses_path_option() -> None:
    runner = FakeRunner(b"class A {}")

    make(runner).cat("/scripts/Game/A.c", [PAK])

    assert runner.calls == [[str(EXE), "cat", "--path", "/scripts/Game/A.c", "--", str(PAK)]]


def test_grep_options() -> None:
    runner = FakeRunner()

    make(runner).grep(
        "class Foo",
        [PAK],
        ignore_case=True,
        glob="**/*.c",
        files_only=True,
        context=3,
    )

    assert runner.calls == [
        [
            str(EXE),
            "grep",
            "--ignore-case",
            "--glob",
            "**/*.c",
            "--files-only",
            "--context",
            "3",
            "--",
            "class Foo",
            str(PAK),
        ]
    ]


def test_grep_extensions() -> None:
    runner = FakeRunner()

    make(runner).grep("x", [PAK], extensions=["c", "et"])

    assert runner.calls[0][2:4] == ["--extensions", "c,et"]


def test_list_defaults_to_flat() -> None:
    runner = FakeRunner()

    make(runner).list([PAK], glob="Prefabs/**")

    assert runner.calls == [[str(EXE), "list", "--flat", "--glob", "Prefabs/**", "--", str(PAK)]]


def test_info() -> None:
    runner = FakeRunner()

    make(runner).info([PAK])

    assert runner.calls == [[str(EXE), "info", "--", str(PAK)]]


def test_extract_builds_argv(tmp_path: Path) -> None:
    runner = FakeRunner()

    make(runner).extract("scripts/**", [PAK], tmp_path, flat=True)

    assert runner.calls == [
        [str(EXE), "extract", "--output", str(tmp_path), "--flat", "--", "scripts/**", str(PAK)]
    ]


def test_pattern_starting_with_dash_is_a_positional() -> None:
    runner = FakeRunner()

    make(runner).glob("-rf", [PAK])

    argv = runner.calls[0]
    assert argv.index("--") < argv.index("-rf")


def test_runs_without_shell_and_with_timeout() -> None:
    runner = FakeRunner()

    make(runner, timeout=7).glob("*", [PAK])

    assert runner.kwargs["timeout"] == 7
    assert not runner.kwargs.get("shell")
    assert runner.kwargs["capture_output"] is True


def test_nonzero_exit_raises_with_stderr() -> None:
    runner = FakeRunner(stderr=b"boom", returncode=2)

    with pytest.raises(CliError, match="boom"):
        make(runner).glob("*", [PAK])


def test_timeout_raises_cli_error() -> None:
    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(argv, 1)

    with pytest.raises(CliError, match="timed out"):
        EnfusionCli(EXE, runner=runner).glob("*", [PAK])  # type: ignore[arg-type]


def test_output_is_truncated() -> None:
    runner = FakeRunner(b"x" * 100)

    result = make(runner, max_output_chars=10).glob("*", [PAK])

    assert result.truncated is True
    assert result.text.startswith("x" * 10)
    assert len(result.text) < 100


def test_invalid_utf8_is_replaced() -> None:
    runner = FakeRunner(b"ok \xff\xfe end")

    result = make(runner).cat("/a.bin", [PAK])

    assert "ok" in result.text and "end" in result.text


def test_requires_at_least_one_archive() -> None:
    with pytest.raises(ValueError, match="archive"):
        make(FakeRunner()).glob("*", [])
