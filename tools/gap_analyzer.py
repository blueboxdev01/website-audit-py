from statistics import mean
from typing import Optional

from tools.models import AnalysisResult, Gap, PlaceDetails, Signals

COMPLETENESS_FIELDS = [
    "phone",
    "website",
    "has_hours",
    "has_description",
    "primary_category",
    "address",
]


def compute_signals(details: PlaceDetails, local_pack_rank: Optional[int]) -> Signals:
    filled = 0
    for field_name in COMPLETENESS_FIELDS:
        value = getattr(details, field_name)
        if value:
            filled += 1
    completeness = filled / len(COMPLETENESS_FIELDS)

    category_count = 1 if details.primary_category else 0
    category_count += len(details.secondary_categories)

    return Signals(
        place_id=details.place_id,
        name=details.name,
        profile_completeness=completeness,
        category_count=category_count,
        review_count=details.review_count,
        rating=details.rating or 0.0,
        has_posts=details.has_posts,
        has_qa=details.has_qa,
        services_listed=details.services_listed,
        attribute_count=len(details.attributes),
        local_pack_rank=local_pack_rank,
    )


def _impact(gap_ratio: float) -> str:
    if gap_ratio >= 0.5:
        return "high"
    if gap_ratio >= 0.2:
        return "medium"
    return "low"


def _numeric_gap(
    signal_name: str,
    prospect_value: float,
    competitor_values: list[float],
    recommendation: str,
) -> Optional[Gap]:
    if not competitor_values:
        return None
    competitor_best = max(competitor_values)
    competitor_avg = mean(competitor_values)
    if competitor_best <= 0:
        return None
    if prospect_value >= competitor_best:
        return None
    gap_ratio = (competitor_best - prospect_value) / competitor_best
    return Gap(
        signal=signal_name,
        prospect_value=prospect_value,
        competitor_best=competitor_best,
        competitor_avg=competitor_avg,
        impact=_impact(gap_ratio),
        recommendation=recommendation,
    )


def analyze(
    prospect_name: str,
    prospect_city: str,
    target_query: str,
    keyword: str,
    prospect_details: PlaceDetails,
    competitor_details: list[PlaceDetails],
    prospect_rank: Optional[int],
) -> AnalysisResult:
    prospect_signals = compute_signals(prospect_details, prospect_rank)
    competitor_signals = [
        compute_signals(c, None) for c in competitor_details
    ]

    gaps: list[Gap] = []

    reviews_gap = _numeric_gap(
        "reviews",
        prospect_signals.review_count,
        [c.review_count for c in competitor_signals],
        "You have far fewer customer reviews than the businesses showing up above you. When people in your area search, Google is pointing them to the businesses with more social proof — and customers are clicking those first.",
    )
    if reviews_gap:
        gaps.append(reviews_gap)

    categories_gap = _numeric_gap(
        "categories",
        prospect_signals.category_count,
        [c.category_count for c in competitor_signals],
        "Your business is listed under fewer service types than your competitors. That means when customers search for the different things you actually offer, you're simply not showing up for most of them.",
    )
    if categories_gap:
        gaps.append(categories_gap)

    rating_gap = _numeric_gap(
        "rating",
        prospect_signals.rating,
        [c.rating for c in competitor_signals],
        "Your star rating is lower than the top businesses in your area. Customers scanning the map results skip past lower-rated options before they ever see what you offer.",
    )
    if rating_gap:
        gaps.append(rating_gap)

    if not prospect_signals.has_posts and any(c.has_posts for c in competitor_signals):
        gaps.append(
            Gap(
                signal="posts",
                prospect_value=0,
                competitor_best=1,
                competitor_avg=0.5,
                impact="medium",
                recommendation="Your business listing looks inactive compared to competitors who are regularly posting updates, offers, and news. To Google and to potential customers, a quiet listing signals a quiet business.",
            )
        )

    if prospect_signals.profile_completeness < 1.0:
        missing_labels = {
            "phone": "phone number",
            "website": "website link",
            "has_description": "business description",
            "has_hours": "opening hours",
        }
        missing = []
        if not prospect_details.phone:
            missing.append(missing_labels["phone"])
        if not prospect_details.website:
            missing.append(missing_labels["website"])
        if not prospect_details.has_description:
            missing.append(missing_labels["has_description"])
        if not prospect_details.has_hours:
            missing.append(missing_labels["has_hours"])
        if missing:
            missing_text = ", ".join(missing)
            recommendation = (
                f"Your public business listing is missing key information ({missing_text}). "
                "Customers who land on it often leave without contacting you because they can't quickly see what they need to make a decision."
            )
        else:
            recommendation = (
                "Your public business listing has gaps that make it look less trustworthy than the businesses ranking above you."
            )
        gaps.append(
            Gap(
                signal="profile_completeness",
                prospect_value=prospect_signals.profile_completeness,
                competitor_best=1.0,
                competitor_avg=1.0,
                impact="high",
                recommendation=recommendation,
            )
        )

    impact_weight = {"high": 3, "medium": 2, "low": 1}
    gaps.sort(key=lambda g: impact_weight[g.impact], reverse=True)

    summary: list[str] = []
    if prospect_rank is None:
        summary.append(
            f"When people in {prospect_city} search for \"{keyword}\", {prospect_name} is not showing up on the map — customers are finding competitors instead."
        )
    else:
        summary.append(
            f"When people in {prospect_city} search for \"{keyword}\", {prospect_name} currently appears at position #{prospect_rank} on the map — most customers never scroll far enough to see you."
        )

    top_gaps = [g for g in gaps if g.impact == "high"][:3]
    for gap in top_gaps:
        summary.append(gap.recommendation)

    if len(summary) < 3:
        for gap in gaps[len(summary) - 1:]:
            summary.append(gap.recommendation)
            if len(summary) >= 5:
                break

    return AnalysisResult(
        prospect_name=prospect_name,
        prospect_city=prospect_city,
        target_query=target_query,
        keyword=keyword,
        prospect_signals=prospect_signals,
        competitor_signals=competitor_signals,
        prospect_rank=prospect_rank,
        gaps=gaps,
        executive_summary=summary[:5],
    )
