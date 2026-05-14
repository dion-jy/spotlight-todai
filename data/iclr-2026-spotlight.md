# ICLR 2026 — Spotlight Papers

**0 papers** (collected: 2026-05-14)

## Conclusion

**ICLR 2026 has no Spotlight category.** Accept decisions ran with only `Oral` and `Poster`. The 224 Orals are in a separate file ([`iclr-2026-oral.md`](iclr-2026-oral.md)).

## Evidence

1. **OpenReview venue config** — the `accept_decision_options` field at `https://api2.openreview.net/groups?id=ICLR.cc/2026/Conference` is defined as:
   ```
   ["Accept (Oral)", "Accept (Poster)", "Conditional Accept (Oral)", "Conditional Accept (Poster)"]
   ```
   No Spotlight option.
2. **decision_heading_map** — the same venue config's `decision_heading_map` defines only three:
   ```
   {"ICLR 2026 Oral": "Accept (Oral)", "ICLR 2026 Poster": "Accept (Poster)", "Submitted to ICLR 2026": "Reject"}
   ```
3. **Official virtual conference page** — `https://iclr.cc/virtual/2026/events/spotlight` exists but its body only shows "0 Events / No Events Available". The Orals page (`/virtual/2026/events/oral`) renders paper cards normally.
4. **Direct OpenReview query** — querying `content.venue=ICLR 2026 Spotlight` or similar variants returns 0 results.

## Notes

- ICLR ran a Spotlight track (top ~5%) through ICLR 2024, but it was phased out starting ICLR 2025. ICLR 2026 follows the same two-tier (Oral / Poster) system.
- If "Spotlight Talk" information under a different definition (e.g. workshops) is needed later, collect it from `/virtual/2026/workshops`.

## Source & Methodology

- **Primary source:** Direct query of OpenReview API v2 venue config.
- **Cross-check:** HTML of the official iclr.cc virtual conference spotlight page.
- **Collected:** 2026-05-14
