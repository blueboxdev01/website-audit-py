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
