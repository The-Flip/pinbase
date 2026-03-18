#!/usr/bin/env python3
"""Apply batched updates to data/pinbase/**/*.md files.

Changes applied:
1. Remove `slug:` from frontmatter in all markdown files (slug is the filename).
2. Backfill `display_type_slug` on models from OPDB data.
3. Backfill `technology_generation_slug` on models from IPDB/OPDB data.

Reads proposed changes from the DuckDB database at data/explore2/explore2.duckdb.

Usage:
    uv run python scripts/apply_markdown_updates.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
PINBASE_DIR = REPO_ROOT / "data" / "pinbase"
DB_PATH = REPO_ROOT / "data" / "explore2" / "explore2.duckdb"

# Canonical field order for model frontmatter.  When inserting a new field,
# it goes after the last present field that precedes it in this list.
MODEL_FIELD_ORDER = [
    "name",
    "title_slug",
    "opdb_id",
    "ipdb_id",
    "corporate_entity_slug",
    "year",
    "month",
    "player_count",
    "flipper_count",
    "production_quantity",
    "display_type_slug",
    "display_subtype_slug",
    "technology_generation_slug",
    "technology_subgeneration_slug",
    "system_slug",
    "cabinet_slug",
    "game_format_slug",
    "variant_of",
    "converted_from",
    "is_conversion",
    "is_remake",
    "remake_of",
    "tag_slugs",
    "credit_refs",
]


def _load_backfills(db: duckdb.DuckDBPyConnection) -> tuple[dict, dict]:
    """Load proposed backfills from DuckDB views."""
    display = {}
    for slug, value in db.execute(
        "SELECT model_slug, proposed_display_type_slug FROM proposed_display_type_backfill"
    ).fetchall():
        display[slug] = value

    tech_gen = {}
    for slug, value in db.execute(
        "SELECT model_slug, proposed_technology_generation_slug FROM proposed_tech_gen_backfill"
    ).fetchall():
        tech_gen[slug] = value

    return display, tech_gen


def _insert_field(lines: list[str], field_name: str, field_value: str) -> list[str]:
    """Insert a YAML field into frontmatter lines in canonical order.

    `lines` are the frontmatter lines between the --- delimiters (no delimiters).
    """
    # Find the position of each existing field in canonical order.
    target_idx = MODEL_FIELD_ORDER.index(field_name)

    # Find the last line whose field precedes `field_name` in canonical order.
    insert_after = -1  # default: insert at top
    for i, line in enumerate(lines):
        m = re.match(r"^(\w[\w_]*):", line)
        if not m:
            continue
        key = m.group(1)
        if key in MODEL_FIELD_ORDER:
            key_idx = MODEL_FIELD_ORDER.index(key)
            if key_idx < target_idx:
                # Walk past any continuation lines (for arrays like credit_refs).
                insert_after = i
            elif key_idx >= target_idx:
                break

    new_line = f"{field_name}: {field_value}"
    lines.insert(insert_after + 1, new_line)
    return lines


def _process_file(
    path: Path,
    *,
    display_backfills: dict,
    tech_gen_backfills: dict,
    is_model: bool,
) -> tuple[bool, list[str]]:
    """Process a single markdown file.  Returns (changed, change_descriptions)."""
    text = path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        return False, []

    end = text.find("\n---", 3)
    if end == -1:
        return False, []

    fm_text = text[3:end]
    body = text[end + 4:]  # everything after closing ---

    fm_lines = fm_text.strip().split("\n")
    changes = []

    # 1. Remove slug line.
    new_lines = []
    for line in fm_lines:
        if re.match(r"^slug:\s", line) or re.match(r"^slug:$", line):
            changes.append("removed slug")
        else:
            new_lines.append(line)
    fm_lines = new_lines

    # 2-3. Backfill display_type_slug and technology_generation_slug for models.
    if is_model:
        slug = path.stem
        display_value = display_backfills.get(slug)
        if display_value:
            fm_lines = _insert_field(fm_lines, "display_type_slug", display_value)
            changes.append(f"added display_type_slug: {display_value}")

        tech_gen_value = tech_gen_backfills.get(slug)
        if tech_gen_value:
            fm_lines = _insert_field(
                fm_lines, "technology_generation_slug", tech_gen_value
            )
            changes.append(f"added technology_generation_slug: {tech_gen_value}")

    if not changes:
        return False, []

    # Reconstruct file.
    new_fm = "\n".join(fm_lines)
    new_text = f"---\n{new_fm}\n---{body}"
    path.write_text(new_text, encoding="utf-8")
    return True, changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply markdown updates")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print changes without writing files",
    )
    args = parser.parse_args()

    db = duckdb.connect(str(DB_PATH), read_only=True)
    display_backfills, tech_gen_backfills = _load_backfills(db)
    db.close()

    print(f"Loaded backfills: {len(display_backfills)} display_type, {len(tech_gen_backfills)} technology_generation")

    total_changed = 0
    slug_removed = 0
    display_added = 0
    tech_gen_added = 0

    for entity_dir in sorted(PINBASE_DIR.iterdir()):
        if not entity_dir.is_dir():
            continue
        is_model = entity_dir.name == "models"

        for md_file in sorted(entity_dir.glob("*.md")):
            if args.dry_run:
                # Read-only dry run: just check what would change.
                text = md_file.read_text(encoding="utf-8")
                would_change = False
                if re.search(r"(?m)^slug:\s", text) or re.search(r"(?m)^slug:$", text):
                    would_change = True
                    slug_removed += 1
                if is_model:
                    slug = md_file.stem
                    if slug in display_backfills:
                        would_change = True
                        display_added += 1
                    if slug in tech_gen_backfills:
                        would_change = True
                        tech_gen_added += 1
                if would_change:
                    total_changed += 1
                continue

            changed, change_list = _process_file(
                md_file,
                display_backfills=display_backfills,
                tech_gen_backfills=tech_gen_backfills,
                is_model=is_model,
            )
            if changed:
                total_changed += 1
                for c in change_list:
                    if "removed slug" in c:
                        slug_removed += 1
                    elif "display_type_slug" in c:
                        display_added += 1
                    elif "technology_generation_slug" in c:
                        tech_gen_added += 1

    prefix = "Would update" if args.dry_run else "Updated"
    print(f"{prefix} {total_changed} files:")
    print(f"  slug removed: {slug_removed}")
    print(f"  display_type_slug added: {display_added}")
    print(f"  technology_generation_slug added: {tech_gen_added}")


if __name__ == "__main__":
    main()
