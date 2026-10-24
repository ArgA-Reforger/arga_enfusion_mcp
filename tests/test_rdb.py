import os
import struct
from pathlib import Path

import pytest

from arga_enfusion_mcp.rdb import ResourceDatabase

FILE_SEP = b"\x00\x06\x00\x00\x00\x00\x00"
DIR_SEP = b"\x00\x05\x00\x00\x00\x00\x00"

TNT_PATH = "Particles/Logistics/Explosion/TNT/Explosion_TNT_Small.ptc"
TNT_GUID = "8B9323E3EEFBFE99"
TNT_GUID_LE = bytes.fromhex("99fefbeee323938b")

M112_PATH = "Particles/Weapon/Explosion_M112.ptc"
M112_GUID = "9D8D204CCCC44A38"
M112_GUID_LE = bytes.fromhex("384ac4cc4c208d9d")


def _record(path: str, guid_le: bytes, sep: bytes = FILE_SEP) -> bytes:
    encoded = path.encode("ascii")
    return struct.pack("<I", len(encoded)) + encoded + sep + guid_le + b"\x07\x88\xf0iW\x02\x00\x00"


@pytest.fixture
def rdb_bytes() -> bytes:
    return (
        b"FORM\x00\xaf\xa0\xa7RDBC\x07\x00\x00\x00"
        + _record("AIAgents", b"\x0b\x83x\xacf\x10&\xf4", DIR_SEP)
        + _record(TNT_PATH, TNT_GUID_LE)
        + _record(M112_PATH, M112_GUID_LE)
    )


@pytest.fixture
def db(rdb_bytes: bytes) -> ResourceDatabase:
    return ResourceDatabase(rdb_bytes)


def test_guid_of_known_path(db: ResourceDatabase) -> None:
    assert db.guid_of(TNT_PATH) == TNT_GUID


def test_guid_of_second_record(db: ResourceDatabase) -> None:
    assert db.guid_of(M112_PATH) == M112_GUID


def test_guid_of_tolerates_leading_slash(db: ResourceDatabase) -> None:
    assert db.guid_of("/" + TNT_PATH) == TNT_GUID


def test_guid_of_unknown_path_is_none(db: ResourceDatabase) -> None:
    assert db.guid_of("Does/Not/Exist.et") is None


def test_path_of_known_guid(db: ResourceDatabase) -> None:
    assert db.path_of(TNT_GUID) == TNT_PATH


@pytest.mark.parametrize("form", ["{8B9323E3EEFBFE99}", "8b9323e3eefbfe99", "{8b9323e3eefbfe99}"])
def test_path_of_accepts_braces_and_lowercase(db: ResourceDatabase, form: str) -> None:
    assert db.path_of(form) == TNT_PATH


def test_path_of_unknown_guid_is_none(db: ResourceDatabase) -> None:
    assert db.path_of("0000000000000000") is None


def test_directory_records_are_not_indexed(db: ResourceDatabase) -> None:
    assert db.guid_of("AIAgents") is None


def test_len_counts_file_records_only(db: ResourceDatabase) -> None:
    assert len(db) == 2


def test_load_from_file(tmp_path: Path, rdb_bytes: bytes) -> None:
    target = tmp_path / "resourceDatabase.rdb"
    target.write_bytes(rdb_bytes)

    assert ResourceDatabase.from_file(target).guid_of(TNT_PATH) == TNT_GUID


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ResourceDatabase.from_file(tmp_path / "missing.rdb")


@pytest.mark.skipif(
    not os.environ.get("REFORGER_DATA_DIR"),
    reason="needs REFORGER_DATA_DIR pointing to the game's addons/data",
)
def test_real_database_resolves_known_guids() -> None:
    real = ResourceDatabase.from_file(
        Path(os.environ["REFORGER_DATA_DIR"]) / "resourceDatabase.rdb"
    )

    assert real.guid_of(TNT_PATH) == TNT_GUID
    assert real.guid_of(M112_PATH) == M112_GUID
    assert real.path_of(TNT_GUID) == TNT_PATH
    assert len(real) > 90_000
