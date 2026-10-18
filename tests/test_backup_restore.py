from contextlib import closing
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import zipfile

import pytest

import backup
import chat_history
import models
from conftest import test_config
from test_ai_chat import install_ai, propose


@pytest.fixture
def backup_store(app, tmp_path, monkeypatch):
    current = [datetime(2026, 10, 18, 8)]

    def now():
        value = current[0]
        current[0] += timedelta(seconds=1)
        return value

    monkeypatch.setattr(test_config, 'get_local_now', now)
    return tmp_path


@pytest.fixture
def upload(backup_store):
    modified = [1_800_000_000_000_000_000]

    def write(relative, content):
        target = Path(test_config.UPLOAD_FOLDER, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        modified[0] += 1_000_000_000
        os.utime(target, ns=(modified[0], modified[0]))
        return target

    return write


def rows(database, table):
    with closing(sqlite3.connect(database)) as connection:
        return connection.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()


def contents(directory):
    root = Path(directory)
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}


def test_full_plus_incrementals_restore_chat_records_states_and_exact_files(backup_store, upload, client, install_ai):
    proposal, _ = propose(client, install_ai, {'notes': 'baseline'}, operation='create')
    saved = client.post('/api/chat/confirm', json={'token': proposal['token']}).get_json()
    upload('changed.txt', b'baseline')
    removed = upload('removed.txt', b'delete me')
    upload('nested/中文.txt', b'unchanged')
    full = Path(backup.run_full_backup())

    models.update_sample('TEST-001', {'notes': 'first incremental'})
    upload('changed.txt', b'first version')
    transient = upload('new.txt', b'transient')
    removed.unlink()
    first = Path(backup.run_backup())
    first_samples = rows(test_config.DATABASE_PATH, 'samples')
    first_files = contents(test_config.UPLOAD_FOLDER)

    cancelled, _ = propose(client, install_ai, {'notes': 'not applied'})
    client.post('/api/chat/cancel', json={'token': cancelled['token']})
    undone, _ = propose(client, install_ai, {'notes': 'undo this'}, operation='create', sample_id='UNDO-BACKUP')
    to_undo = client.post('/api/chat/confirm', json={'token': undone['token']}).get_json()
    assert client.post('/api/chat/undo', json={'token': to_undo['undo_token']}).status_code == 200
    models.update_sample('TEST-001', {'notes': 'second incremental'})
    upload('changed.txt', b'final version')
    transient.unlink()
    upload('final.txt', b'last addition')
    second = Path(backup.run_backup())
    expected = {name: rows(test_config.DATABASE_PATH, name)
                for name in ('samples', 'chat_conversations', 'chat_messages')}
    expected_files = contents(test_config.UPLOAD_FOLDER)
    info = json.loads((second / 'backup_info.json').read_text(encoding='utf-8'))
    assert info['base_full'] == full.name
    assert info['previous_incremental'] == first.name
    assert info['deleted_files'] == ['new.txt']

    restored = backup_store / 'restored'
    (restored / 'uploads').mkdir(parents=True)
    (restored / 'uploads/future-only.txt').write_bytes(b'must disappear')
    result = backup.restore_backup(second.name, restored / 'uploads', restored / 'samples.db')
    assert result['full_backup'] == full.name
    assert result['incrementals'] == [first.name, second.name]
    for table, expected_rows in expected.items():
        assert rows(restored / 'samples.db', table) == expected_rows
    assert contents(restored / 'uploads') == expected_files
    assert expected['chat_messages']
    assert saved['undo_token'] in str(expected['chat_messages'])
    assert any('cancelled' in row for row in expected['chat_messages'])
    assert any('undone' in row for row in expected['chat_messages'])

    earlier = backup_store / 'earlier'
    backup.restore_backup(first.name, earlier / 'uploads', earlier / 'samples.db')
    assert rows(earlier / 'samples.db', 'samples') == first_samples
    assert contents(earlier / 'uploads') == first_files


def test_new_full_resets_baseline_and_default_uses_its_later_incrementals(backup_store, upload):
    models.create_sample({'id': 'S', 'notes': 'first'})
    upload('base.txt', b'old')
    first_full = Path(backup.run_full_backup())
    upload('base.txt', b'first delta')
    first_delta = Path(backup.run_backup())
    upload('only-in-second-full.txt', b'captured by full only')
    second_full = Path(backup.run_full_backup())
    upload('last.txt', b'last')
    last_delta = Path(backup.run_backup())
    latest = backup.get_restore_plan()
    assert latest['full_backup'] == second_full.name
    assert latest['incrementals'] == [last_delta.name]
    target = backup_store / 'latest'
    backup.restore_backup(None, target / 'uploads', target / 'db.sqlite')
    assert contents(target / 'uploads') == contents(test_config.UPLOAD_FOLDER)

    old_target = backup_store / 'old-chain'
    result = backup.restore_full_backup(first_full.name, old_target / 'uploads', old_target / 'db.sqlite')
    assert result['incrementals'] == [first_delta.name]
    assert contents(old_target / 'uploads') == {'base.txt': b'first delta'}
    with pytest.raises(ValueError, match='不属于'):
        backup.get_restore_plan(last_delta.name, first_full.name)


