from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DEFAULT_SOURCES = ["standvirtual", "olx", "custojusto"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Watch(Base):
    __tablename__ = "watches"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(80))
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    km_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    km_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sources: Mapped[list[str]] = mapped_column(JSON, default=lambda: list(DEFAULT_SOURCES))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    listings: Mapped[list["Listing"]] = relationship(
        back_populates="watch", cascade="all, delete-orphan"
    )


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("watch_id", "source", "external_id", name="uq_listing_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    watch_id: Mapped[int] = mapped_column(ForeignKey("watches.id"))
    source: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(200))
    price: Mapped[int] = mapped_column(Integer)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fuel: Mapped[str | None] = mapped_column(String(40), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    url: Mapped[str] = mapped_column(String(500))
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    watch: Mapped["Watch"] = relationship(back_populates="listings")
    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="PriceHistory.recorded_at",
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    price: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    listing: Mapped["Listing"] = relationship(back_populates="price_history")
