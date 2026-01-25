from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AnalysisType = Literal["seasonal_change", "urban_growth", "migration", "covid_impact"]


class AnalysisRequest(BaseModel):
    """Schema for requesting a new analysis."""

    region_id: str
    analysis_type: AnalysisType
    start_date: date
    end_date: date
    parameters: dict[str, Any] | None = Field(
        None,
        description="Additional analysis parameters",
        json_schema_extra={
            "example": {
                "comparison_period": "winter_vs_summer",
                "baseline_year": 2019,
            }
        },
    )


class AnalysisStatus(BaseModel):
    """Schema for analysis status response."""

    id: str
    status: Literal["pending", "processing", "completed", "failed"]
    progress: float = Field(0.0, ge=0.0, le=100.0)
    message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AnalysisResults(BaseModel):
    """Schema for analysis results."""

    summary: dict[str, Any]
    metrics: dict[str, Any]
    visualizations: list[dict[str, Any]] | None = None
    methodology: str | None = None


class AnalysisResponse(BaseModel):
    """Schema for analysis response."""

    id: str
    region_id: str
    region_name: str
    analysis_type: AnalysisType
    start_date: date
    end_date: date
    results: AnalysisResults
    created_at: datetime

    class Config:
        from_attributes = True


class CompareRequest(BaseModel):
    """Schema for comparing two time periods."""

    region_id: str
    period_a_start: date
    period_a_end: date
    period_b_start: date
    period_b_end: date
    metrics: list[str] | None = None


class PeriodSummary(BaseModel):
    """Summary for a single period."""

    start_date: date
    end_date: date
    averages: dict[str, float]
    observation_count: int


class CompareResponse(BaseModel):
    """Response for period comparison."""

    region_id: str
    region_name: str
    period_a: PeriodSummary
    period_b: PeriodSummary
    change: dict[str, float]  # Percentage change for each metric
    change_absolute: dict[str, float]  # Absolute change
