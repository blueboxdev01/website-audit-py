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


def test_find_business_falls_back_to_local_results(tmp_path):
    payload = {
        "local_results": [
            {
                "place_id": "ChIJfallback001",
                "title": "The Growing Garden Nursery School",
                "address": "123 Main St, Paramus, NJ",
                "type": ["Nursery school", "Preschool"],
                "rating": 4.5,
                "reviews": 30,
                "gps_coordinates": {"latitude": 40.9445, "longitude": -74.0754},
            },
            {
                "place_id": "ChIJfallback002",
                "title": "The Growing Garden Nursery School of Paramus",
            },
        ]
    }
    fetcher = FakeFetcher(payload)
    provider = SerpProvider(api_key="fake", cache_dir=tmp_path, fetcher=fetcher)

    result = provider.find_business("The Growing Garden Nursery School", "Paramus, NJ")

    assert result is not None
    assert result.place_id == "ChIJfallback001"
    assert result.name == "The Growing Garden Nursery School"
    assert result.primary_category == "Nursery school"


def test_find_business_passes_correct_query(tmp_path, find_business_payload):
    fetcher = FakeFetcher(find_business_payload)
    provider = SerpProvider(api_key="fake", cache_dir=tmp_path, fetcher=fetcher)

    provider.find_business("Sunny Days Daycare", "Newark, NJ")

    assert fetcher.calls[0]["q"] == "Sunny Days Daycare Newark, NJ"
    assert fetcher.calls[0]["engine"] == "google_maps"
    assert fetcher.calls[0]["api_key"] == "fake"


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
    assert details.has_hours is True
    assert details.has_description is True
    assert details.has_posts is False
    assert details.has_qa is False
    assert details.services_listed == 2
    assert "Wheelchair accessible entrance" in details.attributes
    assert details.latest_review_date == "2 weeks ago"
