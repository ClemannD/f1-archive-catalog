"""Shared catalog helpers for merge, season/round inference, and cleaning."""

import json
import re
from pathlib import Path

VALID_TYPES = {"race", "extended_highlights", "highlights", "season_review"}

DEFAULT_RACES_PATH = (
    Path(__file__).resolve().parents[2].parent
    / "_apps"
    / "f1-rewatch"
    / "F1Rewatch"
    / "Resources"
    / "Races.json"
)

# Aliases for matching F1TV titles to race calendar entries
LOCATION_ALIASES = {
    "australia": {"australia", "australian"},
    "austria": {"austria", "austrian"},
    "azerbaijan": {"azerbaijan", "baku"},
    "bahrain": {"bahrain"},
    "belgium": {"belgium", "belgian", "spa"},
    "brazil": {"brazil", "brazilian", "sao paulo"},
    "britain": {"britain", "british", "great britain", "united kingdom", "uk"},
    "canada": {"canada", "canadian"},
    "china": {"china", "chinese"},
    "france": {"france", "french"},
    "germany": {"germany", "german", "hockenheim", "nurburgring", "eifel"},
    "hungary": {"hungary", "hungarian"},
    "italy": {"italy", "italian", "monza"},
    "japan": {"japan", "japanese", "suzuka"},
    "mexico": {"mexico", "mexican", "mexico city"},
    "monaco": {"monaco"},
    "netherlands": {"netherlands", "dutch", "zandvoort"},
    "portugal": {"portugal", "portuguese"},
    "qatar": {"qatar"},
    "russia": {"russia", "russian", "sochi"},
    "saudi arabia": {"saudi arabia", "saudi", "jeddah"},
    "singapore": {"singapore"},
    "spain": {"spain", "spanish", "barcelona", "catalunya"},
    "turkey": {"turkey", "turkish", "istanbul"},
    "united arab emirates": {"abu dhabi", "united arab emirates", "uae"},
    "united states": {"united states", "us", "usa", "austin", "las vegas", "miami", "united states grand prix"},
    "vietnam": {"vietnam", "vietnamese"},
    "malaysia": {"malaysia", "malaysian"},
}


def entry_key(entry):
    """Unique merge key: (season, round, type) or (season, name, type) when round is null."""
    season = entry["season"]
    typ = entry.get("type", "race")
    round_ = entry.get("round")
    if round_ is not None:
        return (season, round_, typ)
    name = entry.get("name", "").lower().strip()
    return (season, name, typ)


def season_from_url(url):
    if not url:
        return None
    for pat in (
        r"-(\d{4})(?:-|$|\?)",
        r"/(\d{4})-",
        r"(\d{4})-[^/]+-grand-prix",
    ):
        m = re.search(pat, url)
        if m:
            year = int(m.group(1))
            if 1950 <= year <= 2030:
                return year
    return None


def normalize_text(text):
    return re.sub(r"\s+", " ", text.lower().strip())


