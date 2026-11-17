import pytest


@pytest.fixture(autouse=True)
def offline_opencode_catalog(monkeypatch):
    """Unrelated UI tests must not depend on an upstream network request."""
    monkeypatch.setattr(
        "manager.app.list_opencode_releases",
        lambda page, arch: {"releases": [], "has_more": False, "page": page},
    )
