#!/usr/bin/env python3
"""
build.py — Parse data/*.md markdown tables into data.json and data.js

No external dependencies (standard library only).

Each paper record:
  {
    "id": int,                # row # within its file (as written in the table)
    "conference": "ICML"|"ICLR"|"NeurIPS",
    "year": int,
    "track": "Oral"|"Spotlight",
    "title": str,
    "author": str,
    "affiliation": str,       # "" if unknown
    "links": {"openreview": str, "arxiv": str, "detail": str},  # "" if absent
    "summary": str,           # "" if absent
  }
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECTIONS = os.path.join(HERE, "data")

# (filename, conference, year, track)
FILES = [
    ("iclr-2026-oral.md",        "ICLR",    2026, "Oral"),
    ("icml-2026-oral.md",        "ICML",    2026, "Oral"),
    ("icml-2026-spotlight.md",   "ICML",    2026, "Spotlight"),
    ("neurips-2025-oral.md",     "NeurIPS", 2025, "Oral"),
    ("neurips-2025-spotlight.md","NeurIPS", 2025, "Spotlight"),
]

DATA_ROW_RE = re.compile(r"^\|\s*\d+\s*\|")          # table data rows start with "| <number> |"
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")        # extract URL from [text](url)
AFFIL_RE = re.compile(r"^(.*?)\s*\(([^)]*)\)\s*$")    # "Name (Affiliation)"


def split_row(line, expected_cells):
    """Split a markdown table row into exactly `expected_cells` cells.

    A markdown row looks like: | a | b | c |
    Stripping the outer pipes and splitting on '|' gives the cells. If a cell
    (typically the trailing summary) contains stray unescaped pipes, the split
    produces too many parts; we merge the surplus into the LAST cell so the
    leading fixed-width columns stay aligned.
    """
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    parts = [p.strip() for p in s.split("|")]
    if len(parts) > expected_cells:
        head = parts[: expected_cells - 1]
        tail = " | ".join(parts[expected_cells - 1 :])
        parts = head + [tail]
    while len(parts) < expected_cells:
        parts.append("")
    return parts


def first_link(cell):
    """Return the URL from a [text](url) markdown cell, else ''.

    Plain text such as 'TBA' or empty cells yield ''.
    """
    if not cell:
        return ""
    m = LINK_RE.search(cell)
    if m:
        return m.group(1).strip()
    return ""


def split_author_affil(cell):
    """Split 'Name (Affiliation)' into (name, affiliation). No parens => ('Name', '')."""
    cell = cell.strip()
    m = AFFIL_RE.match(cell)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return cell, ""


def parse_standard(path):
    """Parse the 6-column layout:
       | # | Title | Author (Affil) | OpenReview | arXiv | Summary |
    Used by ICLR oral, ICML spotlight, NeurIPS oral, NeurIPS spotlight.
    """
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not DATA_ROW_RE.match(line):
                continue
            num, title, author_cell, openrev, arxiv, summary = split_row(line, 6)
            author, affil = split_author_affil(author_cell)
            rows.append({
                "id": int(num),
                "title": title,
                "author": author,
                "affiliation": affil,
                "links": {
                    "openreview": first_link(openrev),
                    "arxiv": first_link(arxiv),
                    "detail": "",
                },
                "summary": summary,
            })
    return rows


def parse_icml_oral(path):
    """Parse the ICML-oral layout (different columns):
       | # | Title | Author | #authors | Detail(icml.cc link) |
    No affiliation / openreview / arxiv / summary available.
    """
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not DATA_ROW_RE.match(line):
                continue
            num, title, author, _nauthors, detail = split_row(line, 5)
            rows.append({
                "id": int(num),
                "title": title,
                "author": author.strip(),
                "affiliation": "",
                "links": {
                    "openreview": "",
                    "arxiv": "",
                    "detail": first_link(detail),
                },
                "summary": "",
            })
    return rows


def main():
    papers = []
    counts = {}
    for fname, conf, year, track in FILES:
        path = os.path.join(COLLECTIONS, fname)
        if fname == "icml-2026-oral.md":
            rows = parse_icml_oral(path)
        else:
            rows = parse_standard(path)

        for r in rows:
            papers.append({
                "id": r["id"],
                "conference": conf,
                "year": year,
                "track": track,
                "title": r["title"],
                "author": r["author"],
                "affiliation": r["affiliation"],
                "links": r["links"],
                "summary": r["summary"],
            })

        key = "%s %d %s" % (conf, year, track)
        counts[key] = len(rows)

    # Write data.json
    out_json = os.path.join(HERE, "data.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=1)

    # Write data.js (so index.html opens via file:// without CORS issues)
    out_js = os.path.join(HERE, "data.js")
    with open(out_js, "w", encoding="utf-8") as f:
        f.write("window.PAPERS = ")
        json.dump(papers, f, ensure_ascii=False)
        f.write(";\n")

    # Report
    total = len(papers)
    print("Wrote %s" % out_json)
    print("Wrote %s" % out_js)
    print("Total papers: %d" % total)
    for k in sorted(counts):
        print("  %-22s %4d" % (k, counts[k]))

    expected = 224 + 168 + 9 + 77 + 689
    if total != expected:
        print("WARNING: total %d != expected %d" % (total, expected))
    else:
        print("OK: total matches expected %d" % expected)


if __name__ == "__main__":
    main()
