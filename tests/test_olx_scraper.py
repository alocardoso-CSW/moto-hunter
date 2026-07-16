from pathlib import Path

from app.scrapers.base import WatchFilters
from app.scrapers.olx import OlxScraper, build_search_url, parse_search_html

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "olx_mt07_search.html"


def _load_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _filters(**overrides) -> WatchFilters:
    base = dict(
        brand="Yamaha",
        model="MT-07",
        price_min=4500,
        price_max=7000,
        year_min=2018,
        year_max=2024,
        km_min=0,
        km_max=30000,
    )
    base.update(overrides)
    return WatchFilters(**base)


def test_build_search_url_uses_free_text_query_plus_numeric_filters():
    url, params = build_search_url(_filters())

    assert url == "https://www.olx.pt/carros-motos-e-barcos/motociclos-scooters/q-yamaha-mt-07/"
    assert params == {
        "search[filter_float_price:from]": 4500,
        "search[filter_float_price:to]": 7000,
        "search[filter_float_year:from]": 2018,
        "search[filter_float_year:to]": 2024,
        "search[filter_float_quilometros:from]": 0,
        "search[filter_float_quilometros:to]": 30000,
    }


def test_build_search_url_omits_unset_filters():
    url, params = build_search_url(WatchFilters(brand="Honda", model="CB500F"))

    assert url == "https://www.olx.pt/carros-motos-e-barcos/motociclos-scooters/q-honda-cb500f/"
    assert params == {}


def test_parse_search_html_returns_raw_ads_including_off_topic_matches():
    # parse_search_html itself does no filtering - that's OlxScraper.fetch's job.
    # OLX's free-text search returns some off-topic results (see below), so the
    # raw parse should include them.
    listings = parse_search_html(_load_fixture())

    assert len(listings) == 41
    titles = [listing.title for listing in listings]
    assert any("XSR" in title for title in titles)
    assert any("Tracer" in title for title in titles)


def test_parse_search_html_maps_fields_correctly_for_one_listing():
    listings = parse_search_html(_load_fixture())
    listing = next(item for item in listings if item.external_id == "672327265")

    assert listing.title == "Yamaha MT-07 35KW"
    assert listing.price == 6900
    assert listing.year == 2023
    assert listing.km == 5603
    assert listing.fuel == "Gasolina"
    assert listing.cc is None  # OLX only exposes a bucketed range, not exact cc
    assert listing.power is None  # not exposed at all for motorcycles
    assert listing.url.startswith("https://www.olx.pt/d/anuncio/")
    assert listing.image_url is not None and listing.image_url.startswith("https://")


def test_scraper_fetch_filters_out_off_topic_matches_and_dedupes(monkeypatch):
    # OLX's free-text search for "yamaha mt-07" also surfaces a "Yamaha XSR 700"
    # (duplicated as a promoted slot), a bare "Yamaha XSR", and a "Tracer 7" -
    # none of which are actually an MT-07. The scraper must filter these out.
    from curl_cffi import requests as curl_requests

    class FakeResponse:
        text = _load_fixture()

        def raise_for_status(self):
            pass

    monkeypatch.setattr(curl_requests, "get", lambda *a, **k: FakeResponse())

    listings = OlxScraper().fetch(_filters())

    titles = [listing.title for listing in listings]
    assert not any("XSR" in title for title in titles)
    assert not any("Tracer" in title for title in titles)
    assert len(listings) == len({listing.external_id for listing in listings})
    assert len(listings) == 37
