import pytest

from apps.catalog.models import MachineModel, Title

from .conftest import SAMPLE_IMAGES


class TestTitleDetailPage:
    @pytest.fixture
    def title(self, db):
        return Title.objects.create(
            name="Medieval Madness", slug="medieval-madness", opdb_id="G5pe4"
        )

    @pytest.fixture
    def title_with_machines(self, title, williams_entity):
        MachineModel.objects.create(
            name="Medieval Madness",
            slug="medieval-madness",
            corporate_entity=williams_entity,
            year=1997,
            title=title,
            extra_data={"opdb.images": SAMPLE_IMAGES},
        )
        MachineModel.objects.create(
            name="Medieval Madness (Remake)",
            slug="medieval-madness-remake",
            corporate_entity=williams_entity,
            year=2015,
            title=title,
        )
        return title

    def test_page_endpoint_returns_title(self, client, title_with_machines):
        resp = client.get("/api/pages/title/medieval-madness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Medieval Madness"
        assert len(data["machines"]) == 2

    def test_page_endpoint_404(self, client, db):
        resp = client.get("/api/pages/title/nonexistent")
        assert resp.status_code == 404
