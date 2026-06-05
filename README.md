# F1 Archive Catalog

An open-source, community-maintained catalog of what Formula 1 race content is available on F1TV's archive, organized by region.

## Why

F1TV's archive varies by region and content type. Some races have full replays, others only have extended highlights or appear in a season review. There's no public API for this information. This repo aims to be a structured, machine-readable reference.

## Schema

Each region file is a flat JSON array. Every entry represents a piece of watchable content tied to a race (or season).

```json
{
  "season": 2024,
  "round": 1,
  "name": "Bahrain Grand Prix",
  "type": "race",
  "duration": "1:57:32"
}
```

### Fields

- **`season`** (integer) — The championship year.
- **`round`** (integer | null) — The round number within the season. `null` for content not tied to a specific race (e.g. season reviews).
- **`name`** (string) — The title of the race or content.
- **`type`** (string) — The content type available. One of:
  - `"race"` — Full race replay
  - `"extended_highlights"` — Extended highlights (~25–30 min)
  - `"highlights"` — Short highlights (~5–10 min)
  - `"season_review"` — Season review / recap
- **`duration`** (string | null) — Runtime in `H:MM:SS` or `M:SS` format. `null` if unknown.

### Multiple content types

If a race has both a full replay and extended highlights available, include the **best available** type only (`"race"` > `"extended_highlights"` > `"highlights"` > `"season_review"`).

### Season-level content

For seasons where individual races aren't available but a season review exists:

```json
{
  "season": 1985,
  "round": null,
  "name": "1985 Season Review",
  "type": "season_review",
  "duration": "1:20:00"
}
```

## Regions

Each region has its own file under `regions/`:

- `regions/us.json` — United States

More regions welcome via PR.

## Contributing

1. Fork the repo
2. Add or update entries in the appropriate region file
3. Open a PR with a brief description of what changed

Durations can be added incrementally — `null` is fine as a placeholder.

## License

MIT
