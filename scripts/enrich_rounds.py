#!/usr/bin/env python3
"""Assign round numbers to catalog entries using the race calendar."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_utils import (
    ROUND_BOUND_TYPES,
    canonical_race_name,
    infer_round,
    is_cancelled_race_entry,
    is_generic_race_name,
    is_season_review_entry,
    load_races,
    reconcile_round,
)


def enrich(path, races_path=None, dry_run=False, force=False, reconcile=False, fix_names=False):
    with open(path) as f:
        data = json.load(f)

    races = load_races(races_path)
    updated = 0
    reconciled = 0
    renamed = 0

    for entry in data:
        if entry.get("type") not in ROUND_BOUND_TYPES:
            continue
        if is_season_review_entry(entry):
            continue

        if is_cancelled_race_entry(entry):
            if entry.get("round") is not None:
                entry["round"] = None
                reconciled += 1
            continue

        if reconcile and entry.get("type") == "race":
            before = entry.get("round")
            entry["round"] = reconcile_round(entry, races)
            if entry.get("round") != before:
                reconciled += 1

        if force:
            entry["round"] = None
        if entry.get("round") is None or force:
            inferred = infer_round(entry, races)
            if inferred is not None:
                entry["round"] = inferred
                updated += 1

        if fix_names and entry.get("type") == "race" and is_generic_race_name(entry.get("name", "")):
            canonical = canonical_race_name(entry, races)
            if canonical:
                entry["name"] = canonical
                renamed += 1

    print(f"Inferred round for {updated} entries")
    if reconcile:
        print(f"Reconciled {reconciled} mismatched rounds")
    if fix_names:
        print(f"Fixed {renamed} generic race names")

    changed = updated or reconciled or renamed
    if not dry_run and changed:
        data.sort(key=lambda e: (e["season"], e.get("round") or 9999, e.get("type", ""), e["name"]))
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    return changed


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    force = "--force" in args
    reconcile = "--reconcile" in args
    fix_names = "--fix-names" in args
    args = [a for a in args if a not in ("--dry-run", "--force", "--reconcile", "--fix-names")]
    path = args[0] if args else "regions/us.json"
    races_path = args[1] if len(args) > 1 else None
    enrich(path, races_path, dry_run=dry_run, force=force, reconcile=reconcile, fix_names=fix_names)
