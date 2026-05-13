"""Tests for the review queue endpoint."""

from __future__ import annotations

import pytest

from apps.catalog.models import CreditRole, Person, Series
from apps.catalog.tests.conftest import make_machine_model
from apps.provenance.models import Claim, Source


@pytest.fixture
def source(db):
    return Source.objects.create(
        name="S", slug="s", source_type="editorial", priority=1
    )


def _flag(claim: Claim) -> None:
    claim.needs_review = True
    claim.save(update_fields=["needs_review"])


@pytest.mark.django_db
class TestReviewClaimsDisplay:
    """Wiring check: ``/api/review/claims/`` must populate ``value.display``
    for relationship claims and leave it null for scalars."""

    def test_relationship_claim_value_has_display(self, client, source):
        pm = make_machine_model(name="MM", slug="mm-review", year=1997)
        person = Person.objects.create(name="Pat Lawlor", slug="pat-lawlor")
        role = CreditRole.objects.create(name="Art", slug="art")
        claim = Claim.objects.assert_claim(
            pm,
            "credit",
            {"person": person.pk, "role": role.pk, "exists": True},
            source=source,
            claim_key=f"credit|person:{person.pk}|role:{role.pk}",
        )
        _flag(claim)

        resp = client.get("/api/review/claims/")
        assert resp.status_code == 200
        rows = [r for r in resp.json() if r["field_name"] == "credit"]
        assert len(rows) == 1
        display = rows[0]["value"]["display"]
        assert display is not None
        assert [(p["key"], p["label"]) for p in display["identity"]] == [
            ("person", "Pat Lawlor"),
            ("role", "Art"),
        ]

    def test_scalar_claim_value_has_null_display(self, client, source):
        series = Series.objects.create(slug="s", name="S")
        claim = Claim.objects.assert_claim(series, "name", "Some Name", source=source)
        _flag(claim)

        resp = client.get("/api/review/claims/")
        assert resp.status_code == 200
        row = next(r for r in resp.json() if r["field_name"] == "name")
        assert row["value"]["raw"] == "Some Name"
        assert row["value"]["display"] is None
