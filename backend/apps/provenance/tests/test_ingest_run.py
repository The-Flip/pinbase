"""Tests for IngestRun model and its integration with ChangeSet and Claim."""

from django.utils import timezone

import pytest

from apps.catalog.models import Manufacturer
from apps.provenance.models import ChangeSet, Claim, IngestRun, Source


@pytest.fixture
def source(db):
    return Source.objects.create(name="TestSource", slug="test-source", priority=10)


@pytest.fixture
def mfr(db):
    return Manufacturer.objects.create(name="Williams", slug="williams")


@pytest.mark.django_db
class TestIngestRunModel:
    def test_create_with_all_fields(self, source):
        now = timezone.now()
        run = IngestRun.objects.create(
            source=source,
            started_at=now,
            finished_at=now,
            input_fingerprint="abc123def456",
            git_sha="a" * 40,  # pragma: allowlist secret
            status=IngestRun.Status.SUCCESS,
            counts={
                "parsed": 100,
                "matched": 95,
                "created": 5,
                "asserted": 200,
                "retracted": 3,
                "rejected": 2,
            },
            warnings=["minor issue"],
            errors=[],
        )
        assert run.pk is not None
        assert run.source == source
        assert run.status == "success"
        assert run.counts["parsed"] == 100
        assert run.input_fingerprint == "abc123def456"
        assert run.git_sha == "a" * 40
        assert run.warnings == ["minor issue"]
        assert run.errors == []

    def test_defaults(self, source):
        run = IngestRun.objects.create(
            source=source,
            started_at=timezone.now(),
        )
        assert run.finished_at is None
        assert run.input_fingerprint == ""
        assert run.git_sha == ""
        assert run.status == "running"
        assert run.counts == {}
        assert run.warnings == []
        assert run.errors == []

    def test_str(self, source):
        run = IngestRun.objects.create(
            source=source,
            started_at=timezone.now(),
            status=IngestRun.Status.FAILED,
        )
        assert "TestSource" in str(run)
        assert "failed" in str(run)


@pytest.mark.django_db
class TestChangeSetIngestRunFK:
    def test_changeset_linked_to_ingest_run(self, source):
        run = IngestRun.objects.create(
            source=source,
            started_at=timezone.now(),
        )
        cs = ChangeSet.objects.create(ingest_run=run)
        assert cs.ingest_run == run
        assert run.changesets.count() == 1

    def test_changeset_without_ingest_run(self):
        cs = ChangeSet.objects.create()
        assert cs.ingest_run is None

    def test_delete_run_cascades_to_changesets(self, source):
        run = IngestRun.objects.create(
            source=source,
            started_at=timezone.now(),
        )
        ChangeSet.objects.create(ingest_run=run)
        ChangeSet.objects.create(ingest_run=run)
        run_pk = run.pk
        assert ChangeSet.objects.filter(ingest_run_id=run_pk).count() == 2
        run.delete()
        assert ChangeSet.objects.filter(ingest_run_id=run_pk).count() == 0


@pytest.mark.django_db
class TestClaimRetractedByChangeset:
    def test_retracted_by_changeset_set(self, source, mfr):
        claim = Claim.objects.assert_claim(mfr, "name", "Williams", source=source)
        cs = ChangeSet.objects.create()
        claim.retracted_by_changeset = cs
        claim.is_active = False
        claim.save()

        claim.refresh_from_db()
        assert claim.retracted_by_changeset == cs
        assert claim.is_active is False
        assert cs.retracted_claims.count() == 1

    def test_retracted_by_changeset_null_by_default(self, source, mfr):
        claim = Claim.objects.assert_claim(mfr, "name", "Williams", source=source)
        assert claim.retracted_by_changeset is None

    def test_delete_changeset_nullifies_retracted_by(self, source, mfr):
        claim = Claim.objects.assert_claim(mfr, "name", "Williams", source=source)
        cs = ChangeSet.objects.create()
        claim.retracted_by_changeset = cs
        claim.is_active = False
        claim.save()

        cs.delete()
        claim.refresh_from_db()
        assert claim.retracted_by_changeset is None
