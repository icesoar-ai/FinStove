from __future__ import annotations

from datetime import date, datetime, timedelta

from .models import TrackRecord, ReviewResult
from .record import load_records


def review_ticker(ticker: str, current_price: float, min_days: int = 30) -> list[ReviewResult]:
    """Review historical predictions against current price."""
    records = load_records(ticker)
    results = []
    cutoff = date.today() - timedelta(days=min_days)

    for r in records:
        elapsed = (date.today() - r.timestamp.date()).days
        if elapsed < min_days:
            continue

        if r.current_price and r.current_price > 0:
            price_return = (current_price - r.current_price) / r.current_price
        else:
            price_return = 0.0

        # Determine if prediction was directionally correct
        was_correct = None
        if r.tier in ("BUY", "STRONG_BUY") and price_return > 0:
            was_correct = True
        elif r.tier in ("SELL", "STRONG_SELL") and price_return < 0:
            was_correct = True
        elif r.tier in ("BUY", "STRONG_BUY") and price_return < 0:
            was_correct = False
        elif r.tier in ("SELL", "STRONG_SELL") and price_return > 0:
            was_correct = False

        results.append(ReviewResult(
            record=r,
            elapsed_days=elapsed,
            current_price=current_price,
            price_return=price_return,
            was_correct=was_correct,
        ))

    return results
