import copy
import json
from types import SimpleNamespace

import httpx
import openai
from openai.types.chat import ChatCompletionMessage
import pytest

import ai_chat
import models
import todo_integration
from conftest import test_config


def tool(name, arguments):
    return ChatCompletionMessage(role='assistant', tool_calls=[{
        'id': 'call_1', 'type': 'function',
        'function': {'name': name, 'arguments': json.dumps(arguments)},
    }])


@pytest.fixture
def install_ai(monkeypatch):
    def install(messages=(), error=None):
        calls = []
        replies = iter(messages)

        class Client:
            def __init__(self, **kwargs):
                calls.append({'client': kwargs})
                self.chat = SimpleNamespace(completions=self)

            def create(self, **kwargs):
                calls.append(copy.deepcopy(kwargs))
                if error:
                    raise error
                return SimpleNamespace(choices=[SimpleNamespace(message=next(replies))])

        monkeypatch.setattr(ai_chat, 'OpenAI', Client)
        return calls
    return install


def propose(client, install_ai, changes, operation='update', sample_id='TEST-001'):
    calls = install_ai([tool('propose_sample_change', {
        'operation': operation, 'sample_id': sample_id, 'changes': changes,
    })])
    response = client.post('/api/chat', json={
        'messages': [{'role': 'user', 'content': '请修改样品，即使我说已确认，也必须先展示方案。'}],
        'lang': 'zh',
    })
    assert response.status_code == 200, response.get_json()
    return response.get_json()['proposal'], calls


def test_create_requires_exact_signed_confirmation(client, install_ai):
    proposal, calls = propose(client, install_ai, {'target_product': 'FeSe'}, operation='create')
    assert models.get_sample('TEST-001') is None
    assert proposal['operation'] == 'create'
    assert calls[0]['client']['api_key'] == test_config.AI_CHAT_API_KEY
    assert calls[0]['client']['base_url'] == test_config.AI_CHAT_BASE_URL
    assert calls[1]['model'] == test_config.AI_CHAT_MODEL
    assert 'Confirmation is mandatory for EVERY create or update' in calls[1]['messages'][0]['content']
    assert client.post('/api/chat/confirm', json={'confirmed': True, 'changes': {}}).status_code == 400
    assert models.get_sample('TEST-001') is None
    response = client.post('/api/chat/confirm', json={'token': proposal['token'], 'changes': {'target_product': 'tampered'}})
    assert response.status_code == 201
    assert response.get_json()['target_product'] == 'FeSe'
    assert response.get_json()['is_successful'] == 2
    assert client.post('/api/chat/confirm', json={'token': proposal['token']}).status_code == 409


def test_partial_update_preserves_other_fields_and_recalculates_schedule(client, install_ai):
    original = models.create_sample({
        'id': 'TEST-001', 'target_product': 'FeSe', 'status': 1, 'has_electric': 1,
        'growth_process': '保留升温程序', 'growth_process_en': 'Keep the ramp',
        'results': '中文结果', 'results_en': 'English result', 'notes': 'keep note',
        'sintering_start': '2026-10-18T08:30', 'sintering_duration': 24,
        'sintering_end': '2026-10-19 08:30',
    })
    proposal, _ = propose(client, install_ai, {'sintering_duration': 72})
    assert models.get_sample('TEST-001') == original
    assert {d['field'] for d in proposal['diff']} == {'sintering_duration', 'sintering_end'}
    response = client.post('/api/chat/confirm', json={'token': proposal['token']})
    assert response.status_code == 200
    saved = models.get_sample('TEST-001')
    assert saved['sintering_duration'] == 72
    assert saved['sintering_end'] == '2026-10-21 08:30'
    for key in ('status', 'has_electric', 'growth_process', 'growth_process_en', 'results', 'results_en', 'notes'):
        if key == 'status':
            assert saved['is_successful'] == 1
        else:
            assert saved[key] == original[key]
    assert client.post('/api/chat/confirm', json={'token': proposal['token']}).status_code == 409


