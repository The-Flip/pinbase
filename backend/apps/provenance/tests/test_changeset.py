"""Tests for the ChangeSet model and its integration with Claim."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.catalog.models import Manufacturer
from apps.provenance.models import ChangeSet, Claim, IngestRun, Source

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create(username="editor")


@pytest.fixture
def mfr(db):
    return Manufacturer.objects.create(name="Williams", slug="williams")


@pytest.fixture
def source(db):
    return Source.objects.create(name="TestSource", slug="test-source", priority=10)


@pytest.mark.django_db
class TestChangeSetModel:
    def test_create_changeset(self, user):
        cs = ChangeSet.objects.create(user=user, note="Fixed description")
        assert cs.pk is not None
        assert cs.user == user
        assert cs.note == "Fixed description"
        assert cs.created_at is not None

    def test_changeset_without_note(self, user):
        cs = ChangeSet.objects.create(user=user)
        assert cs.note == ""

    def test_changeset_without_user(self):
        """ChangeSet with null user is allowed (source-level changesets)."""
        cs = ChangeSet.objects.create()
        assert cs.user is None


@pytest.mark.django_db
class TestChangeSetClaimGrouping:
    def test_claims_linked_to_changeset(self, user, mfr):
        cs = ChangeSet.objects.create(user=user, note="Updated fields")
        c1 = Claim.objects.assert_claim(
            mfr, "name", "Williams Electronics", user=user, changeset=cs
        )
        c2 = Claim.objects.assert_claim(
            mfr, "description", "Pinball manufacturer", user=user, changeset=cs
        )
        assert c1.changeset == cs
        assert c2.changeset == cs
        assert set(cs.claims.values_list("pk", flat=True)) == {c1.pk, c2.pk}

    def test_claim_without_changeset(self, user, mfr):
        """Claims without a changeset still work (backwards compatible)."""
        claim = Claim.objects.assert_claim(mfr, "name", "Williams", user=user)
        assert claim.changeset is None

    def test_source_claim_with_changeset_accepted(self, source, mfr):
        """Source-attributed claims can use ChangeSets linked to matching ingest run."""
        run = IngestRun.objects.create(source=source, started_at=timezone.now())
        cs = ChangeSet.objects.create(ingest_run=run)
        claim = Claim.objects.assert_claim(
            mfr, "name", "Williams", source=source, changeset=cs
        )
        assert claim.changeset == cs

    def test_source_claim_changeset_source_mismatch_rejected(self, source, mfr):
        """ChangeSet's ingest run source must match the claim source."""
        other_source = Source.objects.create(
            name="OtherSource", slug="other-source", priority=5
        )
        run = IngestRun.objects.create(source=other_source, started_at=timezone.now())
        cs = ChangeSet.objects.create(ingest_run=run)
        with pytest.raises(ValueError, match="same source"):
            Claim.objects.assert_claim(
                mfr, "name", "Williams", source=source, changeset=cs
            )

    def test_source_claim_changeset_without_ingest_run_rejected(self, source, mfr):
        """Source-attributed claims require a changeset with an ingest run."""
        cs = ChangeSet.objects.create()
        with pytest.raises(ValueError, match="IngestRun"):
            Claim.objects.assert_claim(
                mfr, "name", "Williams", source=source, changeset=cs
            )

    def test_changeset_user_mismatch_rejected(self, user, mfr):
        """ChangeSet user must match the claim user."""
        other_user = User.objects.create(username="other")
        cs = ChangeSet.objects.create(user=other_user)
        with pytest.raises(ValueError, match="must match"):
            Claim.objects.assert_claim(mfr, "name", "Williams", user=user, changeset=cs)

    def test_changeset_survives_claim_superseding(self, user, mfr):
        """When a claim is superseded, the old claim keeps its changeset link."""
        cs1 = ChangeSet.objects.create(user=user, note="First edit")
        c1 = Claim.objects.assert_claim(
            mfr, "description", "First", user=user, changeset=cs1
        )

        cs2 = ChangeSet.objects.create(user=user, note="Second edit")
        c2 = Claim.objects.assert_claim(
            mfr, "description", "Second", user=user, changeset=cs2
        )

        c1.refresh_from_db()
        assert c1.is_active is False
        assert c1.changeset == cs1
        assert c2.is_active is True
        assert c2.changeset == cs2


@pytest.mark.django_db
class TestChangeSetConstraints:
    def test_user_only(self, user):
        cs = ChangeSet.objects.create(user=user)
        assert cs.pk is not None

    def test_ingest_run_only(self, source):
        run = IngestRun.objects.create(source=source, started_at=timezone.now())
        cs = ChangeSet.objects.create(ingest_run=run)
        assert cs.pk is not None

    def test_neither_user_nor_ingest_run(self):
        cs = ChangeSet.objects.create()
        assert cs.pk is not None

    def test_both_user_and_ingest_run_rejected(self, user, source):
        run = IngestRun.objects.create(source=source, started_at=timezone.now())
        with pytest.raises(IntegrityError):
            ChangeSet.objects.create(user=user, ingest_run=run)
