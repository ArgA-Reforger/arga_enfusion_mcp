# arga_enfusion_mcp

An [MCP](https://modelcontextprotocol.io) server that lets an AI agent read **Arma Reforger** `.pak`
archives and resolve GUIDs from `resourceDatabase.rdb`, instead of answering from memory.

It wraps the open-source [`enfusion_tools`](https://github.com/landaire/enfusion_tools) CLI
(MIT, by landaire) for the `.pak` formats, and parses the `.rdb` in pure Python.

> `resourceDatabase.rdb` is not compressed: it is a flat index of resource paths and GUIDs.
> `.pak` files are read by index, without unpacking them first.

## Requirements

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- The `enfusion` CLI binary from [enfusion_tools](https://github.com/landaire/enfusion_tools)
  (prebuilt in its Releases, or `cargo build --release`)
- Arma Reforger installed

## Setup

```bash
uv sync
```

Configuration is read from environment variables:

| Variable | Required | Meaning |
|---|---|---|
| `ENFUSION_CLI` | yes, unless `enfusion` is on `PATH` | Path to the `enfusion` executable |
| `REFORGER_DATA_DIR` | for game paks and `rdb_*` | The game's `addons/data` directory (holds `data007.pak`, `resourceDatabase.rdb`) |
| `REFORGER_MODS_DIR` | for mods | `Documents/My Games/ArmaReforger/addons` (one folder per mod, each with a `data.pak`) |
| `REFORGER_EXTRACT_DIR` | for `pak_extract` | Where extraction is allowed to write. Extraction is disabled when unset |

## Register with an MCP client

Claude Code:

```bash
claude mcp add arga-enfusion \
  --env ENFUSION_CLI="C:\path\to\enfusion.exe" \
  --env REFORGER_DATA_DIR="C:\path\to\Arma Reforger\addons\data" \
  --env REFORGER_MODS_DIR="C:\path\to\My Games\ArmaReforger\addons" \
  -- uv --directory "C:\path\to\arga_enfusion_mcp" run arga-enfusion-mcp
```

Any client that takes a JSON server definition:

```json
{
  "mcpServers": {
    "arga-enfusion": {
      "command": "uv",
      "args": ["--directory", "C:\\path\\to\\arga_enfusion_mcp", "run", "arga-enfusion-mcp"],
      "env": {
        "ENFUSION_CLI": "C:\\path\\to\\enfusion.exe",
        "REFORGER_DATA_DIR": "C:\\path\\to\\Arma Reforger\\addons\\data",
        "REFORGER_MODS_DIR": "C:\\path\\to\\My Games\\ArmaReforger\\addons"
      }
    }
  }
}
```

## Tools

Every tool takes a `source`: a short name, never a filesystem path.

| Source | Resolves to |
|---|---|
| `data007`, `data007.pak` | `REFORGER_DATA_DIR/data007.pak` |
| `<ModFolder>` | `REFORGER_MODS_DIR/<ModFolder>/data.pak` |
| `@data` / `@mods` | The whole directory (slower, scans every pak) |

| Tool | Purpose |
|---|---|
| `list_sources` | Available game paks and mods |
| `pak_glob` | Find files by glob pattern |
| `pak_grep` | Regex search in file contents, returns `file:line` |
| `pak_cat` | Print one file |
| `pak_list` | List files in a source |
| `pak_info` | Archive metadata |
| `pak_extract` | Extract files under `REFORGER_EXTRACT_DIR` (the only tool that writes) |
| `rdb_guid_of` | Resource path to `{GUID}path` |
| `rdb_path_of` | GUID (with or without braces) to resource path |

For `rdb_*`, `source` is the resource database: `data` (default), `core`, or a mod folder name.

## Notes

- **Where things live (vanilla):** `data007` holds the scripts (`.c`), Prefabs, Configs,
  Particles, Missions and Language. `data008`/`data009` hold Sounds, `data010` Terrains and UI.
  A mod has a single `data.pak`.
- **Empty is not absent.** An empty result only covers the source you searched.
- **Configs inherit through `parent`.** Finding the file is not finding the value: a field can
  be defined two levels up.
- **Paths:** `pak_glob` returns paths with a leading `/`. The `.rdb` stores them without one;
  `rdb_guid_of` accepts both.
- **GUIDs:** the brace form in `.et`/`.conf`/`.ptc` files is the 8 stored bytes reversed, as
  uppercase hex.
- Output is bounded and the CLI has a timeout. Truncated output says so.

## Safety model

- Clients never send paths. A source name is validated (no separators, no `..`) and looked up
  under the configured directories only.
- The CLI runs without a shell, and positional arguments go after `--`.
- `pak_extract` writes only under `REFORGER_EXTRACT_DIR`, in a subfolder named after the source.
- Anticipated failures (unknown source, missing config, CLI error) are returned to the model as
  tool errors with a readable message.

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

A test that reads the real `resourceDatabase.rdb` runs only when `REFORGER_DATA_DIR` is set.

## Credits

Pak reading is done by [enfusion_tools](https://github.com/landaire/enfusion_tools) by landaire.
