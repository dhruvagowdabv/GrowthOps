from app.services.mapping import map_profile


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
