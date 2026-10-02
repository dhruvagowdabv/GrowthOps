from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.business import Customer, Session as SessionModel
from app.models.ingestion import IngestionError
from app.services.ingestion import ingest_sessions_csv


def make_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(
        Customer(
            customer_id="C001",
            signup_date=date(2026, 1, 1),
            country="IN",
            region="KA",
            preferred_device="mobile",
            acquisition_channel="organic",
            customer_type="new",
        )
    )
    db.commit()
    return db


def write_csv(path: Path, body: str) -> None:
    path.write_text(
        "session_id,customer_id,timestamp,date,region,device,channel,campaign,app_version,landing_page\n" + body,
        encoding="utf-8",
    )


def test_session_ingestion_inserts_rows_and_completes_run(tmp_path: Path) -> None:
    db = make_session(tmp_path)
    csv_path = tmp_path / "sessions.csv"
    write_csv(
        csv_path,
        "S001,C001,2026-07-14 03:18:01,2026-07-14,North,Mobile,Organic,Meta_Prospecting,4.2.0,product\n"
        "S002,C001,2026-07-14 04:18:01,2026-07-14,North,Desktop,Organic,,web,home\n",
    )

    run = ingest_sessions_csv(db, csv_path, uuid4())

    assert run.status == "completed"
    assert run.rows_read == 2
    assert run.rows_inserted == 2
    assert run.rows_failed == 0
    assert db.scalar(select(SessionModel).where(SessionModel.session_id == "S001")) is not None
    assert db.scalar(select(SessionModel).where(SessionModel.session_id == "S002")) is not None


def test_missing_customer_rolls_back_session_rows(tmp_path: Path) -> None:
    db = make_session(tmp_path)
    csv_path = tmp_path / "sessions.csv"
    write_csv(
        csv_path,
        "S001,C001,2026-07-14 03:18:01,2026-07-14,North,Mobile,Organic,Meta_Prospecting,4.2.0,product\n"
        "S002,C999,2026-07-14 04:18:01,2026-07-14,North,Desktop,Organic,,web,home\n",
    )

    run = ingest_sessions_csv(db, csv_path, uuid4(), batch_size=1)

    assert run.status == "failed"
    assert run.rows_inserted == 0
    assert db.scalar(select(SessionModel).where(SessionModel.session_id == "S001")) is None
    error = db.scalar(select(IngestionError).where(IngestionError.run_id == run.run_id))
    assert error is not None


def test_duplicate_session_rolls_back_session_rows(tmp_path: Path) -> None:
    db = make_session(tmp_path)
    csv_path = tmp_path / "sessions.csv"
    write_csv(
        csv_path,
        "S001,C001,2026-07-14 03:18:01,2026-07-14,North,Mobile,Organic,Meta_Prospecting,4.2.0,product\n"
        "S001,C001,2026-07-14 04:18:01,2026-07-14,North,Desktop,Organic,,web,home\n",
    )

    run = ingest_sessions_csv(db, csv_path, uuid4(), batch_size=1)

    assert run.status == "failed"
    assert run.rows_inserted == 0
    assert db.scalar(select(SessionModel).where(SessionModel.session_id == "S001")) is None
