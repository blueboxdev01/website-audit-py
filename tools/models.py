from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BusinessResult:
    """Minimal business info returned from a SERP search."""
    place_id: str
    name: str
    address: str
    phone: Optional[str]
    website: Optional[str]
    primary_category: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    gps: Optional[tuple[float, float]]  # (lat, lng)


@dataclass
class PlaceDetails:
    """Full GBP detail snapshot used for analysis."""
    place_id: str
    name: str
    address: str
    phone: Optional[str]
    website: Optional[str]
    primary_category: Optional[str]
    secondary_categories: list[str] = field(default_factory=list)
    rating: Optional[float] = None
    review_count: int = 0
    has_hours: bool = False
    has_description: bool = False
    has_posts: bool = False
    has_qa: bool = False
    services_listed: int = 0
    attributes: list[str] = field(default_factory=list)
    latest_review_date: Optional[str] = None


@dataclass
class Signals:
    """Normalized, comparable signals for one business."""
    place_id: str
    name: str
    profile_completeness: float  # 0.0 to 1.0
    category_count: int
    review_count: int
    rating: float
    has_posts: bool
    has_qa: bool
    services_listed: int
    attribute_count: int
    local_pack_rank: Optional[int]  # None if not in top 20


@dataclass
class Gap:
    """One identified gap between prospect and competitors."""
    signal: str
    prospect_value: float
    competitor_best: float
    competitor_avg: float
    impact: str  # "high", "medium", "low"
    recommendation: str


@dataclass
class AnalysisResult:
    """Output of gap_analyzer consumed by report_generator."""
    prospect_name: str
    prospect_city: str
    target_query: str
    keyword: str
    prospect_signals: Signals
    competitor_signals: list[Signals]
    prospect_rank: Optional[int]
    gaps: list[Gap]
    executive_summary: list[str]  # 3-5 bullet points
