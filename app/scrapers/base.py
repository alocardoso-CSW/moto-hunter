from dataclasses import dataclass


@dataclass
class WatchFilters:
    """The subset of a Watch that a scraper needs to run a search."""

    brand: str
    model: str
    price_min: int | None = None
    price_max: int | None = None
    year_min: int | None = None
    year_max: int | None = None
    km_min: int | None = None
    km_max: int | None = None
    location: str | None = None


@dataclass
class ScrapedListing:
    """A single listing as returned by a scraper, before it's stored."""

    source: str
    external_id: str
    title: str
    price: int
    url: str
    year: int | None = None
    km: int | None = None
    cc: int | None = None
    power: int | None = None
    fuel: str | None = None
    location: str | None = None
    image_url: str | None = None


class Scraper:
    """Common interface every marketplace scraper implements."""

    source_name: str

    def fetch(self, filters: WatchFilters) -> list[ScrapedListing]:
        raise NotImplementedError
