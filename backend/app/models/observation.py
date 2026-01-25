from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.region import Region


class Observation(Base, UUIDMixin):
    """Model for temporal satellite observations."""

    __tablename__ = "observations"

    region_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("regions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 'ndvi', 'nightlights', 'urban_density', 'parking'
    value: Mapped[float] = mapped_column(Float, nullable=False)
    raster_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    region: Mapped["Region"] = relationship("Region", back_populates="observations")

    def __repr__(self) -> str:
        return f"<Observation(region_id={self.region_id}, date={self.date}, metric={self.metric})>"
