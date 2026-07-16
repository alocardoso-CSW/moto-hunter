import json
import re

from curl_cffi import requests as curl_requests

from app.scrapers.base import (
    ScrapedListing,
    Scraper,
    WatchFilters,
    matches_location,
    normalize_text,
)

BASE_URL = "https://www.olx.pt/carros-motos-e-barcos/motociclos-scooters"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_search_url(filters: WatchFilters) -> tuple[str, dict[str, int]]:
    """Returns the search URL and query params for the given filters.

    Unlike Standvirtual, OLX has no reliable structured brand/model filter for
    motorcycles (its "params" schema for an ad only has a "modelo" field, no
    brand field at all, and testing confirmed enum filters for this category
    don't behave as query params). So brand+model become OLX's own free-text
    search term instead, and `parse_search_html` applies a client-side model
    match afterwards to drop off-topic results the free-text search pulls in
    (e.g. a "Yamaha Tracer 7" showing up in an "mt-07" search).
    """
    query_slug = _slugify(f"{filters.brand} {filters.model}")
    url = f"{BASE_URL}/q-{query_slug}/"

    params: dict[str, int] = {}
    if filters.price_min is not None:
        params["search[filter_float_price:from]"] = filters.price_min
    if filters.price_max is not None:
        params["search[filter_float_price:to]"] = filters.price_max
    if filters.year_min is not None:
        params["search[filter_float_year:from]"] = filters.year_min
    if filters.year_max is not None:
        params["search[filter_float_year:to]"] = filters.year_max
    if filters.km_min is not None:
        params["search[filter_float_quilometros:from]"] = filters.km_min
    if filters.km_max is not None:
        params["search[filter_float_quilometros:to]"] = filters.km_max
    return url, params


def _extract_prerendered_state(html: str) -> dict:
    marker = "window.__PRERENDERED_STATE__="
    idx = html.find(marker)
    if idx == -1:
        raise ValueError("__PRERENDERED_STATE__ not found on OLX page")
    start = html.find('"', idx)
    decoder = json.JSONDecoder()
    inner_json_str, _ = decoder.raw_decode(html, start)
    return json.loads(inner_json_str)


def _parse_km(value: str | None) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return int(digits) if digits else None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_ad(ad: dict) -> ScrapedListing | None:
    price_info = (ad.get("price") or {}).get("regularPrice")
    if not price_info or price_info.get("value") is None:
        return None

    params = {p["key"]: p["value"] for p in ad.get("params", [])}
    location = ad.get("location") or {}
    photos = ad.get("photos") or []

    return ScrapedListing(
        source="olx",
        external_id=str(ad["id"]),
        title=ad["title"],
        price=int(price_info["value"]),
        url=ad["url"],
        year=_to_int(params.get("year")),
        km=_parse_km(params.get("quilometros")),
        # "cilindrada" is a bucketed range (e.g. "501 - 1000 cc"), not an exact
        # value, so left unset rather than guessing. Same for engine power,
        # which OLX doesn't expose as a structured field for motorcycles.
        cc=None,
        power=None,
        fuel=params.get("combustivel"),
        location=location.get("pathName"),
        image_url=photos[0] if photos else None,
    )


def parse_search_html(html: str) -> list[ScrapedListing]:
    """Pure parsing step, kept separate from the network call so tests can
    feed it a saved fixture instead of hitting the live site."""
    data = _extract_prerendered_state(html)
    ads = data.get("listing", {}).get("listing", {}).get("ads", [])
    listings = [_parse_ad(ad) for ad in ads]
    return [listing for listing in listings if listing is not None]


def _matches_model(listing: ScrapedListing, filters: WatchFilters) -> bool:
    """OLX's free-text search returns off-topic results (related models,
    accessories mentioning the model, etc.) - keep only listings whose title
    actually contains the requested model."""
    return normalize_text(filters.model) in normalize_text(listing.title)


class OlxScraper(Scraper):
    source_name = "olx"

    def fetch(self, filters: WatchFilters) -> list[ScrapedListing]:
        url, params = build_search_url(filters)
        # OLX's bot protection blocks plain Python HTTP clients (httpx2, requests)
        # by TLS fingerprint alone - confirmed by testing the same request with
        # curl (succeeds) vs httpx2 (403, even on the homepage). curl_cffi
        # impersonates a real browser's TLS handshake, which is accepted.
        response = curl_requests.get(url, params=params, impersonate="chrome", timeout=15)
        response.raise_for_status()
        listings = parse_search_html(response.text)

        seen_ids: set[str] = set()
        deduped = []
        for listing in listings:
            if listing.external_id in seen_ids:
                continue
            seen_ids.add(listing.external_id)
            deduped.append(listing)

        return [
            listing
            for listing in deduped
            if _matches_model(listing, filters) and matches_location(listing, filters)
        ]
