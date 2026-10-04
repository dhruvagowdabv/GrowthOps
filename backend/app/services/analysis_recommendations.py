"""Generate domain-neutral analysis recommendations from inferred analytics."""

from __future__ import annotations

from typing import Any


MAX_RECOMMENDATIONS = 30
MAX_DIMENSION_VALUES = 20


def _column_semantics(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        column["name"]: column
        for column in schema.get("columns", [])
        if column.get("name")
    }


def recommend_analyses(analytics: dict[str, Any]) -> list[dict[str, Any]]:
    """Return useful chart/KPI candidates without knowing the dataset domain.

    Recommendations are based only on inferred semantic roles and computed
    analytics. They are suggestions, not claims about business meaning.
    """
    schema = analytics.get("schema", {})
    semantics = _column_semantics(schema)
    numeric = analytics.get("numeric", {})
    distributions = analytics.get("distributions", {})
    trends = analytics.get("trends", {})
    correlations = analytics.get("correlations", [])
    recommendations: list[dict[str, Any]] = []

    measures = [
        name for name, column in semantics.items()
        if name in numeric and column.get("semantic", {}).get("role") == "measure"
    ]
    dimensions = [
        name for name, column in semantics.items()
        if column.get("semantic", {}).get("role") in {"category", "flag"}
        and name in distributions
        and distributions[name]
    ]
    dates = [
        name for name, column in semantics.items()
        if column.get("semantic", {}).get("role") == "datetime"
        and name in trends
        and trends[name]
    ]

    for measure in measures:
        stats = numeric[measure]
        recommendations.append({
            "type": "kpi",
            "priority": 90,
            "title": f"Summary of {measure}",
            "columns": [measure],
            "operation": "summary",
            "metrics": ["sum", "mean", "median", "min", "max"],
            "reason": "A numeric measure supports aggregate summary metrics.",
        })

        if len(recommendations) >= MAX_RECOMMENDATIONS:
            return recommendations

        if stats.get("outlier_count", 0):
            recommendations.append({
                "type": "distribution",
                "priority": 75,
                "title": f"Distribution and outliers of {measure}",
                "columns": [measure],
                "operation": "distribution",
                "metrics": ["q1", "median", "q3", "outlier_count"],
                "reason": "The numeric measure contains observations outside its IQR bounds.",
            })

    for dimension in dimensions:
        values = distributions[dimension]
        if len(values) <= MAX_DIMENSION_VALUES:
            recommendations.append({
                "type": "breakdown",
                "priority": 80,
                "title": f"Records by {dimension}",
                "columns": [dimension],
                "operation": "count",
                "metrics": ["count", "share"],
                "reason": "A low-cardinality categorical dimension is suitable for a frequency breakdown.",
            })

        for measure in measures:
            recommendations.append({
                "type": "comparison",
                "priority": 85,
                "title": f"{measure} by {dimension}",
                "columns": [dimension, measure],
                "operation": "grouped_summary",
                "metrics": ["count", "sum", "mean"],
                "reason": "A categorical dimension can be used to compare a numeric measure.",
            })
            if len(recommendations) >= MAX_RECOMMENDATIONS:
                return recommendations

    for date_column in dates:
        recommendations.append({
            "type": "trend",
            "priority": 95,
            "title": f"Records over {date_column}",
            "columns": [date_column],
            "operation": "time_series_count",
            "metrics": ["count"],
            "reason": "An inferred datetime column supports time-based record frequency analysis.",
        })
        for measure in measures:
            recommendations.append({
                "type": "trend",
                "priority": 98,
                "title": f"{measure} over {date_column}",
                "columns": [date_column, measure],
                "operation": "time_series_summary",
                "metrics": ["sum", "mean"],
                "reason": "A datetime column and numeric measure support a time-series summary.",
            })
            if len(recommendations) >= MAX_RECOMMENDATIONS:
                return recommendations

    for correlation in correlations:
        coefficient = correlation.get("coefficient")
        if coefficient is None:
            continue
        recommendations.append({
            "type": "relationship",
            "priority": 70 if abs(coefficient) >= 0.8 else 55,
            "title": f"Relationship between {correlation['left']} and {correlation['right']}",
            "columns": [correlation["left"], correlation["right"]],
            "operation": "correlation",
            "metrics": ["pearson"],
            "reason": "Both columns are numeric and their observed linear relationship was measured.",
            "coefficient": coefficient,
        })
        if len(recommendations) >= MAX_RECOMMENDATIONS:
            return recommendations

    return sorted(recommendations, key=lambda item: item["priority"], reverse=True)[:MAX_RECOMMENDATIONS]
