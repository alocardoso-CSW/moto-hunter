from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DEFAULT_SOURCES, Listing, PriceHistory, Watch, utcnow


def create_watch(
    session: Session,
    *,
    brand: str,
    model: str,
    price_min: int | None = None,
    price_max: int | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    km_min: int | None = None,
    km_max: int | None = None,
    location: str | None = None,
    sources: list[str] | None = None,
) -> Watch:
    watch = Watch(
        brand=brand,
        model=model,
        price_min=price_min,
        price_max=price_max,
        year_min=year_min,
        year_max=year_max,
        km_min=km_min,
        km_max=km_max,
        location=location,
        sources=sources if sources is not None else list(DEFAULT_SOURCES),
    )
    session.add(watch)
    session.commit()
    session.refresh(watch)
    return watch


def get_watch(session: Session, watch_id: int) -> Watch | None:
    return session.get(Watch, watch_id)


def list_watches(session: Session) -> list[Watch]:
    return list(session.scalars(select(Watch).order_by(Watch.id)))


def update_watch(session: Session, watch_id: int, **fields) -> Watch | None:
    watch = session.get(Watch, watch_id)
    if watch is None:
        return None
    for key, value in fields.items():
        setattr(watch, key, value)
    session.commit()
    session.refresh(watch)
    return watch


def delete_watch(session: Session, watch_id: int) -> bool:
    watch = session.get(Watch, watch_id)
    if watch is None:
        return False
    session.delete(watch)
    session.commit()
    return True


def mark_watch_run(session: Session, watch_id: int) -> None:
    watch = session.get(Watch, watch_id)
    if watch is not None:
        watch.last_run_at = utcnow()
        session.commit()


def upsert_listing(
    session: Session,
    watch_id: int,
    *,
    source: str,
    external_id: str,
    title: str,
    price: int,
    url: str,
    year: int | None = None,
    km: int | None = None,
    cc: int | None = None,
    power: int | None = None,
    fuel: str | None = None,
    location: str | None = None,
    image_url: str | None = None,
) -> Listing:
    """Insert a new listing, or update an existing one matched by
    (watch_id, source, external_id). A PriceHistory row is appended
    whenever the price actually changes."""
    existing = session.scalar(
        select(Listing).where(
            Listing.watch_id == watch_id,
            Listing.source == source,
            Listing.external_id == external_id,
        )
    )
    now = utcnow()

    if existing is None:
        listing = Listing(
            watch_id=watch_id,
            source=source,
            external_id=external_id,
            title=title,
            price=price,
            year=year,
            km=km,
            cc=cc,
            power=power,
            fuel=fuel,
            location=location,
            url=url,
            image_url=image_url,
            first_seen=now,
            last_seen=now,
            is_active=True,
        )
        session.add(listing)
        session.flush()
        session.add(PriceHistory(listing_id=listing.id, price=price, recorded_at=now))
        session.commit()
        session.refresh(listing)
        return listing

    price_changed = existing.price != price
    existing.title = title
    existing.price = price
    existing.year = year
    existing.km = km
    existing.cc = cc
    existing.power = power
    existing.fuel = fuel
    existing.location = location
    existing.url = url
    existing.image_url = image_url
    existing.last_seen = now
    existing.is_active = True
    if price_changed:
        session.add(PriceHistory(listing_id=existing.id, price=price, recorded_at=now))
    session.commit()
    session.refresh(existing)
    return existing


def get_listings_for_watch(
    session: Session, watch_id: int, *, active_only: bool = True
) -> list[Listing]:
    stmt = select(Listing).where(Listing.watch_id == watch_id)
    if active_only:
        stmt = stmt.where(Listing.is_active.is_(True))
    return list(session.scalars(stmt.order_by(Listing.price)))


def mark_inactive_listings(
    session: Session, watch_id: int, seen_external_ids_by_source: dict[str, set[str]]
) -> int:
    """Call after a scrape run: any previously-active listing not present
    in this run's results (per source) is flagged inactive. Returns how
    many were newly marked inactive."""
    active = session.scalars(
        select(Listing).where(Listing.watch_id == watch_id, Listing.is_active.is_(True))
    )
    count = 0
    for listing in active:
        seen_ids = seen_external_ids_by_source.get(listing.source, set())
        if listing.external_id not in seen_ids:
            listing.is_active = False
            count += 1
    session.commit()
    return count
