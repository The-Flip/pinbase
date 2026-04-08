from __future__ import annotations

from typing import Any

from django.apps import AppConfig


def _format_citation_link(obj: Any, index: int, base_url: str, plain_text: bool) -> str:
    """Render a citation marker as a superscript footnote number."""
    if obj is None:
        return "[?]" if plain_text else "<sup>[?]</sup>"
    if plain_text:
        return f"[{index}]"
    return f'<sup data-cite-id="{obj.pk}" tabindex="0" role="button">[{index}]</sup>'


class ProvenanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.provenance"
    verbose_name = "Provenance"

    def ready(self) -> None:
        from apps.core.markdown_links import LinkType, register

        register(
            LinkType(
                name="cite",
                model_path="provenance.CitationInstance",
                label="Citation",
                description="Cite a source (book, web, magazine)",
                slug_field=None,
                format_link=_format_citation_link,
                select_related=("citation_source",),
                sort_order=1,
                autocomplete_flow="custom",
            )
        )
