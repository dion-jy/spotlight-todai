"""
spotlight_api.py — stdlib-only client for the SpotlightTodAI static JSON API.

All the actual logic (fetch, search, recommend, daily) lives here with ZERO
third-party dependencies, so it can be unit/smoke-tested on its own. The MCP
server (server.py) is a thin wrapper around these functions.

Data source resolution (SPOTLIGHT_API_BASE env var):
  * unset            -> the live GitHub Pages API (default)
  * an http(s) URL   -> that base
  * a local dir path -> read <dir>/papers.json etc. (offline / CI)
"""

import json
import os
import re
import urllib.request

DEFAULT_BASE = "https://dion-jy.github.io/spotlight-todai/api"

_CACHE = {}


def _base():
    return os.environ.get("SPOTLIGHT_API_BASE", DEFAULT_BASE).rstrip("/")


def _load(name):
    """Load one API file by basename (e.g. 'papers.json'), cached per process."""
    if name in _CACHE:
        return _CACHE[name]
    base = _base()
    if re.match(r"^https?://", base):
        req = urllib.request.Request(base + "/" + name, headers={"User-Agent": "spotlight-mcp"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    else:
        with open(os.path.join(base, name), encoding="utf-8") as f:
            data = json.load(f)
    _CACHE[name] = data
    return data


def _all_papers():
    return _load("papers.json")["papers"]


def _compact(p):
    """Trim a paper record to the fields most useful in a tool response."""
    return {
        "uid": p["uid"],
        "conference": p["conference"],
        "year": p["year"],
        "track": p["track"],
        "title": p["title"],
        "authors": p["authors"],
        "affiliation": p["affiliation"],
        "summary": p["summary"],
        "openreview": p["links"].get("openreview", ""),
        "arxiv": p["links"].get("arxiv", ""),
    }


def _matches_filters(p, conference, year, track):
    if conference and p["conference"].lower() != conference.lower():
        return False
    if year and int(p["year"]) != int(year):
        return False
    if track and p["track"].lower() != track.lower():
        return False
    return True


# ---------------------------------------------------------------- public API

def search_papers(query="", conference=None, year=None, track=None, limit=20):
    """Keyword search over title / authors / summary / affiliation.

    All whitespace-separated tokens in `query` must be present (AND). Results
    are ranked with title matches weighted above summary/author matches.
    """
    tokens = [t for t in re.split(r"\s+", query.lower().strip()) if t]
    out = []
    for p in _all_papers():
        if not _matches_filters(p, conference, year, track):
            continue
        title = p["title"].lower()
        blob = (p["title"] + " " + " ".join(p["authors"]) + " "
                + p["affiliation"] + " " + p["summary"]).lower()
        if tokens and not all(t in blob for t in tokens):
            continue
        score = sum(3 for t in tokens if t in title) + sum(1 for t in tokens if t in blob)
        out.append((score, p))
    # Higher score first; stable by uid for reproducibility.
    out.sort(key=lambda sp: (-sp[0], sp[1]["uid"]))
    results = [_compact(p) for _, p in out[: max(1, int(limit))]]
    return {"query": query, "count": len(results), "total_matched": len(out), "results": results}


def daily_feed():
    """Return today's deterministically-chosen paper + upcoming candidates."""
    d = _load("daily.json")
    return {
        "date": d["date"],
        "timezone": d.get("timezone"),
        "paper": _compact(d["paper"]),
        "candidates": [_compact(c) for c in d.get("candidates", [])],
    }


def recommend(keywords, conference=None, year=None, track=None, limit=10):
    """Rank papers by a weighted profile of keywords/interests.

    `keywords` may be a list of strings, or a single string (split on commas /
    whitespace). Each keyword scores 3 for a title hit and 1 for a summary hit;
    a paper needs at least one hit to be recommended.
    """
    if isinstance(keywords, str):
        parts = re.split(r"[,\n]+", keywords)
        kws = [k.strip().lower() for part in parts for k in [part] if k.strip()]
    else:
        kws = [str(k).strip().lower() for k in (keywords or []) if str(k).strip()]
    if not kws:
        return {"error": "no keywords provided", "results": []}

    scored = []
    for p in _all_papers():
        if not _matches_filters(p, conference, year, track):
            continue
        title = p["title"].lower()
        summary = p["summary"].lower()
        matched = []
        score = 0
        for k in kws:
            hit = False
            if k in title:
                score += 3
                hit = True
            if k in summary:
                score += 1
                hit = True
            if hit:
                matched.append(k)
        if score > 0:
            scored.append((score, matched, p))
    scored.sort(key=lambda s: (-s[0], s[2]["uid"]))
    results = []
    for score, matched, p in scored[: max(1, int(limit))]:
        rec = _compact(p)
        rec["score"] = score
        rec["matched_keywords"] = matched
        results.append(rec)
    return {"keywords": kws, "count": len(results), "results": results}
