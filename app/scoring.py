from dataclasses import dataclass

import numpy as np

from app.models import Listing

GREAT = "great"
GOOD = "good"
FAIR = "fair"
OVERPRICED = "overpriced"

_BUCKET_ORDER = [OVERPRICED, FAIR, GOOD, GREAT]

# A regression needs enough data to mean anything, and enough of the pool
# actually having the field, or it'd be fit on a small, unrepresentative
# slice - real listings frequently lack km (e.g. CustoJusto never exposes it)
# or cc/power, so this has to degrade gracefully rather than error out.
_MIN_LISTINGS_FOR_REGRESSION = 4
_MIN_COVERAGE_FOR_REGRESSION = 0.6


@dataclass
class ListingScore:
    listing_id: int
    percentile: float  # 0 = best value in the pool, 1 = worst
    bucket: str
    price_dropped: bool


def _fit_model(listings: list[Listing], feature_fns: list) -> dict[int, float]:
    """Fits price ~ features by least squares over whichever listings have
    all of them, returning a predicted price per listing id. Empty if there
    isn't enough data or the features have no variance to fit against.
    """
    if len(listings) < _MIN_LISTINGS_FOR_REGRESSION:
        return {}

    columns = [np.array([fn(item) for item in listings], dtype=float) for fn in feature_fns]
    if all(column.std() == 0 for column in columns):
        return {}

    design = np.column_stack([*columns, np.ones(len(listings))])
    prices = np.array([item.price for item in listings], dtype=float)
    coeffs, *_ = np.linalg.lstsq(design, prices, rcond=None)
    predicted = design @ coeffs
    return {item.id: float(pred) for item, pred in zip(listings, predicted, strict=True)}


def _fit_expected_prices(listings: list[Listing]) -> dict[int, float]:
    """Predicts a "fair" price per listing so every listing can be ranked on
    the same footing: price minus what's expected for its year/km, not raw
    price. Real listings are frequently missing fields (CustoJusto never
    exposes km at all), so this tries the best available model per listing
    rather than an all-or-nothing fit for the whole pool - a listing missing
    km still gets a year-only estimate instead of falling back to comparing
    its raw price (thousands of euros) against everyone else's residuals
    (tens to low hundreds), which would make it look arbitrarily worse.
    """
    n = len(listings)
    predictions: dict[int, float] = {}

    with_year_and_km = [item for item in listings if item.year is not None and item.km is not None]
    if len(with_year_and_km) >= _MIN_COVERAGE_FOR_REGRESSION * n:
        predictions.update(
            _fit_model(with_year_and_km, [lambda item: item.year, lambda item: item.km])
        )

    remaining = [item for item in listings if item.id not in predictions]
    with_year = [item for item in remaining if item.year is not None]
    if with_year:
        predictions.update(_fit_model(with_year, [lambda item: item.year]))

    remaining = [item for item in listings if item.id not in predictions]
    if remaining:
        median_price = float(np.median([item.price for item in listings]))
        predictions.update({item.id: median_price for item in remaining})

    return predictions


def _has_price_drop(listing: Listing) -> bool:
    history = listing.price_history
    if len(history) < 2:
        return False
    return listing.price < history[0].price


def _bump_bucket(bucket: str) -> str:
    index = _BUCKET_ORDER.index(bucket)
    return _BUCKET_ORDER[min(index + 1, len(_BUCKET_ORDER) - 1)]


def _bucket_for_percentile(percentile: float) -> str:
    if percentile <= 0.2:
        return GREAT
    if percentile <= 0.5:
        return GOOD
    if percentile <= 0.8:
        return FAIR
    return OVERPRICED


def score_listings(listings: list[Listing]) -> dict[int, ListingScore]:
    """Scores each listing relative only to the others in `listings` - callers
    are expected to pass one watch's active listings at a time, never a mix
    of different watches, so an MT-07 is never ranked against a CB500F.
    """
    if not listings:
        return {}

    expected_prices = _fit_expected_prices(listings)
    ranked = sorted(listings, key=lambda listing: listing.price - expected_prices[listing.id])
    n = len(ranked)

    scores: dict[int, ListingScore] = {}
    for index, listing in enumerate(ranked):
        percentile = index / (n - 1) if n > 1 else 0.0
        bucket = _bucket_for_percentile(percentile)
        price_dropped = _has_price_drop(listing)
        if price_dropped and bucket != GREAT:
            bucket = _bump_bucket(bucket)
        scores[listing.id] = ListingScore(
            listing_id=listing.id,
            percentile=percentile,
            bucket=bucket,
            price_dropped=price_dropped,
        )
    return scores
