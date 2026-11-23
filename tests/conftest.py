"""Shared test setup: uploaded files go to a temporary folder, never the repository."""

import pytest

from app.db.database import settings
from app.services import storage


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "storage"))
    storage.backend.cache_clear()
    yield tmp_path / "storage"
    storage.backend.cache_clear()
