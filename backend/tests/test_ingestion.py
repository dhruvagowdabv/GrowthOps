from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.business import Customer
from app.models.ingestion import IngestionError, IngestionRun
from app.services.ingestion import ingest_customers_csv


def make_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def write_csv(path: Path, body: str) -> None:
    path.write_text(
        "customer_id,signup_date,country,region,preferred_device,acquisition_channel,customer_type\n" + body,
        encoding="utf-8",
    )


def test_ingestion_inserts_rows_and_completes_run(tmp_path: Path) -> None:
    db = make_session(tmp_path)
    csv_path = tmp_path / "customers.csv"
    write_csv(
        csv_path,
        "C001,2026-01-01,IN,KA,mobile,organic,new\n"
        "C002,2026-01-02,IN,KA,desktop,paid,returning\n",
    )

    run = ingest_customers_csv(db, csv_path, uuid4())

    assert run.status == "completed"
    assert run.rows_read == 2
    assert run.rows_inserted == 2
    assert run.rows_failed == 0
    assert db.scalar(select(Customer).where(Customer.customer_id == "C001")) is not None
    assert db.scalar(select(Customer).where(Customer.customer_id == "C002")) is not None


def test_duplicate_customer_rolls_back_customer_rows(tmp_path: Path) -> None:
    db = make_session(tmp_path)
    csv_path = tmp_path / "customers.csv"
    write_csv(
        csv_path,
        "C001,2026-01-01,IN,KA,mobile,organic,new\n"
        "C001,2026-01-02,IN,KA,desktop,paid,returning\n",
    )

    run = ingest_customers_csv(db, csv_path, uuid4(), batch_size=1)

    assert run.status == "failed"
    assert run.rows_inserted == 1
    assert db.scalar(select(Customer).where(Customer.customer_id == "C001")) is None
    error = db.scalar(select(IngestionError).where(IngestionError.run_id == run.run_id))
    assert error is not None


def test_missing_required_column_fails_without_inserting(tmp_path: Path) -> None:
    db = make_session(tmp_path)
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "customer_id,signup_date,country\nC001,2026-01-01,IN\n",
        encoding="utf-8",
    )

    run = ingest_customers_csv(db, csv_path, uuid4())

    assert run.status == "failed"
    assert run.rows_inserted == 0
    assert db.scalar(select(Customer)) is None
