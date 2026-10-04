"""Backward-compatible facade for the generic relationship engine."""

from app.services.relationship_engine import discover_relationships

__all__ = ["discover_relationships"]
