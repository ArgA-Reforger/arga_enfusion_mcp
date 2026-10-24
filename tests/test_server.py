import asyncio
import subprocess
from pathlib import Path

import pytest
from mcp.client import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent

from arga_enfusion_mcp.cli import EnfusionCli
from arga_enfusion_mcp.config import Settings
from arga_enfusion_mcp.server import build_server
from arga_enfusion_mcp.service import PakService

EXPECTED_TOOLS = {
    "list_sources",
    "pak_glob",
    "pak_grep",
    "pak_cat",
    "pak_list",
    "pak_info",
    "pak_extract",
    "rdb_guid_of",
    "rdb_path_of",
}


def fake_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(argv, 0, b"/scripts/A.c\n", b"")


@pytest.fixture
def server(tmp_path: Path) -> MCPServer:
    data = tmp_path / "data"
    data.mkdir()
    (data / "data007.pak").write_bytes(b"")
    settings = Settings(Path("enfusion.exe"), data, None, None)
    service = PakService(settings, EnfusionCli(settings.cli_path, runner=fake_runner))
    return build_server(service)


def call(server: MCPServer, name: str, arguments: dict[str, object]) -> tuple[bool, str]:
    async def run() -> CallToolResult:
        async with Client(server) as client:
            return await client.call_tool(name, arguments)

    result = asyncio.run(run())
    block = result.content[0]
    assert isinstance(block, TextContent)
    return bool(result.is_error), block.text


def test_registers_expected_tools(server: MCPServer) -> None:
    names = {tool.name for tool in asyncio.run(server.list_tools())}

    assert names == EXPECTED_TOOLS


def test_only_extract_is_not_read_only(server: MCPServer) -> None:
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}

    for name, tool in tools.items():
        read_only = tool.annotations is not None and tool.annotations.read_only_hint is True
        assert read_only == (name != "pak_extract"), name


def test_tools_have_descriptions(server: MCPServer) -> None:
    for tool in asyncio.run(server.list_tools()):
        assert tool.description, tool.name


def test_calling_glob_returns_cli_output(server: MCPServer) -> None:
    is_error, text = call(server, "pak_glob", {"pattern": "**/*.c", "source": "data007"})

    assert not is_error
    assert "/scripts/A.c" in text


def test_unknown_source_is_reported_as_tool_error(server: MCPServer) -> None:
    is_error, text = call(server, "pak_glob", {"pattern": "*", "source": "nope"})

    assert is_error
    assert "Unknown source" in text


def test_server_instructions_carry_the_gotchas(server: MCPServer) -> None:
    instructions = server.instructions or ""

    assert "parent" in instructions
    assert "not proof of absence" in instructions


def test_cli_failure_is_reported_as_tool_error(tmp_path: Path) -> None:
    def failing(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 2, b"", b"bad archive")

    data = tmp_path / "data"
    data.mkdir()
    (data / "data007.pak").write_bytes(b"")
    settings = Settings(Path("enfusion.exe"), data, None, None)
    service = PakService(settings, EnfusionCli(settings.cli_path, runner=failing))

    is_error, text = call(build_server(service), "pak_glob", {"pattern": "*", "source": "data007"})

    assert is_error
    assert "bad archive" in text
