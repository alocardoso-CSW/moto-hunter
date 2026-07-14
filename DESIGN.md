# BikeDeals — Design Document

## Goal
A bot that daily scrapes used-motorcycle marketplaces in Portugal for one or more
bikes you're watching, tracks listings over time, scores them as deals relative to
the current market, and publishes the results to a dashboard (email digest can be
added later).

## Watchlist (config-driven, any bike)
Instead of hardcoding a single model, the bot is driven by a watchlist you define in
`config.yaml`. Each entry is a bike search plus optional filters — no code changes
needed to track a new bike.

```yaml
watches:
  - name: "MT-07"
    query: "yamaha mt-07"
    aliases: ["mt07", "mt 07"]   # helps match inconsistent listing titles
    max_price: null              # e.g. 6000 — null means no filter
    min_year: null               # e.g. 2018
    max_km: null                 # e.g. 30000
    location: null                # optional, e.g. "Porto" — modifiable per watch, not hardcoded

  - name: "Honda CB500F"
    query: "honda cb500f"
```

Filters are optional per-watch. Listings that fail a filter are still stored (for
history/market context) but excluded from your digest/dashboard "active matches".

## Sources (Portugal)
- **Standvirtual.pt** — largest PT marketplace; listing data is often embedded as
  structured JSON in the page, which is more reliable to parse than raw HTML.
- **OLX.pt** — large general classifieds site with strong motorcycle presence.
- **CustoJusto.pt** — smaller, sometimes surfaces listings the others miss.

Each site gets its own scraper module behind a common interface
(`fetch(query) -> list[Listing]`), so adding a 4th site later is a small, isolated
addition.

## Architecture

```
BikeDeals/
  .github/workflows/daily.yml     # cron trigger, runs the whole pipeline
  scrapers/
    base.py                        # common interface: fetch(query) -> list[Listing]
    standvirtual.py
    olx.py
    custojusto.py
  bikedeals/
    models.py                      # Listing dataclass (price, year, km, url, watch, ...)
    db.py                          # SQLite: every listing ever seen, price history
    scoring.py                     # ranks each active listing vs. its own watch's market
    notify.py                      # (future) builds & sends email digest
    dashboard.py                   # renders the static HTML dashboard
    main.py                        # orchestrates: scrape -> store -> score -> render
  templates/dashboard.html.j2
  docs/                            # generated dashboard, served by GitHub Pages
  data/listings.db                 # committed SQLite DB (persists state between runs)
  config.yaml                      # watchlist definition
  requirements.txt
  README.md
```

## Data model
Each stored listing includes: `watch_name`, `source`, external id, title, price,
year, mileage (km), location, url, image url, `first_seen`, `last_seen`,
`is_active`, and a `price_history` (to detect price drops over time).

## Scoring (self-calibrating, no manual thresholds required)
For each watch, active listings are scored *relative to the current pool of active
listings for that same watch* — an MT-07 is only ever compared against other
MT-07s, never against a CB500F:
- Price percentile within the watch's currently active listings (loosely adjusted
  for year/mileage outliers)
- Year and mileage as secondary factors
- Price-drop detection: a listing whose price has been reduced since first seen is
  flagged as a strong signal, independent of percentile
- Bucketed into 🔥 Great / 👍 Good / 🤷 Fair / 📈 Overpriced

This means filters in `config.yaml` (max_price, min_year, max_km) narrow *what
counts as a match*, while scoring ranks *how good the matches are* — both operate
per-watch.

## Scheduling & hosting
- **GitHub Actions**, daily cron (e.g. 7am UTC): checkout → setup Python → install
  deps → run `bikedeals/main.py` → commit updated `data/listings.db` and `docs/` →
  push. GitHub Pages serves `docs/` so the dashboard updates automatically after
  each run.
- Repo: **public** GitHub repository. This is required for free GitHub Pages
  hosting. No personal data is stored beyond scraped public listing links/prices —
  no secrets, no email — so this is a reasonable tradeoff. Dashboard will be
  reachable at `https://<username>.github.io/<repo>/`.

## Notifications
- **Not included in v1** (skipped per your request). `notify.py` is stubbed out in
  the architecture so email (or Telegram, etc.) can be added later without
  restructuring anything else.
- In the meantime, the **dashboard** (GitHub Pages site) is the way you check for
  deals — it will support a tab/filter per watch plus an "all watches" view, sorted
  by deal score.

## Scraping etiquette
Low request volume (a handful of searches, once a day) with realistic delays and a
normal User-Agent. This is personal-use monitoring of public listing pages, not
bulk harvesting — kept deliberately lightweight to avoid burdening the sites.

## Resolved decisions
- Repo visibility: **public** (needed for free GitHub Pages hosting; no sensitive
  data is stored).
- Notifications: **out of scope for v1**; dashboard-only, revisit later.
- Watchlist: **fully configurable**, any bike + optional price/year/km filters,
  starting with MT-07 as the first entry.
- Location filter: **a per-watch config field**, not hardcoded or nationwide-only —
  each watch can optionally set a `location` value; leaving it unset searches
  nationwide.
- Repo name: **`moto-hunter`**, under GitHub account `alocardoso-CSW`.
- `gh` CLI and Python 3.12 installed locally; `gh` authenticated as
  `alocardoso-CSW`.

## Status
Design is complete and under your review. **No repo has been created and no code
has been written yet** — holding until you confirm you're ready to proceed.
