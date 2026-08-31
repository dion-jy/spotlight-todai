#!/usr/bin/env python3
"""
build_pages.py — Generate one static HTML page per paper under ./paper/.

No external dependencies (standard library only). Reads the already-built
static API (api/papers.json + api/topics.json) so this stage stays decoupled
from the markdown parsing in build.py.

Why this exists
---------------
The site used to be a SINGLE indexable URL: 1167 papers living in one table.
Search engines had exactly one page to rank, so every long-tail query (a paper
title, an author, a topic) had no landing page to match. This script mints a
crawlable page per paper and an internal link graph between them.

Output layout
-------------
  paper/<conf>-<year>-<title-slug>/index.html    one page per paper
  paper.css                                      shared stylesheet

Content policy
--------------
Pages are METADATA-first. We never reproduce a paper's full abstract: the only
prose is the short one-or-two-line TL;DR already carried in api/papers.json,
shown as an attributed excerpt with a link to the authoritative source
(OpenReview / arXiv / conference site). Everything else on the page is
bibliographic metadata we assembled ourselves.

Usage
-----
  python build_pages.py --pilot        # 8 hand-picked papers, for review
  python build_pages.py --limit 20     # first 20 papers in canonical order
  python build_pages.py                # all papers
  python build_pages.py --clean        # remove paper/ first
"""

import argparse
import json
import os
import re
import shutil

from slugs import paper_id, slug_map

HERE = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.path.join(HERE, "api")
PAPERS_JSON = os.path.join(API_DIR, "papers.json")
TOPICS_JSON = os.path.join(API_DIR, "topics.json")
PAGES_DIR = os.path.join(HERE, "paper")
VENUE_DIR = os.path.join(HERE, "venue")
CSS_PATH = os.path.join(HERE, "paper.css")

SITE_URL = "https://dion-jy.github.io/spotlight-todai"
SITE_NAME = "SpotlightTodAI"
OG_IMAGE = SITE_URL + "/og-image.png"

DESC_MAX = 158         # meta description budget (Google truncates near ~160)
RELATED_COUNT = 6      # internal links to sibling papers

# Papers used by --pilot. Chosen to cover every venue plus the awkward cases:
# a slug collision, a no-summary record, a non-ASCII title, a 10-author record.
PILOT_UIDS = [
    "iclr-2026-oral-1",             # long author list, has affiliation + summary
    "iclr-2026-oral-2",             # non-ASCII title (U+2011 non-breaking hyphen)
    "icml-2026-oral-1",             # ICML oral: no summary, no affiliation, detail link only
    "icml-2026-spotlight-2",        # the smallest venue (9 papers)
    "neurips-2025-oral-1",          # NeurIPS oral
    "neurips-2025-spotlight-163",   # today's "paper of the day"
    "neurips-2025-spotlight-223",   # short author list, no affiliation
    "icml-2026-oral-26",            # merged duplicate: absorbs icml-2026-spotlight-1
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def esc(s):
    """HTML-escape. Mirrors esc() in build.py / index.html."""
    if s is None:
        s = ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )






def authors_text(p, limit=None):
    """'A, B, C' — optionally truncated to 'A, B, C et al.'."""
    a = p.get("authors") or []
    if limit and len(a) > limit:
        return ", ".join(a[:limit]) + " et al."
    return ", ".join(a)


def first_author(p):
    a = p.get("authors") or []
    return a[0] if a else ""


def venue_label(p):
    """'NeurIPS 2025 Spotlight'."""
    return "%s %s %s" % (p["conference"], p["year"], p["track"])


def clamp(text, budget):
    """Trim to <= budget chars on a word boundary, adding an ellipsis."""
    text = " ".join(text.split())
    if len(text) <= budget:
        return text
    cut = text[: budget - 1]
    if " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(" ,.;:-") + "…"


