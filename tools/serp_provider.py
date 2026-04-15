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
            local = cached.get("local_results") or []
            if not local:
                return None
            place = local[0]

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
            has_hours=bool(place.get("hours")),
            has_description=bool(place.get("description")),
            has_posts=bool(place.get("posts")),
            has_qa=bool(place.get("questions")),
            services_listed=len(place.get("service_options") or []),
            attributes=place.get("attributes") or [],
            latest_review_date=latest_review_date,
        )

    @staticmethod
    def rank_of(place_id: str, results: list[BusinessResult]) -> Optional[int]:
        for index, business in enumerate(results, start=1):
            if business.place_id == place_id:
                return index
        return None
