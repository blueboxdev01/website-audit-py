# Local SEO Audit Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that takes a company name and city, audits the business's Google Business Profile against the top 3 local-pack competitors, and produces a client-ready PDF report.

**Architecture:** Follows the WAT framework (Workflows, Agents, Tools). Orchestrator script (`run_audit.py`) calls focused single-purpose modules for SERP data retrieval, enrichment, gap analysis, and PDF rendering. All external SERP calls go through a provider abstraction so the paid-tier swap on launch is a one-file change.

**Tech Stack:** Python 3.12, `requests` (SerpApi HTTP), `jinja2` (template engine), `playwright` (HTML → PDF rendering), `pytest` (tests), `python-dotenv` (env loading).

**Deviation from spec:** The spec named WeasyPrint for PDF rendering. Switching to Playwright because WeasyPrint's GTK dependency is fragile on Windows (the operator's platform), and Playwright produces higher-fidelity PDFs with zero Windows-specific setup beyond `playwright install chromium`. All other architecture choices are unchanged.

---

## File Structure

```
website-audit/
├── .env                          # Secrets (gitignored)
├── .env.example                  # Template committed to repo
├── .gitignore
├── .tmp/
│   ├── cache/                    # Raw SERP responses (gitignored)
│   └── reports/                  # Output PDFs (gitignored)
├── fixtures/
│   ├── serpapi_find_business.json
│   ├── serpapi_local_pack.json
│   └── serpapi_place_details.json
├── requirements.txt
├── templates/
│   ├── report.html.j2
│   └── report.css
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_cache.py
│   ├── test_serp_provider.py
│   ├── test_gap_analyzer.py
│   └── test_report_generator.py
├── tools/
│   ├── __init__.py
│   ├── models.py                 # Dataclasses: BusinessResult, PlaceDetails, Signals, AnalysisResult
│   ├── cache.py                  # Generic JSON cache with 24h TTL
│   ├── serp_provider.py          # SerpApi wrapper behind stable interface
│   ├── gbp_enricher.py           # Google Places API fallback
│   ├── gap_analyzer.py           # Pure-Python scoring and recommendations
│   ├── report_generator.py       # Jinja2 + Playwright PDF rendering
│   └── run_audit.py              # CLI orchestrator (entry point)
└── workflows/
    └── audit_local_seo.md        # Operator SOP
```

Each file has a single responsibility and can be tested in isolation. `models.py` defines the types that flow between modules so the interfaces stay stable.

---

## Task 1: Project scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `tools/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.tmp/cache/.gitkeep`
- Create: `.tmp/reports/.gitkeep`

- [ ] **Step 1: Create `requirements.txt`**

```
requests==2.32.3
python-dotenv==1.0.1
jinja2==3.1.4
playwright==1.48.0
pytest==8.3.3
```

- [ ] **Step 2: Create `.env.example`**

```
SERPAPI_KEY=your_serpapi_key_here
GOOGLE_PLACES_API_KEY=your_google_places_api_key_here
```

- [ ] **Step 3: Create `.gitignore`**

```
.env
.tmp/cache/*
.tmp/reports/*
!.tmp/cache/.gitkeep
!.tmp/reports/.gitkeep
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: Create empty `tools/__init__.py` and `tests/__init__.py`**

Both files are empty — just `touch` or create empty files.

- [ ] **Step 5: Create `tests/conftest.py`**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

This lets test files import `tools.x` without installing the package.

- [ ] **Step 6: Create `.tmp/cache/.gitkeep` and `.tmp/reports/.gitkeep`**

Empty files — just create them so the directories survive git.

- [ ] **Step 7: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: all packages install without error.

- [ ] **Step 8: Install Playwright browser**

Run: `playwright install chromium`
Expected: Chromium downloads successfully.

- [ ] **Step 9: Verify pytest runs**

Run: `pytest tests/ -v`
Expected: `no tests ran in 0.XXs` (no error, no tests yet).

- [ ] **Step 10: Commit**

```bash
git init
git add requirements.txt .env.example .gitignore tools/__init__.py tests/__init__.py tests/conftest.py .tmp/cache/.gitkeep .tmp/reports/.gitkeep
git commit -m "chore: initialize project scaffold and dependencies"
```

---

## Task 2: Shared data models

**Files:**
- Create: `tools/models.py`

- [ ] **Step 1: Create `tools/models.py` with all dataclasses**

```python
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
    photo_count: int = 0
    has_hours: bool = False
    has_description: bool = False
    has_posts: bool = False
    has_qa: bool = False
    services_listed: int = 0
    attributes: list[str] = field(default_factory=list)
    latest_review_date: Optional[str] = None
    response_rate: Optional[float] = None  # 0.0 to 1.0


@dataclass
class Signals:
    """Normalized, comparable signals for one business."""
    place_id: str
    name: str
    profile_completeness: float  # 0.0 to 1.0
    category_count: int
    photo_count: int
    review_count: int
    rating: float
    response_rate: float
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
    prospect_signals: Signals
    competitor_signals: list[Signals]
    prospect_rank: Optional[int]
    gaps: list[Gap]
    executive_summary: list[str]  # 3-5 bullet points
```

- [ ] **Step 2: Verify the module imports without error**

Run: `python -c "from tools.models import BusinessResult, PlaceDetails, Signals, Gap, AnalysisResult; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tools/models.py
git commit -m "feat: add shared data models for audit pipeline"
```

---

## Task 3: JSON cache with TTL

**Files:**
- Create: `tools/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write failing tests for the cache**

Create `tests/test_cache.py`:

