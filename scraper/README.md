# F1TV Archive Scraper

Tools for scraping F1TV archive pages into the regional catalog (`f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json`).

## What you need

- **Python 3** — runs the local ingest server
- **[Tampermonkey](https://www.tampermonkey.net/)** — browser extension that runs the scraper on F1TV pages
  - [Chrome](https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo)
  - [Firefox](https://addons.mozilla.org/en-US/firefox/addon/tampermonkey/)
  - [Safari](https://www.tampermonkey.net/index.php?browser=safari)
- An **F1TV subscription** and access to the archive in your browser

## Setup

### 1. Install Tampermonkey

Install the extension for your browser using one of the links above. You should see the Tampermonkey icon in your toolbar.

### 2. Install the userscript

1. Open Tampermonkey → **Create a new script** (or **Dashboard** → **+**)
2. Delete the template and paste the contents of [`f1tv-scraper.user.js`](f1tv-scraper.user.js)
3. Save (File → Save, or Cmd/Ctrl+S)

Alternatively, with the server running you can copy the script from http://localhost:8484/script.

Confirm the script header shows `@version 1.8` or later.

### 3. Start the ingest server

From the repo root:

```bash
python3 scraper/scraper_server.py
```

The server listens on **http://localhost:8484** and writes scraped data to `f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json`.

Leave this terminal open while scraping.

## Scraping

1. Log in to [F1TV](https://f1tv.formula1.com/) in the same browser where Tampermonkey is installed
2. Navigate to an archive page — e.g. a season listing or a race detail page with video cards
3. Click the red **Scrape Page** button (bottom-right corner)
4. Wait for the scroll pass to finish — the button shows `found N, +M` when done
5. Repeat for each season or page you want to capture

### What gets scraped

- **Season listing pages** — race hub links (`/page/...`) with season, round, name, and URL
- **Race detail pages** — individual video cards (`/detail/...`) with type, duration, and URL

F2/F3 content and non-race types (documentary, feature, show, race highlights, analysis) are skipped automatically.

The scraper scrolls through virtualized lists and collects each card by unique URL, so all races on the page should be captured.

### Tips

- Scrape **season listings** for race hub URLs (all rounds at once)
- Scrape **individual race pages** for full replays, highlights, and durations
- For a full season you typically need both: the listing for round coverage, detail pages for content types

## After scraping

Run validation and cleanup from the repo root:

```bash
python3 scraper/scripts/clean_catalog.py f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json
python3 scraper/scripts/enrich_rounds.py f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json --reconcile --fix-names
python3 scraper/scripts/validate.py f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json
```

## Server endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Status page with catalog stats |
| `GET /current` | Raw `f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json` contents |
| `GET /script` | Userscript file |
| `POST /add` | Accepts a JSON array of catalog entries |

## Troubleshooting

**"Server error" on the scrape button** — make sure `python3 scraper/scraper_server.py` is running.

**Fewer races than expected** — reload the userscript (check version 1.5+). The scraper must collect cards while scrolling; older versions scrolled back to the top before scraping and missed virtualized cards.

**Wrong round or generic name** (e.g. Canada stored as R6 "FORMULA 1 GRAND PRIX") — update to v1.5+, re-scrape the season listing, then run `enrich_rounds.py --reconcile --fix-names`. v1.5 uses the country label and URL slug when titles use French word order (`GRAND PRIX ... DU CANADA`), merges duplicate href captures from virtualization, and scrolls wall lists in smaller steps.

**`season: 20` instead of `2025`** — update to userscript v1.3+. Run `python3 scraper/scripts/clean_catalog.py f1-tv-archive-catalogs-by-region/US-f1-tv-archive-catalog.json` to repair existing data.

**Tampermonkey not firing** — check the extension is enabled, the script matches `https://f1tv.formula1.com/*`, and `localhost` is allowed under `@connect`.
