"""IngestRun model: run-level audit trail for source ingestion."""

from __future__ import annotations

from django.db import models

from .source import Source


class IngestRun(models.Model):
    """A single invocation of an ingest pipeline for one source.

    Created before the apply transaction begins (status='running') and
    finalised after it commits or rolls back.  If the transaction fails,
    the IngestRun survives with status='failed' and error details — which
    is exactly when the audit record matters most.
    """

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="ingest_runs",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    input_fingerprint = models.CharField(
        max_length=255,
        help_text="Hash of the source data file.",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        db_default=Status.RUNNING,
        help_text=(
            "running — set at creation; a stale running record with an old "
            "timestamp indicates a crash. "
            "success — transaction committed, all data persisted. "
            "failed — exception caught, transaction rolled back."
        ),
    )

    # ── Run statistics ──────────────────────────────────────────────
    records_parsed = models.PositiveIntegerField(db_default=0)
    records_matched = models.PositiveIntegerField(db_default=0)
    records_created = models.PositiveIntegerField(db_default=0)
    claims_asserted = models.PositiveIntegerField(db_default=0)
    claims_retracted = models.PositiveIntegerField(db_default=0)
    claims_rejected = models.PositiveIntegerField(db_default=0)

    warnings = models.JSONField(
        default=list,
        blank=True,
    )
    errors = models.JSONField(
        default=list,
        blank=True,
    )

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["running", "success", "failed"]),
                name="provenance_ingestrun_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(input_fingerprint=""),
                name="provenance_ingestrun_fingerprint_nonempty",
            ),
        ]

    def __str__(self) -> str:
        return f"IngestRun #{self.pk} ({self.source.name}, {self.status})"
