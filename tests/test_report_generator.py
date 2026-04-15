from pathlib import Path

from tools.gap_analyzer import analyze
from tools.models import PlaceDetails
from tools.report_generator import render_html, slugify


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


def test_render_html_contains_prospect_name(tmp_path):
    prospect = make_details(name="Sunny Days Daycare", review_count=10)
    competitors = [
        make_details(place_id=f"c{i}", name=f"Competitor {i}", review_count=150)
        for i in range(3)
    ]

    analysis = analyze(
        prospect_name="Sunny Days Daycare",
        prospect_city="Newark, NJ",
        target_query="day care center Newark NJ",
        prospect_details=prospect,
        competitor_details=competitors,
        prospect_rank=4,
    )

    html = render_html(analysis, templates_dir=Path("templates"))

    assert "Sunny Days Daycare" in html
    assert "Newark, NJ" in html
    assert "Ranked #4" in html
    assert "Competitor 0" in html


def test_slugify_produces_safe_filename():
    assert slugify("Sunny Days Daycare") == "sunny-days-daycare"
    assert slugify("O'Reilly's Auto Parts") == "oreillys-auto-parts"
    assert slugify("ABC  Inc.") == "abc-inc"
