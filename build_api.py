#!/usr/bin/env python3
"""
build_api.py — Generate the static JSON API under api/ from data.json.

No external dependencies (standard library only). This is the "agent-facing"
layer on top of the human website: a small, stable, self-describing set of
JSON files that agents (or any HTTP client) can read directly off GitHub Pages.

Outputs (all under ./api/):
  papers.json   full paper archive with a stabilized schema (schema_version 1)
  venues.json   conference / year / track catalogue with counts
  topics.json   curated keyword -> paper-uid inverted index
  daily.json    "paper of the day" + candidates, chosen deterministically from
                the date (KST) so the pick is reproducible and rotates without
                repeating until the whole archive has been shown.

Design notes:
  * Everything is DETERMINISTIC. papers/venues/topics contain NO build
    timestamp, so re-running on unchanged data produces byte-identical files
    (no git churn). Only daily.json carries a date, and it is the only file the
    daily cron is expected to change.
  * The source data.json `id` field is only unique *within* a source file, so
    we mint a stable global `uid` = "<conf>-<year>-<track>-<id>" (lowercased),
    which is verified unique across the archive.

Usage:
  python build_api.py                # rebuild everything (daily uses today, KST)
  python build_api.py --daily-only   # only regenerate api/daily.json
  python build_api.py --date 2026-07-14   # force a specific KST date for daily
"""

import argparse
import datetime
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_JSON = os.path.join(HERE, "data.json")
API_DIR = os.path.join(HERE, "api")

SCHEMA_VERSION = 1
SITE_URL = "https://dion-jy.github.io/spotlight-todai"
API_BASE = SITE_URL + "/api"

# Epoch for the daily rotation. Fixed forever so the day index is stable.
ROTATION_EPOCH = datetime.date(2026, 1, 1)
DAILY_CANDIDATE_COUNT = 4  # extra papers offered alongside the pick

# Curated topic keywords. Matched case-insensitively against title + summary.
# Kept broad and ML-flavoured; substring match, so "diffusion" also hits
# "diffusion models". Order does not matter; empty buckets are dropped.
TOPIC_KEYWORDS = [
    "reinforcement learning", "large language model", "language model", "llm",
    "diffusion", "transformer", "attention", "reasoning", "agent", "alignment",
    "rlhf", "preference optimization", "fine-tuning", "pretraining", "pre-training",
    "in-context learning", "chain-of-thought", "retrieval", "rag",
    "generative model", "gan", "vae", "flow matching", "score-based",
    "representation learning", "self-supervised", "contrastive",
    "graph neural network", "graph", "geometric",
    "computer vision", "image generation", "video", "segmentation",
    "object detection", "3d", "nerf", "gaussian splatting",
    "multimodal", "vision-language", "speech", "audio", "text-to-image",
    "optimization", "convergence", "generalization", "scaling law",
    "robustness", "adversarial", "privacy", "differential privacy",
    "federated learning", "fairness", "interpretability", "explainability",
    "uncertainty", "bayesian", "causal", "causality",
    "robotics", "control", "planning", "world model", "imitation learning",
    "offline reinforcement learning", "exploration",
    "theory", "sample complexity", "regret", "bandit",
    "mixture of experts", "sparsity", "quantization", "distillation",
    "efficient", "long context", "memory", "state space model", "mamba",
    "protein", "molecule", "drug", "biology", "climate", "physics",
    "time series", "tabular", "recommendation",
    "benchmark", "dataset", "evaluation", "hallucination", "safety",
    "continual learning", "meta-learning", "few-shot", "zero-shot",
    "transfer learning", "domain adaptation", "neural architecture search",
    "optimal transport", "kernel", "gaussian process", "energy-based",
]


def stable_hash(s):
    """Deterministic, process-independent 64-bit hash (FNV-1a).

    Python's built-in hash() is salted per process, so we roll our own to keep
    the daily rotation reproducible across machines and CI runs.
    """
    mask = 0xFFFFFFFFFFFFFFFF
    h = 0xCBF29CE484222325
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x100000001B3) & mask
    # splitmix64 finalizer — FNV alone barely avalanches the trailing bytes, so
    # strings differing only in a suffix number would sort near each other.
    z = h
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & mask
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & mask
    z = z ^ (z >> 31)
    return z


def make_uid(rec):
    return "{}-{}-{}-{}".format(
        rec["conference"].lower(),
        rec["year"],
        rec["track"].lower(),
        rec["id"],
    )


