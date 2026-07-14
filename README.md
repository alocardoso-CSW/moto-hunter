# moto-hunter

A small web app that watches Portuguese motorcycle classifieds (Standvirtual,
OLX, CustoJusto, Auto.pt, and optionally Facebook Marketplace) for whatever
bikes you configure, scores what it finds against its own current market, and
shows results as photo cards. You trigger runs manually — there's no
background schedule.

See `DESIGN.md` and `DEVELOPMENT_PLAN.md` for the full design and build plan.

## Running locally

```
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/health to confirm it's up, or
http://127.0.0.1:8000/docs for the interactive API docs.

## Tests

```
pytest
ruff check .
```
