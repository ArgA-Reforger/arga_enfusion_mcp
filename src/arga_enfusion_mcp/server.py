"""MCP server exposing read-only access to Arma Reforger .pak archives."""

import os
import sys
from collections.abc import Callable

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from arga_enfusion_mcp.cli import CliError, EnfusionCli
from arga_enfusion_mcp.config import ConfigError, load_settings
from arga_enfusion_mcp.service import PakService
from arga_enfusion_mcp.sources import SourceError

INSTRUCTIONS = """\
Read Arma Reforger .pak archives and resolve GUIDs. Nothing here is readable on disk
directly: the game, its scripts included, lives inside .pak files.

Sources: call list_sources first. `source` is a name (data007, a mod folder, @data, @mods),
never a filesystem path.

Where things live (vanilla): data007 holds scripts (.c), Prefabs, Configs, Particles,
Missions and Language. data008/data009 hold Sounds, data010 Terrains and UI. A mod has a
single data.pak.

Rules:
- Cite file:line. Never state inheritance, modifiers or ranges from memory: grep the
  declaration and walk up the chain.
- Enfusion configs inherit through `parent`. A value can sit two levels up, so finding the
  file is not finding the value.
- An empty result is not proof of absence: say which source you searched and try another
  pak. If a tool fails or returns nothing, report it and stop; never brute-force scan.
- Paths returned by pak_glob start with `/`. Resource database paths do not; rdb_guid_of
  accepts both.
- GUIDs in .et/.conf/.ptc files are written in braces, e.g. {8B9323E3EEFBFE99}.
"""

_READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)
_WRITES_FILES = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True)


def _expected(operation: Callable[[], str]) -> str:
    """Run a service call, turning anticipated failures into tool errors the model can read."""
    try:
        return operation()
    except (SourceError, ConfigError, CliError) as error:
        raise ToolError(str(error)) from error


def build_server(service: PakService) -> MCPServer:
    server = MCPServer("arga-enfusion-mcp", instructions=INSTRUCTIONS)

    @server.tool(annotations=_READ_ONLY)
    def list_sources() -> str:
        """List the available sources: game paks, mods and resource databases."""
        return _expected(lambda: service.list_sources())

    @server.tool(annotations=_READ_ONLY)
    def pak_glob(pattern: str, source: str = "data007", long: bool = False) -> str:
        """Find files by glob pattern (e.g. "**/*Suppress*.c"), one path per line.

        Set long=True to include file sizes.
        """
        return _expected(lambda: service.glob(pattern, source, long=long))

    @server.tool(annotations=_READ_ONLY)
    def pak_grep(
        pattern: str,
        source: str = "data007",
        glob: str | None = None,
        extensions: list[str] | None = None,
        ignore_case: bool = False,
        files_only: bool = False,
        context: int = 0,
    ) -> str:
        """Regex search inside file contents, returning file:line matches.

        By default only common text extensions are searched; narrow with `extensions`
        (e.g. ["c"]) or `glob`. Use files_only=True to list matching files only.
        """
        return _expected(
            lambda: service.grep(
                pattern,
                source,
                glob=glob,
                extensions=extensions,
                ignore_case=ignore_case,
                files_only=files_only,
                context=context,
            )
        )

    @server.tool(annotations=_READ_ONLY)
    def pak_cat(path: str, source: str = "data007") -> str:
        """Print one file's contents. Copy `path` literally from pak_glob output."""
        return _expected(lambda: service.cat(path, source))

    @server.tool(annotations=_READ_ONLY)
    def pak_list(source: str = "data007", glob: str | None = None, long: bool = False) -> str:
        """List every file in a source, optionally filtered by a glob pattern."""
        return _expected(lambda: service.list_files(source, glob=glob, long=long))

    @server.tool(annotations=_READ_ONLY)
    def pak_info(source: str = "data007") -> str:
        """Show archive metadata: extensions, entry count and prefix."""
        return _expected(lambda: service.info(source))

    @server.tool(annotations=_WRITES_FILES)
    def pak_extract(pattern: str, source: str = "data007", flat: bool = False) -> str:
        """Extract files matching a glob pattern into the configured extraction directory.

        Prefer pak_cat/pak_grep: extract only for sustained work on a subsystem.
        """
        return _expected(lambda: service.extract(pattern, source, flat=flat))

    @server.tool(annotations=_READ_ONLY)
    def rdb_guid_of(path: str, source: str = "data") -> str:
        """Resolve a resource path to its GUID, returned as {GUID}path.

        `source` is the resource database: data, core, or a mod folder name.
        """
        return _expected(lambda: service.guid_of(path, source))

    @server.tool(annotations=_READ_ONLY)
    def rdb_path_of(guid: str, source: str = "data") -> str:
        """Resolve a GUID (with or without braces) to its resource path."""
        return _expected(lambda: service.path_of(guid, source))

    return server


def main() -> None:
    try:
        settings = load_settings(os.environ)
    except ConfigError as error:
        print(f"arga-enfusion-mcp: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    service = PakService(settings, EnfusionCli(settings.cli_path))
    build_server(service).run()


if __name__ == "__main__":
    main()
