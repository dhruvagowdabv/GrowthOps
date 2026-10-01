from pathlib import Path

from app.services.profiling import profile_csv


def test_profile_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "customer_id,signup_date,spend,active\n"
        "C001,2026-01-01,12.5,true\n"
        "C002,2026-01-02,20.0,false\n"
        "C003,,15.0,true\n",
        encoding="utf-8",
    )

    profile = profile_csv(csv_path)

    assert profile["row_count"] == 3
    assert profile["column_count"] == 4
    assert profile["columns"][0]["name"] == "customer_id"
    assert profile["columns"][0]["inferred_type"] == "string"
    assert profile["columns"][1]["inferred_type"] == "date"
    assert profile["columns"][1]["null_count"] == 1
    assert profile["columns"][2]["inferred_type"] == "number"
    assert profile["columns"][3]["inferred_type"] == "boolean"


def test_profile_rejects_duplicate_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text("id,id\n1,2\n", encoding="utf-8")

    try:
        profile_csv(csv_path)
    except ValueError as exc:
        assert str(exc) == "CSV contains duplicate column names"
    else:
        raise AssertionError("Expected duplicate-column validation error")
