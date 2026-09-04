import sqlite3

import models

from conftest import test_config


def test_init_db_migrates_legacy_growth_process_en_idempotently(tmp_path):
    test_config.DATABASE_PATH = str(tmp_path / "legacy-growth.db")
    conn = sqlite3.connect(test_config.DATABASE_PATH)
    conn.execute(
        """
        CREATE TABLE samples (
            id TEXT PRIMARY KEY,
            growth_process TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO samples (id, growth_process) VALUES (?, ?)",
        ("legacy-growth", "legacy Chinese process"),
    )
    conn.commit()
    conn.close()

    models.init_db()
    models.init_db()

    conn = sqlite3.connect(test_config.DATABASE_PATH)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(samples)")}
    row = conn.execute(
        "SELECT growth_process, growth_process_en FROM samples WHERE id = ?",
        ("legacy-growth",),
    ).fetchone()
    conn.close()

    assert "growth_process_en" in columns
    assert row == ("legacy Chinese process", "")


def test_create_sample_persists_bilingual_growth_process(tmp_path):
    test_config.DATABASE_PATH = str(tmp_path / "create-growth.db")
    models.init_db()

    sample = models.create_sample(
        {
            "id": "create-growth",
            "growth_process": "Chinese growth draft",
            "growth_process_en": "English growth draft",
        }
    )

    assert sample["growth_process"] == "Chinese growth draft"
    assert sample["growth_process_en"] == "English growth draft"


def test_update_sample_updates_bilingual_growth_process(tmp_path):
    test_config.DATABASE_PATH = str(tmp_path / "update-growth.db")
    models.init_db()
    models.create_sample(
        {
            "id": "update-growth",
            "growth_process": "Initial Chinese",
            "growth_process_en": "Initial English",
        }
    )

    sample = models.update_sample(
        "update-growth",
        {
            "id": "update-growth",
            "growth_process": "Updated Chinese",
            "growth_process_en": "Updated English",
        },
    )

    assert sample["growth_process"] == "Updated Chinese"
    assert sample["growth_process_en"] == "Updated English"


def test_rename_sample_preserves_bilingual_growth_process(tmp_path):
    test_config.DATABASE_PATH = str(tmp_path / "rename-growth.db")
    models.init_db()
    models.create_sample(
        {
            "id": "old-growth-id",
            "growth_process": "Chinese before rename",
            "growth_process_en": "English before rename",
        }
    )

    sample = models.update_sample(
        "old-growth-id",
        {
            "id": "new-growth-id",
            "growth_process": "Chinese after rename",
            "growth_process_en": "English after rename",
        },
    )

    assert sample["id"] == "new-growth-id"
    assert sample["growth_process"] == "Chinese after rename"
    assert sample["growth_process_en"] == "English after rename"
    assert models.get_sample("old-growth-id") is None


def test_legacy_put_without_growth_process_en_preserves_existing_english(client):
    created = client.post(
        "/api/samples",
        json={
            "id": "legacy-growth-put",
            "growth_process": "Saved Chinese process",
            "growth_process_en": "Saved English process",
        },
    )
    assert created.status_code == 201

    updated = client.put(
        "/api/samples/legacy-growth-put",
        json={"id": "legacy-growth-put", "growth_process": "Updated Chinese process"},
    )

    assert updated.status_code == 200
    assert updated.get_json()["growth_process"] == "Updated Chinese process"
    assert updated.get_json()["growth_process_en"] == "Saved English process"


def test_get_all_samples_searches_english_growth_process(tmp_path):
    test_config.DATABASE_PATH = str(tmp_path / "search-growth.db")
    models.init_db()
    models.create_sample(
        {
            "id": "search-growth",
            "growth_process": "Chinese process",
            "growth_process_en": "unique English growth phrase",
        }
    )

    samples = models.get_all_samples(query="unique English growth phrase")

    assert [sample["id"] for sample in samples] == ["search-growth"]
