"""Deterministic, evidence-grounded business explanations and recommendations.

This module deliberately avoids causal language. It narrates measured changes and
suggests investigations; it does not claim an observed association is causal.
"""
from __future__ import annotations

from typing import Any


def build_explanation(analysis: dict[str, Any]) -> dict[str, Any]:
    kpis = analysis.get("kpis", {})
    period = analysis.get("period", {})
    findings = []
    for metric, data in kpis.items():
        change = data.get("percentage_change")
        if change is None or abs(change) < 1:
            continue
        direction = "increased" if change > 0 else "decreased"
        findings.append({
            "metric": metric,
            "summary": f"{metric.replace('_', ' ').title()} {direction} by {abs(change):.2f}%.",
            "current": data.get("current"),
            "previous": data.get("previous"),
            "percentage_change": change,
            "evidence_type": "measured_period_comparison",
        })

    drivers = []
    for dimension, items in analysis.get("revenue_contributions", {}).items():
        for item in items[:3]:
            if item.get("change"):
                drivers.append({
                    "metric": "revenue",
                    "dimension": dimension,
                    "segment": item.get("value"),
                    "change": item.get("change"),
                    "contribution_to_net_change_percent": item.get("contribution_to_net_change_percent"),
                    "evidence_type": "descriptive_segment_decomposition",
                    "causal_status": "not_established",
                })
    payment_drivers = []
    for dimension, items in analysis.get("payment_failure_contributions", {}).items():
        for item in items[:2]:
            if item.get("change"):
                payment_drivers.append({
                    "dimension": dimension,
                    "segment": item.get("value"),
                    "failure_count_change": item.get("change"),
                    "evidence_type": "observed_failure_segment_comparison",
                    "causal_status": "not_established",
                })

    revenue = kpis.get("revenue", {})
    revenue_pct = revenue.get("percentage_change")
    headline = "Business performance was broadly stable in the selected comparison."
    if revenue_pct is not None:
        headline = f"Revenue {'increased' if revenue_pct >= 0 else 'decreased'} by {abs(revenue_pct):.2f}% in the selected period."
    narrative_parts = [headline]
    if drivers:
        lead = drivers[0]
        narrative_parts.append(
            f"The largest measured revenue segment change is {lead['dimension']}={lead['segment']} "
            f"({lead['change']:+.2f} revenue units). This is a descriptive contribution, not proof of cause."
        )
    if payment_drivers:
        lead = payment_drivers[0]
        narrative_parts.append(
            f"Payment failures changed most in {lead['dimension']}={lead['segment']} "
            f"({lead['failure_count_change']:+.0f} failures); investigate alongside app releases and payment-provider logs."
        )

    return {
        "headline": headline,
        "narrative": " ".join(narrative_parts),
        "period": period,
        "findings": findings,
        "revenue_contributors": drivers,
        "payment_failure_signals": payment_drivers,
        "evidence_policy": "All findings are computed from supplied records. Associations and segment contributions are not causal proof.",
    }


def generate_recommendations(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations = []
    kpis = analysis.get("kpis", {})
    conversion = kpis.get("conversion_rate_percent", {})
    payment = kpis.get("payment_failure_rate_percent", {})
    revenue = kpis.get("revenue", {})
    margin = kpis.get("gross_margin", {})

    if conversion.get("percentage_change") is not None and conversion["percentage_change"] <= -5:
        weakest = next((stage for stage in analysis.get("funnel", []) if stage.get("dropoff_from_previous_stage")), None)
        recommendations.append({
            "priority": "high",
            "title": "Investigate the conversion decline",
            "action": "Inspect the largest funnel drop-off and compare affected sessions by device, app version and acquisition channel.",
            "evidence": {"conversion_rate": conversion, "largest_observed_funnel_dropoff": weakest},
        })
    if payment.get("percentage_change") is not None and payment["percentage_change"] >= 5:
        top = {
            dimension: items[0]
            for dimension, items in analysis.get("payment_failure_contributions", {}).items() if items
        }
        recommendations.append({
            "priority": "high",
            "title": "Investigate increased payment failures",
            "action": "Review provider responses, payment-method logs and affected device/app-version combinations before changing checkout flows.",
            "evidence": {"payment_failure_rate": payment, "largest_failure_segments": top},
        })
    if revenue.get("percentage_change") is not None and revenue["percentage_change"] <= -5:
        top = {
            dimension: items[0]
            for dimension, items in analysis.get("revenue_contributions", {}).items() if items
        }
        recommendations.append({
            "priority": "high",
            "title": "Validate the largest revenue declines",
            "action": "Check the highest-impact segments for changes in traffic, availability, pricing, discounts and conversion before assigning a cause.",
            "evidence": {"revenue": revenue, "largest_segment_changes": top},
        })
    if margin.get("percentage_change") is not None and margin["percentage_change"] <= -5:
        recommendations.append({
            "priority": "medium",
            "title": "Review margin deterioration",
            "action": "Compare product-level selling prices, costs, discounts and product mix across both periods.",
            "evidence": {"gross_margin": margin, "product_category_contributions": analysis.get("revenue_contributions", {}).get("product_category", [])[:5]},
        })
    if not recommendations:
        recommendations.append({
            "priority": "low",
            "title": "Continue monitoring",
            "action": "No configured high-severity KPI trigger was met. Review the period comparison and data-quality signals before taking action.",
            "evidence": {"kpis": kpis},
        })
    return recommendations
