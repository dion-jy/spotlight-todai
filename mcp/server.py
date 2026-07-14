#!/usr/bin/env python3
"""
SpotlightTodAI MCP server — 3 tools over the static JSON API.

Thin wrapper around spotlight_api.py (which holds all logic and has no
third-party deps). The only dependency here is the `mcp` SDK.

Run:  python server.py            (stdio transport)
Env:  SPOTLIGHT_API_BASE          override the data source (URL or local dir)
"""

from mcp.server.fastmcp import FastMCP

import spotlight_api

mcp = FastMCP("spotlight-todai")


@mcp.tool()
def search_papers(query: str = "", conference: str = "", year: int = 0,
                  track: str = "", limit: int = 20) -> dict:
    """Search Oral/Spotlight papers (NeurIPS/ICLR/ICML) by keyword.

    Args:
        query: space-separated terms; all must appear (title/authors/summary/affiliation).
        conference: optional filter — ICLR | ICML | NeurIPS.
        year: optional filter — e.g. 2025 or 2026 (0 = any).
        track: optional filter — Oral | Spotlight.
        limit: max results (default 20).
    """
    return spotlight_api.search_papers(
        query=query, conference=conference or None, year=year or None,
        track=track or None, limit=limit)


@mcp.tool()
def daily_feed() -> dict:
    """Get today's paper of the day (deterministic, KST) plus upcoming candidates."""
    return spotlight_api.daily_feed()


@mcp.tool()
def recommend(keywords: str = "", conference: str = "", year: int = 0,
              track: str = "", limit: int = 10) -> dict:
    """Recommend papers matching a profile of interests.

    Args:
        keywords: comma- or space-separated interests, e.g. "diffusion, rlhf, agents".
        conference: optional filter — ICLR | ICML | NeurIPS.
        year: optional filter (0 = any).
        track: optional filter — Oral | Spotlight.
        limit: max results (default 10). Each result includes a score and matched_keywords.
    """
    return spotlight_api.recommend(
        keywords=keywords, conference=conference or None, year=year or None,
        track=track or None, limit=limit)


if __name__ == "__main__":
    mcp.run()
