from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_upload_rejects_non_csv() -> None:
    response = client.post(
        "/api/uploads",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only CSV files are accepted"


def test_upload_rejects_empty_csv() -> None:
    response = client.post(
        "/api/uploads",
        files={"file": ("empty.csv", BytesIO(b""), "text/csv")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Empty CSV files are not accepted"