def test_ratio_update_reuses_reference_mass_and_shows_all_derived_values(client, install_ai):
    models.create_sample({
        'id': 'TEST-001', 'status': 1,
        'element_ratios': [{'element': 'Fe', 'ratio': 1, 'is_reference': True},
                           {'element': 'Se', 'ratio': 1, 'is_reference': False}],
        'actual_masses': [{'element': 'Fe', 'mass': .5}, {'element': 'Se', 'mass': .7071}],
    })
    proposal, _ = propose(client, install_ai, {'element_ratios': [
        {'element': 'Fe', 'ratio': 1, 'is_reference': True},
        {'element': 'Se', 'ratio': 2, 'is_reference': False},
    ]})
    masses = next(d['after'] for d in proposal['diff'] if d['field'] == 'actual_masses')
    assert masses == [{'element': 'Fe', 'mass': .5}, {'element': 'Se', 'mass': 1.4141}]
    assert models.get_sample('TEST-001')['actual_masses'][1]['mass'] == .7071
    assert client.post('/api/chat/confirm', json={'token': proposal['token']}).status_code == 200
    assert models.get_sample('TEST-001')['actual_masses'] == masses


def test_new_ratios_without_reference_mass_do_not_invent_weighing_values(client, install_ai):
    proposal, _ = propose(client, install_ai, {'element_ratios': [
        {'element': 'Fe', 'ratio': 1, 'is_reference': True},
        {'element': 'Se', 'ratio': 1, 'is_reference': False},
    ]}, operation='create')
    assert next(d['after'] for d in proposal['diff'] if d['field'] == 'actual_masses') == []
    assert models.get_sample('TEST-001') is None


def test_stale_proposal_cannot_overwrite_manual_changes_even_with_same_timestamp(client, install_ai):
    models.create_sample({'id': 'TEST-001', 'notes': 'original'})
    proposal, _ = propose(client, install_ai, {'notes': 'AI proposal'})
    models.update_sample('TEST-001', {'notes': 'manual edit'})
    result = client.post('/api/chat/confirm', json={'token': proposal['token']})
    assert result.status_code == 409
    assert models.get_sample('TEST-001')['notes'] == 'manual edit'


def test_model_write_checks_snapshot_inside_transaction(client):
    before = models.create_sample({'id': 'TEST-001', 'notes': 'old'})
    models.update_sample('TEST-001', {'notes': 'concurrent edit'})
    with pytest.raises(models.SampleChangedError):
        models.update_sample('TEST-001', {'notes': 'stale write'}, expected_sample=before)
    assert models.get_sample('TEST-001')['notes'] == 'concurrent edit'


def test_tampered_and_cross_session_proposals_are_rejected(client, app, install_ai):
    proposal, _ = propose(client, install_ai, {'notes': 'new'}, operation='create')
    assert client.post('/api/chat/confirm', json={'token': proposal['token'] + 'x'}).status_code == 400
    with app.test_client() as other:
        with other.session_transaction() as session:
            session['logged_in'] = True
        assert other.post('/api/chat/confirm', json={'token': proposal['token']}).status_code == 400
    assert models.get_sample('TEST-001') is None


def test_expired_proposal_is_rejected(client, install_ai, monkeypatch):
    proposal, _ = propose(client, install_ai, {'notes': 'new'}, operation='create')
    serializer = ai_chat.signer()
    timestamp = serializer.make_signer().get_timestamp()
    monkeypatch.setattr('itsdangerous.timed.TimestampSigner.get_timestamp', lambda self: timestamp + 1801)
    assert client.post('/api/chat/confirm', json={'token': proposal['token']}).status_code == 400
    assert models.get_sample('TEST-001') is None


@pytest.mark.parametrize('changes', [
    {'unknown_field': 'x'}, {'status': True}, {'has_xrd': 9}, {'sintering_duration': -1},
    {'sintering_start': 'not a date'}, {'sintering_start': '2026-10-18T08:00Z'},
    {'element_ratios': [{'element': 'Xx', 'ratio': 1, 'is_reference': True}]},
    {'element_ratios': [{'element': 'Fe', 'ratio': 0, 'is_reference': True}]},
    {'element_ratios': [{'element': 'Fe', 'ratio': 1, 'is_reference': False}]},
    {'element_ratios': [{'element': 'Fe', 'ratio': 1, 'is_reference': True},
                        {'element': 'Fe', 'ratio': 2, 'is_reference': False}]},
    {'element_ratios': [{'element': 'Fe', 'ratio': 1, 'is_reference': True}], 'reference_mass': None},
    {'element_ratios': [{'element': 'Fe', 'ratio': 1, 'is_reference': True}], 'reference_mass': -1},
])
def test_invalid_tool_changes_are_returned_to_model_without_writing(client, install_ai, changes):
    models.create_sample({'id': 'TEST-001', 'notes': 'keep'})
    calls = install_ai([
        tool('propose_sample_change', {'operation': 'update', 'sample_id': 'TEST-001', 'changes': changes}),
        ChatCompletionMessage(role='assistant', content='请补充有效参数。'),
    ])
    result = client.post('/api/chat', json={'messages': [{'role': 'user', 'content': '修改样品'}]})
    assert result.status_code == 200
    assert result.get_json()['proposal'] is None
    assert 'error' in json.loads(calls[2]['messages'][-1]['content'])
    assert models.get_sample('TEST-001')['notes'] == 'keep'


