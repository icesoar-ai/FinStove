from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import TrackRecord

TRACK_DIR = Path.home() / ".cache" / "stocks" / "tracking"


def save_record(record: TrackRecord) -> None:
    TRACK_DIR.mkdir(parents=True, exist_ok=True)
    path = TRACK_DIR / f"{record.id}.json"
    data = {
        "id": record.id,
        "ticker": record.ticker,
        "timestamp": record.timestamp.isoformat(),
        "composite_score": record.composite_score,
        "tier": record.tier,
        "dimension_scores": record.dimension_scores,
        "current_price": record.current_price,
        "notes": record.notes,
    }
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_records(ticker: str | None = None) -> list[TrackRecord]:
    if not TRACK_DIR.exists():
        return []
    records = []
    for path in sorted(TRACK_DIR.glob("*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
            if ticker and data.get("ticker") != ticker:
                continue
            records.append(TrackRecord(
                id=data["id"],
                ticker=data["ticker"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                composite_score=data["composite_score"],
                tier=data["tier"],
                dimension_scores=data.get("dimension_scores", {}),
                current_price=data.get("current_price"),
                notes=data.get("notes", ""),
            ))
        except Exception:
            pass
    return records
