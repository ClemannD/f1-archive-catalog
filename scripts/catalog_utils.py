"""Shared catalog helpers for merge, season/round inference, and cleaning."""

import json
import re
from pathlib import Path

VALID_TYPES = {"race", "extended_highlights", "highlights", "season-review"}
LEGACY_TYPES = {"season_review"}  # migrated to season-review on clean
ROUND_BOUND_TYPES = {"race", "extended_highlights", "highlights"}
SEASON_REVIEW_TYPE = "season-review"

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
    "styrian": {"styrian", "steiermark", "styria"},
    "turkey": {"turkey", "turkish", "istanbul"},
    "united arab emirates": {"abu dhabi", "united arab emirates", "uae"},
    "united states": {"united states", "us", "usa", "austin", "las vegas", "miami", "united states grand prix"},
    "vietnam": {"vietnam", "vietnamese"},
    "malaysia": {"malaysia", "malaysian"},
}


def entry_key(entry):
    """Unique merge key: (season, round, type) or (season, type) for season reviews."""
    season = entry["season"]
    typ = entry.get("type", "race")
    round_ = entry.get("round")
    if round_ is not None:
        return (season, round_, typ)
    if typ == SEASON_REVIEW_TYPE:
        return (season, typ)
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


def canonicalize_location(location):
    """Expand abbreviations so 'us' does not substring-match 'australian'."""
    loc = normalize_text(location or "")
    if not loc:
        return loc

    shorthand = {
        "us": "united states",
        "usa": "united states",
        "u s": "united states",
        "uk": "britain",
    }
    if loc in shorthand:
        return shorthand[loc]

    loc_tokens = slug_tokens(loc)
    for canonical, aliases in LOCATION_ALIASES.items():
        alias_tokens = slug_tokens(canonical) | aliases
        if loc_tokens & alias_tokens:
            return canonical

    return loc


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


GENERIC_RACE_NAMES = {
    "formula 1 grand prix",
    "formula 1 pirelli grand prix",
    "formula 1 gran premio",
    "formula 1 grande prêmio",
    "formula 1 grande premio",
}

SLUG_STOPWORDS = {
    "formula", "grand", "prix", "gran", "premio", "grande",
    "heineken", "pirelli", "rolex", "gulf", "air", "aws", "msc", "cruises",
    "lenovo", "aramco", "qatar", "airways", "etihad", "singapore", "airlines",
    "johnnie", "walker", "honda", "vtb", "eyetime", "tag", "heuer", "stc",
    "crypto", "com", "louis", "vuitton", "grosser", "von", "osterreich",
    "magyar", "nagydij", "preis", "eyetime",
}


def is_feeder_series_entry(entry):
    """F2 / F3 content — not part of the F1 catalog."""
    name = entry.get("name", "") or ""
    url = (entry.get("url", "") or "").lower()
    slug = url.rsplit("/", 1)[-1].split("?")[0]

    if re.search(r"^\s*F2\b", name, re.I) or re.search(r"^\s*F3\b", name, re.I):
        return True
    if re.search(r"\bF2\s+season\b", name, re.I) or re.search(r"\bF3\s+season\b", name, re.I):
        return True
    if re.search(r"\bformula\s*2\b", name, re.I) or re.search(r"\bformula\s*3\b", name, re.I):
        return True
    if re.search(r"(?:^|[-/])(f2|f3)(?:[-/]|$)", slug):
        return True
    if re.search(r"\bf[23]-season\b", slug):
        return True

    return False


def is_catalog_season_review(entry):
    """Whole-season review content — not per-race 'In Review' highlights."""
    typ = entry.get("type", "")
    if typ in {SEASON_REVIEW_TYPE, "season_review"}:
        return True

    name = normalize_text(entry.get("name", ""))
    if name in {"season review", "season recap"}:
        return True
    if re.match(r"^\d{4}\s+season review$", name):
        return True

    if re.search(r"\bin review\b", name):
        return False

    url = entry.get("url", "") or ""
    if re.search(r"-season-review(?:/|$)", url) and entry.get("round") is None:
        return True

    return False


def is_season_review_entry(entry):
    return is_catalog_season_review(entry)


def season_review_name(season):
    return f"{season} Season Review"


def normalize_season_review(entry):
    """Normalize a season review entry to catalog conventions."""
    if not is_catalog_season_review(entry):
        return False
    season = entry.get("season")
    if season is None:
        return False
    entry["type"] = SEASON_REVIEW_TYPE
    entry["name"] = season_review_name(season)
    entry["round"] = None
    return True