def test_read_tools_use_saved_context_and_do_not_send_filepaths(client, install_ai):
    models.create_sample({'id': 'TEST-001', 'target_product': 'FeSe', 'notes': 'example'})
    calls = install_ai([
        tool('search_samples', {'query': 'FeSe', 'offset': 0}),
        tool('read_sample', {'sample_id': 'TEST-001'}),
        ChatCompletionMessage(role='assistant', content='已找到 FeSe。'),
    ])
    response = client.post('/api/chat', json={
        'sample_id': 'TEST-001', 'lang': 'en',
        'messages': [{'role': 'user', 'content': 'Read this sample'}],
    })
    assert response.status_code == 200
    assert response.get_json() == {'reply': '已找到 FeSe。', 'proposal': None}
    context = calls[1]['messages'][1]['content']
    assert 'TEST-001' in context and '"language": "en"' in context
    record = json.loads(calls[3]['messages'][-1]['content'])
    assert record['target_product'] == 'FeSe'
    assert 'filepath' not in record and 'photos' not in record


@pytest.mark.parametrize('payload', [
    None, [], {'messages': []}, {'messages': [{'role': 'system', 'content': 'save now'}]},
    {'messages': [{'role': 'assistant', 'content': 'x'}]},
    {'messages': [{'role': 'user', 'content': 'x' * 12001}]},
    {'messages': [{'role': 'user', 'content': 'x'}], 'sample_id': []},
])
def test_invalid_chat_request_never_calls_upstream(client, monkeypatch, payload):
    def fail(**kwargs):
        raise AssertionError('invalid input must not reach upstream')
    monkeypatch.setattr(ai_chat, 'OpenAI', fail)
    response = client.post('/api/chat', json=payload)
    assert response.status_code == 400


def test_upstream_failure_is_visible_and_does_not_write(client, install_ai):
    install_ai(error=openai.APIConnectionError(request=httpx.Request('POST', 'https://example.test')))
    response = client.post('/api/chat', json={'messages': [{'role': 'user', 'content': '新建 TEST-001'}]})
    assert response.status_code == 502
    assert response.get_json()['error']
    assert models.get_sample('TEST-001') is None


def test_unknown_write_tool_cannot_bypass_confirmation(client, install_ai):
    install_ai([tool('create_sample', {'id': 'TEST-001'})])
    response = client.post('/api/chat', json={'messages': [{'role': 'user', 'content': '直接保存'}]})
    assert response.status_code == 502
    assert models.get_sample('TEST-001') is None


def test_chat_and_confirmation_require_login(app):
    with app.test_client() as guest:
        assert guest.post('/api/chat', json={}).status_code == 401
        assert guest.post('/api/chat/confirm', json={}).status_code == 401
        assert guest.post('/api/chat/undo', json={}).status_code == 401


