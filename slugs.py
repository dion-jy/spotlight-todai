#!/usr/bin/env python3
"""
slugs.py — the single source of truth for paper page URLs.

Both build.py (which bakes the main table into index.html and writes the
sitemap) and build_pages.py (which renders the pages themselves) must agree
byte-for-byte on every slug, or the internal link graph breaks the moment a
title changes. Rather than duplicate the rules, both import them from here.

The public entry point is slug_map(): give it the paper records and it returns
{uid: slug} covering EVERY uid, including the ones merged away as duplicates,
so a caller can always look up where a record should link.

No external dependencies (standard library only).
"""

import re
import unicodedata

SLUG_MAX = 60          # characters of title kept in the URL slug


def make_uid(conference, year, track, pid):
    """The stable global id minted by build_api.py: '<conf>-<year>-<track>-<id>'."""
    return "%s-%s-%s-%s" % (str(conference).lower(), year, str(track).lower(), pid)


def canonical_order(papers):
    """The archive's canonical order, matching build_api.py's sort.

    Slug assignment and duplicate resolution both depend on which record comes
    FIRST, so every caller has to sort identically before asking for slugs —
    otherwise build.py and build_pages.py could disagree about which of two
    duplicates owns the bare slug.
    """
    return sorted(papers, key=lambda p: (p["conference"], p["year"], p["track"],
                                         paper_id(p)))


def slug_map(papers):
    """{uid: slug} for every record, duplicates aliased onto their survivor.

    Returns (slugs, unique_papers) — unique_papers is the deduplicated archive
    in canonical order, which is exactly the set of pages that get generated.
    """
    ordered = canonical_order(papers)
    unique, alias = dedupe(ordered)
    slugs = assign_slugs(unique)
    for uid, keep in alias.items():
        slugs.setdefault(uid, slugs[keep])
    return slugs, unique



def slugify(title):
    """ASCII, lowercase, hyphen-joined slug, truncated on a word boundary.

    Titles carry typographic characters (curly quotes, U+2011 non-breaking
    hyphens, accented names), so we fold to ASCII first; anything that folds to
    nothing (e.g. a CJK-only title) falls back to 'paper'.
    """
    t = unicodedata.normalize("NFKD", title)
    t = "".join(c for c in t if not unicodedata.combining(c))
    # Typographic dashes and spaces must become separators, not vanish: dropping
    # a U+2011 would fuse "Multi-Step" into "multistep".
    t = "".join("-" if unicodedata.category(c) in ("Pd", "Zs") else c for c in t)
    t = t.encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    if len(t) > SLUG_MAX:
        cut = t[: SLUG_MAX + 1]
        if "-" in cut:
            cut = cut[: cut.rindex("-")]
        t = cut.strip("-")
    return t or "paper"


def dedupe(papers):
    """Collapse records that describe the SAME paper into one page.

    The archive carries 5 genuine duplicates: 2 NeurIPS papers scraped twice
    under different OpenReview forum ids, and 3 ICML papers that appear in both
    the oral and the spotlight source file. Left alone they would produce pairs
    of pages with an identical <title>, description and h1 — the duplicate
    content problem this whole task exists to avoid.

    The FIRST record in canonical order wins the URL; the other one's non-empty
    fields are merged in (so the surviving page is strictly richer) and its uid
    is aliased to the survivor, which keeps BOTH index.html rows pointing at
    the one canonical page.

    Returns (unique_papers, alias) where alias maps every uid — including the
    survivors' own — to the surviving uid.
    """
    key_of = lambda p: (p["conference"], p["year"], slugify(p["title"]))
    unique, first, alias = [], {}, {}
    for p in papers:
        k = key_of(p)
        if k not in first:
            merged = dict(p)
            merged["links"] = dict(p.get("links") or {})
            merged["duplicate_uids"] = []
            first[k] = merged
            unique.append(merged)
            alias[p["uid"]] = p["uid"]
            continue
        keep = first[k]
        alias[p["uid"]] = keep["uid"]
        keep["duplicate_uids"].append(p["uid"])
        for f in ("affiliation", "summary"):
            if not keep.get(f) and p.get(f):
                keep[f] = p[f]
        for f in ("openreview", "arxiv", "detail"):
            if not keep["links"].get(f) and (p.get("links") or {}).get(f):
                keep["links"][f] = p["links"][f]
        if len(p.get("authors") or []) > len(keep.get("authors") or []):
            keep["authors"] = p["authors"]
    return unique, alias


def assign_slugs(papers):
    """uid -> URL slug, resolving collisions deterministically.

    Base slug is '<conf>-<year>-<title-slug>'. Two papers can collide (the
    archive has 5 duplicate titles). The FIRST paper in canonical uid order
    keeps the bare slug and later ones get '-<track>-<id>' appended, so adding
    a third duplicate later never rewrites an already-published URL.
    """
    slugs = {}
    taken = set()
    for p in papers:
        base = "%s-%s-%s" % (p["conference"].lower(), p["year"], slugify(p["title"]))
        s = base
        if s in taken:
            s = "%s-%s-%d" % (base, p["track"].lower(), paper_id(p))
            n = 2
            while s in taken:                      # pathological; kept for safety
                s = "%s-%s-%d-%d" % (base, p["track"].lower(), paper_id(p), n)
                n += 1
        taken.add(s)
        slugs[p["uid"]] = s
    return slugs


def paper_id(p):
    """Trailing numeric id out of the uid ('neurips-2025-spotlight-163' -> 163).

    Falls back to the raw `id` field so records straight out of build.py, which
    have not been through build_api.py's uid minting, work here too.
    """
    if p.get("uid"):
        m = re.search(r"-(\d+)$", p["uid"])
        if m:
            return int(m.group(1))
    return int(p.get("id") or 0)
