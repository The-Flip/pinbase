"""Management command to seed citation sources with known pinball reference works."""

from typing import Any

from django.core.management.base import BaseCommand

from apps.citation.seeding import ensure_citation_sources


class Command(BaseCommand):
    help = "Seed citation sources with known pinball reference works."

    # argparse-driven Django management command surface — framework owns kwargs
    def handle(
        self,
        *args: Any,  # noqa: ANN401
        **options: Any,  # noqa: ANN401
    ) -> None:
        counts = ensure_citation_sources()
        self.stdout.write(
            f"Citation sources: {counts['created']} created, "
            f"{counts['updated']} updated, {counts['unchanged']} unchanged."
        )