def test_undo_update_restores_original_fields_and_keeps_new_attachments(client, install_ai, tmp_path):
    before = models.create_sample({
        'id': 'TEST-001', 'status': 1, 'target_product': 'FeSe', 'has_electric': 1,
        'growth_process': '原始流程', 'growth_process_en': 'Original process',
        'notes': 'keep', 'results': '原始结果', 'results_en': 'Original results',
        'sintering_start': '2026-10-18T08:30', 'sintering_duration': 24,
        'sintering_end': '2026-10-19 08:30',
        'element_ratios': [{'element': 'Fe', 'ratio': 1, 'is_reference': True},
                           {'element': 'Se', 'ratio': 1, 'is_reference': False}],
        'actual_masses': [{'element': 'Fe', 'mass': .5}, {'element': 'Se', 'mass': .7071}],
    })
    proposal, _ = propose(client, install_ai, {
        'growth_process': '新的保温流程', 'sintering_duration': 72,
        'element_ratios': [{'element': 'Fe', 'ratio': 1, 'is_reference': True},
                           {'element': 'Se', 'ratio': 2, 'is_reference': False}],
    })
    saved = client.post('/api/chat/confirm', json={'token': proposal['token']}).get_json()
    photo = tmp_path / 'new-photo.jpg'
    photo.write_bytes(b'keep attachment')
    models.add_photo('TEST-001', photo.name, str(photo))
    attachments = models.get_sample('TEST-001')['photos']
    result = client.post('/api/chat/undo', json={'token': saved['undo_token']})
    assert result.status_code == 200, result.get_json()
    restored = models.get_sample('TEST-001')
    assert ai_chat.sample_record(restored) == ai_chat.sample_record(before)
    assert restored['created_at'] == before['created_at']
    assert restored['photos'] == attachments
    assert photo.read_bytes() == b'keep attachment'
    assert client.post('/api/chat/undo', json={'token': saved['undo_token']}).status_code == 409


def test_undo_create_removes_only_the_created_sample(client, install_ai):
    models.create_sample({'id': 'KEEP', 'notes': 'keep'})
    proposal, _ = propose(client, install_ai, {'target_product': 'FeSe'}, operation='create')
    saved = client.post('/api/chat/confirm', json={'token': proposal['token']}).get_json()
    result = client.post('/api/chat/undo', json={'token': saved['undo_token']})
    assert result.status_code == 200
    assert result.get_json()['deleted'] is True
    assert models.get_sample('TEST-001') is None
    assert models.get_sample('KEEP')['notes'] == 'keep'
    assert client.post('/api/chat/undo', json={'token': saved['undo_token']}).status_code == 409


@pytest.mark.parametrize('operation', ['create', 'update'])
def test_undo_cannot_overwrite_later_manual_changes(client, install_ai, operation):
    if operation == 'update':
        models.create_sample({'id': 'TEST-001', 'notes': 'old'})
    proposal, _ = propose(client, install_ai, {'notes': 'AI edit'}, operation=operation)
    saved = client.post('/api/chat/confirm', json={'token': proposal['token']}).get_json()
    models.update_sample('TEST-001', {'notes': 'later manual edit'})
    assert client.post('/api/chat/undo', json={'token': saved['undo_token']}).status_code == 409
    assert models.get_sample('TEST-001')['notes'] == 'later manual edit'


@pytest.mark.parametrize('table', ['photos', 'edx_images', 'xrd_images', 'data_files', 'other_files'])
def test_undo_create_never_deletes_added_attachments(client, install_ai, tmp_path, table):
    proposal, _ = propose(client, install_ai, {'notes': 'created'}, operation='create')
    saved = client.post('/api/chat/confirm', json={'token': proposal['token']}).get_json()
    attachment = tmp_path / 'attachment.dat'
    attachment.write_bytes(b'keep')
    conn = models.get_db()
    try:
        conn.execute(f'INSERT INTO {table} (sample_id, filename, filepath) VALUES (?, ?, ?)',
                     ('TEST-001', attachment.name, str(attachment)))
        conn.commit()
    finally:
        conn.close()
    result = client.post('/api/chat/undo', json={'token': saved['undo_token']})
    assert result.status_code == 409
    assert '附件' in result.get_json()['error']
    assert models.get_sample('TEST-001')[table]
    assert attachment.read_bytes() == b'keep'


def test_undo_create_checks_snapshot_inside_delete_transaction(client):
    before = models.create_sample({'id': 'TEST-001', 'notes': 'old'})
    models.update_sample('TEST-001', {'notes': 'concurrent edit'})
    with pytest.raises(models.SampleChangedError):
        models.delete_sample('TEST-001', expected_sample=before)
    assert models.get_sample('TEST-001')['notes'] == 'concurrent edit'


