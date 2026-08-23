#!/usr/bin/env python3
"""
build_sitemap.py — write sitemap.xml with an honest per-page <lastmod>.

Runs LAST in the pipeline (build.py -> build_api.py -> build_pages.py -> here)
because it stats the generated files, which do not exist until build_pages.py
has run.

Why not just stamp today
-----------------------
The old sitemap carried a hardcoded 2026-06-01 on its single URL. The obvious
fix — stamp today on every build — is worse than it looks: it churns the file
daily and tells crawlers that 1168 pages changed when none did. A lastmod that
always says "just now" is a lastmod crawlers learn to discount.

So each URL gets the date its OWN file last changed, taken from git:
  * a file whose content differs from HEAD (or that git has never seen) is
    being modified by THIS build, so it gets today;
  * everything else keeps the date of the last commit that touched it.

That makes the first deploy stamp everything with today (correct — the pages
are new), and a later run that only adds one paper touches only the URLs that
actually moved.

No external dependencies (standard library only).
"""

import datetime
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SITEMAP_XML = os.path.join(HERE, "sitemap.xml")
SITE_URL = "https://dion-jy.github.io/spotlight-todai/"

# (path relative to repo root, url suffix, changefreq, priority)
ROOT_PAGE = ("index.html", "", "weekly", "1.0")
VENUE_FREQ = ("monthly", "0.8")
PAPER_FREQ = ("monthly", "0.6")


def git(*args):
    out = subprocess.run(["git"] + list(args), cwd=HERE,
                         capture_output=True, text=True, timeout=60)
    return out.stdout if out.returncode == 0 else ""


def kst_today():
    return (datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(hours=9)).date().isoformat()


def last_commit_dates():
    """{path: YYYY-MM-DD} — when git last committed a change to each path.

    One `git log` pass over the whole history rather than 1168 invocations.
    """
    raw = git("log", "--format=%x00%cs", "--name-only")
    dates, stamp = {}, None
    for line in raw.splitlines():
        if line.startswith("\0"):
            stamp = line[1:].strip()
        elif line.strip() and stamp:
            dates.setdefault(line.strip(), stamp)   # log is newest-first
    return dates


def dirty_paths():
    """Paths this build is changing: modified, added, or never tracked."""
    out = set()
    for line in git("status", "--porcelain", "--untracked-files=all").splitlines():
        path = line[3:].strip().strip('"')
        if path:
            out.add(path)
    return out


def collect():
    """[(relative path, url, changefreq, priority)] for every indexable page."""
    pages = [(ROOT_PAGE[0], SITE_URL, ROOT_PAGE[2], ROOT_PAGE[3])]
    for kind, (freq, prio) in (("venue", VENUE_FREQ), ("paper", PAPER_FREQ)):
        d = os.path.join(HERE, kind)
        if not os.path.isdir(d):
            continue
        for slug in sorted(os.listdir(d)):
            page = os.path.join(d, slug, "index.html")
            if os.path.isfile(page):
                pages.append(("%s/%s/index.html" % (kind, slug),
                              "%s%s/%s/" % (SITE_URL, kind, slug), freq, prio))
    return pages


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def main():
    pages = collect()
    dates = last_commit_dates()
    dirty = dirty_paths()
    today = kst_today()

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    fresh = 0
    for path, url, freq, prio in pages:
        if path in dirty or path not in dates:
            lastmod = today
            fresh += 1
        else:
            lastmod = dates[path]
        out.append("  <url>")
        out.append("    <loc>%s</loc>" % esc(url))
        out.append("    <lastmod>%s</lastmod>" % lastmod)
        out.append("    <changefreq>%s</changefreq>" % freq)
        out.append("    <priority>%s</priority>" % prio)
        out.append("  </url>")
    out.append("</urlset>")

    with open(SITEMAP_XML, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    print("Wrote %s" % SITEMAP_XML)
    print("  %d URLs (%d stamped today as changed, %d kept their commit date)"
          % (len(pages), fresh, len(pages) - fresh))
    if len(pages) > 50000:
        print("  WARNING: over the 50,000-URL single-sitemap limit")


if __name__ == "__main__":
    main()