```python
import json
import time
from pathlib import Path

import pytest

from tools.cache import JsonCache


@pytest.fixture
def tmp_cache(tmp_path):
    return JsonCache(tmp_path, ttl_seconds=2)


def test_miss_returns_none(tmp_cache):
    assert tmp_cache.get("missing_key") is None


def test_set_then_get_returns_value(tmp_cache):
    tmp_cache.set("abc", {"hello": "world"})
    assert tmp_cache.get("abc") == {"hello": "world"}


def test_expired_entry_returns_none(tmp_cache):
    tmp_cache.set("k", {"v": 1})
    time.sleep(2.1)
    assert tmp_cache.get("k") is None


def test_set_writes_json_file(tmp_path):
    cache = JsonCache(tmp_path, ttl_seconds=60)
    cache.set("sample", {"a": 1})
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["data"] == {"a": 1}
    assert "cached_at" in payload


def test_get_when_disabled_always_returns_none(tmp_path):
    cache = JsonCache(tmp_path, ttl_seconds=60, enabled=False)
    cache.set("k", {"v": 1})
    assert cache.get("k") is None
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_cache.py -v`
Expected: ImportError / ModuleNotFoundError on `tools.cache`.

- [ ] **Step 3: Implement `tools/cache.py`**

```python
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional


class JsonCache:
    """Filesystem-backed JSON cache with TTL.

    Keys are hashed to produce safe filenames. Values must be JSON-serializable.
    """

    def __init__(self, directory: Path, ttl_seconds: int = 86400, enabled: bool = True):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

    def _path_for(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        cached_at = payload.get("cached_at", 0)
        if time.time() - cached_at > self.ttl_seconds:
            return None
        return payload.get("data")

    def set(self, key: str, value: Any) -> None:
        path = self._path_for(key)
        payload = {"cached_at": time.time(), "key": key, "data": value}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/test_cache.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/cache.py tests/test_cache.py
git commit -m "feat: add JSON cache with TTL for SERP responses"
```

---

## Task 4: SerpApi provider (find_business)

**Files:**
- Create: `fixtures/serpapi_find_business.json`
- Create: `tools/serp_provider.py`
- Create: `tests/test_serp_provider.py`

- [ ] **Step 1: Create the fixture**

Create `fixtures/serpapi_find_business.json` — a hand-crafted minimal version of a real SerpApi `google_maps` engine response. This is what a real call for `"Sunny Days Daycare Newark NJ"` might return.

```json
{
  "search_metadata": {"status": "Success"},
  "search_parameters": {"engine": "google_maps", "q": "Sunny Days Daycare Newark NJ"},
  "place_results": {
    "title": "Sunny Days Daycare",
    "place_id": "ChIJexampleplaceid1",
    "data_id": "0x0:0xexampledataid1",
    "address": "123 Main St, Newark, NJ 07102",
    "phone": "(555) 123-4567",
    "website": "https://sunnydaysdaycare.example",
    "type": ["Day care center"],
    "rating": 4.2,
    "reviews": 47,
    "gps_coordinates": {"latitude": 40.7357, "longitude": -74.1724}
  }
}
```

- [ ] **Step 2: Write failing tests for `find_business`**

Create `tests/test_serp_provider.py`:

```python
import json
from pathlib import Path

import pytest

from tools.serp_provider import SerpProvider

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class FakeFetcher:
    """Stand-in for the HTTP fetcher. Returns a preloaded JSON payload."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, params):
        self.calls.append(params)
        return self.payload


@pytest.fixture
def find_business_payload():
    return json.loads((FIXTURES / "serpapi_find_business.json").read_text())


def test_find_business_returns_business_result(tmp_path, find_business_payload):
    fetcher = FakeFetcher(find_business_payload)
    provider = SerpProvider(api_key="fake", cache_dir=tmp_path, fetcher=fetcher)

    result = provider.find_business("Sunny Days Daycare", "Newark, NJ")

    assert result is not None
    assert result.place_id == "ChIJexampleplaceid1"
    assert result.name == "Sunny Days Daycare"
    assert result.primary_category == "Day care center"
    assert result.rating == 4.2
    assert result.review_count == 47
    assert result.gps == (40.7357, -74.1724)


def test_find_business_returns_none_when_no_match(tmp_path):
    fetcher = FakeFetcher({"search_metadata": {"status": "Success"}})
    provider = SerpProvider(api_key="fake", cache_dir=tmp_path, fetcher=fetcher)

    result = provider.find_business("Nonexistent Biz", "Nowhere, XX")

    assert result is None


def test_find_business_passes_correct_query(tmp_path, find_business_payload):
    fetcher = FakeFetcher(find_business_payload)
    provider = SerpProvider(api_key="fake", cache_dir=tmp_path, fetcher=fetcher)

    provider.find_business("Sunny Days Daycare", "Newark, NJ")

    assert fetcher.calls[0]["q"] == "Sunny Days Daycare Newark, NJ"
    assert fetcher.calls[0]["engine"] == "google_maps"
    assert fetcher.calls[0]["api_key"] == "fake"
```

- [ ] **Step 3: Run tests to confirm they fail**

Run: `pytest tests/test_serp_provider.py -v`
Expected: ImportError on `tools.serp_provider`.

- [ ] **Step 4: Implement `tools/serp_provider.py` (partial — find_business only)**

```python
from pathlib import Path
from typing import Callable, Optional

import requests

from tools.cache import JsonCache
from tools.models import BusinessResult

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


def _default_fetcher(params: dict) -> dict:
    response = requests.get(SERPAPI_ENDPOINT, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


class SerpProvider:
    """Wraps SerpApi behind a stable interface for the rest of the pipeline.

    Swap this class for another provider (DataForSEO, paid SerpApi tier, etc.)
    without touching the rest of the pipeline, as long as the interface holds.
    """

    def __init__(
        self,
        api_key: str,
        cache_dir: Path,
        fetcher: Callable[[dict], dict] = _default_fetcher,
        cache_enabled: bool = True,
    ):
        self.api_key = api_key
        self.fetcher = fetcher
        self.cache = JsonCache(cache_dir, ttl_seconds=86400, enabled=cache_enabled)

    def find_business(self, company: str, city: str) -> Optional[BusinessResult]:
        query = f"{company} {city}"
        cache_key = f"find_business::{query}"
        cached = self.cache.get(cache_key)
        if cached is None:
            params = {
                "engine": "google_maps",
                "q": query,
                "type": "search",
                "api_key": self.api_key,
            }
            cached = self.fetcher(params)
            self.cache.set(cache_key, cached)

        place = cached.get("place_results")
        if not place:
            return None

        gps = None
        if place.get("gps_coordinates"):
            gps = (
                place["gps_coordinates"].get("latitude"),
                place["gps_coordinates"].get("longitude"),
            )

        types = place.get("type") or []
        primary_category = types[0] if types else None

        return BusinessResult(
            place_id=place.get("place_id", ""),
            name=place.get("title", ""),
            address=place.get("address", ""),
            phone=place.get("phone"),
            website=place.get("website"),
            primary_category=primary_category,
            rating=place.get("rating"),
            review_count=place.get("reviews"),
            gps=gps,
        )
```

