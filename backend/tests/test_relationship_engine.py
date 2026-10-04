from pathlib import Path

from app.services.analytics_engine import analyze_csv
from app.services.relationship_engine import discover_relationships


def test_relationship_engine_detects_reference_to_identifier(tmp_path: Path) -> None:
    customers = tmp_path / "people.csv"
    orders = tmp_path / "activity.csv"

    customers.write_text(
        "person_id,name\nP1,Alice\nP2,Bob\nP3,Carol\n",
        encoding="utf-8",
    )
    orders.write_text(
        "event_id,person_id,event_date,amount\nE1,P1,2026-01-01,10\nE2,P1,2026-01-02,20\nE3,P2,2026-01-02,30\n",
        encoding="utf-8",
    )

    datasets = [
        {"upload_id": "people", "filename": "people.csv", "path": str(customers), "analytics": analyze_csv(customers)},
        {"upload_id": "activity", "filename": "activity.csv", "path": str(orders), "analytics": analyze_csv(orders)},
    ]

    relationships = discover_relationships(datasets)

    assert relationships
    relationship = relationships[0]
    assert relationship["parent"]["column"] == "person_id"
    assert relationship["child"]["column"] == "person_id"
    assert relationship["overlap_count"] == 2
