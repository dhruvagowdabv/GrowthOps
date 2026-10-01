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
    "signup_date": {"signup_date", "signupdate", "registration_date", "registrationdate", "registered_date", "registereddate"},
    "country": {"country", "country_code", "countrycode"},
    "region": {"region", "state", "state_region", "stateprovince"},
    "device": {"device", "device_type", "devicetype", "preferred_device", "preferreddevice"},
    "channel": {"channel", "acquisition_channel", "acquisitionchannel", "traffic_source", "trafficsource"},
    "customer_type": {"customer_type", "customertype", "segment", "customer_segment", "customersegment"},
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
