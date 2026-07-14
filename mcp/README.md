# SpotlightTodAI MCP server

A tiny [MCP](https://modelcontextprotocol.io) server exposing **3 tools** over
the SpotlightTodAI [static JSON API](../api/README.md). It only ever *reads*
public JSON — no backend, no keys, no writes.

| Tool | What it does |
|---|---|
| `search_papers` | keyword search over title/authors/summary/affiliation, with conference/year/track filters |
| `daily_feed` | today's deterministic "paper of the day" + upcoming candidates |
| `recommend` | rank papers against a profile of interests (weighted keyword match) |

## Layout

- [`spotlight_api.py`](spotlight_api.py) — all logic, **stdlib only** (fetch + search + recommend).
- [`server.py`](server.py) — thin FastMCP wrapper. Only dep: the `mcp` SDK.
- [`smoke_test.py`](smoke_test.py) — exercises the 3 tools without needing the SDK.

## Install

```bash
cd mcp
pip install -r requirements.txt     # just: mcp
python server.py                    # stdio MCP server
```

## Register with Claude Desktop / Claude Code

Add to your MCP config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "spotlight-todai": {
      "command": "python",
      "args": ["/absolute/path/to/spotlight-todai/mcp/server.py"]
    }
  }
}
```

Or with Claude Code:

```bash
claude mcp add spotlight-todai -- python /absolute/path/to/spotlight-todai/mcp/server.py
```

## Data source

By default the tools fetch the live API at
`https://dion-jy.github.io/spotlight-todai/api`. Override with
`SPOTLIGHT_API_BASE` — a different URL, or a **local directory** for offline use:

```bash
SPOTLIGHT_API_BASE=../api python server.py        # read the checked-out api/ files
```

## Smoke test

```bash
cd mcp
SPOTLIGHT_API_BASE=../api python smoke_test.py     # offline, against local api/
# or, against the live site:
python smoke_test.py
```
