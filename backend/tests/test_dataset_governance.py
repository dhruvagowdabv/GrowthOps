from pathlib import Path

from app.services.dataset_governance import apply_cleaning, compare_drift, preview_cleaning


def test_cleaning_is_reversible_and_keeps_raw_file(tmp_path: Path) -> None:
    source = tmp_path / "raw.csv"
    source.write_text("name,score\n Alice ,10\nBob,NA\nBob,NA\n", encoding="utf-8")
    before = source.read_text(encoding="utf-8")
    preview = preview_cleaning(source)
    assert any(item["operation"] == "trim_whitespace" for item in preview["suggestions"])
    assert any(item["operation"] == "drop_duplicate_rows" for item in preview["suggestions"])

    result = apply_cleaning(source, ["trim_whitespace", "normalize_nulls"], tmp_path / "versions", "upload-1")
    assert source.read_text(encoding="utf-8") == before
    cleaned = Path(result["version_file"]).read_text(encoding="utf-8")
    assert " Alice " not in cleaned
    assert "NA" not in cleaned


def test_drift_detects_removed_and_new_columns() -> None:
    baseline = {"row_count": 10, "columns": [
        {"name": "a", "inferred_type": "integer", "null_count": 0, "null_percent": 0, "unique_count": 5}
    ]}
    current = {"row_count": 10, "columns": [
        {"name": "b", "inferred_type": "string", "null_count": 0, "null_percent": 0, "unique_count": 2}
    ]}
    result = compare_drift(baseline, current)
    assert result["drift_detected"]
    assert {item["type"] for item in result["changes"]} == {"column_added", "column_removed"}
