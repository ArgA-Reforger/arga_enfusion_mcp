from pathlib import Path

import pytest

from arga_enfusion_mcp.sources import SourceError, SourceResolver


@pytest.fixture
def layout(tmp_path: Path) -> tuple[Path, Path]:
    data = tmp_path / "addons" / "data"
    data.mkdir(parents=True)
    (data / "data007.pak").write_bytes(b"")
    (data / "data.pak").write_bytes(b"")
    (data / "resourceDatabase.rdb").write_bytes(b"")
    core = tmp_path / "addons" / "core"
    core.mkdir()
    (core / "resourceDatabase.rdb").write_bytes(b"")
    mods = tmp_path / "mods"
    (mods / "MyMod_ABC123").mkdir(parents=True)
    (mods / "MyMod_ABC123" / "data.pak").write_bytes(b"")
    (mods / "MyMod_ABC123" / "resourceDatabase.rdb").write_bytes(b"")
    return data, mods


@pytest.fixture
def resolver(layout: tuple[Path, Path]) -> SourceResolver:
    return SourceResolver(*layout)


def test_resolves_data_pak_by_stem(resolver: SourceResolver, layout: tuple[Path, Path]) -> None:
    assert resolver.archives("data007") == [layout[0] / "data007.pak"]


def test_resolves_data_pak_with_extension(
    resolver: SourceResolver, layout: tuple[Path, Path]
) -> None:
    assert resolver.archives("data007.pak") == [layout[0] / "data007.pak"]


def test_resolves_mod_folder(resolver: SourceResolver, layout: tuple[Path, Path]) -> None:
    assert resolver.archives("MyMod_ABC123") == [layout[1] / "MyMod_ABC123" / "data.pak"]


def test_resolves_whole_data_dir(resolver: SourceResolver, layout: tuple[Path, Path]) -> None:
    assert resolver.archives("@data") == [layout[0]]


def test_resolves_whole_mods_dir(resolver: SourceResolver, layout: tuple[Path, Path]) -> None:
    assert resolver.archives("@mods") == [layout[1]]


@pytest.mark.parametrize(
    "name",
    ["..", "../data007", "a/b", "a\b", "C:\Windows", "/etc/passwd", "", "x..y", "bad name"],
)
def test_rejects_unsafe_names(resolver: SourceResolver, name: str) -> None:
    with pytest.raises(SourceError):
        resolver.archives(name)


def test_unknown_source_error_lists_available(resolver: SourceResolver) -> None:
    with pytest.raises(SourceError, match="data007"):
        resolver.archives("nope")


def test_unconfigured_dirs_raise_clear_error() -> None:
    with pytest.raises(SourceError, match="REFORGER_DATA_DIR"):
        SourceResolver(None, None).archives("data007")
    with pytest.raises(SourceError, match="REFORGER_MODS_DIR"):
        SourceResolver(None, None).archives("@mods")


def test_available_lists_paks_and_mods(resolver: SourceResolver) -> None:
    available = resolver.available()

    assert available["data"] == ["data", "data007"]
    assert available["mods"] == ["MyMod_ABC123"]


def test_rdb_path_for_data_core_and_mod(
    resolver: SourceResolver, layout: tuple[Path, Path]
) -> None:
    data, mods = layout

    assert resolver.rdb_path("data") == data / "resourceDatabase.rdb"
    assert resolver.rdb_path("core") == data.parent / "core" / "resourceDatabase.rdb"
    assert resolver.rdb_path("MyMod_ABC123") == mods / "MyMod_ABC123" / "resourceDatabase.rdb"


def test_rdb_path_rejects_unsafe_and_missing(resolver: SourceResolver) -> None:
    with pytest.raises(SourceError):
        resolver.rdb_path("../x")
    with pytest.raises(SourceError, match="not found"):
        resolver.rdb_path("Ghost")
