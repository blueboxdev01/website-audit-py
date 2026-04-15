import re
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from tools.models import AnalysisResult


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"\s+", "-", value).strip("-")
    value = re.sub(r"-+", "-", value)
    return value


def render_html(analysis: AnalysisResult, templates_dir: Path) -> str:
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "jinja"]),
    )
    template = env.get_template("report.html.j2")
    css = (templates_dir / "report.css").read_text(encoding="utf-8")
    return template.render(
        analysis=analysis,
        css=css,
        report_date=date.today().strftime("%B %d, %Y"),
    )


def render_pdf(html: str, output_path: Path) -> Path:
    from playwright.sync_api import sync_playwright

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        page.set_content(html, wait_until="domcontentloaded")
        page.pdf(
            path=str(output_path),
            format="Letter",
            margin={"top": "0.75in", "bottom": "0.75in", "left": "0.75in", "right": "0.75in"},
            print_background=True,
        )
        browser.close()
    return output_path


def generate_report(
    analysis: AnalysisResult,
    output_dir: Path,
    templates_dir: Path = Path("templates"),
) -> Path:
    html = render_html(analysis, templates_dir=templates_dir)
    slug = slugify(analysis.prospect_name)
    today = date.today().strftime("%Y-%m-%d")
    output_path = output_dir / f"{slug}-{today}.pdf"
    try:
        return render_pdf(html, output_path)
    except Exception:
        fallback = output_path.with_suffix(".html")
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(html, encoding="utf-8")
        raise
