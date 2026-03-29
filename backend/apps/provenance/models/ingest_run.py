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
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="ingest_runs",
    )
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set on completion (success, partial, or failure).",
    )
    input_fingerprint = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Hash of the source dump used as input.",
    )
    git_sha = models.CharField(
        max_length=40,
        blank=True,
        default="",
        help_text="Code version (git commit SHA) at run time.",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    counts = models.JSONField(
        default=dict,
        blank=True,
        help_text="Run statistics: parsed, matched, created, asserted, retracted, rejected.",
    )
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

    def __str__(self) -> str:
        return f"IngestRun #{self.pk} ({self.source.name}, {self.status})"
