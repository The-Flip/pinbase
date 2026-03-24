import pytest


@pytest.fixture(autouse=True)
def _default_display_policy_show_all(settings):
    """Default Constance display policy to show-all for tests.

    Most tests don't care about license filtering. Tests that specifically
    test threshold behavior can override via settings fixture.
    """
    from constance.test import override_config

    with override_config(CONTENT_DISPLAY_POLICY="show-all"):
        yield
