# F1 Archive Catalog

An open-source, community-maintained catalog of what Formula 1 race content is available on F1TV's archive, organized by region.

## Why

F1TV's archive varies by region and content type. Some races have full replays, others only have extended highlights or appear in a season review. There's no public API for this information. This repo is a structured, machine-readable reference you can join to [`calendar/f1-all-time-race-list.json`](calendar/f1-all-time-race-list.json) on `season` + `round`.

## Schema

Each region file is a flat JSON array. Every entry represents one watchable item on F1TV.

```json
{
  "season": 2017,
  "round": 1,
  "name": "Australian Grand Prix",
  "type": "race",
  "duration": "02:04:30",
  "url": "https://f1tv.formula1.com/detail/1000002299/2017-australian-grand-prix"
}
```

### Fields

- **`season`** (integer) — Championship year. Must match the race calendar.
- **`round`** (integer | null) — Official FIA championship round number. **Required** for race-bound content (`race`, `extended_highlights`, `highlights`). Only `season-review` may use `null`. Round numbers may have gaps when a scheduled race was cancelled (e.g. 2023 has no round 6 — Emilia Romagna). Sourced from [`calendar/f1-all-time-race-list.json`](calendar/f1-all-time-race-list.json), not F1TV's UI badges.
- **`name`** (string) — Display label from F1TV (not used for joining).
- **`type`** (string) — Content type. One of:
  - `"race"` — Full race replay
  - `"extended_highlights"` — Extended highlights (~25–30 min)
  - `"highlights"` — Short highlights (~5–10 min)
  - `"season-review"` — Season review / recap
- **`duration`** (string | null) — Runtime in `HH:MM:SS` format. `null` if unknown.
- **`url`** (string) — F1TV deep link. Prefer `/detail/...` watch URLs over `/page/...` hub URLs when both exist.

### Uniqueness

Each entry is uniquely identified by:

- **`(season, round, type)`** for round-bound content
- **`(season, type)`** when `round` is `null` (season reviews only)

A single race may have **multiple entries** — e.g. full replay, extended highlights, and short highlights each get their own row with its own `url`.

### Season-level content

For seasons where individual races aren't available but a season review exists:

```json
{
  "season": 1985,
  "round": null,
  "name": "1985 Season Review",
  "type": "season-review",
  "duration": "01:20:00",
  "url": "https://f1tv.formula1.com/detail/..."
}
```

## Viewer

Browse the catalog in your browser:

```bash
python3 -m http.server 8080
```

Open [http://localhost:8080/scraper/viewer/](http://localhost:8080/scraper/viewer/). You can also use the file picker on that page to load `f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json` directly.

## Calendar

Official FIA race calendar used for round assignment and validation:

- [`calendar/f1-all-time-race-list.json`](calendar/f1-all-time-race-list.json) — championship races by `season` + `round` (gaps allowed for cancelled races)

## Regions

Each region has its own file under `f1-tv-archive-catalogs-by-region/`:

- `f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json` — United States

More regions welcome via PR.

## Scraping

See **[scraper/README.md](scraper/README.md)** for full setup. You need [Tampermonkey](https://www.tampermonkey.net/) and Python 3.

```bash
python3 scraper/scraper_server.py
```

Then install `scraper/f1tv-scraper.user.js` in Tampermonkey and scrape pages on f1tv.formula1.com.

### Post-processing

```bash
python3 scraper/scripts/clean_catalog.py f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json
python3 scraper/scripts/enrich_rounds.py f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json --reconcile --fix-names
python3 scraper/scripts/validate.py f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json
```

## Contributing

1. Fork the repo
2. Add or update entries in the appropriate region file
3. Run `python3 scraper/scripts/validate.py f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json`
4. Open a PR with a brief description of what changed

Durations can be added incrementally — `null` is fine as a placeholder. `url` should be present for all new entries.

## Disclaimer

This project is a community-maintained index of Formula 1 content available on [F1TV](https://f1tv.formula1.com). It is **not** affiliated with, endorsed by, or sponsored by Formula 1, Formula One Management, Liberty Media, or F1TV.

All Formula 1 trademarks, race names, logos, and video content are the property of their respective owners. This repository does not host, distribute, or claim ownership of any video or broadcast material. Entries are metadata and links to content on F1TV; viewing requires an active F1TV subscription in your region.

The catalog is provided as-is and may be incomplete or outdated. Availability on F1TV can change at any time.

## License

MIT License — see [LICENSE](LICENSE).
