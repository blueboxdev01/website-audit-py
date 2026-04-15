import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from tools.gap_analyzer import analyze
from tools.report_generator import generate_report
from tools.serp_provider import SerpProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".tmp" / "cache"
REPORTS_DIR = PROJECT_ROOT / ".tmp" / "reports"
TEMPLATES_DIR = PROJECT_ROOT / "templates"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a local SEO audit PDF report for a business."
    )
    parser.add_argument("--company", required=True, help="Business name")
    parser.add_argument("--city", required=True, help="City and state, e.g. 'Newark, NJ'")
    parser.add_argument(
        "--service",
        help="Service type (e.g. 'daycare'). Required only if the business has no GBP.",
    )
    parser.add_argument(
        "--category",
        help="Override the auto-detected business category used to build the target query.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Override default report save path.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore cached SERP responses and force fresh API calls.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args(argv)

    serpapi_key = os.environ.get("SERPAPI_KEY")
    if not serpapi_key:
        print("ERROR: SERPAPI_KEY not set in .env", file=sys.stderr)
        return 1

    provider = SerpProvider(
        api_key=serpapi_key,
        cache_dir=CACHE_DIR,
        cache_enabled=not args.no_cache,
    )

    print(f"Resolving business: {args.company} in {args.city}...")
    business = provider.find_business(args.company, args.city)

    if business is None:
        category = args.category or args.service
        if not category:
            print(
                "ERROR: No Google Business Profile found for this business.\n"
                "Re-run with --category '<business type>' (or --service) to proceed with a no-GBP audit.",
                file=sys.stderr,
            )
            return 2
        target_query = f"{category} {args.city}"
        print(f"No GBP found. Using category override -> target query: '{target_query}'")
    else:
        category = args.category or business.primary_category or args.service
        if not category:
            print(
                "ERROR: Business found but has no category. Re-run with --category '<business type>'.",
                file=sys.stderr,
            )
            return 3
        target_query = f"{category} {args.city}"
        print(f"Target query: '{target_query}'")

    print(f"Pulling local pack for '{target_query}'...")
    local_pack = provider.get_local_pack(target_query, args.city)
    if not local_pack:
        print("ERROR: No local pack results returned.", file=sys.stderr)
        return 4

    prospect_rank: Optional[int] = None
    if business is not None:
        prospect_rank = provider.rank_of(business.place_id, local_pack)
        competitors_pool = [c for c in local_pack if c.place_id != business.place_id]
    else:
        competitors_pool = local_pack
    top_three = competitors_pool[:3]

    print(f"Prospect rank: {prospect_rank if prospect_rank else 'not in top 20'}")
    print(f"Enriching prospect and {len(top_three)} competitors...")

    if business is not None:
        prospect_details = provider.get_place_details(business.place_id)
    else:
        from tools.models import PlaceDetails

        prospect_details = PlaceDetails(
            place_id="",
            name=args.company,
            address="",
            phone=None,
            website=None,
            primary_category=args.category or args.service,
        )

    competitor_details = []
    for competitor in top_three:
        detail = provider.get_place_details(competitor.place_id)
        competitor_details.append(detail)

    print("Running gap analysis...")
    analysis = analyze(
        prospect_name=args.company,
        prospect_city=args.city,
        target_query=target_query,
        keyword=category,
        prospect_details=prospect_details,
        competitor_details=competitor_details,
        prospect_rank=prospect_rank,
    )

    print("Rendering PDF report...")
    output_dir = args.output.parent if args.output else REPORTS_DIR
    pdf_path = generate_report(
        analysis=analysis,
        output_dir=output_dir,
        templates_dir=TEMPLATES_DIR,
    )
    if args.output:
        pdf_path.rename(args.output)
        pdf_path = args.output

    print(f"\nReport generated: {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