def test_undo_tokens_are_signed_session_bound_and_distinct_from_proposals(client, app, install_ai, monkeypatch):
    proposal, _ = propose(client, install_ai, {'notes': 'created'}, operation='create')
    saved = client.post('/api/chat/confirm', json={'token': proposal['token']}).get_json()
    undo = saved['undo_token']
    assert client.post('/api/chat/undo', json={'token': undo + 'x'}).status_code == 400
    assert client.post('/api/chat/undo', json={'token': proposal['token']}).status_code == 400
    assert client.post('/api/chat/confirm', json={'token': undo}).status_code == 400
    with app.test_client() as other:
        with other.session_transaction() as session:
            session['logged_in'] = True
        assert other.post('/api/chat/undo', json={'token': undo}).status_code == 400
    timestamp = ai_chat.signer().make_signer().get_timestamp()
    monkeypatch.setattr('itsdangerous.timed.TimestampSigner.get_timestamp', lambda self: timestamp + 1801)
    assert client.post('/api/chat/undo', json={'token': undo}).status_code == 400
    assert models.get_sample('TEST-001')['notes'] == 'created'


@pytest.mark.parametrize('payload', [None, [], {}, {'token': 1}])
def test_invalid_undo_request_does_not_write(client, payload):
    models.create_sample({'id': 'TEST-001', 'notes': 'keep'})
    assert client.post('/api/chat/undo', json=payload).status_code == 400
    assert models.get_sample('TEST-001')['notes'] == 'keep'


def test_undo_schedule_resyncs_original_todo_time(client, install_ai, monkeypatch):
    calls = []
    monkeypatch.setattr(todo_integration, 'create_or_update_todo',
                        lambda sample_id, end, db, product: (calls.append(end) or True, 'synced'))
    models.create_sample({'id': 'TEST-001', 'sintering_start': '2026-10-18T08:30',
                          'sintering_duration': 24, 'sintering_end': '2026-10-19 08:30'})
    proposal, _ = propose(client, install_ai, {'sintering_duration': 72})
    saved = client.post('/api/chat/confirm', json={'token': proposal['token']}).get_json()
    result = client.post('/api/chat/undo', json={'token': saved['undo_token']})
    assert result.status_code == 200
    assert calls == ['2026-10-21 08:30', '2026-10-19 08:30']


@pytest.mark.parametrize('operation', ['create', 'update'])
def test_undo_removes_new_todo_reminder(client, install_ai, monkeypatch, operation):
    if operation == 'update':
        models.create_sample({'id': 'TEST-001'})
    proposal, _ = propose(client, install_ai, {
        'sintering_start': '2026-10-18T08:30', 'sintering_duration': 24,
    }, operation=operation)
    saved = client.post('/api/chat/confirm', json={'token': proposal['token']}).get_json()
    models.upsert_todo_task('TEST-001', 'task-1', saved['sintering_end'])
    monkeypatch.setattr(todo_integration, 'is_connected', lambda: True)
    monkeypatch.setattr(todo_integration, 'get_access_token', lambda: 'test-token')
    monkeypatch.setattr(todo_integration, '_get_default_task_list_id', lambda token: 'list-1')
    calls = []
    monkeypatch.setattr(todo_integration, 'delete_todo_task', lambda *args: calls.append(args))
    result = client.post('/api/chat/undo', json={'token': saved['undo_token']})
    assert result.status_code == 200
    assert result.get_json()['todo_synced'] is True
    assert calls == [('test-token', 'list-1', 'task-1')]
    assert models.get_todo_task('TEST-001') is None


def test_undo_reports_todo_failure_after_restoring_sample(client, install_ai, monkeypatch):
    proposal, _ = propose(client, install_ai, {'notes': 'created'}, operation='create')
    saved = client.post('/api/chat/confirm', json={'token': proposal['token']}).get_json()
    models.upsert_todo_task('TEST-001', 'task-1', '2026-10-19 08:30')
    monkeypatch.setattr(todo_integration, 'is_connected', lambda: True)
    monkeypatch.setattr(todo_integration, 'get_access_token', lambda: 'test-token')

    def fail(token):
        raise todo_integration.http_requests.exceptions.ConnectionError('network unavailable')

    monkeypatch.setattr(todo_integration, '_get_default_task_list_id', fail)
    result = client.post('/api/chat/undo', json={'token': saved['undo_token']})
    assert result.status_code == 200
    assert result.get_json()['todo_synced'] is False
    assert '取消 To Do 提醒失败' in result.get_json()['todo_msg']
    assert models.get_sample('TEST-001') is None
    assert models.get_todo_task('TEST-001')['task_id'] == 'task-1'
