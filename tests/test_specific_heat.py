from io import BytesIO
import sqlite3

from docx import Document
import pytest

import models
from conftest import test_config
from test_ai_chat import install_ai, propose


def test_existing_database_gets_unselected_specific_heat_flag_without_losing_data(tmp_path, monkeypatch):
    monkeypatch.setattr(test_config, 'DATABASE_PATH', str(tmp_path / 'legacy.db'))
    with sqlite3.connect(test_config.DATABASE_PATH) as connection:
        connection.execute('CREATE TABLE samples (id TEXT PRIMARY KEY, notes TEXT, '
                           'has_electric INTEGER DEFAULT 0, has_magnetic INTEGER DEFAULT 0, '
                           'created_at TEXT, updated_at TEXT)')
        connection.execute('INSERT INTO samples (id, notes, has_electric, has_magnetic) VALUES (?, ?, ?, ?)',
                           ('OLD-001', 'preserve this record', 1, 1))
    models.init_db()
    models.init_db()
    with sqlite3.connect(test_config.DATABASE_PATH) as connection:
        row = connection.execute('SELECT notes, has_electric, has_magnetic, has_specific_heat '
                                 'FROM samples WHERE id = ?', ('OLD-001',)).fetchone()
    assert row == ('preserve this record', 1, 1, 0)


@pytest.mark.parametrize('new_id', ['HEAT-001', 'HEAT-RENAMED'])
def test_specific_heat_flag_saves_clears_and_survives_sample_rename(client, new_id):
    created = client.post('/api/samples', json={
        'id': 'HEAT-001', 'has_specific_heat': 1, 'has_electric': 1, 'has_magnetic': 1,
    })
    assert created.status_code == 201
    assert created.get_json()['has_specific_heat'] == 1
    assert client.get('/api/samples/HEAT-001').get_json()['has_specific_heat'] == 1
    assert next(sample for sample in client.get('/api/samples').get_json() if sample['id'] == 'HEAT-001')['has_specific_heat'] == 1
    cleared = client.put('/api/samples/HEAT-001', json={
        'id': new_id, 'has_specific_heat': 0, 'has_electric': 1, 'has_magnetic': 1,
    })
    assert cleared.status_code == 200
    saved = client.get('/api/samples/' + new_id).get_json()
    assert saved['has_specific_heat'] == 0
    assert saved['has_electric'] == saved['has_magnetic'] == 1
    if new_id != 'HEAT-001':
        assert client.get('/api/samples/HEAT-001').status_code == 404
    assert client.put('/api/samples/' + new_id, json={'id': new_id, 'has_specific_heat': 1}).status_code == 200
    assert client.get('/api/samples/' + new_id).get_json()['has_specific_heat'] == 1
    blank = client.post('/api/samples', json={'id': 'BLANK'}).get_json()
    assert blank['has_specific_heat'] == 0


@pytest.mark.parametrize('before', [0, 1])
def test_ai_specific_heat_changes_require_confirmation_and_can_be_undone(client, install_ai, before):
    models.create_sample({'id': 'HEAT-AI', 'has_specific_heat': before, 'has_magnetic': 1})
    proposal, _ = propose(client, install_ai, {'has_specific_heat': 1 - before}, sample_id='HEAT-AI')
    assert proposal['diff'] == [{'field': 'has_specific_heat', 'before': before, 'after': 1 - before}]
    assert models.get_sample('HEAT-AI')['has_specific_heat'] == before
    confirmed = client.post('/api/chat/confirm', json={'token': proposal['token']})
    assert confirmed.status_code == 200
    assert models.get_sample('HEAT-AI')['has_specific_heat'] == 1 - before
    assert models.get_sample('HEAT-AI')['has_magnetic'] == 1
    undone = client.post('/api/chat/undo', json={'token': confirmed.get_json()['undo_token']})
    assert undone.status_code == 200
    assert models.get_sample('HEAT-AI')['has_specific_heat'] == before
    assert models.get_sample('HEAT-AI')['has_magnetic'] == 1


@pytest.mark.parametrize('lang, label, measurement', [('zh', '测量', '比热'), ('en', 'Measurements', 'Specific heat')])
def test_word_report_includes_specific_heat_in_measurements(client, lang, label, measurement):
    models.create_sample({'id': 'HEAT-EXPORT', 'has_specific_heat': 1})
    response = client.get(f'/api/samples/HEAT-EXPORT/export_word?lang={lang}')
    assert response.status_code == 200
    document = Document(BytesIO(response.data))
    row = next(row for row in document.tables[0].rows if row.cells[0].text == label)
    assert row.cells[1].text == measurement
