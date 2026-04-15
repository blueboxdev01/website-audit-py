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
