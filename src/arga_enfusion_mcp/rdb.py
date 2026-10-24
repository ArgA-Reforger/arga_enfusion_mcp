"""Reader for Arma Reforger's ``resourceDatabase.rdb``.

The file is a flat index, not a compressed archive. Each file record is::

    [u32 length][ASCII path] 00 06 00 00 00 00 00 [8-byte GUID, little-endian] ...

Directory records use ``00 05`` instead of ``00 06`` and are ignored. The GUID
written in braces inside ``.et``/``.conf``/``.ptc`` files is those 8 bytes
reversed, as uppercase hex. Paths are stored without a leading slash.
"""

import re
from pathlib import Path
from typing import Self

_FILE_RECORD = re.compile(rb"([\x20-\x7e]+)\x00\x06\x00\x00\x00\x00\x00(.{8})", re.DOTALL)
_GUID_HEX = re.compile(r"[0-9A-F]{16}")


def _normalise_path(path: str) -> str:
    return path.lstrip("/")


def _normalise_guid(guid: str) -> str:
    return guid.strip().strip("{}").upper()


class ResourceDatabase:
    def __init__(self, data: bytes) -> None:
        self._guid_by_path: dict[str, str] = {}
        self._path_by_guid: dict[str, str] = {}
        for match in _FILE_RECORD.finditer(data):
            path = match.group(1).decode("ascii")
            guid = match.group(2)[::-1].hex().upper()
            self._guid_by_path[path] = guid
            self._path_by_guid[guid] = path

    @classmethod
    def from_file(cls, path: Path) -> Self:
        return cls(path.read_bytes())

    def __len__(self) -> int:
        return len(self._guid_by_path)

    def guid_of(self, path: str) -> str | None:
        """Return the 16-digit uppercase GUID for a resource path, or None."""
        return self._guid_by_path.get(_normalise_path(path))

    def path_of(self, guid: str) -> str | None:
        """Return the resource path for a GUID, with or without braces."""
        normalised = _normalise_guid(guid)
        if not _GUID_HEX.fullmatch(normalised):
            return None
        return self._path_by_guid.get(normalised)
