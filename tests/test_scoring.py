from app import crud
from app.scoring import GOOD, GREAT, OVERPRICED, score_listings


def _make_watch(session):
    return crud.create_watch(session, brand="Yamaha", model="MT-07")


def test_empty_pool_returns_no_scores(session):
    assert score_listings([]) == {}


def test_single_listing_is_scored_great(session):
    watch = _make_watch(session)
    listing = crud.upsert_listing(
        session, watch.id, source="standvirtual", external_id="1", title="A", price=6000, url="u"
    )

    scores = score_listings([listing])

    assert scores[listing.id].percentile == 0.0
    assert scores[listing.id].bucket == GREAT


def test_cheap_outlier_lands_in_great_bucket_when_no_year_km_adjustment_applies(session):
    watch = _make_watch(session)
    # same year/km across the board (no variance) -> regression can't fit
    # anything, so this exercises plain price ranking
    prices = [4000, 6000, 6200, 6500, 7000]
    listings = [
        crud.upsert_listing(
            session,
            watch.id,
            source="standvirtual",
            external_id=str(i),
            title=f"listing {i}",
            price=price,
            year=2022,
            km=10000,
            url="u",
        )
        for i, price in enumerate(prices)
    ]

    scores = score_listings(listings)

    cheapest = next(listing for listing in listings if listing.price == 4000)
    priciest = next(listing for listing in listings if listing.price == 7000)
    assert scores[cheapest.id].percentile == 0.0
    assert scores[cheapest.id].bucket == GREAT
    assert scores[priciest.id].percentile == 1.0
    assert scores[priciest.id].bucket == OVERPRICED


def test_price_drop_bumps_bucket_up_one_level(session):
    watch = _make_watch(session)
    prices = [4000, 5000, 6000, 7000, 8000]
    listings = [
        crud.upsert_listing(
            session,
            watch.id,
            source="standvirtual",
            external_id=str(i),
            title=f"listing {i}",
            price=price,
            year=2022,
            km=10000,
            url="u",
        )
        for i, price in enumerate(prices)
    ]

    middle = next(listing for listing in listings if listing.price == 6000)
    baseline_bucket = score_listings(listings)[middle.id].bucket

    # drop its price without changing rank order relative to the others enough
    # to matter for this assertion - just confirm the bump happens
    dropped = crud.upsert_listing(
        session,
        watch.id,
        source="standvirtual",
        external_id=middle.external_id,
        title=middle.title,
        price=middle.price - 500,
        year=middle.year,
        km=middle.km,
        url="u",
    )
    listings = crud.get_listings_for_watch(session, watch.id)

    scores = score_listings(listings)

    assert scores[dropped.id].price_dropped is True
    assert baseline_bucket != GREAT  # sanity check the test setup is meaningful
    bucket_order = [OVERPRICED, "fair", GOOD, GREAT]
    assert bucket_order.index(scores[dropped.id].bucket) > bucket_order.index(baseline_bucket)


def test_year_km_adjustment_ranks_newer_lower_km_bike_above_same_priced_older_one(session):
    watch = _make_watch(session)
    same_price = 6000
    listings = [
        # the pair we care about: identical price, very different condition
        crud.upsert_listing(
            session, watch.id, source="standvirtual", external_id="new",
            title="new low-km", price=same_price, year=2023, km=2000, url="u",
        ),
        crud.upsert_listing(
            session, watch.id, source="standvirtual", external_id="old",
            title="old high-km", price=same_price, year=2016, km=40000, url="u",
        ),
        # extra spread so the regression has real signal to fit
        crud.upsert_listing(
            session, watch.id, source="standvirtual", external_id="e1",
            title="e1", price=7500, year=2023, km=3000, url="u",
        ),
        crud.upsert_listing(
            session, watch.id, source="standvirtual", external_id="e2",
            title="e2", price=4000, year=2016, km=42000, url="u",
        ),
        crud.upsert_listing(
            session, watch.id, source="standvirtual", external_id="e3",
            title="e3", price=5000, year=2019, km=20000, url="u",
        ),
    ]

    scores = score_listings(listings)

    new_low_km = next(listing for listing in listings if listing.external_id == "new")
    old_high_km = next(listing for listing in listings if listing.external_id == "old")

    # same sticker price, but the newer/lower-km bike is the better value
    assert scores[new_low_km.id].percentile < scores[old_high_km.id].percentile


def test_falls_back_to_year_only_model_when_km_is_missing_entirely(session):
    # mirrors real CustoJusto listings, which never expose a structured km
    # field. Cheaper in absolute terms isn't the same as a better deal here:
    # "old" has a lower sticker price than "new", but is expensive for how
    # old it is, while "new" is cheap for how new it is - a year-only model
    # should catch that even with no km data at all, rather than falling
    # back to comparing raw prices (which would rank "old" as the better
    # deal purely for being a smaller number).
    watch = _make_watch(session)
    listings = [
        crud.upsert_listing(
            session, watch.id, source="custojusto", external_id="new",
            title="new", price=6000, year=2024, km=None, url="u",
        ),
        crud.upsert_listing(
            session, watch.id, source="custojusto", external_id="old",
            title="old", price=5500, year=2016, km=None, url="u",
        ),
        crud.upsert_listing(
            session, watch.id, source="custojusto", external_id="e1",
            title="e1", price=7500, year=2024, km=None, url="u",
        ),
        crud.upsert_listing(
            session, watch.id, source="custojusto", external_id="e2",
            title="e2", price=4000, year=2016, km=None, url="u",
        ),
        crud.upsert_listing(
            session, watch.id, source="custojusto", external_id="e3",
            title="e3", price=5500, year=2020, km=None, url="u",
        ),
    ]

    scores = score_listings(listings)

    new = next(listing for listing in listings if listing.external_id == "new")
    old = next(listing for listing in listings if listing.external_id == "old")

    assert new.price > old.price  # cheaper in absolute terms isn't the point
    assert scores[new.id].percentile < scores[old.id].percentile  # but the better value