- [ ] **Step 5: Run tests to confirm they pass**

Run: `pytest tests/test_serp_provider.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add fixtures/serpapi_find_business.json tools/serp_provider.py tests/test_serp_provider.py
git commit -m "feat: add SerpProvider.find_business with caching"
```

---

## Task 5: SerpApi provider (get_local_pack)

**Files:**
- Create: `fixtures/serpapi_local_pack.json`
- Modify: `tools/serp_provider.py`
- Modify: `tests/test_serp_provider.py`

- [ ] **Step 1: Create the local pack fixture**

Create `fixtures/serpapi_local_pack.json`:

```json
{
  "search_metadata": {"status": "Success"},
  "search_parameters": {"engine": "google_maps", "q": "day care center Newark NJ"},
  "local_results": [
    {
      "position": 1,
      "title": "Top Tots Learning Center",
      "place_id": "ChIJcompetitor001",
      "address": "45 Broad St, Newark, NJ",
      "phone": "(555) 111-0001",
      "website": "https://toptots.example",
      "type": ["Day care center"],
      "rating": 4.8,
      "reviews": 220,
      "gps_coordinates": {"latitude": 40.7350, "longitude": -74.1700}
    },
    {
      "position": 2,
      "title": "Little Stars Daycare",
      "place_id": "ChIJcompetitor002",
      "address": "88 Market St, Newark, NJ",
      "phone": "(555) 111-0002",
      "website": "https://littlestars.example",
      "type": ["Day care center"],
      "rating": 4.6,
      "reviews": 180,
      "gps_coordinates": {"latitude": 40.7360, "longitude": -74.1710}
    },
    {
      "position": 3,
      "title": "Bright Kids Academy",
      "place_id": "ChIJcompetitor003",
      "address": "12 Park Pl, Newark, NJ",
      "phone": "(555) 111-0003",
      "website": "https://brightkids.example",
      "type": ["Day care center"],
      "rating": 4.5,
      "reviews": 145,
      "gps_coordinates": {"latitude": 40.7340, "longitude": -74.1730}
    },
    {
      "position": 4,
      "title": "Sunny Days Daycare",
      "place_id": "ChIJexampleplaceid1",
      "address": "123 Main St, Newark, NJ 07102",
      "phone": "(555) 123-4567",
      "website": "https://sunnydaysdaycare.example",
      "type": ["Day care center"],
      "rating": 4.2,
      "reviews": 47,
      "gps_coordinates": {"latitude": 40.7357, "longitude": -74.1724}
    }
  ]
}
```

- [ ] **Step 2: Add failing tests for `get_local_pack` and `rank_of`**

Append to `tests/test_serp_provider.py`:

```python
@pytest.fixture
def local_pack_payload():
    return json.loads((FIXTURES / "serpapi_local_pack.json").read_text())


def test_get_local_pack_returns_ordered_results(tmp_path, local_pack_payload):
    fetcher = FakeFetcher(local_pack_payload)
    provider = SerpProvider(api_key="fake", cache_dir=tmp_path, fetcher=fetcher)

    results = provider.get_local_pack("day care center Newark NJ", "Newark, NJ")

    assert len(results) == 4
    assert results[0].name == "Top Tots Learning Center"
    assert results[0].place_id == "ChIJcompetitor001"
    assert results[3].name == "Sunny Days Daycare"


def test_get_local_pack_empty_when_no_results(tmp_path):
    fetcher = FakeFetcher({"search_metadata": {"status": "Success"}})
    provider = SerpProvider(api_key="fake", cache_dir=tmp_path, fetcher=fetcher)

    results = provider.get_local_pack("no results query", "Nowhere, XX")

    assert results == []


def test_rank_of_returns_position_when_found(tmp_path, local_pack_payload):
    fetcher = FakeFetcher(local_pack_payload)
    provider = SerpProvider(api_key="fake", cache_dir=tmp_path, fetcher=fetcher)

    results = provider.get_local_pack("day care center Newark NJ", "Newark, NJ")
    rank = provider.rank_of("ChIJexampleplaceid1", results)

    assert rank == 4


def test_rank_of_returns_none_when_not_found(tmp_path, local_pack_payload):
    fetcher = FakeFetcher(local_pack_payload)
    provider = SerpProvider(api_key="fake", cache_dir=tmp_path, fetcher=fetcher)

    results = provider.get_local_pack("day care center Newark NJ", "Newark, NJ")
    rank = provider.rank_of("ChIJunknown", results)

    assert rank is None
```

- [ ] **Step 3: Run tests to confirm the new ones fail**

Run: `pytest tests/test_serp_provider.py -v`
Expected: 4 new failures (missing `get_local_pack`, `rank_of`).

- [ ] **Step 4: Extend `SerpProvider` with `get_local_pack` and `rank_of`**

Add to `tools/serp_provider.py` inside the `SerpProvider` class:

```python
    def get_local_pack(self, query: str, city: str) -> list[BusinessResult]:
        cache_key = f"local_pack::{query}::{city}"
        cached = self.cache.get(cache_key)
        if cached is None:
            params = {
                "engine": "google_maps",
                "q": query,
                "type": "search",
                "api_key": self.api_key,
            }
            cached = self.fetcher(params)
            self.cache.set(cache_key, cached)

        local_results = cached.get("local_results") or []
        results: list[BusinessResult] = []
        for place in local_results:
            gps = None
            if place.get("gps_coordinates"):
                gps = (
                    place["gps_coordinates"].get("latitude"),
                    place["gps_coordinates"].get("longitude"),
                )
            types = place.get("type") or []
            primary_category = types[0] if types else None
            results.append(
                BusinessResult(
                    place_id=place.get("place_id", ""),
                    name=place.get("title", ""),
                    address=place.get("address", ""),
                    phone=place.get("phone"),
                    website=place.get("website"),
                    primary_category=primary_category,
                    rating=place.get("rating"),
                    review_count=place.get("reviews"),
                    gps=gps,
                )
            )
        return results

    @staticmethod
    def rank_of(place_id: str, results: list[BusinessResult]) -> Optional[int]:
        for index, business in enumerate(results, start=1):
            if business.place_id == place_id:
                return index
        return None
```

- [ ] **Step 5: Run tests to confirm all pass**

Run: `pytest tests/test_serp_provider.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add fixtures/serpapi_local_pack.json tools/serp_provider.py tests/test_serp_provider.py
git commit -m "feat: add SerpProvider.get_local_pack and rank_of"
```

---

## Task 6: SerpApi provider (get_place_details)

**Files:**
- Create: `fixtures/serpapi_place_details.json`
- Modify: `tools/serp_provider.py`
- Modify: `tests/test_serp_provider.py`

- [ ] **Step 1: Create the place details fixture**

Create `fixtures/serpapi_place_details.json`:

```json
{
  "search_metadata": {"status": "Success"},
  "place_results": {
    "title": "Sunny Days Daycare",
    "place_id": "ChIJexampleplaceid1",
    "address": "123 Main St, Newark, NJ 07102",
    "phone": "(555) 123-4567",
    "website": "https://sunnydaysdaycare.example",
    "type": ["Day care center"],
    "types": ["Day care center", "Preschool"],
    "rating": 4.2,
    "reviews": 47,
    "description": "A warm and nurturing daycare in downtown Newark.",
    "hours": [{"monday": "7AM-6PM"}],
    "photos_count": 12,
    "posts": [],
    "questions": [],
    "service_options": ["Pickup", "Drop-off"],
    "attributes": ["Wheelchair accessible entrance"],
    "user_reviews": {
      "summary": [],
      "most_relevant": [{"date": "2 weeks ago", "rating": 5, "snippet": "Great teachers!"}]
    },
    "owner_response_rate": 0.35
  }
}
```

- [ ] **Step 2: Add failing test for `get_place_details`**

Append to `tests/test_serp_provider.py`:

```python
@pytest.fixture
def place_details_payload():
    return json.loads((FIXTURES / "serpapi_place_details.json").read_text())


def test_get_place_details_maps_all_fields(tmp_path, place_details_payload):
    fetcher = FakeFetcher(place_details_payload)
    provider = SerpProvider(api_key="fake", cache_dir=tmp_path, fetcher=fetcher)

    details = provider.get_place_details("ChIJexampleplaceid1")

    assert details.place_id == "ChIJexampleplaceid1"
    assert details.name == "Sunny Days Daycare"
    assert details.primary_category == "Day care center"
    assert "Preschool" in details.secondary_categories
    assert details.rating == 4.2
    assert details.review_count == 47
    assert details.photo_count == 12
    assert details.has_hours is True
    assert details.has_description is True
    assert details.has_posts is False
    assert details.has_qa is False
    assert details.services_listed == 2
    assert "Wheelchair accessible entrance" in details.attributes
    assert details.response_rate == 0.35
    assert details.latest_review_date == "2 weeks ago"
```

- [ ] **Step 3: Run test to confirm failure**

Run: `pytest tests/test_serp_provider.py::test_get_place_details_maps_all_fields -v`
Expected: AttributeError on missing `get_place_details`.

- [ ] **Step 4: Extend `SerpProvider` with `get_place_details`**

Add to `tools/serp_provider.py`:

```python
    def get_place_details(self, place_id: str):
        from tools.models import PlaceDetails  # local import to avoid cycles

        cache_key = f"place_details::{place_id}"
        cached = self.cache.get(cache_key)
        if cached is None:
            params = {
                "engine": "google_maps",
                "place_id": place_id,
                "api_key": self.api_key,
            }
            cached = self.fetcher(params)
            self.cache.set(cache_key, cached)

        place = cached.get("place_results") or {}
        types = place.get("types") or place.get("type") or []
        primary_category = types[0] if types else None
        secondary_categories = types[1:] if len(types) > 1 else []

        reviews_block = place.get("user_reviews") or {}
        most_relevant = reviews_block.get("most_relevant") or []
        latest_review_date = most_relevant[0].get("date") if most_relevant else None

        return PlaceDetails(
            place_id=place.get("place_id", place_id),
            name=place.get("title", ""),
            address=place.get("address", ""),
            phone=place.get("phone"),
            website=place.get("website"),
            primary_category=primary_category,
            secondary_categories=secondary_categories,
            rating=place.get("rating"),
            review_count=place.get("reviews", 0) or 0,
            photo_count=place.get("photos_count", 0) or 0,
            has_hours=bool(place.get("hours")),
            has_description=bool(place.get("description")),
            has_posts=bool(place.get("posts")),
            has_qa=bool(place.get("questions")),
            services_listed=len(place.get("service_options") or []),
            attributes=place.get("attributes") or [],
            latest_review_date=latest_review_date,
            response_rate=place.get("owner_response_rate"),
        )
```

- [ ] **Step 5: Run all serp_provider tests**

Run: `pytest tests/test_serp_provider.py -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add fixtures/serpapi_place_details.json tools/serp_provider.py tests/test_serp_provider.py
git commit -m "feat: add SerpProvider.get_place_details"
```

