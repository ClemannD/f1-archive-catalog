#!/usr/bin/env python3
"""Assign round numbers to catalog entries using the race calendar."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_utils import infer_round, load_races


def enrich(path, races_path=None, dry_run=False, force=False):
    with open(path) as f:
        data = json.load(f)

    races = load_races(races_path)
    updated = 0

    for entry in data:
        if entry.get("type") == "season_review":
            continue
        if force:
            entry["round"] = None
        if entry.get("round") is not None and not force:
            continue
        inferred = infer_round(entry, races)
        if inferred is not None:
            entry["round"] = inferred
            updated += 1

    print(f"Inferred round for {updated} entries")

    if not dry_run and updated:
        data.sort(key=lambda e: (e["season"], e.get("round") or 9999, e.get("type", ""), e["name"]))
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    return updated


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    force = "--force" in args
    args = [a for a in args if a not in ("--dry-run", "--force")]
    path = args[0] if args else "regions/us.json"
    races_path = args[1] if len(args) > 1 else None
    enrich(path, races_path, dry_run=dry_run)
