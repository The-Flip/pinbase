"""Shared API schemas for the provenance app.

These schemas are used by both the edit-history endpoints (api.py) and the
page-oriented changes endpoints (page_endpoints.py).
"""

from __future__ import annotations

from typing import Optional

from ninja import Schema


class FieldChangeSchema(Schema):
    """A single field change within a ChangeSet (old -> new)."""

    field_name: str
    claim_key: str
    old_value: Optional[object] = None
    new_value: object
    claim_id: Optional[int] = None
    claim_user_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_winning: Optional[bool] = None
    is_retracted: Optional[bool] = None


class RetractionSchema(Schema):
    claim_id: int
    field_name: str
    claim_key: str
    old_value: object
