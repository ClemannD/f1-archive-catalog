#!/usr/bin/env python3
"""Validate catalog JSON before copying to f1-rewatch."""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_utils import (
    SEASON_REVIEW_TYPE,
    VALID_TYPES,
    entry_key,
    load_races,
    season_review_name,
)

# Seasons to check against Races.json (official FIA round numbers, gaps allowed).
CHECK_SEASONS = (2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025)


def validate(path):
    with open(path) as f:
        data = json.load(f)

    errors = []
    warnings = []

    keys = defaultdict(list)
    for i, e in enumerate(data):
        season = e.get("season")
        if season is None or season < 1950 or season > 2030:
            errors.append(f"[{i}] invalid season: {season!r}")

        typ = e.get("type")
        if typ not in VALID_TYPES:
            errors.append(f"[{i}] invalid type: {typ!r}")

        if typ == SEASON_REVIEW_TYPE:
            if e.get("round") is not None:
                errors.append(f"[{i}] season-review must have null round: {e.get('name')!r}")
            expected_name = season_review_name(season)
            if e.get("name") != expected_name:
                warnings.append(
                    f"[{i}] season-review name should be {expected_name!r}, got {e.get('name')!r}"
                )
        elif e.get("round") is None:
            warnings.append(f"[{i}] missing round: {e.get('name')!r} ({typ})")

        if not e.get("url"):
            warnings.append(f"[{i}] missing url: {e.get('name')!r}")

        keys[entry_key(e)].append(i)

    for key, indices in keys.items():
        if len(indices) > 1:
            errors.append(f"duplicate key {key}: entries {indices}")

    races = load_races()
    for year in CHECK_SEASONS:
        season_races = races.get(year, [])
        if not season_races:
            continue
        official_rounds = {r["round"] for r in season_races}
        catalog_rounds = {
            e["round"]
            for e in data
            if e["season"] == year and e.get("round") and e.get("type") == "race"
        }
        missing = sorted(official_rounds - catalog_rounds)
        if missing:
            warnings.append(
                f"{year}: missing race rounds {missing} "
                f"({len(catalog_rounds)}/{len(official_rounds)} official rounds)"
            )

    print(f"Validated {len(data)} entries in {path}")
    print(f"  Errors:   {len(errors)}")
    print(f"  Warnings: {len(warnings)}")

    for msg in errors[:20]:
        print(f"  ERROR: {msg}")
    if len(errors) > 20:
        print(f"  ... and {len(errors) - 20} more errors")

    for msg in warnings[:20]:
        print(f"  WARN:  {msg}")
    if len(warnings) > 20:
        print(f"  ... and {len(warnings) - 20} more warnings")

    return len(errors) == 0


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "regions/us.json"
    ok = validate(path)
    sys.exit(0 if ok else 1)
