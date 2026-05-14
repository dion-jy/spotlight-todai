# ICML 2026 — Oral Papers

**0 papers confirmed** (collected: 2026-05-14)
**Status**: ⚠️ **Oral track not yet published — re-collection needed**

---

## Status summary (as of 2026-05-14)

ICML 2026 will be held 2026-07-06 to 07-11 in Seoul. Acceptance notification went out on 2026-05-12 (just 2 days ago). **As of now, there is no public list of Oral-designated papers.**

### Confirmed facts

| Item | Value | Source |
|---|---|---|
| Total submissions | 23,918 | RIKEN AIP / 36kr |
| Total accepted | 6,352 (26.6%) | RIKEN AIP / Paper Digest |
| Spotlight ratio | 2.2% (~536 papers) | RIKEN AIP / 36kr |
| Oral ratio | **no official figure** | — |
| Notification date | 2026-05-12 | search results |
| Track designation publish date | **TBD** (not yet public) | icml.cc page check |

### Data source investigation

1. **icml.cc official site** (https://icml.cc/virtual/2026/events/oral)
   - The URL returns 200 but page content reads: `"Orals  0 Events  No Events Available  There are currently no events in this category"`
   - The category exists but no papers assigned yet.

2. **OpenReview API** (https://api2.openreview.net)
   - `content.venueid=ICML.cc/2026/Conference` → 0 notes
   - `content.venue=ICML 2026 oral` → 0 notes
   - `content.venue=ICML 2026` → 35 notes (all `venueid=OpenReview.net/Archive`, author self-uploads)
   - ICML 2026's OpenReview proceedings are not yet published.

3. **Paper Copilot** (https://github.com/papercopilot/paperlists/tree/main/icml)
   - Only `icml2025.json` exists; no `icml2026.json`. The statistics page shows "data loading".

4. **icml.cc virtual papers page** (https://icml.cc/virtual/2026/papers.html)
   - All 6,567 papers are exposed only under `/virtual/2026/poster/{N}` paths. No Oral / Spotlight distinguishing tags.

### Policy background

From the ICML 2026 Call for Papers:
> "They will all be eligible for ICML awards as well as for the designations of distinction corresponding to the past 'oral presentations' and 'spotlight posters.'"

Track designations are retained, but starting this year authors can choose afterward whether to present in person (proceedings-only is allowed). This likely explains why designation publishing lags behind the acceptance notification.

---

## Data (currently empty)

| # | Title | First Author (Affiliation) | OpenReview | arXiv | Summary |
|---|---|---|---|---|---|
| — | (Oral track papers not yet public) | — | — | — | — |

---

## Next actions (re-collection triggers)

- [ ] Periodically check whether icml.cc/virtual/2026/events/oral fills with events (every 1-2 weeks)
- [ ] Monitor for OpenReview API `content.venueid=ICML.cc/2026/Conference` returning > 0
- [ ] Monitor Paper Copilot github for `icml2026.json`
- [ ] The Spotlight page (spotlight-posters) will likely fill at the same time

Re-collection signal candidates:
- ICML official X (Twitter) `@icmlconf` track announcement
- Paper cards appearing at icml.cc/virtual/2026/events/oral
- ICML.cc/2026/Conference venueid appearing on OpenReview

---

## Source & Methodology

- **Primary source attempted**: OpenReview API (https://api2.openreview.net/notes?content.venueid=ICML.cc/2026/Conference) — 0 hits.
- **Primary source attempted**: icml.cc official track page (https://icml.cc/virtual/2026/events/oral) — empty.
- **Cross-checked with**:
  - Paper Digest (https://www.paperdigest.org/2026/05/icml-2026-papers-highlights/) — no track designations.
  - Paper Copilot (https://papercopilot.com/statistics/icml-statistics/icml-2026-statistics/) — data loading.
  - Institutional press releases (RIKEN AIP, Aarhus U, UPenn ASSET, UCL, KAIST DM Lab, Wake Forest, U Washington Math) — only Spotlight mentioned, 0 Oral mentions.
- **Collected**: 2026-05-14
- **Status**: Oral track not yet public. Re-collection needed. ICML 2026 acceptance notification was 2026-05-12, so track designations will likely be published soon.
