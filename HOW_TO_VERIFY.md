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

5. **(Optional, for later) A friendlier way to browse the database:** everything above happens in a file at `data\moto_hunter.db`. There's no lightweight command-line SQLite browser installed, so if you'd like a visual way to click through tables instead of typing Python, a free tool called **DB Browser for SQLite** (https://sqlitebrowser.org/) can open that file directly — let me know if you want me to install it.

---

*(Checkpoint 2 onward will get their own section here as we build them.)*
