"""
GST policy helpers for quarter-specific filing treatment overrides.

This currently supports an amnesty window that neutralizes late-filing
penalties for covered periods without requiring a model retrain.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable

from ..core.settings import Settings, get_settings


def _parse_month_value(value: str | None) -> date | None:
    if not value:
        return None

    raw = value.strip()
    if not raw:
        return None

    month_candidate = raw[:7]
    try:
        return datetime.strptime(month_candidate, "%Y-%m").date().replace(day=1)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(raw, fmt).date().replace(day=1)
        except ValueError:
            continue

    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date().replace(day=1)
    except ValueError:
        return None


def _month_key(value: str | None) -> str | None:
    parsed = _parse_month_value(value)
    return parsed.strftime("%Y-%m") if parsed else None


def _compute_gst_velocity_metrics(history: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    rows = list(history)
    eligible_periods = [row for row in rows if not row.get("_exclude_from_filing_rate")]
    filed_rows = [row for row in eligible_periods if row.get("filed")]
    total_periods = len(eligible_periods)
    total_filed = len(filed_rows)
    delays = [
        float(row["delay_days"])
        for row in filed_rows
        if row.get("delay_days") is not None
    ]
    on_time = len([row for row in filed_rows if row.get("delay_days") is not None and float(row["delay_days"]) <= 10])

    return {
        "filings_per_month": round(total_filed / max(total_periods, 1), 2),
        "avg_delay_days": round(sum(delays) / max(total_filed, 1), 1) if delays else 0.0,
        "on_time_pct": round(on_time / max(total_filed, 1) * 100, 1) if total_filed else 100.0,
        "eligible_period_count": total_periods,
        "filed_period_count": total_filed,
    }


def _covered_periods_from_settings(settings: Settings) -> set[str]:
    explicit_periods = {
        period
        for period in (_month_key(item) for item in settings.gst_amnesty_periods)
        if period
    }

    start = _parse_month_value(settings.gst_amnesty_start)
    end = _parse_month_value(settings.gst_amnesty_end)
    if not start or not end:
        return explicit_periods

    if start > end:
        start, end = end, start

    cursor = start
    covered = set(explicit_periods)
    while cursor <= end:
        covered.add(cursor.strftime("%Y-%m"))
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return covered


def summarize_gst_amnesty_policy(
    gst_data: Dict[str, Any],
    *,
    settings: Settings | None = None,
) -> Dict[str, Any]:
    resolved_settings = settings or get_settings()
    filing_history = list(gst_data.get("filing_history") or [])
    raw_metrics = _compute_gst_velocity_metrics(filing_history)
    configured_periods = sorted(_covered_periods_from_settings(resolved_settings))

    summary: Dict[str, Any] = {
        "enabled": resolved_settings.gst_amnesty_enabled,
        "policy_name": "GST late filing amnesty",
        "configured_periods": configured_periods,
        "amnesty_applied": False,
        "covered_periods": [],
        "covered_filing_count": 0,
        "neutralized_late_filings": 0,
        "excluded_unfiled_periods": 0,
        "raw_metrics": raw_metrics,
        "adjusted_metrics": dict(raw_metrics),
    }

    if not resolved_settings.gst_amnesty_enabled or not configured_periods or not filing_history:
        return summary

    adjusted_history = []
    covered_periods = set()
    covered_filing_count = 0
    neutralized_late_filings = 0
    excluded_unfiled_periods = 0

    for row in filing_history:
        period_key = _month_key(row.get("period")) or _month_key(row.get("due_date"))
        covered = period_key in configured_periods if period_key else False
        adjusted_row = dict(row)
        if covered and period_key:
            covered_periods.add(period_key)
            if adjusted_row.get("filed"):
                covered_filing_count += 1
                original_delay = adjusted_row.get("delay_days")
                if original_delay is not None and float(original_delay) > 10:
                    neutralized_late_filings += 1
                adjusted_row["delay_days"] = 0
            else:
                adjusted_row["_exclude_from_filing_rate"] = True
                excluded_unfiled_periods += 1
        adjusted_history.append(adjusted_row)

    adjusted_metrics = _compute_gst_velocity_metrics(adjusted_history)
    summary["amnesty_applied"] = bool(covered_periods)
    summary["covered_periods"] = sorted(covered_periods)
    summary["covered_filing_count"] = covered_filing_count
    summary["neutralized_late_filings"] = neutralized_late_filings
    summary["excluded_unfiled_periods"] = excluded_unfiled_periods
    summary["adjusted_metrics"] = adjusted_metrics
    return summary
