#!/usr/bin/env python3
"""Smoke test for the core logic — no MCP SDK required.

Runs against a local api/ dir by default so it works offline:
  SPOTLIGHT_API_BASE=../api python smoke_test.py
Or against the live site by leaving SPOTLIGHT_API_BASE unset.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spotlight_api


def show(label, obj):
    print("\n=== {} ===".format(label))
    print(json.dumps(obj, ensure_ascii=False, indent=2)[:900])


def main():
    print("data source:", os.environ.get("SPOTLIGHT_API_BASE", spotlight_api.DEFAULT_BASE))

    s = spotlight_api.search_papers("diffusion", conference="ICLR", limit=3)
    assert s["results"], "search returned nothing"
    show("search_papers('diffusion', ICLR)", s)

    d = spotlight_api.daily_feed()
    assert d["paper"]["uid"], "daily has no paper"
    show("daily_feed()", {"date": d["date"], "paper": d["paper"]["title"],
                          "candidates": [c["uid"] for c in d["candidates"]]})

    r = spotlight_api.recommend("reinforcement learning, offline, world model", limit=3)
    assert r["results"], "recommend returned nothing"
    show("recommend(...)", {"keywords": r["keywords"],
                            "top": [(x["uid"], x["score"], x["matched_keywords"]) for x in r["results"]]})

    print("\nOK — all 3 tools returned results.")


if __name__ == "__main__":
    main()
