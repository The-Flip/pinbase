"""Coverage for newer PATCH claims endpoints added after the initial edit work."""

from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import (
    Cabinet,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    RewardType,
    Series,
    System,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
)
from apps.provenance.models import ChangeSet

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="editor", password="testpass")  # pragma: allowlist secret  # fmt: skip


def _patch(client, path: str, body: dict):
    return client.patch(
        path,
        data=json.dumps(body),
        content_type="application/json",
    )


def _create_franchise():
    return Franchise.objects.create(name="Star Trek")


def _create_series():
    return Series.objects.create(name="Eight Ball")


def _create_system():
    return System.objects.create(name="WPC-95")


def _create_technology_generation():
    return TechnologyGeneration.objects.create(name="Solid State")


def _create_technology_subgeneration():
    gen = TechnologyGeneration.objects.create(name="Electromechanical")
    return TechnologySubgeneration.objects.create(
        name="Late EM",
        technology_generation=gen,
    )


def _create_display_type():
    return DisplayType.objects.create(name="DMD")


def _create_display_subtype():
    display_type = DisplayType.objects.create(name="LCD")
    return DisplaySubtype.objects.create(
        name="HD LCD",
        display_type=display_type,
    )


def _create_cabinet():
    return Cabinet.objects.create(name="Widebody")


def _create_game_format():
    return GameFormat.objects.create(name="Pinball")


def _create_reward_type():
    return RewardType.objects.create(name="Replay")


def _create_tag():
    return Tag.objects.create(name="Prototype")


PATCH_CASES = [
    pytest.param(
        "/api/franchises/{slug}/claims/",
        _create_franchise,
        "description",
        "Updated franchise copy",
        "franchises",
        id="franchise",
    ),
    pytest.param(
        "/api/series/{slug}/claims/",
        _create_series,
        "description",
        "Updated series copy",
        "series",
        id="series",
    ),
    pytest.param(
        "/api/systems/{slug}/claims/",
        _create_system,
        "description",
        "Updated system copy",
        "systems",
        id="system",
    ),
    pytest.param(
        "/api/technology-generations/{slug}/claims/",
        _create_technology_generation,
        "description",
        "Updated technology generation copy",
        "technology-generations",
        id="technology-generation",
    ),
    pytest.param(
        "/api/technology-subgenerations/{slug}/claims/",
        _create_technology_subgeneration,
        "description",
        "Updated technology subgeneration copy",
        "technology-subgenerations",
        id="technology-subgeneration",
    ),
    pytest.param(
        "/api/display-types/{slug}/claims/",
        _create_display_type,
        "description",
        "Updated display type copy",
        "display-types",
        id="display-type",
    ),
    pytest.param(
        "/api/display-subtypes/{slug}/claims/",
        _create_display_subtype,
        "description",
        "Updated display subtype copy",
        "display-subtypes",
        id="display-subtype",
    ),
    pytest.param(
        "/api/cabinets/{slug}/claims/",
        _create_cabinet,
        "description",
        "Updated cabinet copy",
        "cabinets",
        id="cabinet",
    ),
    pytest.param(
        "/api/game-formats/{slug}/claims/",
        _create_game_format,
        "description",
        "Updated game format copy",
        "game-formats",
        id="game-format",
    ),
    pytest.param(
        "/api/reward-types/{slug}/claims/",
        _create_reward_type,
        "description",
        "Updated reward type copy",
        "reward-types",
        id="reward-type",
    ),
    pytest.param(
        "/api/tags/{slug}/claims/",
        _create_tag,
        "description",
        "Updated tag copy",
        "tags",
        id="tag",
    ),
]


@pytest.mark.django_db
class TestAdditionalPatchClaimEndpoints:
    @pytest.mark.parametrize(
        ("path_template", "factory", "field_name", "field_value", "resource_name"),
        PATCH_CASES,
    )
    def test_anonymous_gets_401(
        self, client, path_template, factory, field_name, field_value, resource_name
    ):
        entity = factory()
        resp = _patch(
            client,
            path_template.format(slug=entity.slug),
            {"fields": {field_name: field_value}},
        )
        assert resp.status_code in (401, 403), resource_name

    @pytest.mark.parametrize(
        ("path_template", "factory", "field_name", "field_value", "resource_name"),
        PATCH_CASES,
    )
    def test_empty_fields_returns_422(
        self,
        client,
        user,
        path_template,
        factory,
        field_name,
        field_value,
        resource_name,
    ):
        entity = factory()
        client.force_login(user)
        resp = _patch(
            client,
            path_template.format(slug=entity.slug),
            {"fields": {}},
        )
        assert resp.status_code == 422, resource_name

    @pytest.mark.parametrize(
        ("path_template", "factory", "field_name", "field_value", "resource_name"),
        PATCH_CASES,
    )
    def test_unknown_field_returns_422(
        self,
        client,
        user,
        path_template,
        factory,
        field_name,
        field_value,
        resource_name,
    ):
        entity = factory()
        client.force_login(user)
        resp = _patch(
            client,
            path_template.format(slug=entity.slug),
            {"fields": {"slug": "bad"}},
        )
        assert resp.status_code == 422, resource_name

    @pytest.mark.parametrize(
        ("path_template", "factory", "field_name", "field_value", "resource_name"),
        PATCH_CASES,
    )
    def test_creates_claim_changeset_and_activity(
        self,
        client,
        user,
        path_template,
        factory,
        field_name,
        field_value,
        resource_name,
    ):
        entity = factory()
        client.force_login(user)

        resp = _patch(
            client,
            path_template.format(slug=entity.slug),
            {"fields": {field_name: field_value}},
        )

        assert resp.status_code == 200, resource_name
        data = resp.json()
        assert data["description"]["text"] == field_value
        assert any(
            claim["field_name"] == field_name and claim["is_winner"]
            for claim in data["activity"]
        ), resource_name

        entity.refresh_from_db()
        assert entity.description == field_value

        claim = entity.claims.get(user=user, field_name=field_name, is_active=True)
        assert claim.value == field_value

        assert ChangeSet.objects.count() == 1
        changeset = ChangeSet.objects.get()
        assert changeset.user == user
        assert changeset.claims.count() == 1
