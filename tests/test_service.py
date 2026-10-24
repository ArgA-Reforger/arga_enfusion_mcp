import os
import struct
import subprocess
from pathlib import Path

import pytest

from arga_enfusion_mcp.cli import EnfusionCli
from arga_enfusion_mcp.config import ConfigError, Settings
from arga_enfusion_mcp.rdb import ResourceDatabase
from arga_enfusion_mcp.service import PakService
from arga_enfusion_mcp.sources import SourceError

TNT_PATH = "Particles/Logistics/Explosion/TNT/Explosion_TNT_Small.ptc"
TNT_GUID = "8B9323E3EEFBFE99"
TNT_GUID_LE = bytes.fromhex("99fefbeee323938b")


class FakeRunner:
    def __init__(self, stdout: bytes = b"") -> None:
        self.calls: list[list[str]] = []
        self._stdout = stdout

    def __call__(self, argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, self._stdout, b"")


def _record(path: str, guid_le: bytes) -> bytes:
    encoded = path.encode("ascii")
    return (
        struct.pack("<I", len(encoded))
        + encoded
        + b"\x00\x06\x00\x00\x00\x00\x00"
        + guid_le
        + b"\x07\x88\xf0iW\x02\x00\x00"
    )


@pytest.fixture
def dirs(tmp_path: Path) -> dict[str, Path]:
    data = tmp_path / "addons" / "data"
    data.mkdir(parents=True)
    (data / "data007.pak").write_bytes(b"")
    (data / "resourceDatabase.rdb").write_bytes(_record(TNT_PATH, TNT_GUID_LE))
    mods = tmp_path / "mods"
    mods.mkdir()
    return {"data": data, "mods": mods, "extract": tmp_path / "extracted"}


def build(
    dirs: dict[str, Path], runner: FakeRunner, *, extract: bool = True, max_bytes: int = 40_000
) -> PakService:
    settings = Settings(
        cli_path=Path("enfusion.exe"),
        data_dir=dirs["data"],
        mods_dir=dirs["mods"],
        extract_dir=dirs["extract"] if extract else None,
    )
    cli = EnfusionCli(settings.cli_path, runner=runner, max_output_bytes=max_bytes)
    return PakService(settings, cli)


def test_glob_resolves_source_and_returns_text(dirs: dict[str, Path]) -> None:
    runner = FakeRunner(b"/scripts/A.c\n")

    text = build(dirs, runner).glob("**/*.c", "data007")

    assert text == "/scripts/A.c\n"
    assert runner.calls[0][-1] == str(dirs["data"] / "data007.pak")


def test_empty_result_names_the_searched_source(dirs: dict[str, Path]) -> None:
    text = build(dirs, FakeRunner(b"")).glob("**/*.zzz", "data007")

    assert "No results" in text
    assert "data007" in text


def test_truncated_result_gets_a_note(dirs: dict[str, Path]) -> None:
    text = build(dirs, FakeRunner(b"x" * 100), max_bytes=10).cat("/a.c", "data007")

    assert text.startswith("x" * 10)
    assert "truncated" in text


def test_unknown_source_is_a_source_error(dirs: dict[str, Path]) -> None:
    with pytest.raises(SourceError):
        build(dirs, FakeRunner()).glob("*", "nope")


def test_extract_goes_under_extract_dir(dirs: dict[str, Path]) -> None:
    runner = FakeRunner(b"done\n")

    text = build(dirs, runner).extract("scripts/**", "data007")

    target = dirs["extract"] / "data007"
    assert target.is_dir()
    assert str(target) in runner.calls[0]
    assert str(target) in text


def test_extract_requires_extract_dir(dirs: dict[str, Path]) -> None:
    with pytest.raises(ConfigError, match="REFORGER_EXTRACT_DIR"):
        build(dirs, FakeRunner(), extract=False).extract("scripts/**", "data007")


def test_guid_of_returns_resource_name(dirs: dict[str, Path]) -> None:
    text = build(dirs, FakeRunner()).guid_of("/" + TNT_PATH)

    assert text == "{" + TNT_GUID + "}" + TNT_PATH


def test_guid_of_unknown_path_says_so(dirs: dict[str, Path]) -> None:
    assert "No GUID" in build(dirs, FakeRunner()).guid_of("Nope/x.et")


def test_path_of_returns_path(dirs: dict[str, Path]) -> None:
    assert build(dirs, FakeRunner()).path_of("{" + TNT_GUID + "}") == TNT_PATH


def test_path_of_unknown_guid_says_so(dirs: dict[str, Path]) -> None:
    assert "No path" in build(dirs, FakeRunner()).path_of("0000000000000000")


def test_rdb_is_loaded_once(dirs: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[Path] = []
    original = ResourceDatabase.from_file.__func__  # type: ignore[attr-defined]

    def counting(cls: type[ResourceDatabase], path: Path) -> ResourceDatabase:
        loads.append(path)
        return original(cls, path)

    monkeypatch.setattr(ResourceDatabase, "from_file", classmethod(counting))
    service = build(dirs, FakeRunner())

    service.guid_of(TNT_PATH)
    service.guid_of(TNT_PATH)

    assert len(loads) == 1


def test_rdb_is_reloaded_when_file_changes(dirs: dict[str, Path]) -> None:
    service = build(dirs, FakeRunner())
    assert TNT_GUID in service.guid_of(TNT_PATH)

    rdb = dirs["data"] / "resourceDatabase.rdb"
    rdb.write_bytes(_record("Other/New.et", TNT_GUID_LE))
    stat = rdb.stat()
    os.utime(rdb, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    assert "No GUID" in service.guid_of(TNT_PATH)
    assert service.path_of(TNT_GUID) == "Other/New.et"


def test_list_sources_shows_paks_and_mods(dirs: dict[str, Path]) -> None:
    (dirs["mods"] / "MyMod_1").mkdir()
    (dirs["mods"] / "MyMod_1" / "data.pak").write_bytes(b"")

    text = build(dirs, FakeRunner()).list_sources()

    assert "data007" in text
    assert "MyMod_1" in text
