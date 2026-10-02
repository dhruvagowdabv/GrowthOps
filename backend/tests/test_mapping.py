from app.services.mapping import build_source_to_canonical, map_profile


def test_customer_profile_mapping() -> None:
    profile = {
        "row_count": 3,
        "column_count": 3,
        "columns": [
            {"name": "customer_id", "inferred_type": "string"},
            {"name": "signup_date", "inferred_type": "date"},
            {"name": "preferred_device", "inferred_type": "string"},
        ],
    }

    result = map_profile(profile)
    mappings = {item["source_column"]: item for item in result["mappings"]}

    assert mappings["customer_id"]["suggested_field"] == "customer_id"
    assert mappings["signup_date"]["suggested_field"] == "signup_date"
    assert mappings["preferred_device"]["suggested_field"] == "device"
    assert mappings["customer_id"]["confidence"] == 1.0


def test_unknown_column_requires_review() -> None:
    profile = {
        "row_count": 1,
        "column_count": 1,
        "columns": [{"name": "mystery_column", "inferred_type": "string"}],
    }

    result = map_profile(profile)
    mapping = result["mappings"][0]

    assert mapping["suggested_field"] is None
    assert mapping["confidence"] == 0.0
    assert mapping["candidates"] == []


def test_customer_alias_mapping_resolves_to_ingestion_fields() -> None:
    profile = {
        "row_count": 1,
        "column_count": 3,
        "columns": [
            {"name": "cust_id", "inferred_type": "string"},
            {"name": "registration_date", "inferred_type": "date"},
            {"name": "device_type", "inferred_type": "string"},
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

    assert source_to_canonical["cust_id"] == "customer_id"
    assert source_to_canonical["registration_date"] == "signup_date"
    assert source_to_canonical["device_type"] == "preferred_device"
