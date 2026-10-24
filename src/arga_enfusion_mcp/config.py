"""Runtime settings, read from environment variables."""

import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

CLI_ENV = "ENFUSION_CLI"
DATA_DIR_ENV = "REFORGER_DATA_DIR"
MODS_DIR_ENV = "REFORGER_MODS_DIR"


class ConfigError(RuntimeError):
    """Raised when the server cannot find what it needs to run."""


@dataclass(frozen=True)
class Settings:
    cli_path: Path
    data_dir: Path | None
    mods_dir: Path | None


def _optional_path(env: Mapping[str, str], key: str) -> Path | None:
    value = env.get(key)
    return Path(value) if value else None


def _resolve_cli(env: Mapping[str, str], which: Callable[[str], str | None]) -> Path:
    configured = env.get(CLI_ENV)
    if configured:
        path = Path(configured)
        if not path.is_file():
            raise ConfigError(f"{CLI_ENV} points to a file that does not exist: {path}")
        return path

    found = which("enfusion")
    if found:
        return Path(found)

    raise ConfigError(
        f"Cannot locate the enfusion CLI. Set {CLI_ENV} to the path of enfusion.exe "
        "(https://github.com/landaire/enfusion_tools) or put it on PATH."
    )


def load_settings(
    env: Mapping[str, str],
    which: Callable[[str], str | None] = shutil.which,
) -> Settings:
    return Settings(
        cli_path=_resolve_cli(env, which),
        data_dir=_optional_path(env, DATA_DIR_ENV),
        mods_dir=_optional_path(env, MODS_DIR_ENV),
    )
