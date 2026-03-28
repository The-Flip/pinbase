"""Tests for provenance.validation — claim-boundary validation."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.models import MachineModel, Manufacturer, Person, System, Theme
from apps.provenance.models import Claim
from apps.provenance.validation import (
    validate_claim_value,
    validate_claims_batch,
    validate_fk_claims_batch,
)


# ---------------------------------------------------------------------------
# validate_claim_value
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestValidateClaimValue:
    def test_valid_string_passes(self):
        result = validate_claim_value("name", "Eight Ball Deluxe", MachineModel)
        assert result == "Eight Ball Deluxe"

    def test_valid_integer_passes(self):
        # ipdb_id has MinValueValidator(1)
        result = validate_claim_value("ipdb_id", 42, MachineModel)
        assert result == 42

    def test_out_of_range_integer_rejected(self):
        # ipdb_id has MinValueValidator(1), so 0 should fail
        with pytest.raises(ValidationError):
            validate_claim_value("ipdb_id", 0, MachineModel)

    def test_invalid_type_coercion_rejected(self):
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_claim_value("ipdb_id", "not-a-number", MachineModel)

    def test_mojibake_rejected(self):
        # Mojibake: "Ã©" is é misinterpreted through cp1252
        with pytest.raises(ValidationError, match="mojibake"):
            validate_claim_value("name", "Caf\u00c3\u00a9", Person)

    def test_valid_accented_passes(self):
        result = validate_claim_value("name", "Café", Person)
        assert result == "Café"

    def test_empty_string_skips_validators(self):
        # Empty string is the sentinel for "clear this field". Should not run
        # validators (which would reject "" as out of range for ipdb_id).
        result = validate_claim_value("ipdb_id", "", MachineModel)
        assert result == ""

    def test_float_decimal_field_not_rejected(self):
        # JSON has no Decimal type — values arrive as float. Ensure float 8.95
        # is not rejected by DecimalValidator due to IEEE 754 artifacts.
        result = validate_claim_value("ipdb_rating", 8.95, MachineModel)
        assert result == 8.95

    def test_fk_field_passes_through(self):
        # System.manufacturer is a FK to Manufacturer — should return unchanged.
        result = validate_claim_value("manufacturer", "some-slug", System)
        assert result == "some-slug"


# ---------------------------------------------------------------------------
# validate_claims_batch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestValidateClaimsBatch:
    @pytest.fixture
    def manufacturer(self):
        return Manufacturer.objects.create(name="Williams")

    @pytest.fixture
    def system(self, manufacturer):
        return System.objects.create(name="WPC", manufacturer=manufacturer)

    @pytest.fixture
    def model(self):
        return MachineModel.objects.create(name="Eight Ball")

    def test_valid_scalar_claim_passes(self, model):
        claim = Claim.for_object(model, field_name="name", value="Eight Ball Deluxe")
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1
        assert valid[0].value == "Eight Ball Deluxe"

    def test_invalid_scalar_claim_rejected(self, model):
        claim = Claim.for_object(model, field_name="ipdb_id", value="not-a-number")
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 1
        assert len(valid) == 0

    def test_mixed_valid_and_invalid(self, model):
        good = Claim.for_object(model, field_name="name", value="Good Name")
        bad = Claim.for_object(model, field_name="ipdb_id", value="bad")
        valid, rejected = validate_claims_batch([good, bad])
        assert rejected == 1
        assert len(valid) == 1
        assert valid[0].field_name == "name"

    def test_relationship_namespace_passes_through(self, model):
        claim = Claim.for_object(
            model,
            field_name="credit",
            value={"person_slug": "pat-lawlor", "role": "design", "exists": True},
            claim_key="credit|person:pat-lawlor|role:design",
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1

    def test_extra_data_claim_passes_through(self, model):
        claim = Claim.for_object(
            model, field_name="opdb.description", value="A great game"
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1

    def test_unrecognized_field_name_rejected(self):
        # Use Theme which has no extra_data fallback — unknown fields are rejected.
        theme = Theme.objects.create(name="Medieval", slug="medieval")
        claim = Claim.for_object(
            theme, field_name="nonexistent_field", value="whatever"
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 1
        assert len(valid) == 0

    def test_unknown_field_on_extra_data_model_passes(self, model):
        # MachineModel has extra_data — unknown fields resolve into it.
        claim = Claim.for_object(
            model, field_name="nonexistent_field", value="whatever"
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1

    def test_fk_claim_with_valid_target(self, system, manufacturer):
        claim = Claim.for_object(
            system, field_name="manufacturer", value=manufacturer.slug
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1

    def test_fk_claim_with_nonexistent_target(self, system):
        claim = Claim.for_object(
            system, field_name="manufacturer", value="no-such-manufacturer"
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 1
        assert len(valid) == 0

    def test_fk_claim_with_empty_value_passes(self, system):
        claim = Claim.for_object(system, field_name="manufacturer", value="")
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1


# ---------------------------------------------------------------------------
# validate_fk_claims_batch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestValidateFkClaimsBatch:
    @pytest.fixture
    def manufacturer(self):
        return Manufacturer.objects.create(name="Williams")

    @pytest.fixture
    def system(self, manufacturer):
        return System.objects.create(name="WPC", manufacturer=manufacturer)

    def test_valid_fk_passes(self, system, manufacturer):
        claim = Claim.for_object(
            system, field_name="manufacturer", value=manufacturer.slug
        )
        rejected = validate_fk_claims_batch([(claim, System)])
        assert rejected == []

    def test_invalid_fk_rejected(self, system):
        claim = Claim.for_object(
            system, field_name="manufacturer", value="no-such-slug"
        )
        rejected = validate_fk_claims_batch([(claim, System)])
        assert len(rejected) == 1

    def test_empty_value_not_rejected(self, system):
        claim = Claim.for_object(system, field_name="manufacturer", value="")
        rejected = validate_fk_claims_batch([(claim, System)])
        assert rejected == []

    def test_batch_queries_once_per_group(
        self, system, manufacturer, django_assert_num_queries
    ):
        """Multiple claims for the same (model, field) should result in one query."""
        c1 = Claim.for_object(
            system, field_name="manufacturer", value=manufacturer.slug
        )
        c2 = Claim.for_object(system, field_name="manufacturer", value="nonexistent")
        with django_assert_num_queries(1):
            rejected = validate_fk_claims_batch(
                [
                    (c1, System),
                    (c2, System),
                ]
            )
        assert len(rejected) == 1
