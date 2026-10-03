from pathlib import Path

from app.services.analytics_engine import analyze_csv


def test_engine_analyzes_unknown_dataset_without_table_specific_logic(tmp_path: Path) -> None:
    csv_path = tmp_path / "inventory.csv"
    csv_path.write_text(
        "item_code,recorded_date,category,quantity,revenue\n"
        "A1,2026-01-01,Hardware,2,100.50\n"
        "A2,2026-01-01,Software,4,250.00\n"
        "A3,2026-01-02,Hardware,3,150.00\n"
        "A4,2026-01-02,Software,1,50.00\n",
        encoding="utf-8",
    )

    result = analyze_csv(csv_path)

    assert result["summary"]["row_count"] == 4
    assert result["summary"]["column_count"] == 5
    assert result["numeric"]["quantity"]["sum"] == 10.0
    assert result["numeric"]["revenue"]["sum"] == 550.5
    assert result["distributions"]["category"][0] == {"value": "Hardware", "count": 2}
    assert len(result["trends"]["recorded_date"]) == 2
    assert any(key["column"] == "item_code" for key in result["candidate_keys"])


def test_engine_handles_empty_optional_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "mixed.csv"
    csv_path.write_text(
        "name,score,active,created_at\n"
        "Alice,10,true,2026-01-01\n"
        "Bob,,false,2026-01-02\n"
        "Carol,30,true,2026-01-03\n",
        encoding="utf-8",
    )

    result = analyze_csv(csv_path)

    assert result["summary"]["row_count"] == 3
    assert result["numeric"]["score"]["count"] == 2
    assert result["numeric"]["score"]["mean"] == 20.0
    assert "created_at" in result["trends"]