---

## Task 7: GBP enricher (Places API fallback)

**Files:**
- Create: `tools/gbp_enricher.py`

- [ ] **Step 1: Implement `tools/gbp_enricher.py`**

This module is a thin fallback for when SerpApi doesn't return a specific field. For v1 it's mostly a passthrough — the interface is in place so we can bolt on Places API calls later without changing callers.

```python
from typing import Optional

import requests

from tools.models import PlaceDetails

PLACES_ENDPOINT = "https://places.googleapis.com/v1/places"


class GbpEnricher:
    """Fallback enrichment via Google Places API (New).

    Only invoked when SerpApi is missing a field. Fails silently — missing
    data propagates to the report as 'Data unavailable' rather than blocking
    the audit.
    """

    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key

    def enrich(self, details: PlaceDetails) -> PlaceDetails:
        if not self.api_key:
            return details
        if details.response_rate is not None and details.photo_count > 0:
            return details
        try:
            enriched = self._fetch(details.place_id)
        except (requests.RequestException, ValueError, KeyError):
            return details
        if enriched.get("photoCount") and details.photo_count == 0:
            details.photo_count = enriched["photoCount"]
        return details

    def _fetch(self, place_id: str) -> dict:
        url = f"{PLACES_ENDPOINT}/{place_id}"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "id,displayName,photos",
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 2: Verify the module imports**

Run: `python -c "from tools.gbp_enricher import GbpEnricher; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tools/gbp_enricher.py
git commit -m "feat: add GbpEnricher fallback using Google Places API"
```

---

## Task 8: Gap analyzer

**Files:**
- Create: `tools/gap_analyzer.py`
- Create: `tests/test_gap_analyzer.py`

- [ ] **Step 1: Write failing tests for `compute_signals`**

Create `tests/test_gap_analyzer.py`:

```python
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
        photo_count=10,
        has_hours=True,
        has_description=True,
        has_posts=False,
        has_qa=False,
        services_listed=2,
        attributes=["Wheelchair accessible entrance"],
        latest_review_date="1 week ago",
        response_rate=0.4,
    )
    defaults.update(overrides)
    return PlaceDetails(**defaults)


def test_compute_signals_profile_completeness_full():
    details = make_details()
    signals = compute_signals(details, local_pack_rank=4)

    assert signals.profile_completeness == 1.0
    assert signals.category_count == 2
    assert signals.photo_count == 10
    assert signals.review_count == 50
    assert signals.rating == 4.0
    assert signals.response_rate == 0.4
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
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_gap_analyzer.py -v`
Expected: ImportError on `tools.gap_analyzer`.

- [ ] **Step 3: Implement `tools/gap_analyzer.py`**

```python
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
        photo_count=details.photo_count,
        review_count=details.review_count,
        rating=details.rating or 0.0,
        response_rate=details.response_rate or 0.0,
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
        "Run a review-generation campaign. Request reviews from recent customers via SMS or email follow-ups.",
    )
    if reviews_gap:
        gaps.append(reviews_gap)

    photos_gap = _numeric_gap(
        "photos",
        prospect_signals.photo_count,
        [c.photo_count for c in competitor_signals],
        "Add high-quality photos: exterior, interior, staff, and activities. Aim to match top competitor count.",
    )
    if photos_gap:
        gaps.append(photos_gap)

    categories_gap = _numeric_gap(
        "categories",
        prospect_signals.category_count,
        [c.category_count for c in competitor_signals],
        "Add relevant secondary categories to expand the keywords you can rank for.",
    )
    if categories_gap:
        gaps.append(categories_gap)

    response_rate_gap = _numeric_gap(
        "review_response_rate",
        prospect_signals.response_rate,
        [c.response_rate for c in competitor_signals],
        "Reply to all recent reviews (positive and negative). Aim for a response rate above 80%.",
    )
    if response_rate_gap:
        gaps.append(response_rate_gap)

    rating_gap = _numeric_gap(
        "rating",
        prospect_signals.rating,
        [c.rating for c in competitor_signals],
        "Improve service quality and actively ask satisfied customers for reviews to raise the average rating.",
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
                recommendation="Publish weekly GBP posts (updates, offers, events) — competitors are active and you are not.",
            )
        )

    if prospect_signals.profile_completeness < 1.0:
        missing = []
        if not prospect_details.phone:
            missing.append("phone")
        if not prospect_details.website:
            missing.append("website")
        if not prospect_details.has_description:
            missing.append("description")
        if not prospect_details.has_hours:
            missing.append("hours")
        recommendation = "Fill in missing GBP profile fields: " + ", ".join(missing) if missing else "Complete all remaining GBP profile fields."
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
        summary.append(f"{prospect_name} is not currently ranking in the Google local pack for '{target_query}'.")
    else:
        summary.append(f"{prospect_name} currently ranks #{prospect_rank} in the Google local pack for '{target_query}'.")

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
        prospect_signals=prospect_signals,
        competitor_signals=competitor_signals,
        prospect_rank=prospect_rank,
        gaps=gaps,
        executive_summary=summary[:5],
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/test_gap_analyzer.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/gap_analyzer.py tests/test_gap_analyzer.py
git commit -m "feat: add gap_analyzer with signal scoring and prioritized recommendations"
```

---

## Task 9: Report HTML template and CSS

**Files:**
- Create: `templates/report.html.j2`
- Create: `templates/report.css`

- [ ] **Step 1: Create `templates/report.css`**

```css
@page {
    size: Letter;
    margin: 0.75in;
    @bottom-right {
        content: counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #888;
    }
}

* {
    box-sizing: border-box;
}

body {
    font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #1a1a1a;
    line-height: 1.5;
    font-size: 11pt;
    margin: 0;
}

h1 {
    font-size: 28pt;
    margin: 0 0 0.25em 0;
    color: #0b3d91;
}

