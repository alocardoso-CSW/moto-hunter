from pathlib import Path

from app.scrapers.base import WatchFilters
from app.scrapers.standvirtual import build_search_url, parse_search_html

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "standvirtual_mt07_search.html"


def _load_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_build_search_url_encodes_brand_model_and_all_filters():
    filters = WatchFilters(
        brand="Yamaha",
        model="MT-07",
        price_min=4500,
        price_max=7000,
        year_min=2018,
        year_max=2024,
        km_min=0,
        km_max=30000,
    )

    url, params = build_search_url(filters)

    assert url == "https://www.standvirtual.com/motos/yamaha/mt-07"
    assert params == {
        "search[filter_float_price:from]": 4500,
        "search[filter_float_price:to]": 7000,
        "search[filter_float_first_registration_year:from]": 2018,
        "search[filter_float_first_registration_year:to]": 2024,
        "search[filter_float_mileage:from]": 0,
        "search[filter_float_mileage:to]": 30000,
    }


def test_build_search_url_omits_unset_filters():
    filters = WatchFilters(brand="Honda", model="CB500F")

    url, params = build_search_url(filters)

    assert url == "https://www.standvirtual.com/motos/honda/cb500f"
    assert params == {}


def test_parse_search_html_returns_all_listings_from_fixture():
    listings = parse_search_html(_load_fixture())

    assert len(listings) == 11
    assert all(listing.source == "standvirtual" for listing in listings)
    # every listing in this fixture matched a MT-07 search with a price/year/km filter
    assert all(4500 <= listing.price <= 7000 for listing in listings)
    assert all(2018 <= listing.year <= 2024 for listing in listings)
    assert all(0 <= listing.km <= 30000 for listing in listings)


def test_parse_search_html_maps_fields_correctly_for_one_listing():
    listings = parse_search_html(_load_fixture())
    listing = next(item for item in listings if item.external_id == "8097577605")

    assert listing.title == "Yamaha MT-07"
    assert listing.price == 6290
    assert listing.year == 2022
    assert listing.km == 12000
    assert listing.cc == 689
    assert listing.power == 73
    assert listing.location == "Barcelos, Braga"
    assert listing.url == "https://www.standvirtual.com/motos/anuncio/yamaha-mt-07-ID8Q0BQp.html"
    assert listing.image_url is not None and listing.image_url.startswith("https://")


def test_parse_search_html_handles_missing_optional_parameters():
    # this listing in the fixture has no engine_capacity/engine_power parameters
    listings = parse_search_html(_load_fixture())
    listing = next(item for item in listings if item.external_id == "8097585907")

    assert listing.cc is None
    assert listing.power is None
    # required fields are still present
    assert listing.price == 6990
    assert listing.year == 2022
