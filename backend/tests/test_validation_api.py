from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_validation_endpoint_for_upload(tmp_path: Path) -> None:
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "customer_id,signup_date,country,preferred_device\n"
        "C001,2026-01-01,IN,mobile\n"
        "C002,2026-01-02,IN,desktop\n",
        encoding="utf-8",
    )

    with csv_path.open("rb") as file:
        response = client.post(
            "/api/uploads",
            files={"file": ("customers.csv", file, "text/csv")},
        )

    assert response.status_code == 201
    upload_id = response.json()["upload_id"]

    response = client.get(f"/api/uploads/{upload_id}/validation")

    assert response.status_code == 200
    validation = response.json()["validation"]
    assert validation["status"] == "passed"
    assert validation["row_count"] == 2
    assert validation["summary"] == {"errors": 0, "warnings": 0, "info": 0}


def test_validation_endpoint_returns_404_for_unknown_upload() -> None:
    response = client.get(f"/api/uploads/{uuid4()}/validation")
    assert response.status_code == 404
