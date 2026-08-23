#!/usr/bin/env python3
"""
indexnow.py — notify IndexNow (Bing, Yandex, Naver, Seznam) about new/changed URLs.

Why bother when Google ignores IndexNow: ChatGPT and Perplexity lean on the
Bing index, so this is the cheapest path to getting the archive visible to AI
search. It also needs no account, unlike Google Search Console.

Protocol: host a key file at the site root containing the key, then POST the
changed URLs. See https://www.indexnow.org/documentation

SAFETY: this script does NOT send anything unless you pass --submit. Without
it you get a dry run that prints exactly what would go out.

Usage:
  python indexnow.py --write-key            # (re)create the key verification file
  python indexnow.py --all                  # dry run over every sitemap URL
  python indexnow.py --all --submit         # one-time seeding after the pages go live
  python indexnow.py --changed HEAD~1       # dry run over URLs touched since a ref
  python indexnow.py --changed HEAD~1 --submit
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITEMAP_XML = os.path.join(HERE, "sitemap.xml")

SITE_HOST = "dion-jy.github.io"
SITE_URL = "https://dion-jy.github.io/spotlight-todai/"
ENDPOINT = "https://api.indexnow.org/indexnow"

# IndexNow keys are public by design — the whole verification scheme is "serve
# this key at your site root", so there is nothing here to keep secret.
KEY = "279cb1edf8c5da77cbc73301b5690192"
KEY_LOCATION = SITE_URL + KEY + ".txt"

# IndexNow accepts at most 10,000 URLs per request.
BATCH = 10000


def write_key_file():
    path = os.path.join(HERE, KEY + ".txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(KEY + "\n")
    print("Wrote %s" % path)


def sitemap_urls():
    with open(SITEMAP_XML, encoding="utf-8") as f:
        return re.findall(r"<loc>([^<]+)</loc>", f.read())


def changed_urls(since):
    """URLs whose generated files changed since a git ref.

    Maps changed paths back to public URLs: paper/<slug>/index.html ->
    /paper/<slug>/, venue/<v>/index.html -> /venue/<v>/, and index.html -> /.
    """
    out = subprocess.run(["git", "diff", "--name-only", since, "--"],
                         cwd=HERE, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit("git diff failed: %s" % out.stderr.strip())
    urls = []
    for path in out.stdout.split():
        m = re.fullmatch(r"(paper|venue)/([^/]+)/index\.html", path)
        if m:
            urls.append("%s%s/%s/" % (SITE_URL, m.group(1), m.group(2)))
        elif path == "index.html":
            urls.append(SITE_URL)
    return sorted(set(urls))


def submit(urls, really):
    if not urls:
        print("Nothing to submit.")
        return 0
    for i in range(0, len(urls), BATCH):
        chunk = urls[i:i + BATCH]
        payload = {
            "host": SITE_HOST,
            "key": KEY,
            "keyLocation": KEY_LOCATION,
            "urlList": chunk,
        }
        if not really:
            print("DRY RUN — would POST %d URL(s) to %s" % (len(chunk), ENDPOINT))
            print("  keyLocation: %s" % KEY_LOCATION)
            for u in chunk[:5]:
                print("    %s" % u)
            if len(chunk) > 5:
                print("    ... and %d more" % (len(chunk) - 5))
            continue
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            print("POSTed %d URL(s) -> HTTP %d" % (len(chunk), resp.status))
    return len(urls)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-key", action="store_true",
                    help="create the <key>.txt verification file at the site root")
    ap.add_argument("--all", action="store_true", help="use every URL in sitemap.xml")
    ap.add_argument("--changed", metavar="GIT_REF",
                    help="use only URLs whose files changed since GIT_REF")
    ap.add_argument("--submit", action="store_true",
                    help="actually POST. Without this the script only prints.")
    args = ap.parse_args()

    if args.write_key:
        write_key_file()
        if not (args.all or args.changed):
            return

    if args.all:
        urls = sitemap_urls()
    elif args.changed:
        urls = changed_urls(args.changed)
    else:
        ap.error("pass --all or --changed GIT_REF (or --write-key)")

    print("%d URL(s) selected." % len(urls))
    submit(urls, args.submit)


if __name__ == "__main__":
    main()
