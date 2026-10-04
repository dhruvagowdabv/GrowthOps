"""Backward-compatible facade for the generic semantic engine."""

from app.services.semantic_engine import infer_column_semantics, infer_dataset_semantics, infer_schema

__all__ = [
    "infer_column_semantics",
    "infer_dataset_semantics",
    "infer_schema",
]
