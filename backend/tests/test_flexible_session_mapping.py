from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.business import Customer, Session as SessionModel
from app.services.ingestion import SESSION_REQUIRED_COLUMNS, ingest_sessions_csv
from app.services.mapping import build_source_to_canonical, map_profile


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


def test_session_ingestion_uses_mapping_for_alternate_columns(tmp_path: Path) -> None:
    db = make_session(tmp_path)
    csv_path = tmp_path / "sessions.csv"
    csv_path.write_text(
        "visit_id,cust_id,event_timestamp,event_date,state,device_type,traffic_source,campaign_name,application_version,entry_page\n"
        "S101,C001,2026-07-14 03:18:01,2026-07-14,KA,Mobile,Organic,Meta_Prospecting,4.2.0,product\n",
        encoding="utf-8",
    )

    profile = {
        "row_count": 1,
        "column_count": 10,
        "columns": [
            {"name": "visit_id", "inferred_type": "string"},
            {"name": "cust_id", "inferred_type": "string"},
            {"name": "event_timestamp", "inferred_type": "datetime"},
            {"name": "event_date", "inferred_type": "date"},
            {"name": "state", "inferred_type": "string"},
            {"name": "device_type", "inferred_type": "string"},
            {"name": "traffic_source", "inferred_type": "string"},
            {"name": "campaign_name", "inferred_type": "string"},
            {"name": "application_version", "inferred_type": "string"},
            {"name": "entry_page", "inferred_type": "string"},
        ],
    }
    mapping = map_profile(profile)
    source_to_canonical = build_source_to_canonical(mapping, set(SESSION_REQUIRED_COLUMNS))

    run = ingest_sessions_csv(
        db,
        csv_path,
        uuid4(),
        source_to_canonical=source_to_canonical,
    )

    assert run.status == "completed"
    assert run.rows_inserted == 1
    session = db.scalar(select(SessionModel).where(SessionModel.session_id == "S101"))
    assert session is not None
    assert session.customer_id == "C001"
    assert session.device == "Mobile"
    assert session.channel == "Organic"
