from __future__ import annotations

import numpy as np

from .models import TrackRecord, ReviewResult


def compute_stats(records: list[TrackRecord], reviews: list[ReviewResult]) -> dict:
    if not reviews:
        return {"total_predictions": len(records), "reviewed": 0}

    correct = [r for r in reviews if r.was_correct is not None]
    accuracy = sum(1 for r in correct if r.was_correct) / len(correct) if correct else 0
    avg_return = float(np.mean([r.price_return for r in reviews])) if reviews else 0

    # By tier
    by_tier: dict[str, dict] = {}
    for r in reviews:
        tier = r.record.tier
        if tier not in by_tier:
            by_tier[tier] = {"total": 0, "correct": 0, "returns": []}
        by_tier[tier]["total"] += 1
        if r.was_correct:
            by_tier[tier]["correct"] += 1
        by_tier[tier]["returns"].append(r.price_return)

    tier_stats = {}
    for tier, stats in by_tier.items():
        tier_stats[tier] = {
            "count": stats["total"],
            "accuracy": stats["correct"] / stats["total"] if stats["total"] > 0 else 0,
            "avg_return": float(np.mean(stats["returns"])) if stats["returns"] else 0,
        }

    return {
        "total_predictions": len(records),
        "reviewed": len(reviews),
        "accuracy": round(accuracy, 2),
        "avg_return": round(avg_return, 4),
        "by_tier": tier_stats,
    }
