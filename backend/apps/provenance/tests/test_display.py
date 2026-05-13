"""Tests for the relationship-claim display labeler in apps.provenance.display."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.test_factories import make_user
from apps.catalog.models import (
    CreditRole,
    GameplayFeature,
    Person,
    Theme,
)
from apps.catalog.tests.conftest import make_machine_model
from apps.provenance.display import (
    FieldValue,
    FkRef,
    LabelLookup,
    build_display_label,
    resolve_labels,
)
from apps.provenance.models import Claim, Source


@pytest.mark.django_db
class TestBuildDisplayLabel:
    def test_credit_renders_person_em_dash_role(self):
        person = Person.objects.create(name="Pat Lawlor", slug="pat-lawlor")
        role = CreditRole.objects.create(name="Art", slug="art")
        value = {"person": person.pk, "role": role.pk, "exists": True}

        labels = resolve_labels([FieldValue("credit", value)])
        assert build_display_label("credit", value, labels) == "Pat Lawlor — Art"

    def test_credit_with_missing_target_falls_back_to_pk_marker(self):
        # Person row deleted between claim creation and history rendering.
        value = {"person": 999, "role": 888, "exists": True}
        labels = resolve_labels([FieldValue("credit", value)])
        assert build_display_label("credit", value, labels) == "?#999 — ?#888"

    def test_gameplay_feature_includes_count_when_greater_than_one(self):
        feat = GameplayFeature.objects.create(name="Multiball", slug="multiball")
        value = {"gameplay_feature": feat.pk, "count": 3, "exists": True}
        labels = resolve_labels([FieldValue("gameplay_feature", value)])
        assert build_display_label("gameplay_feature", value, labels) == "Multiball ×3"

    def test_gameplay_feature_omits_count_when_one_or_missing(self):
        feat = GameplayFeature.objects.create(name="Multiball", slug="multiball")
        no_count = {"gameplay_feature": feat.pk, "exists": True}
        count_one = {"gameplay_feature": feat.pk, "count": 1, "exists": True}
        labels = resolve_labels(
            [
                FieldValue("gameplay_feature", no_count),
                FieldValue("gameplay_feature", count_one),
            ]
        )
        assert build_display_label("gameplay_feature", no_count, labels) == "Multiball"
        assert build_display_label("gameplay_feature", count_one, labels) == "Multiball"

    def test_theme_renders_single_fk_label(self):
        theme = Theme.objects.create(name="Sci-Fi", slug="sci-fi")
        value = {"theme": theme.pk, "exists": True}
        labels = resolve_labels([FieldValue("theme", value)])
        assert build_display_label("theme", value, labels) == "Sci-Fi"

    def test_abbreviation_renders_scalar(self):
        value = {"value": "DW", "exists": True}
        labels = resolve_labels([FieldValue("abbreviation", value)])
        assert build_display_label("abbreviation", value, labels) == "DW"

    def test_bare_marker_renders_with_unresolved_placeholders(self):
        # Validation rule 4 (required identity keys) shouldn't allow this
        # shape to reach build_display_label. If it ever does — e.g. a stale row,
        # a fixture, or a future validation relaxation — surface it visibly
        # ("?") rather than swallow to None or crash. Filtering absent
        # values is the caller's policy decision (see hasMeaningfulValue
        # on the frontend).
        labels = LabelLookup()
        assert build_display_label("credit", {"exists": False}, labels) == "? — ?"
        assert build_display_label("theme", {"exists": False}, labels) == "?"
        # Literal-scalar namespaces have to follow the same contract — bare
        # subscription on a missing key would tank the edit-history endpoint.
        assert build_display_label("abbreviation", {"exists": False}, labels) == "?"
        # An alias namespace (one is registered per AliasModel subclass).
        assert build_display_label("person_alias", {"exists": False}, labels) == "?"

    def test_unknown_namespace_returns_none(self):
        # Direct-field claims (scalar new_value, not a registered namespace)
        # fall through — frontend renders the raw scalar.
        labels = LabelLookup()
        assert build_display_label("year", 1998, labels) is None
        assert (
            build_display_label("technology_generation", "solid-state", labels) is None
        )

    def test_non_dict_value_returns_none(self):
        labels = LabelLookup()
        assert build_display_label("credit", None, labels) is None
        assert build_display_label("credit", "string", labels) is None

    def test_resolve_labels_ignores_direct_fields_and_bare_markers(self):
        # Resolve over a mixed batch: a creditable dict, a theme dict, a
        # direct-field scalar (year), and a bare retraction marker. The
        # resulting lookup should only know about the FKs that were
        # genuinely referenced.
        person = Person.objects.create(name="Pat Lawlor", slug="pat-lawlor")
        role = CreditRole.objects.create(name="Art", slug="art")
        theme = Theme.objects.create(name="Sci-Fi", slug="sci-fi")
        labels = resolve_labels(
            [
                FieldValue(
                    "credit",
                    {"person": person.pk, "role": role.pk, "exists": True},
                ),
                FieldValue("theme", {"theme": theme.pk, "exists": True}),
                FieldValue("year", 1998),
                FieldValue("credit", {"exists": False}),
            ]
        )
        assert labels.get(FkRef(Person, person.pk)) == "Pat Lawlor"
        assert labels.get(FkRef(CreditRole, role.pk)) == "Art"
        assert labels.get(FkRef(Theme, theme.pk)) == "Sci-Fi"
        # Pks that were never referenced return None.
        assert labels.get(FkRef(Person, 999)) is None


# ---------------------------------------------------------------------------
# Query-count regression: FK label resolution must be batched. If a future
# change inlines ``str(instance)`` into per-row formatting, query count
# would scale with the number of distinct FK targets in history — this
# test pins it.
# ---------------------------------------------------------------------------


@pytest.fixture
def bootstrap_source(db):
    return Source.objects.create(
        name="Bootstrap", slug="bootstrap", source_type="editorial", priority=1
    )


def _q(fn: Callable[[], object]) -> int:
    with CaptureQueriesContext(connection) as ctx:
        fn()
    return len(ctx.captured_queries)


@pytest.mark.django_db
class TestQueryCountDoesNotScale:
    def test_credits_resolved_in_batched_queries(self, client, bootstrap_source):
        """Adding more credits must not add per-credit FK lookup queries.

        Failure mode this guards against: build_display_label calling
        ``str(instance)`` via a lazy FK fetch inside the per-row loop,
        producing one query per credit on top of the batched baseline.
        """
        user = make_user()
        pm = make_machine_model(name="MM", slug="mm-credits", year=1997)
        Claim.objects.assert_claim(pm, "name", "MM", source=bootstrap_source)
        CreditRole.objects.create(name="Design", slug="design")

        counter = 0

        def add_credits(n: int) -> None:
            # New Person each iteration → maximises distinct FK pks
            # build_display_label must resolve across the two measured fetches.
            nonlocal counter
            client.force_login(user)
            for _ in range(n):
                counter += 1
                Person.objects.create(
                    name=f"Person {counter}", slug=f"person-{counter}"
                )
                resp = client.patch(
                    f"/api/models/{pm.slug}/claims/",
                    data=json.dumps(
                        {
                            "credits": [
                                {"person_slug": f"person-{counter}", "role": "design"}
                            ]
                        }
                    ),
                    content_type="application/json",
                )
                assert resp.status_code == 200, (
                    f"seed PATCH failed with {resp.status_code}: {resp.content!r}"
                )

        add_credits(2)
        client.logout()
        url = f"/api/pages/edit-history/model/{pm.slug}/"
        base = _q(lambda: client.get(url))

        add_credits(18)
        client.logout()
        scaled = _q(lambda: client.get(url))

        assert scaled == base, (
            f"edit-history query count scales with credit count: {base} -> {scaled}. "
            f"build_display_label is likely resolving FK labels per-row "
            f"instead of via the batched resolve_labels() pass."
        )
