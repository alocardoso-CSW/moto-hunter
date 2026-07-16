import json
import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import ScrapedListing, Scraper, WatchFilters

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

BASE_URL = "https://www.standvirtual.com/motos"


def _slugify(value: str) -> str:
    """Best-effort brand/model -> URL slug (e.g. "Yamaha" -> "yamaha").

    Confirmed correct for Yamaha/MT-07. Not guaranteed to match Standvirtual's
    canonical slug for every brand/model (e.g. multi-word or accented names) -
    that gets verified per-brand as more scrapers are added in Checkpoint 3.
    """
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_search_url(filters: WatchFilters) -> tuple[str, dict[str, int]]:
    """Returns the search URL and query params for the given filters.

    Location is deliberately not translated into a query param here - Standvirtual
    filters by internal city/region IDs, which would need a name-to-ID lookup table.
    Location is instead applied client-side in `fetch`.
    """
    brand_slug = _slugify(filters.brand)
    model_slug = _slugify(filters.model)
    url = f"{BASE_URL}/{brand_slug}/{model_slug}"

    params: dict[str, int] = {}
    if filters.price_min is not None:
        params["search[filter_float_price:from]"] = filters.price_min
    if filters.price_max is not None:
        params["search[filter_float_price:to]"] = filters.price_max
    if filters.year_min is not None:
        params["search[filter_float_first_registration_year:from]"] = filters.year_min
    if filters.year_max is not None:
        params["search[filter_float_first_registration_year:to]"] = filters.year_max
    if filters.km_min is not None:
        params["search[filter_float_mileage:from]"] = filters.km_min
    if filters.km_max is not None:
        params["search[filter_float_mileage:to]"] = filters.km_max
    return url, params


def _extract_next_data(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag is None or tag.string is None:
        raise ValueError("__NEXT_DATA__ script tag not found on Standvirtual page")
    return json.loads(tag.string)


def _find_advert_search(next_data: dict) -> dict:
    urql_state = next_data["props"]["pageProps"].get("urqlState", {})
    for entry in urql_state.values():
        payload = json.loads(entry["data"])
        if "advertSearch" in payload:
            return payload["advertSearch"]
    raise ValueError("advertSearch not found in Standvirtual page data")


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_listing(node: dict) -> ScrapedListing:
    params = {p["key"]: p["value"] for p in node.get("parameters", [])}

    location = node.get("location") or {}
    location_parts = []
    if location.get("city"):
        location_parts.append(location["city"]["name"])
    if location.get("region"):
        location_parts.append(location["region"]["name"])

    thumbnail = node.get("thumbnail") or {}

    return ScrapedListing(
        source="standvirtual",
        external_id=node["id"],
        title=node["title"],
        price=int(node["price"]["amount"]["units"]),
        url=node["url"],
        year=_to_int(params.get("first_registration_year")),
        km=_to_int(params.get("mileage")),
        cc=_to_int(params.get("engine_capacity")),
        power=_to_int(params.get("engine_power")),
        fuel=params.get("fuel_type"),
        location=", ".join(location_parts) or None,
        image_url=thumbnail.get("x2") or thumbnail.get("x1"),
    )


def parse_search_html(html: str) -> list[ScrapedListing]:
    """Pure parsing step, kept separate from the network call so tests can
    feed it a saved fixture instead of hitting the live site."""
    next_data = _extract_next_data(html)
    advert_search = _find_advert_search(next_data)
    return [_parse_listing(edge["node"]) for edge in advert_search.get("edges", [])]


def _matches_location(listing: ScrapedListing, filters: WatchFilters) -> bool:
    if not filters.location:
        return True
    if not listing.location:
        return False
    return filters.location.strip().lower() in listing.location.lower()


class StandvirtualScraper(Scraper):
    source_name = "standvirtual"

    def fetch(self, filters: WatchFilters) -> list[ScrapedListing]:
        url, params = build_search_url(filters)
        response = httpx.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
            follow_redirects=True,
        )
        response.raise_for_status()
        listings = parse_search_html(response.text)
        return [listing for listing in listings if _matches_location(listing, filters)]
