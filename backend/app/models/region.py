from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.observation import Observation
    from app.models.analysis import AnalysisResult


class Region(Base, UUIDMixin, TimestampMixin):
    """Model for geographic regions of interest."""

    __tablename__ = "regions"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    geometry: Mapped[str] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="custom",
        index=True,
    )  # 'predefined', 'custom'
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    state_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )  # 'major_city', 'megacity', 'migration_hotspot'

    # Relationships
    observations: Mapped[list["Observation"]] = relationship(
        "Observation", back_populates="region", cascade="all, delete-orphan"
    )
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(
        "AnalysisResult", back_populates="region", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Region(id={self.id}, name={self.name}, type={self.type})>"
