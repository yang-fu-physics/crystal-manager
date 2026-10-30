from io import BytesIO
from pathlib import Path
import sqlite3

from docx import Document
import pytest

import ai_chat
import backup
import models
from conftest import test_config
from test_ai_chat import install_ai, propose
from test_backup_restore import backup_store, rows


def test_migration_adds_empty_fields_without_inventing_actual_product(tmp_path, monkeypatch):
    monkeypatch.setattr(test_config, 'DATABASE_PATH', str(tmp_path / 'legacy.db'))
    with sqlite3.connect(test_config.DATABASE_PATH) as connection:
        connection.execute("CREATE TABLE samples (id TEXT PRIMARY KEY, target_product TEXT, growth_process TEXT, "
                           "results TEXT, notes TEXT, created_at TEXT, updated_at TEXT)")
        connection.execute('INSERT INTO samples (id, target_product, growth_process, results) VALUES (?, ?, ?, ?)',
                           ('OLD', 'NbRhTe4', 'preserve temperature program', 'preserve observations'))
    models.init_db()
    models.init_db()
    with sqlite3.connect(test_config.DATABASE_PATH) as connection:
        saved = connection.execute('SELECT target_product, growth_process, results, growth_method, actual_product '
                                   'FROM samples WHERE id = ?', ('OLD',)).fetchone()
    assert saved == ('NbRhTe4', 'preserve temperature program', 'preserve observations', '', '')


@pytest.mark.parametrize('new_id', ['SAMPLE', 'RENAMED'])
def test_fields_save_read_preserve_for_older_clients_and_clear(client, new_id):
    created = client.post('/api/samples', json={
        'id': 'SAMPLE', 'target_product': 'NbRhTe4', 'growth_method': '自助熔剂法',
        'actual_product': 'RhTe2 + NbRhTe4', 'growth_process': '900 度退火', 'results': 'independent result',
    })
    assert created.status_code == 201
    assert created.get_json()['growth_method'] == '自助熔剂法'
    assert created.get_json()['actual_product'] == 'RhTe2 + NbRhTe4'
    updated = client.put('/api/samples/SAMPLE', json={'id': new_id, 'target_product': 'changed target'})
    assert updated.status_code == 200
    saved = client.get('/api/samples/' + new_id).get_json()
    assert saved['growth_method'] == '自助熔剂法'
    assert saved['actual_product'] == 'RhTe2 + NbRhTe4'
    assert client.put('/api/samples/' + new_id, json={
        'id': new_id, 'growth_method': '', 'actual_product': '',
    }).status_code == 200
    cleared = client.get('/api/samples/' + new_id).get_json()
    assert cleared['growth_method'] == cleared['actual_product'] == ''
    blank = client.post('/api/samples', json={'id': 'BLANK', 'target_product': 'FeSe', 'status': 1}).get_json()
    assert blank['growth_method'] == blank['actual_product'] == ''


@pytest.mark.parametrize('field, value', [('growth_method', 'uniqueCVTmethod'), ('actual_product', 'uniqueActualRhTe')])
def test_new_fields_are_searchable(client, field, value):
    models.create_sample({'id': 'FOUND', field: value})
    models.create_sample({'id': 'OTHER'})
    assert [sample['id'] for sample in models.get_all_samples(value)] == ['FOUND']
    assert [sample['id'] for sample in client.get('/api/samples', query_string={'q': value}).get_json()] == ['FOUND']


@pytest.mark.parametrize('field', ['growth_method', 'actual_product'])
@pytest.mark.parametrize('value', [None, ['invalid'], 'x' * 20001])
def test_new_fields_validate_external_input_without_changing_saved_data(client, field, value):
    models.create_sample({'id': 'KEEP', 'growth_method': 'CVT', 'actual_product': 'FeSe'})
    assert client.post('/api/samples', json={'id': 'BAD', field: value}).status_code == 400
    assert models.get_sample('BAD') is None
    assert client.put('/api/samples/KEEP', json={'id': 'KEEP', field: value}).status_code == 400
    assert models.get_sample('KEEP')['growth_method'] == 'CVT'
    assert models.get_sample('KEEP')['actual_product'] == 'FeSe'


def test_ai_new_fields_require_confirmation_and_undo_restores_them(client, install_ai):
    before = models.create_sample({'id': 'AI', 'target_product': 'NbRhTe4',
                                   'growth_method': 'Self-flux', 'actual_product': 'RhTe2'})
    proposal, _ = propose(client, install_ai, {'growth_method': 'CVT', 'actual_product': 'NbRhTe4 + RhTe2'}, sample_id='AI')
    assert {change['field'] for change in proposal['diff']} == {'growth_method', 'actual_product'}
    assert models.get_sample('AI') == before
    confirmed = client.post('/api/chat/confirm', json={'token': proposal['token']})
    assert confirmed.status_code == 200
    assert confirmed.get_json()['growth_method'] == 'CVT'
    assert confirmed.get_json()['actual_product'] == 'NbRhTe4 + RhTe2'
    assert client.post('/api/chat/undo', json={'token': confirmed.get_json()['undo_token']}).status_code == 200
    assert ai_chat.sample_record(models.get_sample('AI')) == ai_chat.sample_record(before)


def test_later_changes_to_new_fields_invalidate_ai_proposal(client, install_ai):
    models.create_sample({'id': 'AI', 'growth_method': 'CVT', 'actual_product': 'FeSe'})
    proposal, _ = propose(client, install_ai, {'notes': 'pending note'}, sample_id='AI')
    models.update_sample('AI', {'actual_product': 'FeTe'})
    assert client.post('/api/chat/confirm', json={'token': proposal['token']}).status_code == 409
    assert models.get_sample('AI')['actual_product'] == 'FeTe'


@pytest.mark.parametrize('lang, method_label, product_label', [('zh', '生长方法', '实际产物'),
                                                             ('en', 'Growth Method', 'Actual Product')])
def test_word_report_includes_separate_method_and_actual_product_rows(client, lang, method_label, product_label):
    models.create_sample({'id': 'WORD', 'target_product': 'NbRhTe4',
                          'growth_method': 'CVT', 'actual_product': 'RhTe2', 'growth_process': '900C'})
    response = client.get('/api/samples/WORD/export_word', query_string={'lang': lang})
    assert response.status_code == 200
    table = Document(BytesIO(response.data)).tables[0]
    metadata = {row.cells[0].text: row.cells[1].text for row in table.rows}
    assert metadata[method_label] == 'CVT'
    assert metadata[product_label] == 'RhTe2'


def test_full_and_incremental_backups_preserve_method_and_actual_product(backup_store, client):
    models.create_sample({'id': 'BACKUP', 'growth_method': 'Self-flux', 'actual_product': 'RhTe2'})
    full = Path(backup.run_full_backup())
    models.update_sample('BACKUP', {'growth_method': 'CVT', 'actual_product': 'NbRhTe4'})
    incremental = Path(backup.run_backup())
    target = backup_store / 'restored'
    backup.restore_backup(incremental.name, target / 'uploads', target / 'samples.db')
    assert rows(target / 'samples.db', 'samples') == rows(test_config.DATABASE_PATH, 'samples')
    earlier = backup_store / 'earlier'
    backup.restore_backup(full.name[5:-4], earlier / 'uploads', earlier / 'samples.db')
    with sqlite3.connect(earlier / 'samples.db') as connection:
        assert connection.execute('SELECT growth_method, actual_product FROM samples').fetchone() == ('Self-flux', 'RhTe2')