def meta_description(p):
    """Unique, metadata-first description for every paper.

    The title already owns the <title> tag and the <h1>, so spending the 158
    characters on it again would leave no room for anything distinctive. We
    lead with the compact bibliographic stamp (venue, track, first authors) and
    give the rest of the budget to the TL;DR. The 168 records with no TL;DR
    fall back to a title-led sentence, since metadata is all they have.
    """
    summary = " ".join((p.get("summary") or "").split())
    if summary:
        head = venue_label(p)
        who = authors_text(p, limit=2)
        if who:
            head += " · " + who
        return clamp(head + " — " + summary, DESC_MAX)
    head = "%s — %s paper at %s %s" % (p["title"], p["track"], p["conference"], p["year"])
    who = authors_text(p, limit=3)
    if who:
        head += " by %s" % who
    if p.get("affiliation"):
        head += " (%s)" % p["affiliation"]
    if not head.endswith("."):            # authors_text may already end "et al."
        head += "."
    return clamp(head, DESC_MAX)


def excerpt(summary):
    """The stored TL;DR is a hard-truncated first sentence, so it usually stops
    mid-thought. Close it with an ellipsis unless it already ends cleanly."""
    t = " ".join((summary or "").split())
    if t and t[-1] not in ".!?…\u201d\")":
        t += "…"
    return t


def keywords(p, topics_by_uid):
    """meta keywords: venue facets + up to 6 matched topics."""
    kw = [p["conference"], "%s %s" % (p["conference"], p["year"]),
          "%s paper" % p["track"], "AI research paper"]
    kw += topics_by_uid.get(p["uid"], [])[:6]
    seen, out = set(), []
    for k in kw:
        if k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return ", ".join(out)


def load_topics():
    """(topic -> [uid], uid -> [topic]) from the curated inverted index."""
    with open(TOPICS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    by_uid = {}
    for entry in data["topics"]:
        for uid in entry["paper_uids"]:
            by_uid.setdefault(uid, []).append(entry["topic"])
    # longest topic first: 'large language model' is more informative than 'llm'
    for uid in by_uid:
        by_uid[uid].sort(key=lambda t: (-len(t), t))
    return by_uid


def related(p, papers, topics_by_uid, index):
    """Pick sibling papers to link to, building the internal crawl graph.

    Ranked by shared curated topics, then by same venue, then by uid order for
    determinism. Papers with no topics (mostly the un-enriched ICML orals) fall
    back to their nearest neighbours inside the same venue, so EVERY page still
    links out to real siblings and no page becomes a crawl dead end.
    """
    mine = set(topics_by_uid.get(p["uid"], []))
    scored = []
    for q in papers:
        if q["uid"] == p["uid"]:
            continue
        shared = len(mine & set(topics_by_uid.get(q["uid"], [])))
        if not shared:
            continue
        same_venue = 1 if (q["conference"] == p["conference"] and q["year"] == p["year"]) else 0
        scored.append((-shared, -same_venue, index[q["uid"]], q))
    scored.sort(key=lambda t: t[:3])
    out = [t[3] for t in scored[:RELATED_COUNT]]
    if len(out) < RELATED_COUNT:
        seen = {p["uid"]} | {q["uid"] for q in out}
        siblings = [q for q in papers
                    if q["uid"] not in seen
                    and q["conference"] == p["conference"]
                    and q["year"] == p["year"]
                    and q["track"] == p["track"]]
        siblings.sort(key=lambda q: (abs(paper_id(q) - paper_id(p)), index[q["uid"]]))
        out += siblings[: RELATED_COUNT - len(out)]
    return out


def source_links(p):
    """[(label, url)] for the authoritative sources, best first."""
    links = p.get("links") or {}
    out = []
    if links.get("openreview"):
        out.append(("OpenReview", links["openreview"]))
    if links.get("arxiv"):
        out.append(("arXiv", links["arxiv"]))
    if links.get("detail"):
        out.append(("%s site" % p["conference"], links["detail"]))
    return out


def icon_links(depth):
    """Favicon declarations for a generated page.

    Without these the browser falls back to /favicon.ico at the HOST root, and
    dion-jy.github.io is a single origin shared with the owner's personal
    homepage — so every page here inherited that site's portrait icon. Google
    shows favicons in mobile search results, so this is a search-appearance
    bug, not just a cosmetic one.
    """
    up = "../" * depth
    return (
        '<link rel="icon" href="%sfavicon.ico" sizes="48x48">\n'
        '<link rel="icon" href="%sfavicon.svg" type="image/svg+xml">\n'
        '<link rel="apple-touch-icon" href="%sapple-touch-icon.png">'
        % (up, up, up)
    )


def site_footer(depth):
    """Shared footer for every generated page.

    These pages are the ones search traffic actually lands on, so the JSON
    API / MCP pitch and the support link belong here too — not only on the
    home page. `depth` is how many levels up the site root is.
    """
    up = "../" * depth
    return (
        '<footer class="site-footer">'
        '<a href="%s">SpotlightTodAI</a> · '
        '<a href="%s#for-agents">JSON API + MCP for agents</a> · '
        '<a href="https://github.com/dion-jy/spotlight-todai" target="_blank" rel="noopener">GitHub</a> · '
        '☕ <a href="https://paypal.me/JunyeobBaek" target="_blank" rel="noopener">Buy me a coffee</a>'
        "</footer>" % (up, up)
    )


def venue_slug(p):
    """'neurips-2025-spotlight' — the hub URL for a paper's venue."""
    return "%s-%s-%s" % (p["conference"].lower(), p["year"], p["track"].lower())


def group_by_venue(papers):
    """ordered {venue_slug: [papers]}, biggest venue first.

    The hubs are what turn a flat pile of 1162 pages into a crawlable tree:
    home -> 5 hubs -> every paper. Without them 188 papers had no inbound link
    from anywhere except the one giant index table.
    """
    groups = {}
    for p in papers:
        groups.setdefault(venue_slug(p), []).append(p)
    return dict(sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])))


