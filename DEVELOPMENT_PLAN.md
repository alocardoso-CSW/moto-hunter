# moto-hunter — Development Plan

Design reference: `DESIGN.md` and `design-history/design-plan-v4.html` (accepted).

## How this works

The build is split into **checkpoints**. Each checkpoint is small enough to
review in one sitting, ends with a concrete verification step, and is followed
by an explicit stop — I will not start the next checkpoint until you've
confirmed the current one is good.

**Every checkpoint that produces code goes through the same validation
routine before I present it as done:**
1. Automated tests (`pytest`) covering the new logic — written alongside the
   code, not after.
2. Linting/type-checks (`ruff`, and `mypy` where it's worth the friction) —
   catches the same class of bug a code reviewer would flag.
3. A manual smoke test I run myself — actually calling the endpoint /
   clicking the UI / running the scraper against the real site — since
   passing tests isn't the same as the feature working.
4. A short self-review of the diff for the things tests don't catch:
   unused code, obvious edge cases, anything that doesn't match the design.

Only after all four does a checkpoint get marked ready for your review.

---

## Checkpoint 0 — Repo & environment scaffolding ✅ done

**Goal:** an empty but runnable skeleton, nothing functional yet.

- [x] Create the `moto-hunter` GitHub repo — public, https://github.com/alocardoso-CSW/moto-hunter
- [x] Project structure: `app/`, `web/`, `tests/`, `requirements.txt`, `.gitignore`, `README.md`
- [x] Python virtual environment + base dependencies (FastAPI, uvicorn, SQLAlchemy, httpx, BeautifulSoup4, pytest, ruff)
- [x] Minimal FastAPI app with a `/health` endpoint
- [x] First commit pushed

**Verify:**
- [x] `uvicorn app.main:app` boots locally and `/health` returns `200 OK`
- [x] `pytest` runs cleanly (even with zero tests collected — proves the harness works)
- [x] `ruff check .` runs clean

**Checkpoint gate:** confirm repo structure and that the app boots before any real logic gets written. — confirmed by user.

---

## Checkpoint 1 — Data model & database layer ✅ done

**Goal:** `Watch`, `Listing`, `PriceHistory` tables, with working CRUD, no scraping yet.

- [x] SQLAlchemy models: `Watch` (brand, model, price/year/km min–max, location, enabled sources, last_run_at), `Listing`, `PriceHistory`
- [x] DB init (SQLite file under `data/`)
- [x] CRUD functions: create/update/delete a watch, upsert a listing (with price-history tracking), mark listings inactive after a run

**Verify:**
- [x] Unit tests against an in-memory SQLite DB: create a watch, upsert a listing twice with a price change, confirm `PriceHistory` records the change (9 tests, all passing)
- [x] Manually inspected the generated `.db` file (via Python's built-in `sqlite3` module — no standalone CLI installed) to confirm the schema matches the design

**Checkpoint gate:** review the schema itself — easier to adjust field names/types now than after scrapers depend on them.

---

## Checkpoint 2 — First scraper: Standvirtual (proof of concept) ✅ done

**Goal:** prove the scraping approach works end-to-end on one site before repeating it four more times.

- [x] `scrapers/base.py` — common interface: `fetch(filters) -> list[ScrapedListing]`
- [x] `scrapers/standvirtual.py` — search by brand/model, parse the embedded JSON, map to `ScrapedListing`, apply price/year/km/location filters

**Verify:**
- [x] Unit tests against a saved fixture (a real captured search-results page for Yamaha MT-07), so tests don't depend on the live site or network — 5 new tests, 14 total, all passing
- [x] One **live** manual run against real Standvirtual search results for "Yamaha MT-07", using the actual production scraper class — 11 real listings fetched live, matching the fixture

**What this checkpoint actually caught:** while reverse-engineering the site's filter parameters, `search[filter_float_year:from/to]` looked plausible but silently did nothing — years outside the requested range kept appearing. The real parameter is `search[filter_float_first_registration_year:from/to]`, confirmed by testing against the live site until results actually matched the filter. Exactly the kind of subtle, wrong-but-plausible bug this checkpoint exists to catch before it's copied into 4 more scrapers.

**Known simplification:** the `location` filter is applied client-side (substring match against the listing's city/region text) rather than via the site's own filter, since that would require a name-to-internal-ID lookup table. Documented in code; revisit if it proves too loose in practice.

**Checkpoint gate:** this is the most important gate in the whole plan — if the scraping approach or data mapping is wrong, better to catch it on one site than fix it in five.

---

## Checkpoint 3 — Remaining core scrapers: OLX, CustoJusto, (Auto.pt dropped) ✅ done

**Goal:** repeat the proven Checkpoint 2 pattern across the rest of the always-on sources.

- [x] `scrapers/olx.py` — no structured brand/model filter exists for motorcycles on OLX, so brand+model become free-text search, with a client-side title-match filter to drop off-topic results (confirmed real case: a "Yamaha Tracer 7" and a bare "Yamaha XSR" both surfaced in an MT-07 search). Price/year/km filters do work as structured query params. Also hit OLX's bot protection blocking plain Python HTTP clients by TLS fingerprint (curl worked, httpx2 got 403 even on the homepage) — fixed with `curl_cffi`, which impersonates a real browser's TLS handshake.
- [x] `scrapers/custojusto.py` — the brand/model URL path works, but its "structure" query param (price/year/km/text filters) is silently ignored over plain GET, confirmed by testing several encodings. Since per-model result counts are small, those filters are applied client-side instead. This category also mixes in spare parts/accessories tagged with a matching brand+model (a shock absorber "for a MT-07," a windshield) with no structured field to tell them apart from an actual bike — filtered via a price-plausibility floor plus the same title-match approach used for OLX.
- [x] `scrapers/autopt.py` — **dropped**, by your decision. Investigated first: its entire motorcycle catalog is ~120 listings site-wide (0 currently matching an MT-07 search), and its search form is CSRF/session-protected rather than plain URL filters like the other three sites. Not worth the added complexity for that little coverage.

**Verify:**
- [x] Fixture-based unit tests per site, same pattern as Checkpoint 2 — 23 tests total, all passing
- [x] Live manual run per site using the actual production scraper classes, spot-checked against the real search results

**Checkpoint gate:** confirm all sources return sane, comparable data before scoring is built on top of them.

---

## Checkpoint 4 — Scoring engine ✅ done

**Goal:** turn a pool of listings for a watch into percentile-based scores and buckets (Great / Good / Fair / Overpriced).

- [x] Price percentile within a watch's active pool, adjusted for year/km via least-squares regression (`app/scoring.py`)
- [x] Price-drop detection from `PriceHistory` — bumps a listing's bucket up one level
- [x] Bucket assignment

**Verify:**
- [x] Unit tests with synthetic listing sets with known distributions — 6 tests, including a cheap outlier landing in "great," a price drop bumping a bucket, and a same-priced newer/lower-km bike correctly outranking an older/high-km one
- [x] Ran scoring against real data pulled live from all three scrapers (57 real Yamaha MT-07 listings) and spot-checked the output by eye

**What this checkpoint actually caught:** the first version of the regression fallback mixed scales — a listing missing `km` (every CustoJusto listing) fell back to being ranked by raw price directly, while everything else was ranked by *residual from an expected price* (a difference of tens-to-hundreds of euros, not thousands). That silently dumped every CustoJusto listing into "overpriced" regardless of whether it was actually a good deal. Only caught by actually looking at real scored output, not by the synthetic unit tests — fixed by predicting an expected price for every listing via the best available model (year+km, falling back to year-only, falling back to the pool's median price), so everything is ranked on the same footing.

**Checkpoint gate:** scoring is the part that's hardest to unit-test into correctness — needs your eyes on real output.

---

## Checkpoint 5 — Backend API

**Goal:** wire watches, scrapers, and scoring together behind HTTP endpoints.

- [ ] `POST /watches`, `GET /watches`, `PUT /watches/{id}`, `DELETE /watches/{id}`
- [ ] `POST /watches/{id}/run` — triggers scrape → store → score for that watch
- [ ] `GET /watches/{id}/listings` — scored, sorted results

**Verify:**
- API tests via FastAPI's `TestClient`, scrapers mocked so tests are fast and don't hit real sites
- Manual smoke test through the auto-generated `/docs` Swagger UI: create a watch, hit run, fetch listings, confirm the full cycle works over HTTP

**Checkpoint gate:** confirm the API shape before building the UI against it — cheaper to adjust a route now than after the frontend depends on it.

---

## Checkpoint 6 — Frontend: watch management UI

**Goal:** the add/edit watch form and the watch table, wired to the real API — no more mockups.

- [ ] Add-watch form (brand, model, price/year/km ranges, location, source toggles including Facebook off-by-default)
- [ ] Watch table: edit, delete, "Run now", last-run timestamp

**Verify:**
- Manually add a real watch through the browser, click Run now, confirm the table updates
- Edit and delete flows checked by hand

**Checkpoint gate:** the first checkpoint you can fully click through yourself — good moment to react to anything that feels off in practice versus the mockup.

---

## Checkpoint 7 — Frontend: dashboard deal cards

**Goal:** the photo-card dashboard from the accepted design — image, title, spec line, bold price, deal badge, source pill.

- [ ] Card grid rendering real scored listings
- [ ] Click-through to the original listing URL

**Verify:**
- Visual check against the approved mockup (`design-plan-v4.html`)
- Click through a handful of cards to confirm links resolve to the real ads

**Checkpoint gate:** sign-off that the live UI matches what was approved in the design phase.

---

## Checkpoint 8 — Facebook Marketplace scraper (optional, off by default)

**Goal:** the one flagged-risk source, built last and in isolation so it can't destabilize anything already working.

- [ ] `scrapers/facebook.py` using your own logged-in session, low frequency
- [ ] Wired only behind the per-watch opt-in toggle

**Verify:**
- Manual test only, run by you against your own account — not something to automate into CI given the ToS/account-risk caveat
- Confirm the other four sources are unaffected if this one breaks

**Checkpoint gate:** explicit go/no-go — this is the source most likely to need revisiting later, so worth deciding fresh whether it's still wanted at this point.

---

## Checkpoint 9 — Deployment to Oracle Cloud Always Free

**Goal:** the app running continuously on your own free VM instead of your laptop.

- [ ] Oracle Cloud account created (your action — separate signup from GitHub)
- [ ] Always Free VM provisioned, Python + dependencies installed
- [ ] App running as a `systemd` service (survives reboots)
- [ ] Basic firewall rule opened for the app's port

**Verify:**
- App reachable at the VM's public IP from your own browser
- Full add-watch → run → view-dashboard cycle tested against the deployed instance, not just locally

**Checkpoint gate:** final infrastructure sign-off before calling this "shipped."

---

## Checkpoint 10 — End-to-end acceptance

**Goal:** the actual point of the whole project — find you a real MT-07.

- [ ] Add your real watch(es) with your real filters
- [ ] Run against all enabled sources
- [ ] Confirm the dashboard surfaces sane, correctly scored, correctly linked real listings

**Verify:** this one's entirely yours — does it actually help you find a bike?
