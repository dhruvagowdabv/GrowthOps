from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.uploads import get_db
from app.main import app

client = TestClient(app)


def test_mapping_endpoint_for_upload(tmp_path: Path) -> None:
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "customer_id,signup_date,country,preferred_device,unknown_field\n"
        "C001,2026-01-01,IN,mobile,x\n"
        "C002,2026-01-02,IN,desktop,y\n",
        encoding="utf-8",
    )

    with csv_path.open("rb") as file:
        response = client.post(
            "/api/uploads",
            files={"file": ("customers.csv", file, "text/csv")},
        )

    assert response.status_code == 201
    upload_id = response.json()["upload_id"]

    response = client.get(f"/api/uploads/{upload_id}/mapping")

    assert response.status_code == 200
    mapping = response.json()["mapping"]["mappings"]
    assert mapping[0]["suggested_field"] == "customer_id"
    assert mapping[0]["confidence"] == 1.0
    assert mapping[3]["suggested_field"] == "device"
    assert mapping[4]["suggested_field"] is None


def test_mapping_endpoint_returns_404_for_unknown_upload() -> None:
    response = client.get(f"/api/uploads/{uuid4()}/mapping")
    assert response.status_code == 404