# --------------------------------------------------------------------------- #
# JSON-LD
# --------------------------------------------------------------------------- #

def jsonld(p, url, topics, srcs):
    """ScholarlyArticle + BreadcrumbList, emitted as one @graph."""
    article = {
        "@type": "ScholarlyArticle",
        "@id": url + "#article",
        "headline": p["title"],
        "name": p["title"],
        "url": url,
        "inLanguage": "en",
        "datePublished": str(p["year"]),
        "isAccessibleForFree": True,
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL + "/"},
        "isPartOf": {
            "@type": "PublicationEvent",
            "name": "%s %s" % (p["conference"], p["year"]),
            "startDate": str(p["year"]),
        },
        "creativeWorkStatus": "Published",
        "additionalType": "%s presentation" % p["track"],
    }
    authors = p.get("authors") or []
    if authors:
        article["author"] = [{"@type": "Person", "name": a} for a in authors]
    if p.get("affiliation") and authors:
        article["author"][0]["affiliation"] = {
            "@type": "Organization", "name": p["affiliation"]
        }
    if p.get("summary"):
        # NOT "abstract": this is a one-line excerpt, not the full abstract.
        article["description"] = excerpt(p["summary"])
    if topics:
        article["keywords"] = topics
    if srcs:
        article["sameAs"] = [u for _label, u in srcs]

    crumbs = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": venue_label(p),
             "item": "%s/venue/%s/" % (SITE_URL, venue_slug(p))},
            {"@type": "ListItem", "position": 3, "name": p["title"], "item": url},
        ],
    }
    graph = {"@context": "https://schema.org", "@graph": [article, crumbs]}
    # '<' cannot appear raw inside a <script> block; titles do contain it.
    return json.dumps(graph, ensure_ascii=False, indent=1).replace("<", "\\u003c")


