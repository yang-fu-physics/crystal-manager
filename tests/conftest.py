"""Shared pytest setup for isolated Crystal Manager tests.

The application imports ``config`` at module import time.  Install a
secret-free module stub before tests import application modules so collection
never depends on a developer's or deployment's real config.py.
"""

from datetime import datetime
import sys
import tempfile
import types
from pathlib import Path

import pytest


_TEST_ROOT = Path(tempfile.mkdtemp(prefix="crystal-manager-tests-"))
_TEST_NOW = datetime(2024, 1, 2, 3, 4, 5)


def _build_config_stub():
    config = types.ModuleType("config")
    config.DATABASE_PATH = str(_TEST_ROOT / "crystal_samples.db")
    config.UPLOAD_FOLDER = str(_TEST_ROOT / "uploads")
    config.BACKUP_FOLDER = str(_TEST_ROOT / "backups")
    config.FULL_BACKUP_FOLDER = str(_TEST_ROOT / "full_backups")
    config.PHOTO_FOLDER = str(_TEST_ROOT / "uploads" / "photos")
    config.EDX_FOLDER = str(_TEST_ROOT / "uploads" / "edx")
    config.DATA_FOLDER = str(_TEST_ROOT / "uploads" / "data")

    config.BACKUP_INTERVAL_HOURS = 24
    config.BACKUP_KEEP_COUNT = 100000
    config.FULL_BACKUP_INTERVAL_HOURS = 168
    config.FULL_BACKUP_KEEP_COUNT = 10

    config.SECRET_KEY = "x"
    config.LOGIN_PASSWORD = "x"
    config.APP_PORT = 5000

    config.OPENAI_API_KEY = "x"
    config.OPENAI_BASE_URL = "https://api.openai.com/v1/"
    config.OPENAI_MODEL = "test-model"

    config.MS_CLIENT_ID = ""
    config.MS_CLIENT_SECRET = ""
    config.MS_AUTHORITY = "https://login.microsoftonline.com/common"
    config.MS_REDIRECT_URI = "http://localhost:5000/auth/callback"
    config.MS_SCOPES = ["Tasks.ReadWrite"]
    config.MS_TOKEN_CACHE_PATH = str(_TEST_ROOT / "ms_token_cache.json")

    config.get_local_now = lambda: _TEST_NOW
    return config


# Must happen before importing models, app, or todo_integration in tests.
test_config = _build_config_stub()
sys.modules["config"] = test_config


def _set_storage_paths(config, root):
    root = Path(root)
    config.DATABASE_PATH = str(root / "crystal_samples.db")
    config.UPLOAD_FOLDER = str(root / "uploads")
    config.BACKUP_FOLDER = str(root / "backups")
    config.FULL_BACKUP_FOLDER = str(root / "full_backups")
    config.PHOTO_FOLDER = str(root / "uploads" / "photos")
    config.EDX_FOLDER = str(root / "uploads" / "edx")
    config.DATA_FOLDER = str(root / "uploads" / "data")
    config.MS_TOKEN_CACHE_PATH = str(root / "ms_token_cache.json")

    for folder in (
        config.UPLOAD_FOLDER,
        config.BACKUP_FOLDER,
        config.FULL_BACKUP_FOLDER,
        config.PHOTO_FOLDER,
        config.EDX_FOLDER,
        config.DATA_FOLDER,
    ):
        Path(folder).mkdir(parents=True, exist_ok=True)


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Return the Flask app configured against a per-test temporary store."""
    _set_storage_paths(test_config, tmp_path)

    import app as app_module
    import models

    models.init_db()
    monkeypatch.setattr(app_module.app, "secret_key", test_config.SECRET_KEY)
    app_module.app.config.update(TESTING=True)

    # backup.py computes this constant at import time; keep it isolated too.
    backup_module = sys.modules.get("backup")
    if backup_module is not None:
        monkeypatch.setattr(
            backup_module,
            "MANIFEST_PATH",
            str(Path(test_config.BACKUP_FOLDER) / "manifest.json"),
        )

    return app_module.app


@pytest.fixture
def client(app):
    """Return an authenticated Flask test client."""
    with app.test_client() as test_client:
        with test_client.session_transaction() as session:
            session["logged_in"] = True
        yield test_client
