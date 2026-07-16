import json
import re

import httpx2

from app.scrapers.base import (
    ScrapedListing,
    Scraper,
    WatchFilters,
    matches_location,
    normalize_text,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

BASE_URL = "https://www.custojusto.pt/portugal/veiculos/motos"

# CustoJusto's category also carries spare parts/accessories tagged with a
# matching brand+model (a shock absorber "for a MT-07", etc). There's no
# structured field to tell those apart from an actual motorcycle-for-sale, so
# a plausibility floor on price is used instead - real bikes in this market
# are priced well above this even in poor condition; accessories aren't.
MIN_PLAUSIBLE_BIKE_PRICE = 300


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_search_url(filters: WatchFilters) -> tuple[str, dict]:
    """Returns the search URL for the given filters.

    Confirmed empirically: CustoJusto's brand/model URL path
    (/motos/{brand}/{model}) works and returns properly filtered results, but
    its "structure" query parameter (used for price/year/km/text filters) is
    silently ignored when sent as a plain query string - it's only ever
    populated server-side, not read from the URL. With no working numeric
    filter, and total result counts for a single model being small (an
    unfiltered CustoJusto brand/model page tops out at ~40 lightly-paginated
    results), price/year/km filters are applied client-side in `fetch`
    instead, same as location already is on every scraper.
    """
    brand_slug = _slugify(filters.brand)
    model_slug = _slugify(filters.model)
    url = f"{BASE_URL}/{brand_slug}/{model_slug}"
    return url, {}


def _extract_next_data(html: str) -> dict:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if match is None:
        raise ValueError("__NEXT_DATA__ script tag not found on CustoJusto page")
    return json.loads(match.group(1))


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_item(item: dict) -> ScrapedListing:
    location_names = item.get("locationNames") or {}
    location_parts = [
        location_names.get(part)
        for part in ("district", "county", "parish")
        if location_names.get(part)
    ]

    return ScrapedListing(
        source="custojusto",
        external_id=str(item["listID"]),
        title=item["title"],
        price=int(item["price"]),
        url=f"https://www.custojusto.pt{item['url']}",
        year=_to_int((item.get("params") or {}).get("regdate")),
        # CustoJusto's list view only ever exposes "regdate" as a structured
        # param - no mileage/engine-capacity/power/fuel field, even though
        # those presumably exist on the individual ad page. Left unset rather
        # than scraping every ad's detail page, which Checkpoint 2/3 kept out
        # of scope for request-volume reasons.
        km=None,
        cc=None,
        power=None,
        fuel=None,
        location=", ".join(location_parts) or None,
        image_url=item.get("imageFullURL"),
    )


def parse_search_html(html: str) -> list[ScrapedListing]:
    """Pure parsing step, kept separate from the network call so tests can
    feed it a saved fixture instead of hitting the live site."""
    next_data = _extract_next_data(html)
    items = next_data["props"]["pageProps"].get("listItems") or []
    return [_parse_item(item) for item in items]


def _matches_model(listing: ScrapedListing, filters: WatchFilters) -> bool:
    return normalize_text(filters.model) in normalize_text(listing.title)


def _matches_price_range(listing: ScrapedListing, filters: WatchFilters) -> bool:
    if listing.price < MIN_PLAUSIBLE_BIKE_PRICE:
        return False
    if filters.price_min is not None and listing.price < filters.price_min:
        return False
    if filters.price_max is not None and listing.price > filters.price_max:
        return False
    return True


def _matches_year_range(listing: ScrapedListing, filters: WatchFilters) -> bool:
    if listing.year is None:
        return True  # can't verify - don't hide a possibly-relevant listing
    if filters.year_min is not None and listing.year < filters.year_min:
        return False
    if filters.year_max is not None and listing.year > filters.year_max:
        return False
    return True


class CustoJustoScraper(Scraper):
    source_name = "custojusto"

    def fetch(self, filters: WatchFilters) -> list[ScrapedListing]:
        url, params = build_search_url(filters)
        response = httpx2.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
            follow_redirects=True,
        )
        response.raise_for_status()
        listings = parse_search_html(response.text)

        return [
            listing
            for listing in listings
            if _matches_model(listing, filters)
            and _matches_price_range(listing, filters)
            and _matches_year_range(listing, filters)
            and matches_location(listing, filters)
        ]