def slug_tokens(text):
    text = normalize_text(text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return {t for t in re.split(r"[\s-]+", text) if t}


def load_races(path=None):
    races_path = Path(path) if path else DEFAULT_RACES_PATH
    if not races_path.exists():
        return {}
    with open(races_path) as f:
        races = json.load(f)
    by_season = {}
    for race in races:
        by_season.setdefault(race["season"], []).append(race)
    return by_season


def race_search_terms(race):
    terms = slug_tokens(race["name"])
    terms |= slug_tokens(race.get("country", ""))
    terms |= slug_tokens(race.get("circuit", ""))
    for canonical, aliases in LOCATION_ALIASES.items():
        if canonical in terms or aliases & terms:
            terms.add(canonical.replace(" ", ""))
            terms |= aliases
    return terms


def infer_location_from_entry(entry):
    name = entry.get("name", "")
    url = entry.get("url", "") or ""

    m = re.search(r"in review\s*:\s*(.+)$", name, re.I)
    if m:
        return normalize_text(m.group(1))

    m = re.search(r"in review\s*-\s*(.+)$", name, re.I)
    if m:
        return normalize_text(m.group(1))

    m = re.search(r"^([^:]+):", name)
    if m:
        return normalize_text(m.group(1))

    slug = url.rsplit("/", 1)[-1] if url else ""
    m = re.search(r"in-review-([a-z-]+)", slug)
    if m:
        return normalize_text(m.group(1).replace("-", " "))

    m = re.search(r"(\d{4})-([a-z-]+?)(?:-grand-prix|-extended|-in-review|$)", slug)
    if m:
        return normalize_text(m.group(2).replace("-", " "))

    gp = re.search(r"([a-z\s]+)\s+grand prix", name, re.I)
    if gp:
        return normalize_text(gp.group(1))

    return normalize_text(name)


def match_score(location, race):
    loc = normalize_text(location)
    race_name = normalize_text(race["name"])

    if loc == race_name:
        return 100
    if loc in race_name or race_name in loc:
        return 90

    loc_tokens = slug_tokens(loc)
    name_tokens = slug_tokens(race_name)
    generic = {"grand", "prix", "formula", "review", "race", "the"}
    specific_common = (loc_tokens & name_tokens) - generic
    if specific_common:
        return len(specific_common) * 20

    country = normalize_text(race.get("country", ""))
    country_tokens = slug_tokens(country)
    if loc_tokens & country_tokens:
        return 15

    for canonical, aliases in LOCATION_ALIASES.items():
        alias_tokens = slug_tokens(canonical) | aliases
        if loc_tokens & alias_tokens and name_tokens & alias_tokens:
            return 25

    return 0


def location_matches_race(location, race):
    return match_score(location, race) >= 15


def infer_round(entry, races_by_season):
    if entry.get("round") is not None:
        return entry["round"]
    if entry.get("type") == "season_review":
        return None

    name = normalize_text(entry.get("name", ""))
    if name in {"season review", "season recap"}:
        return None

    season = entry["season"]
    races = races_by_season.get(season, [])
    if not races:
        return None

    location = infer_location_from_entry(entry)
    best_round = None
    best_score = 0
    for race in races:
        score = match_score(location, race)
        if score > best_score:
            best_score = score
            best_round = race["round"]
    return best_round if best_score >= 15 else None


def prefer_url(existing_url, new_url):
    """Prefer /detail/ URLs over /page/ hub URLs."""
    if not existing_url:
        return new_url
    if not new_url:
        return existing_url
    existing_detail = "/detail/" in existing_url
    new_detail = "/detail/" in new_url
    if new_detail and not existing_detail:
        return new_url
    return existing_url


def merge_entries(existing, new_entries, races_by_season=None):
    lookup = {}
    for i, e in enumerate(existing):
        lookup[entry_key(e)] = i

    added = 0
    updated = 0

    for entry in new_entries:
        if races_by_season and entry.get("round") is None and entry.get("type") != "season_review":
            inferred = infer_round(entry, races_by_season)
            if inferred is not None:
                entry["round"] = inferred

        key = entry_key(entry)
        if key in lookup:
            idx = lookup[key]
            if entry.get("duration"):
                existing[idx]["duration"] = entry["duration"]
            if entry.get("url"):
                existing[idx]["url"] = prefer_url(existing[idx].get("url"), entry["url"])
            if entry.get("round") is not None and existing[idx].get("round") is None:
                existing[idx]["round"] = entry["round"]
            updated += 1
        else:
            existing.append(entry)
            lookup[key] = len(existing) - 1
            added += 1

    return existing, added, updated


def fix_season_from_url(entry):
    """Repair truncated season values (e.g. 20 instead of 2025)."""
    season = entry.get("season")
    if season is not None and season >= 1950:
        return entry
    url_year = season_from_url(entry.get("url"))
    if url_year:
        entry["season"] = url_year
    return entry
