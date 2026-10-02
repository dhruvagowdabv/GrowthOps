import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MappingCandidate:
    internal_field: str
    confidence: float
    reason: str


# Controlled aliases keep semantic mapping deterministic and auditable.
ALIASES: dict[str, set[str]] = {
    "customer_id": {"customer_id", "customerid", "cust_id", "custid", "user_id", "userid", "client_id", "clientid"},
    "session_id": {"session_id", "sessionid", "session", "visit_id", "visitid"},
    "signup_date": {"signup_date", "signupdate", "registration_date", "registrationdate", "registered_date", "registereddate"},
    "country": {"country", "country_code", "countrycode"},
    "region": {"region", "state", "state_region", "stateprovince"},
    "device": {"device", "device_type", "devicetype", "preferred_device", "preferreddevice"},
    "channel": {"channel", "acquisition_channel", "acquisitionchannel", "traffic_source", "trafficsource"},
    "customer_type": {"customer_type", "customertype", "segment", "customer_segment", "customersegment"},
    "timestamp": {"timestamp", "event_timestamp", "eventtimestamp", "datetime", "date_time", "datetime_utc"},
    "date": {"date", "event_date", "eventdate"},
    "campaign": {"campaign", "campaign_name", "campaignname"},
    "app_version": {"app_version", "appversion", "application_version", "applicationversion"},
    "landing_page": {"landing_page", "landingpage", "page", "entry_page", "entrypage"},
}


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def suggest_mapping(column: dict) -> list[dict]:
    normalized = _normalize(column["name"])
    candidates: list[MappingCandidate] = []

    for internal_field, aliases in ALIASES.items():
        normalized_aliases = {_normalize(alias) for alias in aliases}
        if normalized in normalized_aliases:
            candidates.append(
                MappingCandidate(
                    internal_field=internal_field,
                    confidence=1.0,
                    reason="Exact semantic alias match",
                )
            )

    return [
        {
            "internal_field": candidate.internal_field,
            "confidence": candidate.confidence,
            "reason": candidate.reason,
        }
        for candidate in candidates
    ]


def map_profile(profile: dict) -> dict:
    mappings = []
    for column in profile.get("columns", []):
        candidates = suggest_mapping(column)
        mappings.append(
            {
                "source_column": column["name"],
                "inferred_type": column["inferred_type"],
                "candidates": candidates,
                "suggested_field": candidates[0]["internal_field"] if candidates else None,
                "confidence": candidates[0]["confidence"] if candidates else 0.0,
            }
        )

    return {
        "row_count": profile.get("row_count", 0),
        "column_count": profile.get("column_count", 0),
        "mappings": mappings,
    }


def build_source_to_canonical(mapping: dict, canonical_fields: set[str]) -> dict[str, str]:
    """Convert semantic mapping suggestions into entity-specific source mappings."""
    source_to_canonical: dict[str, str] = {}

    for item in mapping.get("mappings", []):
        source_column = item["source_column"]
        suggested_field = item.get("suggested_field")
        confidence = item.get("confidence", 0.0)
        if not suggested_field or confidence < 1.0:
            continue

        # The mapper uses shared semantic names for device/channel. Customer
        # ingestion has more specific canonical field names for those values.
        if suggested_field == "device" and "preferred_device" in canonical_fields:
            suggested_field = "preferred_device"
        elif suggested_field == "channel" and "acquisition_channel" in canonical_fields:
            suggested_field = "acquisition_channel"

        if suggested_field in canonical_fields:
            source_to_canonical[source_column] = suggested_field

    return source_to_canonical
