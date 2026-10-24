"""Use cases behind the MCP tools: resolve a source, run the CLI, shape the answer."""

from collections.abc import Sequence
from pathlib import Path

from arga_enfusion_mcp.cli import CliResult, EnfusionCli
from arga_enfusion_mcp.config import EXTRACT_DIR_ENV, ConfigError, Settings
from arga_enfusion_mcp.rdb import ResourceDatabase
from arga_enfusion_mcp.sources import SourceResolver

_TRUNCATED_NOTE = "\n[output truncated: narrow the pattern or use a more specific source]"


class PakService:
    def __init__(self, settings: Settings, cli: EnfusionCli) -> None:
        self._settings = settings
        self._cli = cli
        self._sources = SourceResolver(settings.data_dir, settings.mods_dir)
        self._rdb_cache: dict[Path, tuple[int, ResourceDatabase]] = {}

    def list_sources(self) -> str:
        available = self._sources.available()
        lines = ["Data paks (use the name as `source`):"]
        lines += [f"  {name}" for name in available["data"]] or ["  (none)"]
        lines.append("Mods (folder name as `source`):")
        lines += [f"  {name}" for name in available["mods"]] or ["  (none)"]
        lines.append("Whole directories: @data (all game paks, slow), @mods (all mods).")
        lines.append("Resource databases: data, core, or a mod folder name.")
        return "\n".join(lines)

    def glob(self, pattern: str, source: str, *, long: bool = False) -> str:
        archives = self._sources.archives(source)
        return self._render(self._cli.glob(pattern, archives, long=long), source)

    def grep(
        self,
        pattern: str,
        source: str,
        *,
        glob: str | None = None,
        extensions: Sequence[str] | None = None,
        ignore_case: bool = False,
        files_only: bool = False,
        context: int = 0,
    ) -> str:
        archives = self._sources.archives(source)
        result = self._cli.grep(
            pattern,
            archives,
            glob=glob,
            extensions=extensions,
            ignore_case=ignore_case,
            files_only=files_only,
            context=context,
        )
        return self._render(result, source)

    def cat(self, path: str, source: str) -> str:
        archives = self._sources.archives(source)
        return self._render(self._cli.cat(path, archives), source)

    def list_files(self, source: str, *, glob: str | None = None, long: bool = False) -> str:
        archives = self._sources.archives(source)
        return self._render(self._cli.list(archives, glob=glob, long=long), source)

    def info(self, source: str) -> str:
        archives = self._sources.archives(source)
        return self._render(self._cli.info(archives), source)

    def extract(self, pattern: str, source: str, *, flat: bool = False) -> str:
        if self._settings.extract_dir is None:
            raise ConfigError(f"Extraction is disabled: set {EXTRACT_DIR_ENV} to enable it.")
        archives = self._sources.archives(source)
        target = self._settings.extract_dir / source.lstrip("@").removesuffix(".pak")
        target.mkdir(parents=True, exist_ok=True)
        result = self._cli.extract(pattern, archives, target, flat=flat)
        return f"Extracted to {target}\n{self._render(result, source)}"

    def guid_of(self, path: str, source: str = "data") -> str:
        guid = self._rdb(source).guid_of(path)
        if guid is None:
            return f"No GUID found for {path!r} in the {source!r} resource database."
        return "{" + guid + "}" + path.lstrip("/")

    def path_of(self, guid: str, source: str = "data") -> str:
        path = self._rdb(source).path_of(guid)
        if path is None:
            return f"No path found for GUID {guid!r} in the {source!r} resource database."
        return path

    def _rdb(self, source: str) -> ResourceDatabase:
        path = self._sources.rdb_path(source)
        mtime = path.stat().st_mtime_ns
        cached = self._rdb_cache.get(path)
        if cached is None or cached[0] != mtime:
            cached = (mtime, ResourceDatabase.from_file(path))
            self._rdb_cache[path] = cached
        return cached[1]

    @staticmethod
    def _render(result: CliResult, source: str) -> str:
        if not result.text.strip():
            return (
                f"No results in source {source!r}. An empty result is not proof of absence: "
                "the content may live in another pak."
            )
        return result.text + (_TRUNCATED_NOTE if result.truncated else "")
