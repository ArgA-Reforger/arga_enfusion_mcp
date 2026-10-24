"""Resolve a client-supplied source name to archive paths, safely.

MCP clients never send filesystem paths. They send a short name (``data007``,
a mod folder, ``@data``, ``@mods``) that is looked up under the configured
game directories. Anything that could escape those directories is rejected.
"""

import re
from pathlib import Path

from arga_enfusion_mcp.config import DATA_DIR_ENV, MODS_DIR_ENV

_SAFE_NAME = re.compile(r"[A-Za-z0-9_.\-]+")
_RDB_FILE = "resourceDatabase.rdb"
_MOD_PAK = "data.pak"
_MAX_LISTED = 10


class SourceError(ValueError):
    """Raised when a source name is unsafe, unknown or not configured."""


def _check_name(name: str) -> str:
    if not _SAFE_NAME.fullmatch(name) or ".." in name:
        raise SourceError(f"Invalid source name {name!r}: use a plain name, not a path.")
    return name


class SourceResolver:
    def __init__(self, data_dir: Path | None, mods_dir: Path | None) -> None:
        self._data_dir = data_dir
        self._mods_dir = mods_dir

    def available(self) -> dict[str, list[str]]:
        data: list[str] = []
        if self._data_dir and self._data_dir.is_dir():
            data = sorted(p.stem for p in self._data_dir.glob("*.pak"))
        mods: list[str] = []
        if self._mods_dir and self._mods_dir.is_dir():
            mods = sorted(p.name for p in self._mods_dir.iterdir() if (p / _MOD_PAK).is_file())
        return {"data": data, "mods": mods}

    def archives(self, source: str) -> list[Path]:
        if source == "@data":
            return [self._require(self._data_dir, DATA_DIR_ENV)]
        if source == "@mods":
            return [self._require(self._mods_dir, MODS_DIR_ENV)]

        name = _check_name(source)
        if self._data_dir is None and self._mods_dir is None:
            raise SourceError(f"No sources configured: set {DATA_DIR_ENV} and/or {MODS_DIR_ENV}.")

        for candidate in self._candidates(name):
            if candidate.is_file():
                return [candidate]

        available = self.available()
        names = available["data"] + available["mods"]
        shown = ", ".join(names[:_MAX_LISTED]) or "none"
        more = f" (+{len(names) - _MAX_LISTED} more)" if len(names) > _MAX_LISTED else ""
        raise SourceError(
            f"Unknown source {name!r}. Available: {shown}{more}. "
            "Call list_sources for the full list."
        )

    def rdb_path(self, source: str) -> Path:
        name = _check_name(source)
        if name == "data":
            path = self._require(self._data_dir, DATA_DIR_ENV) / _RDB_FILE
        elif name == "core":
            path = self._require(self._data_dir, DATA_DIR_ENV).parent / "core" / _RDB_FILE
        else:
            path = self._require(self._mods_dir, MODS_DIR_ENV) / name / _RDB_FILE
        if not path.is_file():
            raise SourceError(f"{_RDB_FILE} not found for source {name!r}.")
        return path

    def _candidates(self, name: str) -> list[Path]:
        candidates: list[Path] = []
        if self._data_dir is not None:
            pak_name = name if name.endswith(".pak") else f"{name}.pak"
            candidates.append(self._data_dir / pak_name)
        if self._mods_dir is not None:
            candidates.append(self._mods_dir / name / _MOD_PAK)
        return candidates

    @staticmethod
    def _require(directory: Path | None, env_name: str) -> Path:
        if directory is None:
            raise SourceError(f"{env_name} is not set.")
        return directory
