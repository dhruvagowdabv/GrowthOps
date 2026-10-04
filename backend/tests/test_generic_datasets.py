"""Stress tests proving analytics is driven by dataset structure, not table names."""

from pathlib import Path

import pytest

from app.services.analytics_engine import analyze_csv


@pytest.mark.parametrize(
    ("filename", "content", "expected_measure", "expected_date"),
    [
        (
            "warehouse.csv",
            "sku,warehouse,stock_level,reorder_point,checked_on\n"
            "X-01,North,120,40,2026-02-01\n"
            "X-02,South,35,50,2026-02-01\n"
            "X-03,North,80,30,2026-02-02\n",
            "stock_level",
            "checked_on",
        ),
        (
            "employees.csv",
            "employee_code,department,tenure_months,salary_band,joined\n"
            "E101,Engineering,18,7,2025-01-10\n"
            "E102,Finance,30,6,2024-01-15\n"
            "E103,Engineering,6,5,2026-01-20\n",
            "tenure_months",
            "joined",
        ),
        (
            "sensor_readings.csv",
            "reading_ref,zone,temperature,humidity,recorded_at\n"
            "R1,A,21.5,42.0,2026-03-01T10:00:00\n"
            "R2,B,22.1,45.5,2026-03-01T11:00:00\n"
            "R3,A,23.0,44.0,2026-03-01T12:00:00\n",
            "temperature",
            "recorded_at",
        ),
        (
            "marketing_events.csv",
            "event_key,channel,converted,ad_spend,occurred\n"
            "EV1,search,true,120.50,2026-04-01\n"
            "EV2,social,false,80.00,2026-04-01\n"
            "EV3,email,true,40.00,2026-04-02\n",
            "ad_spend",
            "occurred",
        ),
    ],
)
def test_engine_handles_unrelated_dataset_shapes(
    tmp_path: Path,
    filename: str,
    content: str,
    expected_measure: str,
    expected_date: str,
) -> None:
    csv_path = tmp_path / filename
    csv_path.write_text(content, encoding="utf-8")

    result = analyze_csv(csv_path)

    assert result["summary"]["row_count"] == 3
    assert expected_measure in result["numeric"]
    assert expected_date in result["trends"]
    assert result["schema"]["column_count"] == 5
    assert result["quality"]["completeness_percent"] == 100.0


def test_engine_handles_non_business_column_names(tmp_path: Path) -> None:
    csv_path = tmp_path / "anonymous.csv"
    csv_path.write_text(
        "a,b,c,d\n"
        "1001,red,12.5,2026-05-01\n"
        "1002,blue,15.0,2026-05-02\n"
        "1003,red,18.0,2026-05-03\n",
        encoding="utf-8",
    )

    result = analyze_csv(csv_path)

    assert result["summary"]["row_count"] == 3
    assert "c" in result["numeric"]
    assert "d" in result["trends"]
    assert any(column["name"] == "a" for column in result["candidate_keys"])


def test_engine_handles_sparse_and_high_cardinality_data(tmp_path: Path) -> None:
    csv_path = tmp_path / "sparse.csv"
    csv_path.write_text(
        "ref,description,score,group\n"
        "R001,alpha,10,A\n"
        "R002,,20,B\n"
        "R003,gamma,,A\n"
        "R004,delta,40,B\n",
        encoding="utf-8",
    )

    result = analyze_csv(csv_path)

    assert result["summary"]["row_count"] == 4
    assert result["quality"]["null_cells"] == 2
    assert result["quality"]["completeness_percent"] < 100
    assert "score" in result["numeric"]
    assert "group" in result["distributions"]


def test_engine_handles_boolean_flags_without_business_rules(tmp_path: Path) -> None:
    csv_path = tmp_path / "flags.csv"
    csv_path.write_text(
        "ref,enabled,verified,value\n"
        "A,true,false,10\n"
        "B,false,true,20\n"
        "C,true,true,30\n",
        encoding="utf-8",
    )

    result = analyze_csv(csv_path)

    roles = {
        column["name"]: column["semantic"]["role"]
        for column in result["schema"]["columns"]
    }

    assert roles["enabled"] == "flag"
    assert roles["verified"] == "flag"
    assert "value" in result["numeric"]
    assert result["numeric"]["value"]["mean"] == 20.0