# --------------------------------------------------------------------------- #
# page rendering
# --------------------------------------------------------------------------- #

def render_page(p, slugs, papers, topics_by_uid, index):
    slug = slugs[p["uid"]]
    url = "%s/paper/%s/" % (SITE_URL, slug)
    desc = meta_description(p)
    topics = topics_by_uid.get(p["uid"], [])
    srcs = source_links(p)
    rels = related(p, papers, topics_by_uid, index)
    venue = venue_label(p)
    authors = p.get("authors") or []
    # og:title: clamp the TITLE and then append the venue, so the venue suffix
    # is never the thing that gets cut off mid-word in a link preview.
    og_title = "%s | %s" % (clamp(p["title"], 95 - len(venue) - 3), venue)

    h = []
    h.append("<!DOCTYPE html>")
    h.append('<html lang="en">')
    h.append("<head>")
    h.append('<meta charset="utf-8">')
    h.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    h.append("<title>%s — %s | %s</title>" % (esc(p["title"]), esc(venue), SITE_NAME))
    h.append('<meta name="description" content="%s">' % esc(desc))
    h.append('<meta name="keywords" content="%s">' % esc(keywords(p, topics_by_uid)))
    h.append('<meta name="robots" content="index, follow">')
    h.append('<link rel="canonical" href="%s">' % esc(url))
    h.append('<meta property="og:type" content="article">')
    h.append('<meta property="og:title" content="%s">' % esc(og_title))
    h.append('<meta property="og:description" content="%s">' % esc(desc))
    h.append('<meta property="og:url" content="%s">' % esc(url))
    h.append('<meta property="og:site_name" content="%s">' % SITE_NAME)
    h.append('<meta property="og:image" content="%s">' % OG_IMAGE)
    h.append('<meta property="og:image:width" content="1200">')
    h.append('<meta property="og:image:height" content="630">')
    h.append('<meta name="twitter:card" content="summary_large_image">')
    h.append('<meta name="twitter:title" content="%s">' % esc(og_title))
    h.append('<meta name="twitter:description" content="%s">' % esc(clamp(desc, 200)))
    h.append('<meta name="twitter:image" content="%s">' % OG_IMAGE)
    # Deliberately NO citation_* meta: Google Scholar expects those on the site
    # that hosts the full text, and we only link out to it. See the P17 log.
    h.append(icon_links(2))
    h.append('<link rel="stylesheet" href="../../paper.css">')
    h.append('<script type="application/ld+json">')
    h.append(jsonld(p, url, topics, srcs))
    h.append("</script>")
    h.append("</head>")
    h.append("<body>")
    h.append('<div class="wrap">')

    h.append('<nav class="crumbs" aria-label="Breadcrumb">'
             '<a href="../../">%s</a> <span>›</span> '
             '<a href="../../venue/%s/">%s</a>'
             "</nav>" % (SITE_NAME, esc(venue_slug(p)), esc(venue)))

    h.append("<article>")
    h.append("<h1>%s</h1>" % esc(p["title"]))

    h.append('<p class="badges">'
             '<span class="badge b-%s">%s</span>'
             '<span class="badge b-%s">%s</span>'
             '<span class="year">%s</span>'
             "</p>" % (esc(p["conference"]), esc(p["conference"]),
                       esc(p["track"]), esc(p["track"]), p["year"]))

    h.append('<dl class="meta">')
    if authors:
        h.append("<dt>Authors</dt><dd>%s</dd>" % esc(", ".join(authors)))
    if p.get("affiliation"):
        h.append("<dt>Affiliation</dt><dd>%s</dd>" % esc(p["affiliation"]))
    h.append("<dt>Venue</dt><dd>%s %s</dd>" % (esc(p["conference"]), p["year"]))
    h.append("<dt>Track</dt><dd>%s</dd>" % esc(p["track"]))
    h.append("</dl>")

    if p.get("summary"):
        cite = srcs[0][1] if srcs else ""
        attrib = (' <a href="%s" target="_blank" rel="noopener nofollow">source</a>'
                  % esc(cite)) if cite else ""
        h.append('<section class="tldr"><h2>TL;DR</h2>'
                 "<blockquote><p>%s</p></blockquote>"
                 '<p class="attrib">Opening excerpt from the authors’ abstract.%s</p>'
                 "</section>" % (esc(excerpt(p["summary"])), attrib))
    else:
        h.append('<section class="tldr"><h2>TL;DR</h2>'
                 "<p class=\"attrib\">No summary has been collected for this paper yet. "
                 "Read the abstract at the authoritative source below.</p></section>")

    if srcs:
        h.append('<section class="sources"><h2>Read the paper</h2><ul>')
        for label, u in srcs:
            h.append('<li><a href="%s" target="_blank" rel="noopener nofollow">%s</a></li>'
                     % (esc(u), esc(label)))
        h.append("</ul></section>")

    if topics:
        h.append('<section class="topics"><h2>Topics</h2><p class="chips">')
        for t in topics[:10]:
            h.append('<span class="chip">%s</span>' % esc(t))
        h.append("</p></section>")

    if rels:
        h.append('<section class="related"><h2>Related %s papers</h2><ul>' % esc(p["conference"]))
        for q in rels:
            h.append('<li><a href="../%s/">%s</a> '
                     '<span class="rel-venue">%s</span></li>'
                     % (esc(slugs[q["uid"]]), esc(q["title"]), esc(venue_label(q))))
        h.append("</ul></section>")

    h.append('<p class="back"><a href="../../venue/%s/">← All %s papers</a> · '
             '<a href="../../">Browse the whole archive</a></p>'
             % (esc(venue_slug(p)), esc(venue)))
    h.append("</article>")
    h.append(site_footer(2))
    h.append("</div>")
    h.append("</body>")
    h.append("</html>")
    return "\n".join(h) + "\n"


