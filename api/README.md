# SpotlightTodAI — Static JSON API

A tiny, serverless, read-only API for agents (and any HTTP client). It is a set
of static JSON files served straight off GitHub Pages — no auth, no rate limits,
no backend. Just `GET` a URL.

**Base URL:** `https://dion-jy.github.io/spotlight-todai/api`

The archive: **Oral & Spotlight papers only** (the top ~1–5% of accepted papers)
from NeurIPS / ICLR / ICML. 1167 papers.

---

## Endpoints

| Endpoint | What it is | Changes |
|---|---|---|
| [`/api/papers.json`](https://dion-jy.github.io/spotlight-todai/api/papers.json) | The full archive, one stable schema | only when data is added |
| [`/api/daily.json`](https://dion-jy.github.io/spotlight-todai/api/daily.json) | Paper of the day + candidates | daily (cron, KST morning) |
| [`/api/venues.json`](https://dion-jy.github.io/spotlight-todai/api/venues.json) | Conference / year / track catalogue + counts | rarely |
| [`/api/topics.json`](https://dion-jy.github.io/spotlight-todai/api/topics.json) | Curated keyword → paper-uid inverted index | rarely |

Every file carries a `schema_version` (currently `1`).

---

## `papers.json`

```json
{
  "schema_version": 1,
  "source": "https://dion-jy.github.io/spotlight-todai",
  "count": 1167,
  "fields": { "...": "field docs, inline" },
  "papers": [
    {
      "uid": "iclr-2026-oral-1",
      "conference": "ICLR",
      "year": 2026,
      "track": "Oral",
      "title": "Common Corpus: The Largest Collection of Ethical Data ...",
      "authors": ["Pierre-Carl Langlais", "..."],
      "affiliation": "Pleias",
      "summary": "We assemble and release the largest truly open ...",
      "links": { "openreview": "https://...", "arxiv": "", "detail": "" }
    }
  ]
}
```

**`uid`** is the stable primary key: `"<conference>-<year>-<track>-<id>"`,
lowercased (e.g. `neurips-2025-spotlight-42`). Use it to join across endpoints.

Field notes:

- `authors` — full list when known, otherwise `[first author]`.
- `affiliation` — first-author affiliation; `""` if unknown.
- `summary` — 1–2 line TLDR/abstract; `""` when not yet enriched (~86% populated).
- `links.*` — `""` when absent. Most papers have `openreview`.

## `daily.json`

One deterministically-chosen "paper of the day" plus a few upcoming candidates.

```json
{
  "schema_version": 1,
  "date": "2026-07-14",
  "timezone": "Asia/Seoul",
  "rotation": { "day_index": 194, "position": 733, "cycle_length_days": 1167,
                "epoch": "2026-01-01", "method": "stable-hash permutation ..." },
  "paper": { "...full paper record..." },
  "candidates": [ { "...paper record..." }, ... ]
}
```

The pick is a pure function of the date: a fixed hash-permutation of all papers
is walked one step per day. So it is **reproducible** (same date → same paper),
rotates through the whole archive before repeating (~1167 days), and never shows
a recently-seen paper. `candidates` are the next few in the rotation.

## `venues.json`

```json
{
  "schema_version": 1, "total": 1167,
  "conferences": ["ICLR", "ICML", "NeurIPS"],
  "years": [2025, 2026], "tracks": ["Oral", "Spotlight"],
  "venues": [ { "conference": "ICLR", "year": 2026, "track": "Oral", "count": 224 }, ... ]
}
```

## `topics.json`

A curated keyword → `paper_uids` inverted index (substring match over
title+summary; a paper can appear under several topics).

```json
{
  "schema_version": 1, "topic_count": 90,
  "topics": [ { "topic": "reinforcement learning", "count": 76,
                "paper_uids": ["iclr-2026-oral-12", "..."] }, ... ]
}
```

Look up a topic, collect `paper_uids`, then resolve them against `papers.json`.

---

## Examples

```bash
# Paper of the day
curl -s https://dion-jy.github.io/spotlight-todai/api/daily.json | jq '.paper.title'

# All ICLR 2026 Oral titles
curl -s https://dion-jy.github.io/spotlight-todai/api/papers.json \
  | jq -r '.papers[] | select(.conference=="ICLR" and .track=="Oral") | .title'

# Papers tagged "diffusion"
curl -s https://dion-jy.github.io/spotlight-todai/api/topics.json \
  | jq -r '.topics[] | select(.topic=="diffusion") | .paper_uids[]'

# What venues exist
curl -s https://dion-jy.github.io/spotlight-todai/api/venues.json | jq '.venues'
```

## Prefer a tool interface?

There is a 3-tool MCP server (`search_papers` / `daily_feed` / `recommend`) that
wraps these endpoints. See [`../mcp/`](../mcp/).

## Regeneration

All files are produced deterministically by
[`../build_api.py`](../build_api.py) from `data.json` (stdlib only). `daily.json`
is refreshed every morning (KST) by a GitHub Actions cron; the rest change only
when the underlying data changes.
