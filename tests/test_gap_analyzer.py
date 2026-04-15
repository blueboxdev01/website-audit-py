import pytest

from tools.gap_analyzer import analyze, compute_signals
from tools.models import PlaceDetails


def make_details(**overrides) -> PlaceDetails:
    defaults = dict(
        place_id="pid",
        name="Sample Biz",
        address="1 Main St",
        phone="555-0000",
        website="https://example.com",
        primary_category="Day care center",
        secondary_categories=["Preschool"],
        rating=4.0,
        review_count=50,
        has_hours=True,
        has_description=True,
        has_posts=False,
        has_qa=False,
        services_listed=2,
        attributes=["Wheelchair accessible entrance"],
        latest_review_date="1 week ago",
    )
    defaults.update(overrides)
    return PlaceDetails(**defaults)


def test_compute_signals_profile_completeness_full():
    details = make_details()
    signals = compute_signals(details, local_pack_rank=4)

    assert signals.profile_completeness == 1.0
    assert signals.category_count == 2
    assert signals.review_count == 50
    assert signals.rating == 4.0
    assert signals.local_pack_rank == 4


def test_compute_signals_profile_completeness_partial():
    details = make_details(phone=None, website=None, has_description=False)
    signals = compute_signals(details, local_pack_rank=None)

    assert 0.0 < signals.profile_completeness < 1.0
    assert signals.local_pack_rank is None


def test_analyze_flags_review_gap():
    prospect = make_details(review_count=10, rating=3.8)
    competitors = [
        make_details(place_id="c1", review_count=200, rating=4.8),
        make_details(place_id="c2", review_count=180, rating=4.6),
        make_details(place_id="c3", review_count=145, rating=4.5),
    ]

    result = analyze(
        prospect_name="Sunny Days Daycare",
        prospect_city="Newark, NJ",
        target_query="day care center Newark NJ",
        prospect_details=prospect,
        competitor_details=competitors,
        prospect_rank=4,
    )

    review_gaps = [g for g in result.gaps if g.signal == "reviews"]
    assert len(review_gaps) == 1
    assert review_gaps[0].impact == "high"
    assert "review" in review_gaps[0].recommendation.lower()
    assert result.prospect_rank == 4
    assert len(result.executive_summary) >= 3


def test_analyze_handles_prospect_not_ranking():
    prospect = make_details(review_count=5)
    competitors = [make_details(place_id=f"c{i}", review_count=100) for i in range(3)]

    result = analyze(
        prospect_name="Test Biz",
        prospect_city="Newark, NJ",
        target_query="day care center Newark NJ",
        prospect_details=prospect,
        competitor_details=competitors,
        prospect_rank=None,
    )

    assert result.prospect_rank is None
    assert any("not currently ranking" in line.lower() or "not ranking" in line.lower() for line in result.executive_summary)
