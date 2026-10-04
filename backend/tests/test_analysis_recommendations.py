from pathlib import Path

from app.services.analysis_recommendations import recommend_analyses
from app.services.analytics_engine import analyze_csv


def test_recommendations_are_domain_neutral(tmp_path: Path) -> None:
    csv_path = tmp_path / "warehouse.csv"
    csv_path.write_text(
        "sku,region,stock_level,checked_on\n"
        "X-01,North,120,2026-02-01\n"
        "X-02,South,35,2026-02-01\n"
        "X-03,North,80,2026-02-02\n",
        encoding="utf-8",
    )

    result = analyze_csv(csv_path)
    recommendations = result["recommendations"]

    assert recommendations
    assert any(item["type"] == "kpi" and item["columns"] == ["stock_level"] for item in recommendations)
    assert any(item["type"] == "breakdown" and item["columns"] == ["region"] for item in recommendations)
    assert any(item["type"] == "comparison" and item["columns"] == ["region", "stock_level"] for item in recommendations)
    assert any(item["type"] == "trend" and item["columns"] == ["checked_on", "stock_level"] for item in recommendations)


def test_recommendations_include_numeric_relationships() -> None:
    analytics = {
        "schema": {
            "columns": [
                {"name": "a", "semantic": {"role": "measure"}},
                {"name": "b", "semantic": {"role": "measure"}},
            ]
        },
        "numeric": {
            "a": {"sum": 6, "mean": 2, "median": 2, "min": 1, "max": 3, "outlier_count": 0},
            "b": {"sum": 12, "mean": 4, "median": 4, "min": 2, "max": 6, "outlier_count": 0},
        },
        "distributions": {},
        "trends": {},
        "correlations": [{"left": "a", "right": "b", "coefficient": 1.0}],
    }

    recommendations = recommend_analyses(analytics)

    relationship = next(item for item in recommendations if item["type"] == "relationship")
    assert relationship["columns"] == ["a", "b"]
    assert relationship["operation"] == "correlation"
    assert relationship["coefficient"] == 1.0


def test_recommendations_are_bounded() -> None:
    columns = [{"name": f"m{i}", "semantic": {"role": "measure"}} for i in range(20)]
    analytics = {
        "schema": {"columns": columns},
        "numeric": {
            column["name"]: {
                "sum": 1,
                "mean": 1,
                "median": 1,
                "min": 1,
                "max": 1,
                "outlier_count": 0,
            }
            for column in columns
        },
        "distributions": {},
        "trends": {},
        "correlations": [],
    }

    assert len(recommend_analyses(analytics)) <= 30
