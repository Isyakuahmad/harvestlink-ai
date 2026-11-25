from datetime import date, timedelta
from types import SimpleNamespace

from app.agents.market_intelligence import build_market_summary, normalize_commodity


def observation(day, price, source="Market survey"):
    return SimpleNamespace(
        commodity="sesame", market_name="Lafia", state="Nasarawa",
        observed_on=day, unit="tonne", currency="NGN",
        min_price=price - 10000, max_price=price + 10000,
        modal_price=price, source_name=source,
    )


def test_normalize_commodity_aliases_and_spacing():
    assert normalize_commodity("  Corn  ") == "maize"
    assert normalize_commodity("Paddy   Rice") == "rice"
    assert normalize_commodity("Sesame") == "sesame"


def test_empty_summary_does_not_invent_prices():
    result = build_market_summary([], today=date(2026, 11, 25))
    assert result["observation_count"] == 0
    assert result["price_range"] is None
    assert result["confidence"] == "insufficient_data"


def test_summary_calculates_range_confidence_and_trend():
    today = date(2026, 11, 25)
    rows = [
        observation(today - timedelta(days=2), 1_500_000, "Source A"),
        observation(today - timedelta(days=3), 1_520_000, "Source B"),
        observation(today - timedelta(days=9), 1_300_000, "Source A"),
        observation(today - timedelta(days=10), 1_320_000, "Source B"),
    ]
    result = build_market_summary(rows, today=today)
    assert result["observation_count"] == 4
    assert result["price_range"] == {"min": 1_290_000, "max": 1_530_000}
    assert result["trend"]["direction"] == "up"
    assert result["trend"]["change_percent"] > 10
    assert result["confidence"] == "medium"


def test_summary_rejects_mixed_units_or_currencies():
    rows = [observation(date(2026, 11, 24), 100)]
    rows.append(SimpleNamespace(**{**vars(rows[0]), "unit": "kg"}))
    try:
        build_market_summary(rows, today=date(2026, 11, 25))
    except ValueError as exc:
        assert "same currency and unit" in str(exc)
    else:
        raise AssertionError("mixed units must not be combined")
