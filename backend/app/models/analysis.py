from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.region import Region


class AnalysisResult(Base, UUIDMixin):
    """Model for pre-computed analysis results."""

    __tablename__ = "analysis_results"

    region_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("regions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 'seasonal_change', 'urban_growth', 'migration', 'covid_impact'
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    region: Mapped["Region"] = relationship("Region", back_populates="analysis_results")

    def __repr__(self) -> str:
        return f"<AnalysisResult(region_id={self.region_id}, type={self.analysis_type})>"