def test_first_incremental_creates_full_baseline_and_keeps_chat_tables(backup_store):
    chat_history.create_conversation()
    incremental = Path(backup.run_backup())
    plan = backup.get_restore_plan(incremental.name)
    assert plan['full_backup'] in backup.list_full_backups()
    assert plan['incrementals'] == [incremental.name]
    assert rows(incremental / 'db.sqlite', 'chat_conversations') == rows(test_config.DATABASE_PATH, 'chat_conversations')
    with zipfile.ZipFile(Path(test_config.FULL_BACKUP_FOLDER, plan['full_backup'])) as archive:
        full_db = backup_store / 'full-snapshot.sqlite'
        full_db.write_bytes(archive.read('db.sqlite'))
    assert rows(full_db, 'chat_conversations') == rows(test_config.DATABASE_PATH, 'chat_conversations')


def test_missing_incremental_fails_before_touching_live_data(backup_store, upload):
    models.create_sample({'id': 'S', 'notes': 'keep current'})
    upload('value.txt', b'baseline')
    backup.run_full_backup()
    upload('value.txt', b'first change')
    missing = Path(backup.run_backup())
    upload('value.txt', b'last change')
    last = Path(backup.run_backup())
    (missing / 'backup_info.json').unlink()
    before_db = Path(test_config.DATABASE_PATH).read_bytes()
    before_files = contents(test_config.UPLOAD_FOLDER)
    with pytest.raises(ValueError, match='链不完整'):
        backup.restore_backup(last.name)
    assert Path(test_config.DATABASE_PATH).read_bytes() == before_db
    assert contents(test_config.UPLOAD_FOLDER) == before_files


@pytest.mark.parametrize('damage', ['missing_file', 'corrupt_database'])
def test_invalid_incremental_does_not_partly_restore(backup_store, upload, damage):
    models.create_sample({'id': 'S', 'notes': 'baseline'})
    upload('value.txt', b'baseline')
    backup.run_full_backup()
    upload('value.txt', b'changed')
    incremental = Path(backup.run_backup())
    if damage == 'missing_file':
        (incremental / 'files/value.txt').unlink()
        error = FileNotFoundError
    else:
        (incremental / 'db.sqlite').write_bytes(b'not a database')
        error = sqlite3.DatabaseError
    upload('future.txt', b'keep live state')
    before_db = Path(test_config.DATABASE_PATH).read_bytes()
    before_files = contents(test_config.UPLOAD_FOLDER)
    with pytest.raises(error):
        backup.restore_backup(incremental.name)
    assert Path(test_config.DATABASE_PATH).read_bytes() == before_db
    assert contents(test_config.UPLOAD_FOLDER) == before_files


@pytest.mark.parametrize('member', ['uploads/../../escape.txt', 'uploads/C:/escape.txt', 'uploads/..\\..\\escape.txt'])
def test_archive_paths_cannot_escape_restore_directory(backup_store, upload, member):
    models.create_sample({'id': 'S'})
    upload('keep.txt', b'keep')
    archive_path = Path(backup.run_full_backup())
    with zipfile.ZipFile(archive_path) as archive:
        database = archive.read('db.sqlite')
    with zipfile.ZipFile(archive_path, 'w') as archive:
        archive.writestr('db.sqlite', database)
        archive.writestr(member, b'unsafe')
    with pytest.raises(ValueError, match='路径'):
        backup.restore_backup()
    assert contents(test_config.UPLOAD_FOLDER) == {'keep.txt': b'keep'}
    assert not (backup_store / 'escape.txt').exists()


def test_database_install_failure_rolls_back_upload_directory(backup_store, upload, monkeypatch):
    models.create_sample({'id': 'S', 'notes': 'baseline'})
    upload('value.txt', b'baseline')
    backup.run_full_backup()
    upload('value.txt', b'delta')
    incremental = Path(backup.run_backup())
    upload('value.txt', b'live value')
    before_db = Path(test_config.DATABASE_PATH).read_bytes()
    before_files = contents(test_config.UPLOAD_FOLDER)

    def fail(source, destination):
        raise sqlite3.OperationalError('destination is not writable')

    monkeypatch.setattr(backup, '_copy_database', fail)
    with pytest.raises(sqlite3.OperationalError, match='not writable'):
        backup.restore_backup(incremental.name)
    assert Path(test_config.DATABASE_PATH).read_bytes() == before_db
    assert contents(test_config.UPLOAD_FOLDER) == before_files


