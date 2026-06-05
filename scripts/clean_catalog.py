#!/usr/bin/env python3
"""Clean catalog data: fix seasons, dedupe, prefer detail URLs."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_utils import entry_key, fix_season_from_url, load_races, merge_entries


def clean(path, dry_run=False):
    with open(path) as f:
        data = json.load(f)

    fixed_season = 0
    for entry in data:
        before = entry.get("season")
        fix_season_from_url(entry)
        if entry.get("season") != before:
            fixed_season += 1

    print(f"Fixed {fixed_season} truncated season values")

    # Re-merge to dedupe by (season, round, type) and prefer detail URLs
    merged = []
    _, added, updated = merge_entries(merged, data, load_races())
    print(f"After dedupe: {len(merged)} entries ({added} unique, {updated} merged)")

    merged.sort(key=lambda e: (e["season"], e.get("round") or 9999, e.get("type", ""), e["name"]))

    # Report remaining bad seasons
    bad = [e for e in merged if e.get("season", 0) < 1950]
    if bad:
        print(f"WARNING: {len(bad)} entries still have invalid season")

    if not dry_run:
        with open(path, "w") as f:
            json.dump(merged, f, indent=2)
            f.write("\n")

    return len(merged)


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    path = args[0] if args else "regions/us.json"
    clean(path, dry_run=dry_run)
