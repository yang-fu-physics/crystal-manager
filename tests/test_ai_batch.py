import json

from openai.types.chat import ChatCompletionMessage
import pytest

import chat_history
import models
from test_ai_chat import ask, install_ai, tool


def test_batch_cards_confirm_cancel_and_undo_independently_across_devices(client, app, install_ai):
    original = models.create_sample({
        'id': 'B', 'notes': 'keep', 'sintering_start': '2026-10-19T08:00',
        'sintering_duration': 24, 'sintering_end': '2026-10-20 08:00',
    })
    install_ai([tool('propose_sample_changes', {'operations': [
        {'operation': 'create', 'sample_id': 'A', 'changes': {'target_product': 'FeSe'}},
        {'operation': 'update', 'sample_id': 'B', 'changes': {'sintering_duration': 72}},
        {'operation': 'create', 'sample_id': 'C', 'changes': {'notes': 'cancel this'}},
    ]})])
    response = ask(client, {'message': '新建 A 和 C，将 B 烧制耗时改为 72 小时'})
    assert response.status_code == 200
    result = response.get_json()
    proposals = result['proposals']
    assert [proposal['sample_id'] for proposal in proposals] == ['A', 'B', 'C']
    assert len({proposal['token'] for proposal in proposals}) == 3
    assert models.get_sample('A') is None and models.get_sample('C') is None
    assert models.get_sample('B') == original
    conversation_id = result['conversation']['id']
    assert len(result['conversation']['messages']) == 4

    saved_a = client.post('/api/chat/confirm', json={'token': proposals[0]['token']})
    assert saved_a.status_code == 201
    assert models.get_sample('A')['target_product'] == 'FeSe'
    assert models.get_sample('B') == original
    assert models.get_sample('C') is None
    assert client.post('/api/chat/cancel', json={'token': proposals[2]['token']}).status_code == 200
    with app.test_client() as other:
        with other.session_transaction() as session:
            session['logged_in'] = True
        saved_b = other.post('/api/chat/confirm', json={'token': proposals[1]['token']})
        assert saved_b.status_code == 200
    assert models.get_sample('B')['sintering_end'] == '2026-10-22 08:00'
    assert models.get_sample('B')['notes'] == 'keep'
    assert client.post('/api/chat/undo', json={'token': saved_a.get_json()['undo_token']}).status_code == 200
    assert models.get_sample('A') is None
    assert models.get_sample('B')['sintering_duration'] == 72

    models.init_db()
    restored = client.get('/api/chat/conversations/' + conversation_id).get_json()
    cards = restored['messages'][1:]
    assert [card['state'] for card in cards] == ['undone', 'saved', 'cancelled']
    assert [card['proposal']['token'] for card in cards] == [proposal['token'] for proposal in proposals]
    assert client.post('/api/chat/confirm', json={'token': proposals[0]['token']}).status_code == 409
    assert client.post('/api/chat/confirm', json={'token': proposals[2]['token']}).status_code == 409
    context = chat_history.model_messages(restored, '查看操作结果')
    context_text = '\n'.join(message['content'] for message in context)
    assert all(f'"sample_id": "{sample_id}"' in context_text
               for sample_id in ('A', 'B', 'C'))
    assert client.post('/api/chat/undo', json={'token': saved_b.get_json()['undo_token']}).status_code == 200
    assert models.get_sample('B')['sintering_duration'] == original['sintering_duration']


def test_stale_sample_does_not_prevent_confirming_other_batch_card(client, install_ai):
    for sample_id in ('A', 'B'):
        models.create_sample({'id': sample_id, 'notes': 'before'})
    install_ai([tool('propose_sample_changes', {'operations': [
        {'operation': 'update', 'sample_id': sample_id, 'changes': {'notes': 'proposed'}}
        for sample_id in ('A', 'B')
    ]})])
    response = ask(client, {'message': '同时修改 A、B 的备注'})
    assert response.status_code == 200
    proposals = response.get_json()['proposals']
    models.update_sample('A', {'notes': 'manual change'})
    assert client.post('/api/chat/confirm', json={'token': proposals[0]['token']}).status_code == 409
    assert client.post('/api/chat/confirm', json={'token': proposals[1]['token']}).status_code == 200
    assert models.get_sample('A')['notes'] == 'manual change'
    assert models.get_sample('B')['notes'] == 'proposed'


