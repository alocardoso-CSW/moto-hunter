# How to verify each checkpoint yourself

A running log of hands-on steps you can do yourself to confirm what's been
built at each checkpoint — so you're never just taking my word for it. New
sections get added as we complete checkpoints; older sections stay so you can
always look back.

All commands below assume PowerShell, in the project folder:
`c:\Users\alocardoso\OneDrive - CRITICAL SOFTWARE, S.A\Desktop\BikeDeals`

---

## Checkpoint 0 — the skeleton runs

1. **Run the automated tests:**
   ```
   .\.venv\Scripts\python.exe -m pytest -v
   ```
   You should see `1 passed` (or more, as checkpoints add tests). Green means the code does what it claims.

2. **Run the linter** (catches sloppy/unused code):
   ```
   .\.venv\Scripts\python.exe -m ruff check .
   ```
   Should print `All checks passed!`.

3. **Boot the actual app:**
   ```
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```
   Leave it running, then open **http://127.0.0.1:8000/health** in your browser — you should see `{"status":"ok"}`. Press `Ctrl+C` in the terminal to stop it when done.

4. **Check the GitHub repo:** https://github.com/alocardoso-CSW/moto-hunter — confirm the files are there and the commit history makes sense.

---

## Checkpoint 1 — the database actually stores things

Tests prove the code works in theory. This section lets you see it work with your own eyes, using a real Python session.

1. **Run the new tests:**
   ```
   .\.venv\Scripts\python.exe -m pytest -v
   ```
   You should now see **9 passed** — the new ones are in `tests/test_crud.py`, covering creating/editing/deleting a watch and the price-history tracking.

2. **Open a live Python session and create a watch yourself:**
   ```
   .\.venv\Scripts\python.exe
   ```
   Then paste these lines one at a time:
   ```python
   from app.db import SessionLocal, init_db
   from app import crud

   init_db()
   session = SessionLocal()

   watch = crud.create_watch(session, brand="Yamaha", model="MT-07", price_min=4500, price_max=7000)
   watch.id, watch.brand, watch.sources
   ```
   You should see something like `(1, 'Yamaha', ['standvirtual', 'olx', 'custojusto', 'autopt'])` — a real row, saved to disk, with the four default sources already attached.

3. **Add a fake listing and watch the price-history tracking work:**
   ```python
   listing = crud.upsert_listing(session, watch.id, source="standvirtual", external_id="test1", title="Test MT-07", price=5800, url="https://example.com")
   listing.price_history[0].price  # 5800

   listing = crud.upsert_listing(session, watch.id, source="standvirtual", external_id="test1", title="Test MT-07", price=5500, url="https://example.com")
   [ph.price for ph in listing.price_history]  # [5800, 5500] — the price drop was recorded
   ```
   Type `exit()` when done.

4. **Confirm it's really on disk, not just in memory:** close that Python session entirely, reopen `.\.venv\Scripts\python.exe`, and run:
   ```python
   from app.db import SessionLocal
   from app import crud

   session = SessionLocal()
   crud.list_watches(session)  # your Yamaha MT-07 watch is still there
   ```

5. **A friendlier way to browse the database:** **DB Browser for SQLite** is now installed. Open it from the Start menu (search "DB Browser for SQLite"), then **File → Open Database** and pick `data\moto_hunter.db` inside the project folder. Click the **Browse Data** tab and pick a table (`watches`, `listings`, `price_history`) from the dropdown to see the actual rows — no Python needed. This is the easiest way to eyeball what a checkpoint produced from here on.

---

## Checkpoint 2 — the scraper actually finds real bikes

1. **Run the tests** (now 14 total, 5 new ones for the scraper):
   ```
   .\.venv\Scripts\python.exe -m pytest -v
   ```
   The new tests in `tests/test_standvirtual_scraper.py` replay a real, saved Standvirtual search page (`tests/fixtures/standvirtual_mt07_search.html`) rather than hitting the internet, so they stay fast and reliable.

2. **See it fetch real, live listings right now** — open a Python session:
   ```
   .\.venv\Scripts\python.exe
   ```
   ```python
   from app.scrapers.base import WatchFilters
   from app.scrapers.standvirtual import StandvirtualScraper

   filters = WatchFilters(brand="Yamaha", model="MT-07", price_min=4500, price_max=7000, year_min=2018, year_max=2024, km_min=0, km_max=30000)
   listings = StandvirtualScraper().fetch(filters)
   len(listings)  # however many match right now
   listings[0]
   ```

3. **Cross-check against the real site with your own eyes:** open https://www.standvirtual.com/motos/yamaha/mt-07 in your browser, and manually set the same filters (price 4500–7000€, year 2018–2024, km 0–30000) using the site's own filter panel. The listings you see there should be the same ones (or a close, current match — listings change over time) as what `listings` printed above. This is the real check: not "did the code run," but "does it agree with the actual website."

4. **A bug this checkpoint actually caught, if you're curious:** Standvirtual's year filter parameter isn't the one you'd guess from a URL scan (`filter_float_year`) — it silently does nothing. The working one, found by testing until results actually matched, is `filter_float_first_registration_year`. Worth knowing in case a future checkpoint needs to touch this scraper again.

---

## Checkpoint 3 — OLX and CustoJusto, plus why Auto.pt isn't here

