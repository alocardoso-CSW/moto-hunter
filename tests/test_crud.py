import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import crud
from app.models import Base


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def test_create_and_get_watch_uses_default_sources(session):
    watch = crud.create_watch(session, brand="Yamaha", model="MT-07", price_min=4500, price_max=7000)

    assert watch.id is not None
    fetched = crud.get_watch(session, watch.id)
    assert fetched.brand == "Yamaha"
    assert fetched.model == "MT-07"
    assert fetched.sources == ["standvirtual", "olx", "custojusto", "autopt"]


def test_update_and_delete_watch(session):
    watch = crud.create_watch(session, brand="Honda", model="CB500F")

    updated = crud.update_watch(session, watch.id, price_max=5000)
    assert updated.price_max == 5000

    assert crud.delete_watch(session, watch.id) is True
    assert crud.get_watch(session, watch.id) is None


def test_delete_watch_returns_false_when_missing(session):
    assert crud.delete_watch(session, 9999) is False


def test_upsert_listing_creates_initial_price_history(session):
    watch = crud.create_watch(session, brand="Yamaha", model="MT-07")

    listing = crud.upsert_listing(
        session,
        watch.id,
        source="standvirtual",
        external_id="abc123",
        title="Yamaha MT-07 2019",
        price=5800,
        year=2019,
        km=24500,
        cc=689,
        power=75,
        fuel="Gasolina",
        location="Porto",
        url="https://standvirtual.com/anuncio/abc123",
    )

    assert len(listing.price_history) == 1
    assert listing.price_history[0].price == 5800


def test_upsert_listing_same_price_does_not_duplicate_history(session):
    watch = crud.create_watch(session, brand="Yamaha", model="MT-07")
    kwargs = dict(
        source="standvirtual",
        external_id="abc123",
        title="Yamaha MT-07 2019",
        price=5800,
        url="https://standvirtual.com/anuncio/abc123",
    )

    crud.upsert_listing(session, watch.id, **kwargs)
    crud.upsert_listing(session, watch.id, **kwargs)

    listing = crud.get_listings_for_watch(session, watch.id)[0]
    assert len(listing.price_history) == 1


def test_upsert_listing_price_drop_appends_history(session):
    watch = crud.create_watch(session, brand="Yamaha", model="MT-07")
    base_kwargs = dict(
        source="standvirtual",
        external_id="abc123",
        title="Yamaha MT-07 2019",
        url="https://standvirtual.com/anuncio/abc123",
    )

    crud.upsert_listing(session, watch.id, price=5800, **base_kwargs)
    crud.upsert_listing(session, watch.id, price=5500, **base_kwargs)

    listing = crud.get_listings_for_watch(session, watch.id)[0]
    assert listing.price == 5500
    assert [ph.price for ph in listing.price_history] == [5800, 5500]


def test_mark_inactive_listings(session):
    watch = crud.create_watch(session, brand="Yamaha", model="MT-07")
    crud.upsert_listing(
        session, watch.id, source="olx", external_id="1", title="A", price=100, url="u1"
    )
    crud.upsert_listing(
        session, watch.id, source="olx", external_id="2", title="B", price=200, url="u2"
    )

    count = crud.mark_inactive_listings(session, watch.id, {"olx": {"1"}})

    assert count == 1
    active = crud.get_listings_for_watch(session, watch.id, active_only=True)
    assert [listing.external_id for listing in active] == ["1"]


def test_get_listings_for_watch_active_only_false_includes_inactive(session):
    watch = crud.create_watch(session, brand="Yamaha", model="MT-07")
    crud.upsert_listing(
        session, watch.id, source="olx", external_id="1", title="A", price=100, url="u1"
    )
    crud.mark_inactive_listings(session, watch.id, {"olx": set()})

    assert crud.get_listings_for_watch(session, watch.id, active_only=True) == []
    assert len(crud.get_listings_for_watch(session, watch.id, active_only=False)) == 1
