import json

from openai.types.chat import ChatCompletionMessage

import models
from test_ai_chat import ask, install_ai, tool


def test_reported_six_read_rounds_can_propose_on_seventh_without_saving(client, install_ai):
    for sample_id, temperature in [('H041', 1000), ('H042', 900)]:
        models.create_sample({'id': sample_id, 'target_product': 'NbRhTe4',
                              'growth_process': f'多晶，{temperature} 度退火'})
    operations = [
        {'operation': 'create', 'sample_id': sample_id,
         'changes': {'target_product': 'NbRhTe4', 'growth_process': f'多晶，{temperature} 度退火'}}
        for sample_id, temperature in [('H043', 1000), ('H044', 900)]
    ]
    calls = install_ai([
        tool('search_samples', {'query': 'NbRhTe4', 'offset': 0}),
        tool('search_samples', {'query': 'H', 'offset': 0}),
        tool('read_sample', {'sample_id': 'H043'}),
        tool('read_sample', {'sample_id': 'H044'}),
        tool('read_sample', {'sample_id': 'H042'}),
        tool('search_samples', {'query': '', 'offset': 0}),
        tool('propose_sample_changes', {'operations': operations}),
    ])
    response = ask(client, {'message': '写两个 NbRhTe4 多晶，编号顺延。分别 1000 度和 900 度退火。'})
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert len(calls) == 8  # Client initialization and seven completions.
    assert [proposal['sample_id'] for proposal in result['proposals']] == ['H043', 'H044']
    assert all('error' in json.loads(calls[index]['messages'][-1]['content']) for index in (4, 5))
    assert models.get_sample('H043') is None and models.get_sample('H044') is None
    assert client.post('/api/chat/confirm', json={'token': result['proposals'][0]['token']}).status_code == 201
    assert models.get_sample('H043')['growth_process'] == '多晶，1000 度退火'
    assert models.get_sample('H044') is None
    assert client.post('/api/chat/confirm', json={'token': result['proposals'][1]['token']}).status_code == 201
    assert models.get_sample('H044')['growth_process'] == '多晶，900 度退火'


def test_proposal_on_twelfth_round_is_accepted_but_still_needs_confirmation(client, install_ai):
    calls = install_ai([
        *(tool('search_samples', {'query': '', 'offset': 0}) for _ in range(11)),
        tool('propose_sample_change', {'operation': 'create', 'sample_id': 'LAST', 'changes': {}}),
    ])
    response = ask(client, {'message': '新建 LAST，其他先留空'})
    assert response.status_code == 200, response.get_json()
    assert len(calls) == 13
    assert response.get_json()['proposal']['sample_id'] == 'LAST'
    assert models.get_sample('LAST') is None


def test_twelve_read_rounds_still_stop_without_a_thirteenth_request_or_history_write(client, install_ai):
    calls = install_ai([
        *(tool('search_samples', {'query': '', 'offset': 0}) for _ in range(12)),
        ChatCompletionMessage(role='assistant', content='This thirteenth response must not be requested.'),
    ])
    response = ask(client, {'message': '查询样品'})
    assert response.status_code == 502
    assert 'AI 工具调用次数过多' in response.get_json()['error']
    assert len(calls) == 13
    assert models.get_all_samples() == []
    conversation_id = client.get('/api/chat/conversations').get_json()[0]['id']
    assert client.get('/api/chat/conversations/' + conversation_id).get_json()['messages'] == []
