import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file

from tools.gap_analyzer import analyze
from tools.models import PlaceDetails
from tools.report_generator import generate_report
from tools.serp_provider import SerpProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".tmp" / "cache"
REPORTS_DIR = PROJECT_ROOT / ".tmp" / "reports"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

load_dotenv(PROJECT_ROOT / ".env")

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    company = (request.form.get("company") or "").strip()
    city = (request.form.get("city") or "").strip()
    category = (request.form.get("category") or "").strip()

    if not company or not city or not category:
        return jsonify({"error": "Business name, city, and category are all required."}), 400

    serpapi_key = os.environ.get("SERPAPI_KEY")
    if not serpapi_key:
        return jsonify({"error": "Server is missing SERPAPI_KEY configuration."}), 500

    provider = SerpProvider(
        api_key=serpapi_key,
        cache_dir=CACHE_DIR,
        cache_enabled=True,
    )

    try:
        business = provider.find_business(company, city)
        target_query = f"{category} {city}"
        local_pack = provider.get_local_pack(target_query, city)
        if not local_pack:
            return jsonify({"error": "No local search results returned for that area."}), 502

        prospect_rank = None
        if business is not None:
            prospect_rank = provider.rank_of(business.place_id, local_pack)
            competitors_pool = [c for c in local_pack if c.place_id != business.place_id]
            prospect_details = provider.get_place_details(business.place_id)
        else:
            competitors_pool = local_pack
            prospect_details = PlaceDetails(
                place_id="",
                name=company,
                address="",
                phone=None,
                website=None,
                primary_category=category,
            )

        top_three = competitors_pool[:3]
        competitor_details = [provider.get_place_details(c.place_id) for c in top_three]

        analysis = analyze(
            prospect_name=company,
            prospect_city=city,
            target_query=target_query,
            keyword=category,
            prospect_details=prospect_details,
            competitor_details=competitor_details,
            prospect_rank=prospect_rank,
        )

        pdf_path = generate_report(
            analysis=analysis,
            output_dir=REPORTS_DIR,
            templates_dir=TEMPLATES_DIR,
        )
    except Exception as exc:
        app.logger.exception("Report generation failed")
        return jsonify({"error": f"Report generation failed: {exc}"}), 500

    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=pdf_path.name,
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