def test_multiple_single_proposal_tool_calls_are_all_retained(client, install_ai):
    first = tool('propose_sample_change', {'operation': 'create', 'sample_id': 'A', 'changes': {}}).tool_calls[0]
    second = tool('propose_sample_change', {'operation': 'create', 'sample_id': 'B', 'changes': {}}).tool_calls[0]
    first.id, second.id = 'first', 'second'
    install_ai([ChatCompletionMessage(role='assistant', tool_calls=[first, second])])
    response = ask(client, {'message': '新建 A、B'})
    assert response.status_code == 200
    assert [proposal['sample_id'] for proposal in response.get_json()['proposals']] == ['A', 'B']
    assert len(response.get_json()['conversation']['messages']) == 3
    assert models.get_all_samples() == []


@pytest.mark.parametrize('operations', [
    None, [], [{}],
    [{'operation': 'create', 'sample_id': 'A', 'changes': {}},
     {'operation': 'create', 'sample_id': ' A ', 'changes': {'notes': 'duplicate'}}],
    [{'operation': 'create', 'sample_id': 'A', 'changes': {}},
     {'operation': 'create', 'sample_id': 'EXISTS', 'changes': {}}],
    [{'operation': 'create', 'sample_id': 'A', 'changes': {}},
     {'operation': 'update', 'sample_id': 'MISSING', 'changes': {'notes': 'invalid'}}],
    [{'operation': 'create', 'sample_id': 'A', 'changes': {}},
     {'operation': 'create', 'sample_id': 'B', 'changes': {'unsupported': 'invalid'}}],
    [{'operation': 'create', 'sample_id': str(index), 'changes': {}} for index in range(11)],
])
def test_invalid_batch_generates_no_partial_cards_or_samples(client, install_ai, operations):
    models.create_sample({'id': 'EXISTS', 'notes': 'preserve'})
    calls = install_ai([
        tool('propose_sample_changes', {'operations': operations}),
        ChatCompletionMessage(role='assistant', content='批次有问题，请核对编号或字段。'),
    ])
    response = ask(client, {'message': '批量处理'})
    assert response.status_code == 200
    assert response.get_json()['proposals'] == []
    assert all(message['proposal'] is None for message in response.get_json()['conversation']['messages'])
    assert 'error' in json.loads(calls[2]['messages'][-1]['content'])
    assert [sample['id'] for sample in models.get_all_samples()] == ['EXISTS']
    assert models.get_sample('EXISTS')['notes'] == 'preserve'


def test_tool_error_does_not_silently_drop_part_of_parallel_batch(client, install_ai):
    first = tool('propose_sample_change', {'operation': 'create', 'sample_id': 'A', 'changes': {}}).tool_calls[0]
    second = tool('propose_sample_change', {'operation': 'update', 'sample_id': 'MISSING', 'changes': {'notes': 'x'}}).tool_calls[0]
    first.id, second.id = 'first', 'second'
    calls = install_ai([
        ChatCompletionMessage(role='assistant', tool_calls=[first, second]),
        ChatCompletionMessage(role='assistant', content='MISSING 不存在，未生成任何确认卡。'),
    ])
    response = ask(client, {'message': '同时处理 A 和 MISSING'})
    assert response.status_code == 200
    assert response.get_json()['proposals'] == []
    assert models.get_all_samples() == []
    assert 'No proposal from this round was retained or saved' in calls[2]['messages'][-1]['content']


def test_ten_sample_batch_is_supported_and_next_message_supersedes_every_pending_card(client, install_ai):
    calls = install_ai([tool('propose_sample_changes', {'operations': [
        {'operation': 'create', 'sample_id': f'BATCH-{index}', 'changes': {}} for index in range(10)
    ]})])
    response = ask(client, {'message': '为这 10 个编号生成空白样品'})
    assert response.status_code == 200
    proposals = response.get_json()['proposals']
    assert len(proposals) == 10
    assert len(response.get_json()['conversation']['messages']) == 11
    assert 'propose_sample_changes' in {item['function']['name'] for item in calls[1]['tools']}
    install_ai([ChatCompletionMessage(role='assistant', content='已改为仅查询。')])
    conversation = response.get_json()['conversation']
    next_response = client.post('/api/chat', json={
        'conversation_id': conversation['id'], 'revision': conversation['revision'], 'message': '先不新建了',
    })
    assert next_response.status_code == 200
    assert all(message['state'] == 'superseded' for message in next_response.get_json()['conversation']['messages'][1:11])
    assert client.post('/api/chat/confirm', json={'token': proposals[9]['token']}).status_code == 409
    assert models.get_all_samples() == []


