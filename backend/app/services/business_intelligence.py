"""Evidence-first e-commerce KPI, funnel and contribution analysis.

All explanations are descriptive. A segment contribution is not treated as proof
of causation; the response includes the underlying period values and caveats.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S")


def _read(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _day(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return date.fromisoformat(value[:10]) if fmt == DATE_FORMATS[0] else date.fromisoformat(value[:10])
        except ValueError:
            continue
    return None


def _number(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "") or 0)
    except (TypeError, ValueError):
        return 0.0


def _in_period(row: dict[str, str], start: date, end: date, field: str = "date") -> bool:
    value = _day(row.get(field) or row.get("timestamp"))
    return value is not None and start <= value <= end


def _metric_rows(rows: list[dict[str, str]], metric: str) -> float:
    if metric == "orders":
        return float(len({r.get("order_id") for r in rows if r.get("order_id")}))
    if metric == "revenue":
        return sum(_number(r, "amount") for r in rows)
    if metric == "gross_margin":
        return sum(_number(r, "gross_margin") for r in rows)
    if metric == "discount":
        return sum(_number(r, "discount") for r in rows)
    return float(len(rows))


def _aggregate(rows: list[dict[str, str]]) -> dict[str, float]:
    orders = len({r.get("order_id") for r in rows if r.get("order_id")})
    revenue = sum(_number(r, "amount") for r in rows)
    margin = sum(_number(r, "gross_margin") for r in rows)
    return {
        "orders": orders,
        "revenue": round(revenue, 2),
        "gross_margin": round(margin, 2),
        "average_order_value": round(revenue / orders, 2) if orders else 0.0,
    }


def _change(current: float, previous: float) -> dict[str, float | None]:
    delta = current - previous
    return {
        "absolute_change": round(delta, 4),
        "percentage_change": round(delta / abs(previous) * 100, 2) if previous else None,
    }


def _breakdown(rows: list[dict[str, str]], previous_rows: list[dict[str, str]], dimension: str, metric: str, limit: int = 15) -> list[dict[str, Any]]:
    current_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    previous_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        current_groups[row.get(dimension) or "(missing)"].append(row)
    for row in previous_rows:
        previous_groups[row.get(dimension) or "(missing)"].append(row)
    keys = set(current_groups) | set(previous_groups)
    results = []
    for key in keys:
        current = _metric_rows(current_groups[key], metric)
        previous = _metric_rows(previous_groups[key], metric)
        change = current - previous
        results.append({
            "dimension": dimension,
            "value": key,
            "current": round(current, 2),
            "previous": round(previous, 2),
            "change": round(change, 2),
            "percentage_change": round(change / abs(previous) * 100, 2) if previous else None,
        })
    net_change = sum(item["change"] for item in results)
    for item in results:
        item["contribution_to_net_change_percent"] = round(item["change"] / net_change * 100, 2) if net_change else None
    return sorted(results, key=lambda x: abs(x["change"]), reverse=True)[:limit]


def analyze_business(data_dir: str | Path, start_date: str | None = None, end_date: str | None = None,
                     dimensions: list[str] | None = None) -> dict[str, Any]:
    """Calculate business KPIs and evidence-backed period comparisons from CSV inputs."""
    root = Path(data_dir)
    orders_all = _read(root / "orders.csv")
    sessions_all = _read(root / "sessions.csv")
    events_all = _read(root / "events.csv")
    payments_all = _read(root / "payment_attempts.csv")
    if not orders_all and not sessions_all:
        raise ValueError("No orders.csv or sessions.csv found in the configured data directory")

    available_days = [_day(r.get("date") or r.get("timestamp")) for r in orders_all + sessions_all]
    available_days = [d for d in available_days if d]
    if not available_days:
        raise ValueError("No parseable date column found in orders or sessions")
    end = date.fromisoformat(end_date) if end_date else max(available_days)
    start = date.fromisoformat(start_date) if start_date else end - timedelta(days=29)
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    span = (end - start).days + 1
    prev_end, prev_start = start - timedelta(days=1), start - timedelta(days=span)

    orders = [r for r in orders_all if _in_period(r, start, end)]
    prev_orders = [r for r in orders_all if _in_period(r, prev_start, prev_end)]
    sessions = [r for r in sessions_all if _in_period(r, start, end)]
    prev_sessions = [r for r in sessions_all if _in_period(r, prev_start, prev_end)]
    payments = [r for r in payments_all if _in_period(r, start, end)]
    prev_payments = [r for r in payments_all if _in_period(r, prev_start, prev_end)]

    cur = _aggregate(orders)
    prev = _aggregate(prev_orders)
    cur_conv = cur["orders"] / len(sessions) * 100 if sessions else 0.0
    prev_conv = prev["orders"] / len(prev_sessions) * 100 if prev_sessions else 0.0
    cur_fail = sum(1 for r in payments if r.get("payment_status", "").lower() not in {"success", "succeeded", "paid"})
    prev_fail = sum(1 for r in prev_payments if r.get("payment_status", "").lower() not in {"success", "succeeded", "paid"})
    cur_fail_rate = cur_fail / len(payments) * 100 if payments else 0.0
    prev_fail_rate = prev_fail / len(prev_payments) * 100 if prev_payments else 0.0

    kpis = {}
    for name, a, b in [
        ("revenue", cur["revenue"], prev["revenue"]),
        ("orders", cur["orders"], prev["orders"]),
        ("gross_margin", cur["gross_margin"], prev["gross_margin"]),
        ("average_order_value", cur["average_order_value"], prev["average_order_value"]),
        ("conversion_rate_percent", cur_conv, prev_conv),
        ("payment_failure_rate_percent", cur_fail_rate, prev_fail_rate),
    ]:
        kpis[name] = {"current": round(a, 2), "previous": round(b, 2), **_change(a, b)}

    requested = dimensions or ["region", "acquisition_channel", "campaign", "product_id", "payment_method", "low_quality_acquisition"]
    allowed = set(orders[0].keys()) if orders else set()
    contributions = {
        dim: _breakdown(orders, prev_orders, dim, "revenue")
        for dim in requested if dim in allowed
    }

    event_counts: dict[str, set[str]] = defaultdict(set)
    prev_event_counts: dict[str, set[str]] = defaultdict(set)
    for row in events_all:
        event_day = _day(row.get("timestamp"))
        if event_day is None:
            continue
        target = event_counts if start <= event_day <= end else prev_event_counts if prev_start <= event_day <= prev_end else None
        if target is not None:
            target[row.get("event_type") or "(unknown)"].add(row.get("session_id") or row.get("event_id") or "")
    funnel = []
    preferred_order = ["session_start", "product_view", "add_to_cart", "checkout_started", "payment_attempt", "purchase"]
    observed = set(event_counts) | set(prev_event_counts)
    ordered_events = [name for name in preferred_order if name in observed]
    ordered_events.extend(sorted(observed - set(ordered_events)))
    previous_stage_count = None
    for event_name in ordered_events:
        c, p = len(event_counts[event_name]), len(prev_event_counts[event_name])
        funnel.append({
            "stage": event_name,
            "sessions": c,
            "previous_sessions": p,
            "conversion_from_previous_stage_percent": round(c / previous_stage_count * 100, 2) if previous_stage_count else None,
            "dropoff_from_previous_stage": max(previous_stage_count - c, 0) if previous_stage_count is not None else None,
            **_change(float(c), float(p)),
        })
        previous_stage_count = c

    observations = []
    for name, data in kpis.items():
        pct = data["percentage_change"]
        if pct is not None and abs(pct) >= 5:
            direction = "increased" if pct > 0 else "decreased"
            observations.append({
                "type": "kpi_change", "metric": name,
                "statement": f"{name.replace('_', ' ')} {direction} by {abs(pct)}% compared with the previous period.",
                "evidence": data,
            })
    for dimension, items in contributions.items():
        for item in items[:3]:
            if abs(item["change"]) > 0:
                observations.append({
                    "type": "segment_contribution", "metric": "revenue",
                    "statement": f"Revenue change is concentrated in {dimension}={item['value']}.",
                    "evidence": item,
                    "interpretation": "Observed segment contribution; not proof of causation.",
                })

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(),
                   "previous_start": prev_start.isoformat(), "previous_end": prev_end.isoformat()},
        "kpis": kpis,
        "counts": {"sessions": len(sessions), "previous_sessions": len(prev_sessions),
                   "payment_attempts": len(payments), "previous_payment_attempts": len(prev_payments),
                   "payment_failures": cur_fail, "previous_payment_failures": prev_fail},
        "funnel": funnel,
        "revenue_contributions": contributions,
        "observations": observations,
        "limitations": [
            "Segment changes are descriptive contributions, not causal proof.",
            "Conversion is orders divided by sessions; attribution may differ if orders span sessions.",
            "Funnel stages are event types ranked by distinct sessions, not an assumed ordered funnel.",
            "Missing source files or columns reduce the available analysis.",
        ],
    }
