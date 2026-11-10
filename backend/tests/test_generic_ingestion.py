from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.generic_dataset import GenericDatasetRecord
from app.services.generic_ingestion import ingest_generic_csv


def test_generic_ingestion_persists_arbitrary_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'generic.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    upload_id = uuid4()
    source = tmp_path / "unknown.csv"
    source.write_text("sensor_ref,temperature,zone\nR1,21.5,North\nR2,22.0,South\n", encoding="utf-8")

    result = ingest_generic_csv(db, source, upload_id)
    records = db.scalars(select(GenericDatasetRecord).where(GenericDatasetRecord.upload_id == upload_id)).all()
    assert result["rows_inserted"] == 2
    assert records[0].payload["sensor_ref"] == "R1"
    assert records[1].payload["temperature"] == "22.0"
