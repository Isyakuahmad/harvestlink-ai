"""Deterministic, evidence-led market intelligence calculations."""
from collections.abc import Iterable
from datetime import date, timedelta
from statistics import mean
from typing import Any


def normalize_commodity(value: str) -> str:
    aliases = {"corn": "maize", "paddy rice": "rice", "ground nut": "groundnut"}
    cleaned = " ".join(value.strip().casefold().split())
    if not cleaned:
        raise ValueError("commodity is required")
    return aliases.get(cleaned, cleaned)


def build_market_summary(observations: Iterable[Any], *, today: date | None = None) -> dict:
    """Summarise only observations already authorised by the caller.

    Each observation must expose commodity, market_name, state, observed_on,
    unit, currency, min_price, max_price, modal_price and source_name.
    """
    rows = list(observations)
    if not rows:
        return {
            "observation_count": 0,
            "price_range": None,
            "average_modal_price": None,
            "latest_observed_on": None,
            "trend": {"direction": "insufficient_data", "change_percent": None},
            "confidence": "insufficient_data",
            "limitations": ["No approved market observations match this request."],
        }

    currencies = {row.currency for row in rows}
    units = {row.unit for row in rows}
    if len(currencies) != 1 or len(units) != 1:
        raise ValueError("Market observations must use the same currency and unit")

    latest = max(row.observed_on for row in rows)
    reference_day = today or date.today()
    recent_cutoff = reference_day - timedelta(days=7)
    prior_cutoff = reference_day - timedelta(days=14)
    recent = [row.modal_price for row in rows if row.observed_on >= recent_cutoff]
    prior = [
        row.modal_price for row in rows
        if prior_cutoff <= row.observed_on < recent_cutoff
    ]
    change = None
    direction = "insufficient_data"
    if recent and prior:
        previous_average = mean(prior)
        if previous_average:
            change = round((mean(recent) - previous_average) / previous_average * 100, 2)
            direction = "up" if change > 1 else "down" if change < -1 else "stable"

    source_count = len({row.source_name.casefold() for row in rows})
    count = len(rows)
    confidence = "high" if count >= 10 and source_count >= 3 else (
        "medium" if count >= 4 and source_count >= 2 else "low"
    )
    limitations = []
    if latest < reference_day - timedelta(days=14):
        limitations.append("The latest approved observation is more than 14 days old.")
    if confidence == "low":
        limitations.append("Limited observations or source diversity; treat this as indicative.")
    if change is None:
        limitations.append("A 7-day comparison is unavailable; no price trend is asserted.")

    return {
        "observation_count": count,
        "market_count": len({(row.market_name, row.state) for row in rows}),
        "source_count": source_count,
        "currency": rows[0].currency,
        "unit": rows[0].unit,
        "price_range": {
            "min": min(row.min_price for row in rows),
            "max": max(row.max_price for row in rows),
        },
        "average_modal_price": round(mean(row.modal_price for row in rows), 2),
        "latest_observed_on": latest.isoformat(),
        "trend": {"direction": direction, "change_percent": change},
        "confidence": confidence,
        "limitations": limitations,
    }
