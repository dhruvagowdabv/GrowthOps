"""Evidence-first e-commerce KPI, funnel and contribution analysis.

All explanations are descriptive. A segment contribution is not treated as proof
of causation; the response includes the underlying period values and caveats.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, pstdev
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
    total_cost = sum(_number(r, "cost") for r in rows)
    discounts = sum(_number(r, "discount") for r in rows)
    customer_order_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.get("customer_id"):
            customer_order_counts[row["customer_id"]] += 1
    unique_customers = len(customer_order_counts)
    repeat_customers = sum(1 for count in customer_order_counts.values() if count > 1)
    return {
        "orders": orders,
        "revenue": round(revenue, 2),
        "gross_margin": round(margin, 2),
        "gross_margin_rate_percent": round(margin / revenue * 100, 2) if revenue else 0.0,
        "total_cost": round(total_cost, 2),
        "discounts": round(discounts, 2),
        "unique_customers": unique_customers,
        "repeat_customer_rate_percent": round(repeat_customers / unique_customers * 100, 2) if unique_customers else 0.0,
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
    customers_all = _read(root / "customers.csv")
    products_all = _read(root / "products.csv")
    marketing_all = _read(root / "marketing_spend.csv")
    inventory_all = _read(root / "inventory_daily.csv")
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

    session_by_id = {r.get("session_id"): r for r in sessions_all if r.get("session_id")}
    customer_by_id = {r.get("customer_id"): r for r in customers_all if r.get("customer_id")}
    product_by_id = {r.get("product_id"): r for r in products_all if r.get("product_id")}
    enriched_orders = []
    for original in orders_all:
        row = dict(original)
        session = session_by_id.get(row.get("session_id"), {})
        customer = customer_by_id.get(row.get("customer_id"), {})
        product = product_by_id.get(row.get("product_id"), {})
        for key in ("device", "app_version", "region", "channel"):
            if session.get(key):
                row[key if key != "channel" else "session_channel"] = session[key]
        if customer.get("customer_type"):
            row["customer_type"] = customer["customer_type"]
        if product.get("category"):
            row["product_category"] = product["category"]
        if product.get("cost"):
            row["catalog_unit_cost"] = product["cost"]
        enriched_orders.append(row)
    orders = [r for r in enriched_orders if _in_period(r, start, end)]
    prev_orders = [r for r in enriched_orders if _in_period(r, prev_start, prev_end)]
    sessions = [r for r in sessions_all if _in_period(r, start, end)]
    prev_sessions = [r for r in sessions_all if _in_period(r, prev_start, prev_end)]
    payments = [r for r in payments_all if _in_period(r, start, end)]
    prev_payments = [r for r in payments_all if _in_period(r, prev_start, prev_end)]

    cur = _aggregate(orders)
    prev = _aggregate(prev_orders)
    daily_revenue: dict[str, float] = defaultdict(float)
    for row in orders:
        day = _day(row.get("date") or row.get("timestamp"))
        if day is not None:
            daily_revenue[day.isoformat()] += _number(row, "amount")
    daily_values = list(daily_revenue.values())
    daily_mean = mean(daily_values) if daily_values else 0.0
    daily_std = pstdev(daily_values) if len(daily_values) > 1 else 0.0
    daily_anomalies = []
    if len(daily_values) >= 7 and daily_std > 0:
        for day, amount in sorted(daily_revenue.items()):
            z_score = (amount - daily_mean) / daily_std
            if abs(z_score) >= 2.5:
                daily_anomalies.append({
                    "date": day, "revenue": round(amount, 2),
                    "period_daily_mean": round(daily_mean, 2),
                    "z_score": round(z_score, 3),
                    "direction": "above" if z_score > 0 else "below",
                    "method": "period-wide z-score; exploratory signal",
                })
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
        ("gross_margin_rate_percent", cur["gross_margin_rate_percent"], prev["gross_margin_rate_percent"]),
        ("total_cost", cur["total_cost"], prev["total_cost"]),
        ("discounts", cur["discounts"], prev["discounts"]),
        ("unique_customers", cur["unique_customers"], prev["unique_customers"]),
        ("repeat_customer_rate_percent", cur["repeat_customer_rate_percent"], prev["repeat_customer_rate_percent"]),
        ("average_order_value", cur["average_order_value"], prev["average_order_value"]),
        ("conversion_rate_percent", cur_conv, prev_conv),
        ("payment_failure_rate_percent", cur_fail_rate, prev_fail_rate),
    ]:
        kpis[name] = {"current": round(a, 2), "previous": round(b, 2), **_change(a, b)}

    requested = dimensions or ["region", "device", "app_version", "customer_type", "product_category", "acquisition_channel", "campaign", "product_id", "payment_method", "low_quality_acquisition"]
    allowed = set(enriched_orders[0].keys()) if enriched_orders else set()
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

    failure_dimensions = ["device", "app_version", "region", "channel", "payment_method", "failure_reason"]
    payment_failure_contributions = {}
    for dim in failure_dimensions:
        if payments and dim in payments[0]:
            current_failures = [r for r in payments if r.get("payment_status", "").lower() not in {"success", "succeeded", "paid"}]
            previous_failures = [r for r in prev_payments if r.get("payment_status", "").lower() not in {"success", "succeeded", "paid"}]
            payment_failure_contributions[dim] = _breakdown(current_failures, previous_failures, dim, "count")

    spend_current: dict[str, float] = defaultdict(float)
    spend_previous: dict[str, float] = defaultdict(float)
    for row in marketing_all:
        day = _day(row.get("date"))
        if day is None:
            continue
        if start <= day <= end:
            spend_current[row.get("channel") or "(missing)"] += _number(row, "spend")
        elif prev_start <= day <= prev_end:
            spend_previous[row.get("channel") or "(missing)"] += _number(row, "spend")
    marketing_efficiency = []
    for channel in sorted(set(spend_current) | set(spend_previous)):
        current_revenue = sum(_number(r, "amount") for r in orders if r.get("acquisition_channel") == channel)
        previous_revenue = sum(_number(r, "amount") for r in prev_orders if r.get("acquisition_channel") == channel)
        current_spend, previous_spend = spend_current[channel], spend_previous[channel]
        marketing_efficiency.append({
            "channel": channel,
            "current_spend": round(current_spend, 2),
            "previous_spend": round(previous_spend, 2),
            "current_attributed_revenue": round(current_revenue, 2),
            "previous_attributed_revenue": round(previous_revenue, 2),
            "current_roas": round(current_revenue / current_spend, 3) if current_spend else None,
            "previous_roas": round(previous_revenue / previous_spend, 3) if previous_spend else None,
            "attribution_note": "Revenue is grouped by the order acquisition_channel field; this is not a causal incrementality estimate.",
        })

    inventory_summary = {}
    if inventory_all:
        current_inventory = [r for r in inventory_all if _in_period(r, start, end)]
        inventory_summary = {
            "records": len(current_inventory),
            "stock_status_counts": dict(__import__("collections").Counter(r.get("stock_status", "(missing)") for r in current_inventory)),
        }

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
    for anomaly in daily_anomalies:
        observations.append({
            "type": "daily_revenue_anomaly",
            "metric": "revenue",
            "statement": f"Revenue on {anomaly['date']} was {anomaly['direction']} the period distribution (z-score {anomaly['z_score']}).",
            "evidence": anomaly,
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
        "daily_revenue_anomalies": daily_anomalies,
        "revenue_contributions": contributions,
        "payment_failure_contributions": payment_failure_contributions,
        "marketing_efficiency": marketing_efficiency,
        "inventory_signal": inventory_summary,
        "observations": observations,
        "limitations": [
            "Segment changes are descriptive contributions, not causal proof.",
            "Conversion is orders divided by sessions; attribution may differ if orders span sessions.",
            "Known e-commerce event types are ordered into a funnel; unknown event types are appended alphabetically.",
            "Segment changes are observational and may be affected by mix shifts, seasonality or confounding factors.",
            "Marketing ROAS uses observed channel-labelled revenue and spend, not incrementality testing.",
            "Inventory signals are descriptive snapshots and do not establish that stockouts caused lost sales.",
            "Daily revenue anomalies use a period-wide z-score and should be reviewed for calendar, promotion and data-volume effects.",
            "Missing source files or columns reduce the available analysis.",
        ],
    }