def test_legacy_full_and_incremental_remain_readable(backup_store, upload):
    models.create_sample({'id': 'S', 'notes': 'legacy full'})
    database = backup_store / 'legacy-db.sqlite'
    backup._copy_database(test_config.DATABASE_PATH, database)
    full_name = 'full_2026-01-01_00-00-00.zip'
    with zipfile.ZipFile(Path(test_config.FULL_BACKUP_FOLDER, full_name), 'w') as archive:
        archive.write(database, 'db.sqlite')
        archive.writestr('uploads/base.txt', b'base')
    models.update_sample('S', {'notes': 'legacy increment'})
    timestamp = '2026-01-02_00-00-00'
    incremental = Path(test_config.BACKUP_FOLDER, timestamp)
    (incremental / 'files').mkdir(parents=True)
    (incremental / 'files/added.txt').write_bytes(b'added')
    backup._copy_database(test_config.DATABASE_PATH, incremental / 'db.sqlite')
    (incremental / 'backup_info.json').write_text(json.dumps({'timestamp': timestamp}), encoding='utf-8')
    assert backup.get_restore_plan(timestamp)['legacy'] is True
    target = backup_store / 'legacy-restored'
    result = backup.restore_backup(timestamp, target / 'uploads', target / 'db.sqlite')
    assert result['legacy'] is True
    assert contents(target / 'uploads') == {'base.txt': b'base', 'added.txt': b'added'}
    assert rows(target / 'db.sqlite', 'samples') == rows(test_config.DATABASE_PATH, 'samples')


def test_retention_preserves_complete_incremental_chain(backup_store, upload, monkeypatch):
    models.create_sample({'id': 'S'})
    monkeypatch.setattr(test_config, 'BACKUP_KEEP_COUNT', 1)
    monkeypatch.setattr(test_config, 'FULL_BACKUP_KEEP_COUNT', 1)
    first_full = Path(backup.run_full_backup())
    for index in range(3):
        upload('value.txt', str(index).encode())
        backup.run_backup()
    assert len(backup.list_backups()) == 3
    assert len(backup.get_restore_plan()['incrementals']) == 3
    second_full = Path(backup.run_full_backup())
    assert not first_full.exists()
    latest = Path(backup.run_backup())
    assert backup.list_backups() == [latest.name]
    assert backup.get_restore_plan()['full_backup'] == second_full.name


def test_full_retention_does_not_prune_before_limit(backup_store):
    for _ in range(6):
        backup.run_full_backup()
    assert len(backup.list_full_backups()) == 6


@pytest.mark.parametrize('kind', ['full', 'incremental'])
def test_manifest_failure_does_not_publish_an_incomplete_backup(backup_store, monkeypatch, kind):
    backup.run_full_backup()
    before_full = backup.list_full_backups()
    before_incremental = backup.list_backups()
    before_manifest = Path(backup.MANIFEST_PATH).read_bytes()

    def fail(manifest):
        raise OSError('manifest cannot be written')

    monkeypatch.setattr(backup, '_save_manifest', fail)
    with pytest.raises(OSError, match='cannot be written'):
        (backup.run_full_backup if kind == 'full' else backup.run_backup)()
    assert backup.list_full_backups() == before_full
    assert backup.list_backups() == before_incremental
    assert Path(backup.MANIFEST_PATH).read_bytes() == before_manifest


def test_incremental_writer_rejects_missing_parent(backup_store):
    backup.run_full_backup()
    parent = Path(backup.run_backup())
    (parent / 'backup_info.json').unlink()
    with pytest.raises(ValueError, match='时间点不存在'):
        backup.run_backup()
    assert backup.list_backups() == []


def test_backup_guard_excludes_another_process(backup_store):
    source = (
        'import sys, types\n'
        'config = types.ModuleType("config")\n'
        'config.BACKUP_FOLDER = sys.argv[1]\n'
        'sys.modules["config"] = config\n'
        'import backup\n'
        'try:\n'
        '    with backup._backup_guard():\n'
        '        sys.exit(1)\n'
        'except OSError:\n'
        '    print("blocked")\n'
    )
    with backup._backup_guard():
        child = subprocess.run([sys.executable, '-c', source, test_config.BACKUP_FOLDER],
                               capture_output=True, text=True, timeout=15,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == 'blocked'


def test_startup_scheduler_runs_full_before_incremental(backup_store, monkeypatch):
    calls = []
    stop = threading.Event()
    monkeypatch.setattr(backup, '_stop_event', stop)
    monkeypatch.setattr(backup, 'run_full_backup', lambda: calls.append('full'))

    def incremental():
        calls.append('incremental')
        stop.set()

    monkeypatch.setattr(backup, 'run_backup', incremental)
    backup._scheduler_loop()
    assert calls == ['full', 'incremental']


def test_restore_cli_previews_chain_and_preserves_cancelled_targets(backup_store, upload, monkeypatch, capsys):
    import restore_backup

    models.create_sample({'id': 'S'})
    upload('keep.txt', b'keep')
    full = Path(backup.run_full_backup())
    incremental = Path(backup.run_backup())
    before = Path(test_config.DATABASE_PATH).read_bytes()
    monkeypatch.setattr('builtins.input', lambda prompt: 'n')
    restore_backup.cmd_restore(incremental.name)
    output = capsys.readouterr().out
    assert full.name in output and incremental.name in output
    assert '请先停止应用' in output and '已取消' in output
    assert Path(test_config.DATABASE_PATH).read_bytes() == before