def is_generic_race_name(name):
    n = normalize_text(name or "")
    if n in GENERIC_RACE_NAMES:
        return True
    return bool(
        re.match(
            r"^formula 1(?: \d{4})?(?: (?:pirelli|rolex|heineken|gulf air|aws|aramco|qatar airways|etihad airways|singapore airlines|johnnie walker|honda|vtb|eyetime|tag heuer|stc|crypto\.com|louis vuitton|msc cruises|lenovo))* (?:grand prix|gran premio|grande pr[eê]mio)$",
            n,
        )
    )


def location_from_url_slug(url):
    if not url:
        return None
    slug = url.rsplit("/", 1)[-1].split("?")[0]

    m = re.search(r"in-review-([a-z0-9-]+)", slug)
    if m:
        return normalize_text(m.group(1).replace("-", " "))

    m = re.search(r"(\d{4})-([a-z0-9-]+?)(?:-grand-prix|-extended|-in-review|$)", slug)
    if m:
        return normalize_text(m.group(2).replace("-", " "))

    for pat in (
        r"(?:du|de|do|von|del|dell|osterreich|magyar|grosser)-([a-z0-9-]+)-\d{4}$",
        r"(?:grand-prix|gran-premio|grande-premio)-(?:[a-z0-9-]+-)*([a-z0-9-]+)-\d{4}$",
        r"-([a-z0-9-]+)-\d{4}$",
    ):
        m = re.search(pat, slug)
        if not m:
            continue
        parts = [p for p in m.group(1).split("-") if p]
        if not parts:
            continue
        loc = normalize_text(parts[-1] if len(parts) > 1 else m.group(1).replace("-", " "))
        tokens = slug_tokens(loc)
        if tokens and tokens - SLUG_STOPWORDS:
            return loc

    return None


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

    m = re.search(
        r"\b(?:du|de|do|d'|del|dell'|von)\s+([\w\s.'-]+?)(?:\s+\d{4})?\s*$",
        name,
        re.I,
    )
    if m:
        place = normalize_text(m.group(1))
        if place not in {"heineken", "pirelli", "rolex", "formula"}:
            return place

    from_slug = location_from_url_slug(url)
    if from_slug:
        return canonicalize_location(from_slug)

    gp = re.search(r"([a-z\s]+)\s+grand prix", name, re.I)
    if gp:
        loc = normalize_text(gp.group(1))
        if not is_generic_race_name(loc + " grand prix"):
            return canonicalize_location(loc)

    if not is_generic_race_name(name):
        return canonicalize_location(normalize_text(name))

    return canonicalize_location(normalize_text(name))


def canonical_race_name(entry, races_by_season):
    season = entry.get("season")
    round_ = entry.get("round")
    if season is None or round_ is None:
        return None
    for race in races_by_season.get(season, []):
        if race["round"] == round_:
            return race["name"]
    return None


def reconcile_round(entry, races_by_season):
    """Re-infer round from URL/name when the stored round looks wrong."""
    if entry.get("type") != "race":
        return entry.get("round")

    probe = dict(entry)
    probe["round"] = None
    inferred = infer_round(probe, races_by_season)
    if inferred is None:
        return entry.get("round")

    current = entry.get("round")
    if current is None:
        return inferred
    if current == inferred:
        return current

    if is_generic_race_name(entry.get("name", "")):
        return inferred

    location = infer_location_from_entry(entry)
    if not location:
        return current

    current_race = next(
        (r for r in races_by_season.get(entry["season"], []) if r["round"] == current),
        None,
    )
    inferred_race = next(
        (r for r in races_by_season.get(entry["season"], []) if r["round"] == inferred),
        None,
    )
    if not inferred_race:
        return current

    if current_race and match_score(location, current_race) >= 15:
        return current
    if match_score(location, inferred_race) >= 15:
        return inferred

    return current


def match_score(location, race):
    loc = canonicalize_location(location)
    race_name = normalize_text(race["name"])

    if loc == race_name:
        return 100
    # Short tokens like "us" must not substring-match "australian".
    if len(loc) >= 4 and (loc in race_name or race_name in loc):
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
    if is_catalog_season_review(entry):
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
        if races_by_season and entry.get("round") is None and not is_catalog_season_review(entry):
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