def load_papers():
    with open(DATA_JSON, encoding="utf-8") as f:
        raw = json.load(f)

    papers = []
    seen = set()
    for rec in raw:
        uid = make_uid(rec)
        if uid in seen:
            raise SystemExit("FATAL: duplicate uid {} — uid scheme not unique".format(uid))
        seen.add(uid)
        links = rec.get("links", {}) or {}
        papers.append({
            "uid": uid,
            "conference": rec["conference"],
            "year": rec["year"],
            "track": rec["track"],
            "title": rec["title"],
            "authors": rec.get("authors") or ([rec["author"]] if rec.get("author") else []),
            "affiliation": rec.get("affiliation", "") or "",
            "summary": rec.get("summary", "") or "",
            "links": {
                "openreview": links.get("openreview", "") or "",
                "arxiv": links.get("arxiv", "") or "",
                "detail": links.get("detail", "") or "",
            },
        })
    # Stable order: conference, year, track, id — independent of source ordering.
    papers.sort(key=lambda p: (p["conference"], p["year"], p["track"], _uid_num(p["uid"])))
    return papers


def _uid_num(uid):
    m = re.search(r"-(\d+)$", uid)
    return int(m.group(1)) if m else 0


def write_json(name, obj):
    os.makedirs(API_DIR, exist_ok=True)
    path = os.path.join(API_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    size = os.path.getsize(path)
    print("  wrote api/{}  ({:,} bytes)".format(name, size))
    return path


def build_papers(papers):
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SITE_URL,
        "license": "Curation free to use; papers follow their original sources.",
        "count": len(papers),
        "fields": {
            "uid": "stable global id: <conference>-<year>-<track>-<id>, lowercase",
            "conference": "ICLR | ICML | NeurIPS",
            "year": "publication year (int)",
            "track": "Oral | Spotlight",
            "title": "paper title",
            "authors": "full author list (array of strings); may be [first author] only",
            "affiliation": "first-author affiliation, '' if unknown",
            "summary": "1-2 line TLDR/abstract, '' if not yet enriched",
            "links": "{openreview, arxiv, detail} — '' when absent",
        },
        "papers": papers,
    }


def build_venues(papers):
    counts = {}
    for p in papers:
        key = (p["conference"], p["year"], p["track"])
        counts[key] = counts.get(key, 0) + 1
    venues = [
        {"conference": c, "year": y, "track": t, "count": n}
        for (c, y, t), n in sorted(counts.items())
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "total": len(papers),
        "conferences": sorted({p["conference"] for p in papers}),
        "years": sorted({p["year"] for p in papers}),
        "tracks": sorted({p["track"] for p in papers}),
        "venues": venues,
    }


def build_topics(papers):
    haystack = {p["uid"]: (p["title"] + " " + p["summary"]).lower() for p in papers}
    topics = []
    for kw in TOPIC_KEYWORDS:
        needle = kw.lower()
        uids = [uid for uid, text in haystack.items() if needle in text]
        if uids:
            topics.append({"topic": kw, "count": len(uids), "paper_uids": sorted(uids)})
    topics.sort(key=lambda t: (-t["count"], t["topic"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "description": "Curated keyword -> paper uids. Substring match over title+summary; a paper may appear under several topics.",
        "topic_count": len(topics),
        "topics": topics,
    }


def build_daily(papers, the_date):
    """Deterministic 'paper of the day'.

    A fixed permutation of all uids is produced by sorting on a stable hash;
    the day index (days since ROTATION_EPOCH) walks that permutation. This
    cycles through every paper before any repeat (~N days), is reproducible
    from the date alone, and naturally avoids recently-shown papers.
    """
    order = sorted(papers, key=lambda p: stable_hash(p["uid"]))
    n = len(order)
    day_index = (the_date - ROTATION_EPOCH).days
    pos = day_index % n
    pick = order[pos]
    candidates = [order[(pos + 1 + i) % n] for i in range(DAILY_CANDIDATE_COUNT)]
    return {
        "schema_version": SCHEMA_VERSION,
        "date": the_date.isoformat(),
        "timezone": "Asia/Seoul",
        "rotation": {
            "day_index": day_index,
            "position": pos,
            "cycle_length_days": n,
            "epoch": ROTATION_EPOCH.isoformat(),
            "method": "stable-hash permutation walked by days-since-epoch; reproducible & non-repeating",
        },
        "paper": pick,
        "candidates": candidates,
    }


def kst_today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily-only", action="store_true", help="only regenerate api/daily.json")
    ap.add_argument("--date", help="force KST date YYYY-MM-DD for daily.json")
    args = ap.parse_args()

    papers = load_papers()
    the_date = datetime.date.fromisoformat(args.date) if args.date else kst_today()

    if args.daily_only:
        print("Regenerating daily.json for {} (KST)".format(the_date.isoformat()))
        write_json("daily.json", build_daily(papers, the_date))
        return

    print("Building api/ from {} papers".format(len(papers)))
    write_json("papers.json", build_papers(papers))
    write_json("venues.json", build_venues(papers))
    write_json("topics.json", build_topics(papers))
    write_json("daily.json", build_daily(papers, the_date))
    print("Done.")


if __name__ == "__main__":
    main()