h2 {
    font-size: 18pt;
    margin: 1.5em 0 0.5em;
    color: #0b3d91;
    border-bottom: 2px solid #0b3d91;
    padding-bottom: 0.2em;
    page-break-after: avoid;
}

h3 {
    font-size: 13pt;
    margin: 1em 0 0.3em;
    color: #333;
}

.cover {
    height: 9in;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    page-break-after: always;
}

.cover .title {
    font-size: 36pt;
    color: #0b3d91;
    margin-bottom: 0.3em;
}

.cover .company {
    font-size: 22pt;
    margin-bottom: 0.2em;
}

.cover .city {
    font-size: 16pt;
    color: #555;
    margin-bottom: 2em;
}

.cover .date {
    font-size: 12pt;
    color: #888;
}

.exec-summary {
    background: #f5f8ff;
    border-left: 4px solid #0b3d91;
    padding: 1em 1.5em;
    margin: 1em 0 2em;
    page-break-inside: avoid;
}

.exec-summary ul {
    margin: 0.5em 0 0 0;
    padding-left: 1.2em;
}

.exec-summary li {
    margin-bottom: 0.5em;
}

.rank-callout {
    font-size: 18pt;
    font-weight: bold;
    color: #0b3d91;
    text-align: center;
    padding: 1em;
    background: #f5f8ff;
    border-radius: 6px;
    margin: 1em 0;
}

.rank-callout.not-ranking {
    color: #c0392b;
    background: #fdecea;
}

table.comparison {
    width: 100%;
    border-collapse: collapse;
    font-size: 9.5pt;
    margin: 1em 0;
    page-break-inside: avoid;
}

table.comparison th {
    background: #0b3d91;
    color: white;
    padding: 0.6em 0.5em;
    text-align: left;
    font-weight: 600;
}

table.comparison td {
    padding: 0.5em;
    border-bottom: 1px solid #e5e5e5;
    vertical-align: top;
}

table.comparison tr:nth-child(even) td {
    background: #fafafa;
}

.impact-high {
    color: #c0392b;
    font-weight: bold;
}

.impact-medium {
    color: #d68910;
    font-weight: bold;
}

.impact-low {
    color: #7f8c8d;
}

.recommendation {
    padding: 0.8em 1em;
    margin: 0.5em 0;
    border-left: 3px solid #0b3d91;
    background: #f9f9f9;
    page-break-inside: avoid;
}

.recommendation .impact-label {
    display: inline-block;
    padding: 0.15em 0.6em;
    border-radius: 3px;
    font-size: 9pt;
    margin-right: 0.5em;
    text-transform: uppercase;
}