def render_venue_page(vslug, group, all_groups, slugs):
    """One hub per <conference>-<year>-<track>, listing every paper in it.

    This is the page that can actually rank for a head-ish query like
    "NeurIPS 2025 spotlight papers", and it is the crawl hub that gives every
    paper page an inbound link that is two clicks from the site root.
    """
    p0 = group[0]
    venue = venue_label(p0)
    n = len(group)
    url = "%s/venue/%s/" % (SITE_URL, vslug)
    title = "%s Papers — all %d | %s" % (venue, n, SITE_NAME)
    desc = clamp(
        "Complete list of all %d %s papers accepted as %s at %s %s — titles, "
        "authors, affiliations and links to every paper."
        % (n, p0["conference"], p0["track"], p0["conference"], p0["year"]),
        DESC_MAX)

    listing = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CollectionPage",
                "@id": url + "#page",
                "name": "%s Papers" % venue,
                "description": desc,
                "url": url,
                "inLanguage": "en",
                "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": SITE_URL + "/"},
                "mainEntity": {
                    "@type": "ItemList",
                    "numberOfItems": n,
                    "itemListElement": [
                        {"@type": "ListItem", "position": i + 1, "name": q["title"],
                         "url": "%s/paper/%s/" % (SITE_URL, slugs[q["uid"]])}
                        for i, q in enumerate(group)
                    ],
                },
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": SITE_NAME,
                     "item": SITE_URL + "/"},
                    {"@type": "ListItem", "position": 2, "name": venue, "item": url},
                ],
            },
        ],
    }

    h = []
    h.append("<!DOCTYPE html>")
    h.append('<html lang="en">')
    h.append("<head>")
    h.append('<meta charset="utf-8">')
    h.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    h.append("<title>%s</title>" % esc(title))
    h.append('<meta name="description" content="%s">' % esc(desc))
    h.append('<meta name="keywords" content="%s">' % esc(
        ", ".join(["%s %s" % (p0["conference"], p0["year"]),
                   "%s %s papers" % (p0["conference"], p0["track"]),
                   "%s %s %s" % (p0["conference"], p0["year"], p0["track"]),
                   "AI conference papers", "machine learning papers"])))
    h.append('<meta name="robots" content="index, follow">')
    h.append('<link rel="canonical" href="%s">' % esc(url))
    h.append('<meta property="og:type" content="website">')
    h.append('<meta property="og:title" content="%s">' % esc("%s Papers — all %d" % (venue, n)))
    h.append('<meta property="og:description" content="%s">' % esc(desc))
    h.append('<meta property="og:url" content="%s">' % esc(url))
    h.append('<meta property="og:site_name" content="%s">' % SITE_NAME)
    h.append('<meta property="og:image" content="%s">' % OG_IMAGE)
    h.append('<meta property="og:image:width" content="1200">')
    h.append('<meta property="og:image:height" content="630">')
    h.append('<meta name="twitter:card" content="summary_large_image">')
    h.append('<meta name="twitter:title" content="%s">' % esc("%s Papers — all %d" % (venue, n)))
    h.append('<meta name="twitter:description" content="%s">' % esc(desc))
    h.append('<meta name="twitter:image" content="%s">' % OG_IMAGE)
    h.append(icon_links(2))
    h.append('<link rel="stylesheet" href="../../paper.css">')
    h.append('<script type="application/ld+json">')
    h.append(json.dumps(listing, ensure_ascii=False, indent=1).replace("<", "\\u003c"))
    h.append("</script>")
    h.append("</head>")
    h.append("<body>")
    h.append('<div class="wrap wide">')
    h.append('<nav class="crumbs" aria-label="Breadcrumb">'
             '<a href="../../">%s</a> <span>›</span> <span>%s</span></nav>'
             % (SITE_NAME, esc(venue)))
    h.append("<h1>%s Papers</h1>" % esc(venue))
    h.append('<p class="badges"><span class="badge b-%s">%s</span>'
             '<span class="badge b-%s">%s</span><span class="year">%s</span></p>'
             % (esc(p0["conference"]), esc(p0["conference"]),
                esc(p0["track"]), esc(p0["track"]), p0["year"]))
    h.append('<p class="lede">All <b>%d</b> papers accepted as <b>%s</b> at '
             "%s %s — the top slice of the accepted programme. "
             'Every title links to its own page with authors, affiliation and sources.</p>'
             % (n, esc(p0["track"]), esc(p0["conference"]), p0["year"]))

    h.append('<nav class="venue-nav"><h2>Other venues</h2><p class="chips">')
    for other, g in all_groups.items():
        if other == vslug:
            continue
        h.append('<a class="chip" href="../%s/">%s <span class="n">%d</span></a>'
                 % (esc(other), esc(venue_label(g[0])), len(g)))
    h.append('</p></nav>')

    h.append('<h2 id="list">All %d papers</h2>' % n)
    h.append('<ol class="venue-list">')
    for q in group:
        authors = authors_text(q, limit=3)
        extra = []
        if authors:
            extra.append(esc(authors))
        if q.get("affiliation"):
            extra.append(esc(q["affiliation"]))
        h.append('<li><a href="../../paper/%s/">%s</a>%s</li>'
                 % (esc(slugs[q["uid"]]), esc(q["title"]),
                    ('<span class="who">%s</span>' % " · ".join(extra)) if extra else ""))
    h.append("</ol>")
    h.append('<p class="back"><a href="../../">← Browse the whole archive</a></p>')
    h.append(site_footer(2))
    h.append("</div>")
    h.append("</body>")
    h.append("</html>")
    return "\n".join(h) + "\n"


