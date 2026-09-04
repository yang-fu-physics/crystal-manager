import sqlite3

import models
from conftest import test_config


def test_init_db_migrates_legacy_results_en_without_losing_results(tmp_path):
    test_config.DATABASE_PATH = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(test_config.DATABASE_PATH)
    conn.execute(
        """
        CREATE TABLE samples (
            id TEXT PRIMARY KEY,
            results TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO samples (id, results) VALUES (?, ?)",
        ("legacy-1", "旧版结果"),
    )
    conn.commit()
    conn.close()

    models.init_db()
    models.init_db()

    conn = sqlite3.connect(test_config.DATABASE_PATH)
    columns = {
        row[1]: row for row in conn.execute("PRAGMA table_info(samples)")
    }
    row = conn.execute(
        "SELECT results, results_en FROM samples WHERE id = ?", ("legacy-1",)
    ).fetchone()
    conn.close()

    assert "results_en" in columns
    assert row == ("旧版结果", "")


def test_create_sample_persists_chinese_and_english_results(tmp_path):
    test_config.DATABASE_PATH = str(tmp_path / "create.db")
    models.init_db()

    sample = models.create_sample(
        {"id": "sample-1", "results": "中文结果", "results_en": "English result"}
    )

    assert sample["results"] == "中文结果"
    assert sample["results_en"] == "English result"


def test_update_sample_updates_both_result_columns(tmp_path):
    test_config.DATABASE_PATH = str(tmp_path / "update.db")
    models.init_db()
    models.create_sample(
        {"id": "sample-1", "results": "初始中文", "results_en": "Initial English"}
    )

    sample = models.update_sample(
        "sample-1",
        {"id": "sample-1", "results": "更新中文", "results_en": "Updated English"},
    )

    assert sample["results"] == "更新中文"
    assert sample["results_en"] == "Updated English"


def test_update_sample_with_new_id_preserves_bilingual_results(tmp_path):
    test_config.DATABASE_PATH = str(tmp_path / "rename.db")
    models.init_db()
    models.create_sample(
        {"id": "old-id", "results": "旧中文", "results_en": "Old English"}
    )

    sample = models.update_sample(
        "old-id",
        {"id": "new-id", "results": "新中文", "results_en": "New English"},
    )

    assert sample["id"] == "new-id"
    assert sample["results"] == "新中文"
    assert sample["results_en"] == "New English"
    assert models.get_sample("old-id") is None


def test_legacy_put_without_results_en_preserves_existing_english(client):
    created = client.post(
        "/api/samples",
        json={
            "id": "legacy-put",
            "results": "保存中文",
            "results_en": "Saved English",
        },
    )
    assert created.status_code == 201

    updated = client.put(
        "/api/samples/legacy-put",
        json={"id": "legacy-put", "results": "更新中文"},
    )

    assert updated.status_code == 200
    assert updated.get_json()["results"] == "更新中文"
    assert updated.get_json()["results_en"] == "Saved English"


def test_get_all_samples_searches_english_results(tmp_path):
    test_config.DATABASE_PATH = str(tmp_path / "search.db")
    models.init_db()
    models.create_sample(
        {"id": "search-1", "results": "中文", "results_en": "unique-bilingual-term"}
    )

    samples = models.get_all_samples(query="unique-bilingual-term")

    assert [sample["id"] for sample in samples] == ["search-1"]
