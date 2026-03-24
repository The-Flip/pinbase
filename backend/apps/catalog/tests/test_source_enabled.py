"""Tests for Source.is_enabled filtering in claim resolution."""

import pytest

from apps.catalog.models import Manufacturer, Title
from apps.catalog.resolve import (
    TITLE_DIRECT_FIELDS,
    _resolve_bulk,
    resolve_manufacturer,
)
from apps.provenance.models import Claim, Source


@pytest.fixture
def source_a():
    return Source.objects.create(
        name="Source A", slug="source-a", source_type="database", priority=100
    )


@pytest.fixture
def source_b():
    return Source.objects.create(
        name="Source B", slug="source-b", source_type="editorial", priority=200
    )


@pytest.mark.django_db
class TestIsEnabledResolveSingle:
    def test_disabled_source_excluded_from_resolution(self, source_a):
        """Claims from a disabled source should not participate in resolution."""
        mfr = Manufacturer.objects.create(name="", slug="test-mfr")
        Claim.objects.assert_claim(mfr, "name", "From Disabled", source=source_a)

        source_a.is_enabled = False
        source_a.save()

        resolve_manufacturer(mfr)
        mfr.refresh_from_db()
        assert mfr.name == ""

    def test_disabled_source_fallback_to_enabled(self, source_a, source_b):
        """When the higher-priority source is disabled, the lower-priority one wins."""
        mfr = Manufacturer.objects.create(name="", slug="test-mfr")
        Claim.objects.assert_claim(mfr, "name", "Low Priority", source=source_a)
        Claim.objects.assert_claim(mfr, "name", "High Priority", source=source_b)

        # With both enabled, source_b wins (priority 200 > 100).
        resolve_manufacturer(mfr)
        mfr.refresh_from_db()
        assert mfr.name == "High Priority"

        # Disable source_b; source_a should now win.
        source_b.is_enabled = False
        source_b.save()

        resolve_manufacturer(mfr)
        mfr.refresh_from_db()
        assert mfr.name == "Low Priority"


@pytest.mark.django_db
class TestIsEnabledResolveBulk:
    def test_disabled_source_excluded_from_bulk_resolution(self, source_a):
        """Bulk resolution should skip claims from disabled sources."""
        t = Title.objects.create(opdb_id="G1", name="", slug="t1")
        Claim.objects.assert_claim(t, "name", "From Disabled", source=source_a)

        source_a.is_enabled = False
        source_a.save()

        _resolve_bulk(Title, TITLE_DIRECT_FIELDS)

        t.refresh_from_db()
        assert t.name == ""

    def test_bulk_fallback_when_winner_disabled(self, source_a, source_b):
        """Bulk resolution falls back to enabled source when winner is disabled."""
        t = Title.objects.create(opdb_id="G1", name="", slug="t1")
        Claim.objects.assert_claim(t, "name", "Low Priority", source=source_a)
        Claim.objects.assert_claim(t, "name", "High Priority", source=source_b)

        source_b.is_enabled = False
        source_b.save()

        _resolve_bulk(Title, TITLE_DIRECT_FIELDS)

        t.refresh_from_db()
        assert t.name == "Low Priority"


@pytest.mark.django_db
class TestIsEnabledUserClaims:
    def test_user_claims_unaffected_by_source_enabled(self, source_a):
        """User claims (source=None) should not be filtered by is_enabled."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="test")

        mfr = Manufacturer.objects.create(name="", slug="test-mfr")
        Claim.objects.assert_claim(mfr, "name", "User Claim", user=user)

        # Disable source_a (irrelevant — the claim is user-owned, not source-owned).
        source_a.is_enabled = False
        source_a.save()

        resolve_manufacturer(mfr)
        mfr.refresh_from_db()
        assert mfr.name == "User Claim"
