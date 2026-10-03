from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_upload_analytics_endpoint_is_dataset_agnostic() -> None:
    csv_content = (
        "product_code,category,price,recorded_date\n"
        "P001,Hardware,100.0,2026-01-01\n"
        "P002,Software,250.0,2026-01-02\n"
    ).encode()

    response = client.post(
        "/api/uploads",
        files={"file": ("products_custom.csv", BytesIO(csv_content), "text/csv")},
    )
    assert response.status_code == 201

    upload_id = response.json()["upload_id"]
    response = client.get(f"/api/uploads/{upload_id}/analytics")

    assert response.status_code == 200
    body = response.json()["analytics"]
    assert body["summary"]["row_count"] == 2
    assert body["numeric"]["price"]["sum"] == 350.0


def test_generic_analytics_returns_404_for_unknown_upload() -> None:
    response = client.get(f"/api/uploads/{uuid4()}/analytics")
    assert response.status_code == 404