CSS = """/* paper.css — shared by every /paper/<slug>/ page.
   Palette and type scale mirror index.html so the detail pages do not read as
   a different site. Kept dependency-free and small (one cacheable request). */
:root {
  --bg: #f7f8fa; --panel: #ffffff; --text: #1a1d21; --muted: #5b6471;
  --border: #e3e6ea; --accent: #4f46e5;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --ICML: #2563eb; --ICML-bg: #e7efff;
  --ICLR: #0891b2; --ICLR-bg: #e0f5fa;
  --NeurIPS: #7c3aed; --NeurIPS-bg: #efe7fd;
  --Oral: #dc2626; --Oral-bg: #fde7e7;
  --Spotlight: #d97706; --Spotlight-bg: #fdf0db;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e1116; --panel: #171b22; --text: #e6e9ef; --muted: #9aa4b2;
    --border: #2a2f3a; --accent: #818cf8;
    --shadow: 0 1px 3px rgba(0,0,0,0.4);
    --ICML: #93c0ff; --ICML-bg: #16263f;
    --ICLR: #67d7ec; --ICLR-bg: #0e2f38;
    --NeurIPS: #c4a8fb; --NeurIPS-bg: #2a1f44;
    --Oral: #fb8888; --Oral-bg: #3a1c1c;
    --Spotlight: #f3b65a; --Spotlight-bg: #3a2b10;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text); line-height: 1.55;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.wrap { max-width: 760px; margin: 0 auto; padding: 24px 18px 72px; }
.crumbs { font-size: 13px; color: var(--muted); margin-bottom: 18px; }
.crumbs span { margin: 0 6px; }
h1 { font-size: 27px; line-height: 1.25; letter-spacing: -0.4px; margin: 0 0 12px; }
h2 { font-size: 15px; text-transform: uppercase; letter-spacing: 0.6px;
     color: var(--muted); margin: 30px 0 10px; }
.badges { margin: 0 0 20px; }
.badge { display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 9px;
         border-radius: 999px; margin-right: 6px; }
.year { color: var(--muted); font-size: 13px; }
.b-ICML { color: var(--ICML); background: var(--ICML-bg); }
.b-ICLR { color: var(--ICLR); background: var(--ICLR-bg); }
.b-NeurIPS { color: var(--NeurIPS); background: var(--NeurIPS-bg); }
.b-Oral { color: var(--Oral); background: var(--Oral-bg); }
.b-Spotlight { color: var(--Spotlight); background: var(--Spotlight-bg); }
dl.meta { display: grid; grid-template-columns: 116px 1fr; gap: 8px 16px;
          margin: 0; padding: 16px 18px; background: var(--panel);
          border: 1px solid var(--border); border-radius: 10px;
          box-shadow: var(--shadow); font-size: 14px; }
dl.meta dt { color: var(--muted); font-size: 13px; }
dl.meta dd { margin: 0; }
blockquote { margin: 0; padding: 2px 0 2px 14px; border-left: 3px solid var(--border);
             color: var(--text); font-size: 15px; }
blockquote p { margin: 0; }
.attrib { color: var(--muted); font-size: 12.5px; margin: 8px 0 0; }
.sources ul, .related ul { list-style: none; padding: 0; margin: 0; }
.sources li { margin: 0 0 6px; }
.related li { padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 14.5px; }
.related li:last-child { border-bottom: 0; }
.rel-venue { color: var(--muted); font-size: 12px; white-space: nowrap; }
.chips { margin: 0; }
.chip { display: inline-block; font-size: 12px; color: var(--muted);
        border: 1px solid var(--border); background: var(--panel);
        border-radius: 999px; padding: 2px 10px; margin: 0 6px 6px 0; }
.back { margin-top: 36px; font-size: 14px; }
.wrap.wide { max-width: 900px; }
.lede { color: var(--muted); font-size: 15px; margin: 0 0 4px; }
.lede b { color: var(--text); }
.venue-nav h2 { margin-bottom: 8px; }
a.chip { color: var(--muted); }
a.chip:hover { color: var(--accent); border-color: var(--accent); text-decoration: none; }
a.chip .n { opacity: .6; margin-left: 4px; }
ol.venue-list { padding-left: 28px; margin: 0; }
ol.venue-list li { padding: 7px 0; border-bottom: 1px solid var(--border); font-size: 14.5px; }
ol.venue-list li:last-child { border-bottom: 0; }
ol.venue-list li::marker { color: var(--muted); font-size: 12px; }
.who { display: block; color: var(--muted); font-size: 12.5px; margin-top: 2px; }
.site-footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border);
               color: var(--muted); font-size: 12px; text-align: center; }
.site-footer a { color: var(--muted); }
.site-footer a:hover { color: var(--accent); }
@media (max-width: 560px) {
  h1 { font-size: 23px; }
  dl.meta { grid-template-columns: 1fr; gap: 2px 0; }
  dl.meta dd { margin-bottom: 8px; }
}
"""


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true",
                    help="build only the %d hand-picked pilot papers" % len(PILOT_UIDS))
    ap.add_argument("--limit", type=int, default=0,
                    help="build only the first N papers in canonical order")
    ap.add_argument("--clean", action="store_true",
                    help="delete paper/ and venue/ before building")
    args = ap.parse_args()

    with open(PAPERS_JSON, encoding="utf-8") as f:
        papers = json.load(f)["papers"]

    topics_by_uid = load_topics()
    raw_count = len(papers)
    # Slugs come from the shared module so build.py's table links and these
    # pages can never drift apart. They are ALWAYS assigned over the full
    # archive, never the --pilot subset, so a pilot build produces exactly the
    # URLs the full build will.
    slugs, papers = slug_map(papers)
    index = {p["uid"]: i for i, p in enumerate(papers)}

    if args.pilot:
        by_uid = {p["uid"]: p for p in papers}
        missing = [u for u in PILOT_UIDS if u not in by_uid]
        if missing:
            raise SystemExit("FATAL: pilot uids not in archive: %s" % missing)
        selected = [by_uid[u] for u in PILOT_UIDS]
    elif args.limit:
        selected = papers[: args.limit]
    else:
        selected = papers

    if args.clean:
        for d in (PAGES_DIR, VENUE_DIR):
            if os.path.isdir(d):
                shutil.rmtree(d)

    with open(CSS_PATH, "w", encoding="utf-8") as f:
        f.write(CSS)

    os.makedirs(PAGES_DIR, exist_ok=True)
    for p in selected:
        d = os.path.join(PAGES_DIR, slugs[p["uid"]])
        os.makedirs(d, exist_ok=True)
        html = render_page(p, slugs, papers, topics_by_uid, index)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

    # Venue hubs always cover the WHOLE archive even on a pilot build: they are
    # only 5 pages and a hub that silently listed 8 papers would be a lie.
    groups = group_by_venue(papers)
    os.makedirs(VENUE_DIR, exist_ok=True)
    for vslug, group in groups.items():
        d = os.path.join(VENUE_DIR, vslug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(render_venue_page(vslug, group, groups, slugs))

    print("Wrote %s" % CSS_PATH)
    print("Wrote %d paper page(s) under %s" % (len(selected), PAGES_DIR))
    print("Wrote %d venue hub(s) under %s" % (len(groups), VENUE_DIR))
    print("Archive records: %d -> %d unique papers (%d duplicate records merged)"
          % (raw_count, len(papers), raw_count - len(papers)))
    dup = len(papers) - len({slugs[p["uid"]] for p in papers})
    print("Slug uniqueness: %d/%d (%d collisions unresolved)"
          % (len({slugs[p["uid"]] for p in papers}), len(papers), dup))
    for vslug, group in groups.items():
        print("  /venue/%s/  (%d papers)" % (vslug, len(group)))
    for p in selected:
        print("  /paper/%s/" % slugs[p["uid"]])


if __name__ == "__main__":
    main()
