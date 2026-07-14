# SpotlightTodAI

> Today's AI spotlight — a curated archive of **Oral & Spotlight** papers from the top AI conferences (NeurIPS / ICLR / ICML).

For people who want to study AI deeply. Not a daily feed to skim — a backbone for **understanding frontier papers in depth**.

**🔗 Browse online: [dion-jy.github.io/spotlight-todai](https://dion-jy.github.io/spotlight-todai)** — searchable, filterable table of all papers.

## Why only Oral & Spotlight?

Thousands of papers are accepted each year, but only the top 1-5% are designated Oral or Spotlight. That layer has the highest signal-to-noise ratio. This archive collects only that layer.

## Coverage

| Conference | Year | Track | Count | Status |
|---|---|---|---|---|
| NeurIPS | 2025 | Oral | 77 | ✅ |
| NeurIPS | 2025 | Spotlight | 689 | 🟡 raw (affiliation / summary to be enriched) |
| ICLR | 2026 | Oral | 224 | ✅ (TLDR + affiliation) |
| ICML | 2026 | Oral | 168 | ✅ (title + author; affiliation/summary pending OpenReview proceedings) |
| ICML | 2026 | Spotlight | 9 | 🟡 partial (track not yet fully public; from institutional press releases) |

**1167 papers** total.

## Website

A static, dependency-free site renders all papers in one searchable, filterable table:

- **[dion-jy.github.io/spotlight-todai](https://dion-jy.github.io/spotlight-todai)** — search by title/author, filter by conference / track / year, dark mode.
- Built from the `data/` markdown by [`build.py`](build.py) into [`data.json`](data.json).

## API (for agents)

A serverless, read-only JSON API is served straight off GitHub Pages — no auth,
no rate limits. Base: **`https://dion-jy.github.io/spotlight-todai/api`**

- [`api/papers.json`](https://dion-jy.github.io/spotlight-todai/api/papers.json) — full archive, stable schema (`uid` = `<conf>-<year>-<track>-<id>`).
- [`api/daily.json`](https://dion-jy.github.io/spotlight-todai/api/daily.json) — deterministic "paper of the day" + candidates, refreshed each morning (KST) by a GitHub Actions cron.
- [`api/venues.json`](https://dion-jy.github.io/spotlight-todai/api/venues.json) — conference/year/track counts.
- [`api/topics.json`](https://dion-jy.github.io/spotlight-todai/api/topics.json) — curated keyword → paper-uid index.

Docs: [`api/README.md`](api/README.md) · agent discovery: [`llms.txt`](llms.txt) ·
tool interface: a 3-tool MCP server (`search_papers` / `daily_feed` / `recommend`) in [`mcp/`](mcp/).
All files are generated deterministically from `data.json` by [`build_api.py`](build_api.py).

## Data

The [`data/`](data/) folder holds per-conference markdown tables:

- [`neurips-2025-oral.md`](data/neurips-2025-oral.md)
- [`neurips-2025-spotlight.md`](data/neurips-2025-spotlight.md)
- [`iclr-2026-oral.md`](data/iclr-2026-oral.md)
- [`icml-2026-oral.md`](data/icml-2026-oral.md)
- [`icml-2026-spotlight.md`](data/icml-2026-spotlight.md) — partial

Each paper: title / first author (affiliation) / OpenReview link / arXiv link / 1-2 line summary.

GitHub's markdown table rendering makes this directly browsable. Search via GitHub repo search or in-file Ctrl+F.

## Data sources

- **OpenReview API** (`api2.openreview.net`) — canonical source for accept decisions and metadata
- Each conference's official virtual proceedings page — cross-check for Oral/Spotlight tracks
- arXiv — abstract / PDF mapping

## Roadmap

- **Phase 1 (current)** — raw collection. Per-conference Oral/Spotlight listings.
- **Phase 2** — tooling for heavy academic learners:
  - Reading Path Generator (per-topic learning paths)
  - Per-paper Deep Explanation
  - Reproducibility Audit
  - Concept spaced-repetition deck
- **Phase 3** — website / search / API.

## License

Data follows the original sources of each paper / conference. The curation and organization in this archive are free to use.
