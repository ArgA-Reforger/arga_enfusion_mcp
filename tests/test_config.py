from pathlib import Path

import pytest

from arga_enfusion_mcp.config import ConfigError, load_settings


def test_cli_path_comes_from_env(tmp_path: Path) -> None:
    exe = tmp_path / "enfusion.exe"
    exe.write_bytes(b"")

    settings = load_settings({"ENFUSION_CLI": str(exe)})

    assert settings.cli_path == exe


def test_missing_cli_raises_clear_error() -> None:
    with pytest.raises(ConfigError, match="ENFUSION_CLI"):
        load_settings({}, which=lambda _name: None)


def test_cli_falls_back_to_path_lookup(tmp_path: Path) -> None:
    exe = tmp_path / "enfusion.exe"
    exe.write_bytes(b"")

    settings = load_settings({}, which=lambda _name: str(exe))

    assert settings.cli_path == exe


def test_cli_env_pointing_to_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="does not exist"):
        load_settings({"ENFUSION_CLI": str(tmp_path / "nope.exe")})


def test_optional_dirs_are_none_when_unset(tmp_path: Path) -> None:
    exe = tmp_path / "enfusion.exe"
    exe.write_bytes(b"")

    settings = load_settings({"ENFUSION_CLI": str(exe)})

    assert settings.data_dir is None
    assert settings.mods_dir is None


def test_optional_dirs_are_read_from_env(tmp_path: Path) -> None:
    exe = tmp_path / "enfusion.exe"
    exe.write_bytes(b"")
    data = tmp_path / "data"
    mods = tmp_path / "mods"

    settings = load_settings(
        {
            "ENFUSION_CLI": str(exe),
            "REFORGER_DATA_DIR": str(data),
            "REFORGER_MODS_DIR": str(mods),
        }
    )

    assert settings.data_dir == data
    assert settings.mods_dir == mods


def test_extract_dir_is_read_from_env(tmp_path: Path) -> None:
    exe = tmp_path / "enfusion.exe"
    exe.write_bytes(b"")
    out = tmp_path / "out"

    settings = load_settings({"ENFUSION_CLI": str(exe), "REFORGER_EXTRACT_DIR": str(out)})

    assert settings.extract_dir == out


def test_extract_dir_defaults_to_none(tmp_path: Path) -> None:
    exe = tmp_path / "enfusion.exe"
    exe.write_bytes(b"")

    assert load_settings({"ENFUSION_CLI": str(exe)}).extract_dir is None
