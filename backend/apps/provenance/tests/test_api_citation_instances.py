"""Tests for the citation-instances API endpoint."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.citation.models import CitationSource
from apps.provenance.models import CitationInstance

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(username="editor")


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def citation_source(db):
    return CitationSource.objects.create(
        name="The Encyclopedia of Pinball",
        source_type="book",
    )


class TestListCitationInstances:
    def test_anonymous_gets_401(self, client):
        resp = client.get("/api/citation-instances/?source=1")
        assert resp.status_code in (401, 403)

    def test_no_filter_returns_422(self, client, user):
        client.force_login(user)
        resp = client.get("/api/citation-instances/")
        assert resp.status_code == 422

    def test_filter_by_source(self, client, user, citation_source):
        ci = CitationInstance.objects.create(
            citation_source=citation_source, locator="p. 30"
        )
        client.force_login(user)
        resp = client.get(f"/api/citation-instances/?source={citation_source.pk}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == ci.pk
        assert data[0]["locator"] == "p. 30"
        assert data[0]["citation_source_name"] == citation_source.name
        assert data[0]["claim_id"] is None

    def test_filter_by_claim(self, client, user, citation_source):
        from apps.catalog.models import Manufacturer
        from apps.provenance.models import Claim, Source

        src = Source.objects.create(
            name="IPDB", slug="ipdb-test", source_type="database", priority=10
        )
        mfr = Manufacturer.objects.create(name="Williams", slug="williams")
        Claim.objects.assert_claim(mfr, "name", "Williams", source=src)
        claim = Claim.objects.filter(is_active=True).first()

        ci = CitationInstance.objects.create(
            citation_source=citation_source, claim=claim, locator="p. 42"
        )
        client.force_login(user)
        resp = client.get(f"/api/citation-instances/?claim={claim.pk}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == ci.pk
        assert data[0]["claim_id"] == claim.pk

    def test_empty_result(self, client, user, citation_source):
        client.force_login(user)
        resp = client.get(f"/api/citation-instances/?source={citation_source.pk}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_response_shape(self, client, user, citation_source):
        CitationInstance.objects.create(
            citation_source=citation_source, locator="front"
        )
        client.force_login(user)
        resp = client.get(f"/api/citation-instances/?source={citation_source.pk}")
        data = resp.json()[0]
        assert set(data.keys()) == {
            "id",
            "citation_source_id",
            "citation_source_name",
            "claim_id",
            "locator",
            "created_at",
        }
