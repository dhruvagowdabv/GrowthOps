from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_and_list_import_session() -> None:
    response = client.post(
        "/api/import-sessions",
        data={"name": "Store data", "description": "Monthly e-commerce import"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Store data"
    assert payload["dataset_count"] == 0

    listed = client.get("/api/import-sessions")
    assert listed.status_code == 200
    assert any(
        item["import_session_id"] == payload["import_session_id"]
        for item in listed.json()["import_sessions"]
    )


def test_upload_multiple_datasets_into_session() -> None:
    created = client.post("/api/import-sessions", data={"name": "Bulk import"})
    assert created.status_code == 201
    session_id = created.json()["import_session_id"]

    response = client.post(
        f"/api/import-sessions/{session_id}/uploads",
        files=[
            ("files", ("orders.csv", BytesIO(b"order_id,amount\nO1,100\n"), "text/csv")),
            ("files", ("customers.csv", BytesIO(b"customer_id\nC1\n"), "text/csv")),
        ],
        data=[("dataset_types", "orders"), ("dataset_types", "customers")],
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["uploaded_count"] == 2
    assert {item["dataset_type"] for item in payload["datasets"]} == {"orders", "customers"}

    detail = client.get(f"/api/import-sessions/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["dataset_count"] == 2


def test_import_session_upload_rejects_unknown_session() -> None:
    response = client.post(
        f"/api/import-sessions/{uuid4()}/uploads",
        files=[("files", ("orders.csv", BytesIO(b"order_id\nO1\n"), "text/csv"))],
    )
    assert response.status_code == 404


def test_import_session_upload_rejects_mismatched_dataset_types() -> None:
    created = client.post("/api/import-sessions", data={"name": "Mismatch test"})
    session_id = created.json()["import_session_id"]

    response = client.post(
        f"/api/import-sessions/{session_id}/uploads",
        files=[
            ("files", ("orders.csv", BytesIO(b"order_id\nO1\n"), "text/csv")),
            ("files", ("customers.csv", BytesIO(b"customer_id\nC1\n"), "text/csv")),
        ],
        data=[("dataset_types", "orders")],
    )
    assert response.status_code == 422