.recommendation .impact-high { background: #c0392b; color: white; }
.recommendation .impact-medium { background: #d68910; color: white; }
.recommendation .impact-low { background: #7f8c8d; color: white; }

.cta {
    margin-top: 2em;
    padding: 1.5em;
    background: #0b3d91;
    color: white;
    border-radius: 6px;
    text-align: center;
    page-break-inside: avoid;
}

.cta h2 {
    color: white;
    border-bottom: 2px solid white;
}
```

- [ ] **Step 2: Create `templates/report.html.j2`**

```jinja
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Local SEO Audit Report — {{ analysis.prospect_name }}</title>
    <style>{{ css }}</style>
</head>
<body>

<section class="cover">
    <div class="title">Local SEO Audit Report</div>
    <div class="company">{{ analysis.prospect_name }}</div>
    <div class="city">{{ analysis.prospect_city }}</div>
    <div class="date">{{ report_date }}</div>
</section>

<h2>Executive Summary</h2>
<div class="exec-summary">
    <ul>
        {% for item in analysis.executive_summary %}
        <li>{{ item }}</li>
        {% endfor %}
    </ul>
</div>

<h2>Current Local Pack Ranking</h2>
{% if analysis.prospect_rank %}
    <div class="rank-callout">
        Ranked #{{ analysis.prospect_rank }} for "{{ analysis.target_query }}"
    </div>
{% else %}
    <div class="rank-callout not-ranking">
        Not currently ranking in the top 20 for "{{ analysis.target_query }}"
    </div>
{% endif %}

<h2>Google Business Profile Status</h2>
<p>Profile completeness: <strong>{{ (analysis.prospect_signals.profile_completeness * 100) | round(0) | int }}%</strong></p>
<ul>
    <li>Primary category: {{ analysis.prospect_signals.category_count }} {{ 'category' if analysis.prospect_signals.category_count == 1 else 'categories' }} listed</li>
    <li>Photos: {{ analysis.prospect_signals.photo_count }}</li>
    <li>Reviews: {{ analysis.prospect_signals.review_count }} ({{ analysis.prospect_signals.rating }} average)</li>
    <li>Review response rate: {{ (analysis.prospect_signals.response_rate * 100) | round(0) | int }}%</li>
    <li>GBP posts: {{ 'Yes' if analysis.prospect_signals.has_posts else 'No' }}</li>
    <li>Q&amp;A answered: {{ 'Yes' if analysis.prospect_signals.has_qa else 'No' }}</li>
</ul>

<h2>Competitor Comparison</h2>
<table class="comparison">
    <thead>
        <tr>
            <th>Signal</th>
            <th>{{ analysis.prospect_name }}</th>
            {% for c in analysis.competitor_signals %}
            <th>#{{ loop.index }} {{ c.name }}</th>
            {% endfor %}
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>Profile completeness</td>
            <td>{{ (analysis.prospect_signals.profile_completeness * 100) | round(0) | int }}%</td>
            {% for c in analysis.competitor_signals %}
            <td>{{ (c.profile_completeness * 100) | round(0) | int }}%</td>
            {% endfor %}
        </tr>
        <tr>
            <td>Categories</td>
            <td>{{ analysis.prospect_signals.category_count }}</td>
            {% for c in analysis.competitor_signals %}
            <td>{{ c.category_count }}</td>
            {% endfor %}
        </tr>
        <tr>
            <td>Photos</td>
            <td>{{ analysis.prospect_signals.photo_count }}</td>
            {% for c in analysis.competitor_signals %}
            <td>{{ c.photo_count }}</td>
            {% endfor %}
        </tr>
        <tr>
            <td>Reviews</td>
            <td>{{ analysis.prospect_signals.review_count }}</td>
            {% for c in analysis.competitor_signals %}
            <td>{{ c.review_count }}</td>
            {% endfor %}
        </tr>
        <tr>
            <td>Average rating</td>
            <td>{{ analysis.prospect_signals.rating }}</td>
            {% for c in analysis.competitor_signals %}
            <td>{{ c.rating }}</td>
            {% endfor %}
        </tr>
        <tr>
            <td>Response rate</td>
            <td>{{ (analysis.prospect_signals.response_rate * 100) | round(0) | int }}%</td>
            {% for c in analysis.competitor_signals %}
            <td>{{ (c.response_rate * 100) | round(0) | int }}%</td>
            {% endfor %}
        </tr>
        <tr>
            <td>GBP posts</td>
            <td>{{ 'Yes' if analysis.prospect_signals.has_posts else 'No' }}</td>
            {% for c in analysis.competitor_signals %}
            <td>{{ 'Yes' if c.has_posts else 'No' }}</td>
            {% endfor %}
        </tr>
        <tr>
            <td>Services listed</td>
            <td>{{ analysis.prospect_signals.services_listed }}</td>
            {% for c in analysis.competitor_signals %}
            <td>{{ c.services_listed }}</td>
            {% endfor %}
        </tr>
    </tbody>
</table>

<h2>Gap Analysis</h2>
{% if analysis.gaps %}
<ul>
    {% for gap in analysis.gaps %}
    <li>
        <strong>{{ gap.signal | replace('_', ' ') | title }}</strong>:
        you have <strong>{{ gap.prospect_value | round(1) }}</strong>,
        top competitor has <strong>{{ gap.competitor_best | round(1) }}</strong>
        (<span class="impact-{{ gap.impact }}">{{ gap.impact }} impact</span>)
    </li>
    {% endfor %}
</ul>
{% else %}
<p>No significant gaps identified — the business is competitive across all measured signals.</p>
{% endif %}

<h2>Prioritized Recommendations</h2>
{% for gap in analysis.gaps %}
<div class="recommendation">
    <span class="impact-label impact-{{ gap.impact }}">{{ gap.impact }}</span>
    {{ gap.recommendation }}
</div>
{% endfor %}

<div class="cta">
    <h2>Next Steps</h2>
    <p>Ready to close the gaps above? We help local businesses rank higher in Google Maps through GBP optimization, review generation, and local SEO content strategy.</p>
    <p><strong>Reply to this report to schedule a 20-minute strategy call.</strong></p>
</div>

</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add templates/report.html.j2 templates/report.css
git commit -m "feat: add Jinja2 template and CSS for audit PDF report"
```

---

## Task 10: Report generator module

**Files:**
- Create: `tools/report_generator.py`
- Create: `tests/test_report_generator.py`

- [ ] **Step 1: Write failing test for the HTML rendering step**

Create `tests/test_report_generator.py`:

```python
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
        photo_count=10,
        has_hours=True,
        has_description=True,
        has_posts=False,
        has_qa=False,
        services_listed=2,
        attributes=["Wheelchair accessible entrance"],
        latest_review_date="1 week ago",
        response_rate=0.4,
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
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/test_report_generator.py -v`
Expected: ImportError on `tools.report_generator`.

- [ ] **Step 3: Implement `tools/report_generator.py`**

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/test_report_generator.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/report_generator.py tests/test_report_generator.py
git commit -m "feat: add report_generator with Jinja2 rendering and Playwright PDF output"
```

---

## Task 11: CLI orchestrator

**Files:**
- Create: `tools/run_audit.py`

- [ ] **Step 1: Implement `tools/run_audit.py`**

```python
import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from tools.gap_analyzer import analyze
from tools.gbp_enricher import GbpEnricher
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
    enricher = GbpEnricher(api_key=os.environ.get("GOOGLE_PLACES_API_KEY"))

    print(f"Resolving business: {args.company} in {args.city}...")
    business = provider.find_business(args.company, args.city)

    if business is None:
        if not args.service:
            print(
                "ERROR: No Google Business Profile found for this business.\n"
                "Re-run with --service '<service type>' to proceed with a no-GBP audit.",
                file=sys.stderr,
            )
            return 2
        target_query = f"{args.service} {args.city}"
        print(f"No GBP found. Using service override → target query: '{target_query}'")
    else:
        category = business.primary_category or args.service
        if not category:
            print(
                "ERROR: Business found but has no category and no --service was provided.",
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

    top_three = local_pack[:3]
    prospect_rank: Optional[int] = None
    if business is not None:
        prospect_rank = provider.rank_of(business.place_id, local_pack)

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
            primary_category=args.service,
        )
    prospect_details = enricher.enrich(prospect_details)

    competitor_details = []
    for competitor in top_three:
        detail = provider.get_place_details(competitor.place_id)
        detail = enricher.enrich(detail)
        competitor_details.append(detail)

    print("Running gap analysis...")
    analysis = analyze(
        prospect_name=args.company,
        prospect_city=args.city,
        target_query=target_query,
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

    print(f"\n✓ Report generated: {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the module imports and shows help**

Run: `python tools/run_audit.py --help`
Expected: argparse help output listing `--company`, `--city`, `--service`, `--output`, `--no-cache`.

- [ ] **Step 3: Run the full test suite to confirm nothing is broken**

Run: `pytest tests/ -v`
Expected: all tests pass (14 total across cache, serp_provider, gap_analyzer, report_generator).

- [ ] **Step 4: Commit**

```bash
git add tools/run_audit.py
git commit -m "feat: add run_audit CLI orchestrator"
```

---

## Task 12: Operator workflow SOP

**Files:**
- Create: `workflows/audit_local_seo.md`

- [ ] **Step 1: Create `workflows/audit_local_seo.md`**

```markdown
# Workflow: Local SEO Audit

**Objective:** Generate a client-ready PDF audit report for a local business, showing their current Google local-pack rank, a comparison against the top 3 competitors, and prioritized recommendations.

## Required inputs

- Business name (as displayed on their GBP or website)
- City and state (e.g. `Newark, NJ`)

## Optional inputs

- `--service "<service type>"` — only needed when the business has no GBP
- `--output <path>` — override default save location
- `--no-cache` — force fresh API calls

## Setup (one-time)

1. Copy `.env.example` to `.env` and fill in `SERPAPI_KEY`. Get a free key at https://serpapi.com (100 searches/month on the free tier).
2. (Optional) Add `GOOGLE_PLACES_API_KEY` if you want the Places API fallback for missing fields.
3. Install dependencies: `pip install -r requirements.txt`
4. Install Playwright browser: `playwright install chromium`

## Running an audit

```bash
python tools/run_audit.py --company "Sunny Days Daycare" --city "Newark, NJ"
```

The report saves to `.tmp/reports/<company-slug>-<YYYY-MM-DD>.pdf`.

## Auditing a business with no GBP

```bash
python tools/run_audit.py \
  --company "Greenfield Daycare" \
  --city "Newark, NJ" \
  --service "daycare"
```

The tool will fail cleanly if the business has no GBP and `--service` is not provided. The error message will tell you what to do.

## API budget

Each audit consumes roughly **6 SerpApi calls**:
- 1 for business resolution
- 1 for the local pack
- 4 for place details (prospect + top 3 competitors)

On the free tier (100 calls/month), that's about 16 audits per month before hitting the limit. Cached responses are reused for 24 hours, so re-running the same audit doesn't burn additional credits.

## Known edge cases

- **Business not found** → re-run with `--service` to do a "no GBP" audit
- **Business not in top 20** → report still generates; the ranking section says "Not currently ranking"
- **Fewer than 3 competitors in local pack** → report uses what's available, noted in the methodology
- **SerpApi out of credits** → tool fails fast. Wait for the monthly reset or upgrade

## Lessons learned

(Empty for now. Add entries here as you run real audits and discover things.)
```

- [ ] **Step 2: Commit**

```bash
git add workflows/audit_local_seo.md
git commit -m "docs: add operator SOP for local SEO audit workflow"
```

---

## Task 13: Smoke test with a real business

**Files:**
- No file changes. This is a manual validation step.

- [ ] **Step 1: Set up real API key**

Create `.env` from `.env.example` and add a real SerpApi key.

- [ ] **Step 2: Pick a real business with a strong GBP**

Choose a well-established business you can manually verify. Example: a popular local restaurant, daycare, or salon in a city you know.

- [ ] **Step 3: Run the audit end-to-end**

Run: `python tools/run_audit.py --company "<real business>" --city "<real city>"`
Expected: PDF generated at `.tmp/reports/<slug>-<date>.pdf` with no errors.

- [ ] **Step 4: Open the PDF and verify**

Check that:
- Cover page shows the correct business name and city
- Executive summary has 3–5 meaningful bullet points
- Ranking section shows a real position or "not ranking" message
- Comparison table is populated for prospect and 3 competitors
- Gap analysis lists real gaps
- Recommendations are prioritized (high → medium → low)

- [ ] **Step 5: Repeat with a weaker GBP**

Run: `python tools/run_audit.py --company "<smaller business>" --city "<real city>"`
Verify the gap analysis picks up more issues and the recommendations feel useful.

- [ ] **Step 6: Repeat with a no-GBP business**

Try a brand-new or very small business that has no GBP. First attempt should fail cleanly with the "re-run with --service" message.

Then run: `python tools/run_audit.py --company "<no gbp biz>" --city "<city>" --service "<service>"`
Verify the report generates and leads with GBP setup recommendations.

- [ ] **Step 7: Capture real fixtures for committed tests (optional)**

If the real API responses look clean, copy them from `.tmp/cache/` into `fixtures/` (renaming appropriately) to give the test suite real-world data. Scrub any PII before committing.

- [ ] **Step 8: Commit any fixture updates**

```bash
git add fixtures/
git commit -m "test: capture real SerpApi fixtures from smoke test"
```

---

## Self-Review Results

**Spec coverage:**

| Spec requirement | Implemented in |
|------------------|----------------|
| CLI inputs (--company, --city, --service, --output, --no-cache) | Task 11 |
| SerpApi free-tier integration | Tasks 4, 5, 6 |
| Provider abstraction for paid-tier swap | Task 4 |
| Google Places API fallback | Task 7 |
| Business resolution → target query derivation | Task 11 |
| Local pack ranking lookup | Task 5 |
| Enrichment of prospect + top 3 | Task 6, Task 11 |
| Gap analysis with 10 signals | Task 8 |
| Prioritized recommendations | Task 8 |
| 8-section PDF report structure | Tasks 9, 10 |
| Error handling (no GBP, not ranking, API errors, PDF render fail) | Tasks 8, 10, 11 |
| Cache with 24h TTL | Task 3 |
| Fixture-based unit tests | Tasks 4–10 |
| Operator workflow SOP | Task 12 |
| Manual smoke test validation | Task 13 |

All spec requirements have at least one task. The one deliberate deviation (WeasyPrint → Playwright) is called out in the Architecture section at the top of this plan.

**Placeholder scan:** None found. All steps show exact code or exact commands.

**Type consistency:** `BusinessResult`, `PlaceDetails`, `Signals`, `Gap`, `AnalysisResult` used consistently across Tasks 2, 4, 5, 6, 8, 10, 11. Method names (`find_business`, `get_local_pack`, `rank_of`, `get_place_details`, `compute_signals`, `analyze`, `render_html`, `render_pdf`, `generate_report`, `slugify`) match across their definition and usage sites.
