from pathlib import Path

from app.services.validation import validate_csv


CUSTOMER_SCHEMA = {
    "required_fields": {"customer_id", "signup_date", "country"},
    "expected_types": {
        "customer_id": "string",
        "signup_date": "date",
        "country": "string",
    },
    "key_fields": ["customer_id"],
}


def test_valid_csv_passes(tmp_path: Path) -> None:
    path = tmp_path / "valid.csv"
    path.write_text(
        "customer_id,signup_date,country\n"
        "C001,2026-01-01,IN\n"
        "C002,2026-01-02,IN\n",
        encoding="utf-8",
    )

    result = validate_csv(path, **CUSTOMER_SCHEMA)

    assert result["status"] == "passed"
    assert result["summary"]["errors"] == 0


def test_missing_required_field_is_error(tmp_path: Path) -> None:
    path = tmp_path / "missing.csv"
    path.write_text(
        "customer_id,country\n"
        "C001,IN\n",
        encoding="utf-8",
    )

    result = validate_csv(path, **CUSTOMER_SCHEMA)

    assert result["status"] == "error"
    assert any(issue["code"] == "missing_required_field" for issue in result["issues"])


def test_type_mismatch_is_error(tmp_path: Path) -> None:
    path = tmp_path / "bad_type.csv"
    path.write_text(
        "customer_id,signup_date,country\n"
        "C001,not-a-date,IN\n",
        encoding="utf-8",
    )

    result = validate_csv(path, **CUSTOMER_SCHEMA)

    assert result["status"] == "error"
    assert any(issue["code"] == "type_mismatch" for issue in result["issues"])


def test_duplicate_key_is_error(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.csv"
    path.write_text(
        "customer_id,signup_date,country\n"
        "C001,2026-01-01,IN\n"
        "C001,2026-01-02,IN\n",
        encoding="utf-8",
    )

    result = validate_csv(path, **CUSTOMER_SCHEMA)

    assert result["status"] == "error"
    assert any(issue["code"] == "duplicate_key" for issue in result["issues"])


def test_null_values_are_warning_when_not_key(tmp_path: Path) -> None:
    path = tmp_path / "null.csv"
    path.write_text(
        "customer_id,signup_date,country\n"
        "C001,2026-01-01,\n"
        "C002,2026-01-02,IN\n",
        encoding="utf-8",
    )

    result = validate_csv(path, **CUSTOMER_SCHEMA)

    assert result["status"] == "warning"
    assert result["summary"]["errors"] == 0
    assert any(issue["code"] == "null_values" and issue["column"] == "country" for issue in result["issues"])
