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
    "author": str,            # first author (single string, kept for back-compat)
    "authors": [str],         # FULL author list when available, else [author]
    "affiliation": str,       # "" if unknown
    "links": {"openreview": str, "arxiv": str, "detail": str},  # "" if absent
    "summary": str,           # "" if absent
  }

Full author lists are merged from authors.json (a sidecar enrichment file keyed
by "<conference>|<year>|<track>|<id>") so the source markdown stays untouched.
"""

import json
import os
import re

from slugs import make_uid, slug_map

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECTIONS = os.path.join(HERE, "data")
AUTHORS_JSON = os.path.join(HERE, "authors.json")
INDEX_HTML = os.path.join(HERE, "index.html")
DAILY_JSON = os.path.join(HERE, "api", "daily.json")
ROBOTS_TXT = os.path.join(HERE, "robots.txt")

SITE_URL = "https://dion-jy.github.io/spotlight-todai/"
PAGES_DIR = os.path.join(HERE, "paper")
VENUE_DIR = os.path.join(HERE, "venue")

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


def load_authors_map():
    """Load the optional authors.json enrichment file.

    Keys are "<conference>|<year>|<track>|<id>" -> [full author list].
    Returns {} if the file is absent.
    """
    if not os.path.exists(AUTHORS_JSON):
        return {}
    with open(AUTHORS_JSON, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# Static HTML rendering. These mirror the row-building helpers in index.html's
# JavaScript (esc / primaryLink / badge / authorsCell / rowHTML) so the rows
# baked into index.html are byte-for-byte the same markup the client JS would
# produce. This makes all 1167 papers (titles, authors, links) visible to
# search-engine crawlers WITHOUT JavaScript, while the JS still re-renders the
# same table for interactive search / filter / pagination.
# --------------------------------------------------------------------------- #

def esc(s):
    """HTML-escape mirroring the JS esc(): & < > and double quotes."""
    if s is None:
        s = ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def primary_link(p):
    links = p.get("links") or {}
    return links.get("detail") or links.get("openreview") or links.get("arxiv") or ""


def badge(cls, label):
    return '<span class="badge b-' + cls + '">' + esc(label) + "</span>"


def authors_cell(p):
    authors = p.get("authors") or []
    if not authors:
        authors = [p["author"]] if p.get("author") else []
    if not authors:
        return ""
    if len(authors) == 1:
        return esc(authors[0])
    collapsed = (
        esc(authors[0])
        + ' <span class="authors-meta">et al.</span> '
        + '<button class="authors-toggle" type="button" data-act="expand">('
        + str(len(authors))
        + ")</button>"
    )
    full = (
        '<span class="authors-full">'
        + esc(", ".join(authors))
        + "</span> "
        + '<button class="authors-toggle" type="button" data-act="collapse">(hide)</button>'
    )
    return (
        '<span class="authors-collapsed">' + collapsed + "</span>"
        + '<span class="authors-expanded" style="display:none;">' + full + "</span>"
    )


def row_html(p):
    """One table row.

    The title links to the paper's OWN page, not straight out to OpenReview.
    That is the whole point of the SEO work: 1162 internal destinations instead
    of one page whose every link leaves the site. The external source is still
    one click away via the small ↗ so the old shortcut is not lost, but it is
    rel="nofollow" — we do not want to hand our entire link equity to
    openreview.net 1162 times over.
    """
    title = ('<a href="paper/' + esc(p["slug"]) + '/">' + esc(p["title"]) + "</a>")
    link = primary_link(p)
    if link:
        title += (
            ' <a class="src-link" href="' + esc(link) + '" target="_blank"'
            ' rel="noopener nofollow" title="Open the original"'
            ' aria-label="Open the original">↗</a>'
        )
    venue = (
        badge(p["conference"], p["conference"])
        + badge(p["track"], p["track"])
        + '<span style="color:var(--muted);font-size:12px;">' + str(p["year"]) + "</span>"
    )
    return (
        "<tr>"
        + '<td class="col-id">' + str(p["id"]) + "</td>"
        + '<td class="col-title">' + title + "</td>"
        + '<td class="col-author">' + authors_cell(p) + "</td>"
        + '<td class="col-affil">' + esc(p["affiliation"]) + "</td>"
        + '<td class="col-badges">' + venue + "</td>"
        + "</tr>"
    )


DAILY_AUTHORS_SHOWN = 4


def daily_html(slugs):
    """The "paper of the day" hero, rendered from api/daily.json.

    Baked in at build time rather than fetched by the client. The daily cron
    regenerates daily.json and then re-runs this build in the SAME job, and both
    files land in one commit — so the date printed here cannot disagree with the
    feed the MCP server and the JSON API serve. A client-side fetch would only
    guard against a mismatch that the pipeline makes impossible, at the cost of
    hiding the day's paper from crawlers.

    Returns "" when api/daily.json is absent (a bare `python build.py` before
    build_api.py has ever run) so the build degrades instead of failing.
    """
    try:
        with open(DAILY_JSON, encoding="utf-8") as f:
            daily = json.load(f)
    except (OSError, ValueError):
        return ""

    p = daily.get("paper") or {}
    if not p.get("title"):
        return ""

    date = daily.get("date", "")
    slug = slugs.get(p.get("uid", ""))
    href = "paper/" + esc(slug) + "/" if slug else ""

    title = esc(p["title"])
    title_html = ('<a href="' + href + '">' + title + "</a>") if href else title

    meta = badge(p["conference"], p["conference"]) + badge(p["track"], p["track"])
    meta += "<span>" + esc(p.get("year", "")) + "</span>"
    if p.get("affiliation"):
        meta += '<span aria-hidden="true">·</span><span>' + esc(p["affiliation"]) + "</span>"

    authors = p.get("authors") or []
    shown = ", ".join(esc(a) for a in authors[:DAILY_AUTHORS_SHOWN])
    if len(authors) > DAILY_AUTHORS_SHOWN:
        shown += ' <span class="authors-meta">+%d more</span>' % (
            len(authors) - DAILY_AUTHORS_SHOWN)

    parts = [
        '\n<section class="daily" id="today">',
        '  <div class="daily-head">',
        '    <span class="daily-kicker">Paper of the day</span>',
        '    <time datetime="' + esc(date) + '">' + esc(date) + " · KST</time>",
        "  </div>",
        '  <h2 class="daily-title">' + title_html + "</h2>",
        '  <div class="daily-meta">' + meta + "</div>",
    ]
    if shown:
        parts.append('  <p class="daily-authors">' + shown + "</p>")
    if p.get("summary"):
        parts.append('  <p class="daily-summary">' + esc(p["summary"]) + "</p>")

    parts.append('  <div class="daily-actions">')
    if href:
        parts.append('    <a class="daily-cta" href="' + href + '">Read the summary →</a>')
    src = primary_link(p)
    if src:
        parts.append(
            '    <a class="daily-src" href="' + esc(src) + '" target="_blank"'
            ' rel="noopener nofollow">OpenReview ↗</a>'
        )
    parts.append("  </div>")
    parts.append(
        '  <p class="daily-foot">A new paper every day at 07:00 KST, picked by a'
        " reproducible rotation over all %d papers ·"
        ' <a href="#for-agents">read it from your own agent</a> ·'
        ' <a href="api/daily.json">daily.json</a></p>'
        % (daily.get("rotation", {}).get("cycle_length_days") or len(slugs))
    )
    parts.append("</section>\n")
    return "\n".join(parts)


def replace_marked(text, start_marker, end_marker, payload):
    """Replace whatever sits between start_marker and end_marker (inclusive of
    the markers, which are re-emitted) so the operation is idempotent."""
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )
    replacement = start_marker + payload + end_marker
    # Use a function as the replacement so backslashes / group refs in the
    # payload (e.g. inside titles or URLs) are inserted literally.
    new_text, n = pattern.subn(lambda _m: replacement, text)
    if n == 0:
        raise RuntimeError("markers not found: %s / %s" % (start_marker, end_marker))
    return new_text


def write_index_html(papers, slugs):
    """Inject the static <tbody> rows and the paper-of-the-day hero into
    index.html between their markers. Re-running is idempotent."""
    with open(INDEX_HTML, encoding="utf-8") as f:
        tmpl = f.read()
    rows = "\n" + "\n".join(row_html(p) for p in papers) + "\n"
    out = replace_marked(tmpl, "<!-- STATIC_ROWS_START -->", "<!-- STATIC_ROWS_END -->", rows)
    out = replace_marked(out, "<!-- DAILY_START -->", "<!-- DAILY_END -->", daily_html(slugs))
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(out)
    return out.count("<tr>")


def write_robots():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Sitemap: " + SITE_URL + "sitemap.xml\n"
    )
    with open(ROBOTS_TXT, "w", encoding="utf-8") as f:
        f.write(body)


def main():
    authors_map = load_authors_map()
    papers = []
    counts = {}
    enriched = 0
    for fname, conf, year, track in FILES:
        path = os.path.join(COLLECTIONS, fname)
        if fname == "icml-2026-oral.md":
            rows = parse_icml_oral(path)
        else:
            rows = parse_standard(path)

        for r in rows:
            mk = "%s|%d|%s|%d" % (conf, year, track, r["id"])
            full = authors_map.get(mk)
            if full:
                authors = full
                enriched += 1
            else:
                # fall back to the single first author (back-compat)
                authors = [r["author"]] if r["author"] else []
            papers.append({
                "id": r["id"],
                "uid": make_uid(conf, year, track, r["id"]),
                "conference": conf,
                "year": year,
                "track": track,
                "title": r["title"],
                "author": r["author"],
                "authors": authors,
                "affiliation": r["affiliation"],
                "links": r["links"],
                "summary": r["summary"],
            })

        key = "%s %d %s" % (conf, year, track)
        counts[key] = len(rows)

    # Every record learns where its page lives. Duplicate records resolve to
    # the same slug, so both of their table rows link to the one canonical page.
    slugs, unique = slug_map(papers)
    for p in papers:
        p["slug"] = slugs[p["uid"]]

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

    # Bake all rows into index.html as static HTML (SEO: crawlers see every
    # title/author/link with JS disabled). The client JS re-renders the same
    # markup for interactive search/filter/pagination.
    static_tr = write_index_html(papers, slugs)

    # SEO sidecar files. sitemap.xml is NOT written here: its <lastmod> is
    # per-page and derived from the generated files, which do not exist until
    # build_pages.py has run. build_sitemap.py closes the pipeline.
    write_robots()

    # Report
    total = len(papers)
    print("Wrote %s" % out_json)
    print("Wrote %s" % out_js)
    print("Wrote %s (static <tr> count incl. header: %d)" % (INDEX_HTML, static_tr))
    print("Wrote %s" % ROBOTS_TXT)
    print("Total papers: %d" % total)
    for k in sorted(counts):
        print("  %-22s %4d" % (k, counts[k]))
    multi = sum(1 for p in papers if len(p.get("authors") or []) > 1)
    print("Full-author records (from authors.json): %d" % enriched)
    print("Records with >1 author: %d" % multi)
    print("Unique paper pages: %d (%d duplicate records merged)"
          % (len(unique), len(papers) - len(unique)))
    missing = {p["slug"] for p in papers
               if not os.path.isdir(os.path.join(PAGES_DIR, p["slug"]))}
    if missing:
        print("NOTE: %d linked page(s) not built yet — run build_pages.py"
              % len(missing))

    expected = 224 + 168 + 9 + 77 + 689
    if total != expected:
        print("WARNING: total %d != expected %d" % (total, expected))
    else:
        print("OK: total matches expected %d" % expected)


if __name__ == "__main__":
    main()