1. **Run the tests** (now 23 total):
   ```
   .\.venv\Scripts\python.exe -m pytest -v
   ```
   `tests/test_olx_scraper.py` and `tests/test_custojusto_scraper.py` each replay a real saved search page, same pattern as Standvirtual.

2. **See both fetch real, live listings right now:**
   ```
   .\.venv\Scripts\python.exe
   ```
   ```python
   from app.scrapers.base import WatchFilters
   from app.scrapers.olx import OlxScraper
   from app.scrapers.custojusto import CustoJustoScraper

   filters = WatchFilters(brand="Yamaha", model="MT-07", price_min=4500, price_max=7000, year_min=2018, year_max=2024, km_min=0, km_max=30000)
   len(OlxScraper().fetch(filters))
   len(CustoJustoScraper().fetch(filters))
   ```

3. **Cross-check against the real sites:** open https://www.olx.pt/carros-motos-e-barcos/motociclos-scooters/q-yamaha-mt-07/ and https://www.custojusto.pt/portugal/veiculos/motos/yamaha/mt-07 in your browser and compare by eye, same as Checkpoint 2.

4. **Two real things this checkpoint caught, if you're curious:**
   - **OLX has no structured brand/model filter for motorcycles at all** (checked its own ad data — there's no "brand" field, only a "model" field sellers sometimes fill in wrong). So OLX search is free-text, which pulled in a "Yamaha Tracer 7" and a bare "Yamaha XSR" when searching for "yamaha mt-07." The scraper now checks that the listing's title actually contains "mt07" (ignoring punctuation/spacing) before keeping it — you can see this in `tests/test_olx_scraper.py::test_scraper_fetch_filters_out_off_topic_matches_and_dedupes`.
   - **OLX blocks Python HTTP libraries outright** — not by rate limit, but by TLS fingerprint. `curl` could reach the site, `httpx2` got a 403 on every page including the homepage. Fixed with `curl_cffi`, a library that makes Python's HTTP client present a real browser's TLS handshake. Only the OLX scraper needs this; Standvirtual and CustoJusto are fine with the normal client.

5. **Why there's no `scrapers/autopt.py`:** investigated, then dropped by your call. Its whole motorcycle section is ~120 listings total (checked by paging through until it ran dry), none of which were an MT-07 at the time, and its search form requires a CSRF token tied to a session rather than working off plain URL parameters like the other three sites. You can retrace this yourself: `curl -s -A "Mozilla/5.0" "https://www.auto.pt/motas-usadas?page=6"` still returns listings, `?page=7` returns none.

---

## Checkpoint 4 — scoring turns listings into Great/Good/Fair/Overpriced

1. **Run the tests** (now 29 total, 6 new ones for scoring):
   ```
   .\.venv\Scripts\python.exe -m pytest -v
   ```
   `tests/test_scoring.py` uses synthetic listings with known, deliberately constructed distributions — e.g. two listings priced identically where one is newer/lower-km, and asserts the newer one scores as the better value.

2. **See it score real, live listings from all three sites at once:**
   ```
   .\.venv\Scripts\python.exe
   ```
   ```python
   from sqlalchemy import create_engine
   from sqlalchemy.orm import sessionmaker
   from app import crud
   from app.models import Base
   from app.scrapers.base import WatchFilters
   from app.scrapers.standvirtual import StandvirtualScraper
   from app.scrapers.olx import OlxScraper
   from app.scrapers.custojusto import CustoJustoScraper
   from app.scoring import score_listings

   engine = create_engine("sqlite:///:memory:")
   Base.metadata.create_all(engine)
   session = sessionmaker(bind=engine, expire_on_commit=False)()
   watch = crud.create_watch(session, brand="Yamaha", model="MT-07")
   filters = WatchFilters(brand="Yamaha", model="MT-07", price_min=4500, price_max=7500, year_min=2018, year_max=2024, km_min=0, km_max=30000)

   for scraper in [StandvirtualScraper(), OlxScraper(), CustoJustoScraper()]:
       for item in scraper.fetch(filters):
           crud.upsert_listing(session, watch.id, source=item.source, external_id=item.external_id, title=item.title, price=item.price, url=item.url, year=item.year, km=item.km)

   listings = crud.get_listings_for_watch(session, watch.id)
   scores = score_listings(listings)
   ranked = sorted(listings, key=lambda listing: scores[listing.id].percentile)
   for listing in ranked:
       print(scores[listing.id].bucket, listing.price, listing.year, listing.km, listing.title)
   ```
   Read through the printed list top to bottom — the "great" listings at the top should look like real bargains for their year/km to your own eye, and "overpriced" at the bottom should look like the worst-value listings, not necessarily the most expensive ones.

3. **A real bug this checkpoint's spot-check caught, that the unit tests didn't:** the first version of the scoring code compared listings inconsistently — a listing missing `km` (true of every CustoJusto listing, which never exposes a structured mileage field) fell back to being ranked by its raw price in euros, while every other listing was ranked by *how far its price was from what's expected for its year/km* (a much smaller number). That silently sorted all CustoJusto listings to the bottom regardless of whether they were actually good deals. Only visible by looking at real output — fixed so every listing gets an expected-price estimate from the best model available (year+km, or year alone, or the pool's median price as a last resort) before ranking.

---

*(Checkpoint 5 onward will get their own section here as we build them.)*