def test_batch_read_returns_exact_records_and_explicit_missing_ids(client, install_ai):
    models.create_sample({'id': 'A', 'target_product': 'FeSe', 'growth_process': 'grow A'})
    models.create_sample({'id': 'B', 'target_product': 'FeTe', 'growth_process_en': 'grow B'})
    models.create_sample({'id': 'A-extra', 'notes': 'must not match exact A'})
    calls = install_ai([
        tool('read_samples', {'sample_ids': ['A', 'MISSING', 'B']}),
        ChatCompletionMessage(role='assistant', content='A 和 B 的流程不同，MISSING 不存在。'),
    ])
    response = ask(client, {'message': '比较 A、MISSING 和 B 的生长流程'})
    assert response.status_code == 200
    records = json.loads(calls[2]['messages'][-1]['content'])
    assert [record['id'] for record in records['samples']] == ['A', 'B']
    assert records['missing_ids'] == ['MISSING']
    assert records['samples'][0]['growth_process'] == 'grow A'
    assert records['samples'][1]['growth_process_en'] == 'grow B'
    assert all('photos' not in record and 'filepath' not in record for record in records['samples'])
    assert response.get_json()['proposals'] == []
    assert len(models.get_all_samples()) == 3


@pytest.mark.parametrize('ids', [None, [], 'A', ['A', 1], [' '], ['A', ' A '], list(map(str, range(11)))])
def test_invalid_batch_read_is_reported_to_model(client, install_ai, ids):
    calls = install_ai([
        tool('read_samples', {'sample_ids': ids}),
        ChatCompletionMessage(role='assistant', content='请提供有效编号。'),
    ])
    response = ask(client, {'message': '查询多个编号'})
    assert response.status_code == 200
    assert 'error' in json.loads(calls[2]['messages'][-1]['content'])
    assert models.get_all_samples() == []


@pytest.mark.parametrize('field', ['id', 'target_product', 'notes', 'results', 'results_en', 'growth_process', 'growth_process_en'])
def test_search_can_match_every_documented_text_field(client, install_ai, field):
    models.create_sample({'id': 'MATCH' if field == 'id' else 'A', **({field: 'MATCH'} if field != 'id' else {})})
    models.create_sample({'id': 'UNRELATED'})
    calls = install_ai([
        tool('search_samples', {'query': 'MATCH', 'offset': 0}),
        ChatCompletionMessage(role='assistant', content='找到 1 个匹配样品。'),
    ])
    response = ask(client, {'message': '查找 MATCH'})
    assert response.status_code == 200
    records = json.loads(calls[2]['messages'][-1]['content'])
    assert records['total'] == 1
    assert [record['id'] for record in records['samples']] == ['MATCH' if field == 'id' else 'A']


def test_search_pagination_exposes_all_matches_without_writes(client, install_ai):
    for index in range(23):
        models.create_sample({'id': f'S-{index:02}', 'notes': 'common search term'})
    calls = install_ai([
        tool('search_samples', {'query': 'common search term', 'offset': 0}),
        tool('search_samples', {'query': 'common search term', 'offset': 20}),
        ChatCompletionMessage(role='assistant', content='共 23 个样品。'),
    ])
    response = ask(client, {'message': '找出全部匹配的样品'})
    assert response.status_code == 200
    pages = [json.loads(calls[index]['messages'][-1]['content']) for index in (2, 3)]
    assert [page['total'] for page in pages] == [23, 23]
    assert [len(page['samples']) for page in pages] == [20, 3]
    assert len({record['id'] for page in pages for record in page['samples']}) == 23
    assert len(models.get_all_samples()) == 23
