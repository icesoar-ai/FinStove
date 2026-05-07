from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path
from typing import Optional

import diskcache
import pandas as pd


class DataCache:
    def __init__(self, directory: str = "~/.cache/stocks"):
        self._cache = diskcache.Cache(Path(directory).expanduser())

    def _make_key(self, source: str, method: str, *args, **kwargs) -> str:
        raw = json.dumps({"source": source, "method": method, "args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, source: str, method: str, *args, **kwargs) -> Optional[pd.DataFrame]:
        key = self._make_key(source, method, *args, **kwargs)
        entry = self._cache.get(key)
        if entry is None:
            return None
        stored_at, ttl, df_json = entry
        if ttl > 0 and time.time() - stored_at > ttl:
            self._cache.delete(key)
            return None
        return pd.read_json(io.StringIO(df_json), orient="table") if df_json else None

    def set(self, source: str, method: str, df: pd.DataFrame, *args, ttl: int = 3600, **kwargs) -> None:
        key = self._make_key(source, method, *args, **kwargs)
        self._cache.set(key, (time.time(), ttl, df.to_json(orient="table", date_format="iso")))

    def invalidate(self, source: str = "", pattern: str = "") -> None:
        for key in list(self._cache.iterkeys()):
            if (not source or source in key) and (not pattern or pattern in key):
                self._cache.delete(key)

    def close(self) -> None:
        self._cache.close()
