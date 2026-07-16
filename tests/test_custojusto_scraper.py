from pathlib import Path

from app.scrapers.base import WatchFilters
from app.scrapers.custojusto import CustoJustoScraper, build_search_url, parse_search_html

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "custojusto_mt07_search.html"


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
    )
    base.update(overrides)
    return WatchFilters(**base)


def test_build_search_url_uses_brand_model_path_with_no_query_params():
    url, params = build_search_url(_filters())

    assert url == "https://www.custojusto.pt/portugal/veiculos/motos/yamaha/mt-07"
    assert params == {}


def test_parse_search_html_returns_raw_items_including_parts_and_off_model_matches():
    # parse_search_html itself does no filtering - CustoJustoScraper.fetch does.
    # This category page mixes in spare parts (a shock absorber, a windshield)
    # and related-but-different models (Tenere T7, XSR700), confirmed for real
    # against the live site.
    listings = parse_search_html(_load_fixture())

    assert len(listings) == 21
    titles = [listing.title for listing in listings]
    assert any("Amortecedor" in title for title in titles)  # a shock absorber, not a bike
    assert any("Tenere" in title for title in titles)
    assert any("Xsr700" in title for title in titles)


def test_parse_search_html_maps_fields_correctly_for_one_listing():
    listings = parse_search_html(_load_fixture())
    listing = next(item for item in listings if item.external_id == "44758292")

    assert listing.title == "Yamaha MT-07 Editon Moto Cage 2016 Potência 55 KW - 16"
    assert listing.price == 6850
    assert listing.year == 2016
    assert listing.url == (
        "https://www.custojusto.pt/braga/veiculos/motos/mota-de-estrada/"
        "yamaha-mt-07-editon-moto-cage--44758292"
    )
    assert listing.location == "Braga, Vila Verde, Marrancos e Arcozelo"
    # CustoJusto's list view has no structured mileage/cc/power/fuel fields
    assert listing.km is None
    assert listing.cc is None
    assert listing.power is None
    assert listing.fuel is None


def test_scraper_fetch_filters_parts_placeholders_and_off_model_matches(monkeypatch):
    import httpx2

    class FakeResponse:
        text = _load_fixture()

        def raise_for_status(self):
            pass

    monkeypatch.setattr(httpx2, "get", lambda *a, **k: FakeResponse())

    listings = CustoJustoScraper().fetch(_filters())

    titles = [listing.title for listing in listings]
    assert not any("Amortecedor" in title for title in titles)
    assert not any("Paravento" in title for title in titles)
    assert not any("Tenere" in title for title in titles)
    assert not any("Xsr700" in title for title in titles)
    assert all(listing.price >= 4500 for listing in listings)
    assert all(2018 <= listing.year <= 2024 for listing in listings)
    assert len(listings) == 4
