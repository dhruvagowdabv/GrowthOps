from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.business import Customer
from app.services.ingestion import ingest_customers_csv
from app.services.mapping import build_source_to_canonical, map_profile


def make_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_ingestion_uses_mapping_for_alternate_customer_columns(tmp_path: Path) -> None:
    db = make_session(tmp_path)
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "cust_id,registration_date,country_code,state,device_type,traffic_source,segment\n"
        "C101,2026-02-01,IN,KA,mobile,organic,new\n",
        encoding="utf-8",
    )

    profile = {
        "row_count": 1,
        "column_count": 7,
        "columns": [
            {"name": "cust_id", "inferred_type": "string"},
            {"name": "registration_date", "inferred_type": "date"},
            {"name": "country_code", "inferred_type": "string"},
            {"name": "state", "inferred_type": "string"},
            {"name": "device_type", "inferred_type": "string"},
            {"name": "traffic_source", "inferred_type": "string"},
            {"name": "segment", "inferred_type": "string"},
        ],
    }
    mapping = map_profile(profile)
    source_to_canonical = build_source_to_canonical(
        mapping,
        {
            "customer_id",
            "signup_date",
            "country",
            "region",
            "preferred_device",
            "acquisition_channel",
            "customer_type",
        },
    )

    run = ingest_customers_csv(
        db,
        csv_path,
        uuid4(),
        source_to_canonical=source_to_canonical,
    )

    assert run.status == "completed"
    assert run.rows_inserted == 1
    customer = db.scalar(select(Customer).where(Customer.customer_id == "C101"))
    assert customer is not None
    assert customer.preferred_device == "mobile"
    assert customer.acquisition_channel == "organic"
    assert customer.customer_type == "new"
