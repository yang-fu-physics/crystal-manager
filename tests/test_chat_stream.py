import json

import httpx
from openai import OpenAI

import ai_chat
import chat_history
import models
from test_chat_uploads import image_file, uploaded_images


class ModelStream(httpx.SyncByteStream):
    def __init__(self, *chunks):
        self.chunks = chunks
        self.closed = False

    def __iter__(self):
        for delta, finish_reason in self.chunks:
            chunk = {
                'id': 'chatcmpl-test', 'object': 'chat.completion.chunk', 'created': 0,
                'model': 'test-model', 'choices': [
                    {'index': 0, 'delta': delta, 'finish_reason': finish_reason},
                ],
            }
            yield ('data: ' + json.dumps(chunk, ensure_ascii=False) + '\n\n').encode()
        yield b'data: [DONE]\n\n'

    def close(self):
        self.closed = True


def model_streams(monkeypatch, *streams):
    remaining = iter(streams)
    requests = []

    def request_handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, stream=next(remaining))

    def make_client(**kwargs):
        return OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(request_handler)))

    monkeypatch.setattr(ai_chat, 'OpenAI', make_client)
    return requests


def start_reply(client):
    conversation = client.post('/api/chat/conversations').get_json()
    response = client.post('/api/chat', json={
        'conversation_id': conversation['id'], 'revision': 0, 'message': '请检查样品',
    }, headers={'Accept': 'application/x-ndjson'}, buffered=False)
    assert response.status_code == 200
    assert response.mimetype == 'application/x-ndjson'
    return conversation['id'], response


def test_stream_sends_text_before_committing_history(client, monkeypatch):
    upstream = ModelStream(({'content': '## 样品'}, None), ({'content': '结果'}, None), ({}, 'stop'))
    requests = model_streams(monkeypatch, upstream)
    conversation_id, response = start_reply(client)
    with response:
        events = iter(response.response)
        assert json.loads(next(events))['type'] == 'progress'
        assert json.loads(next(events)) == {'type': 'delta', 'text': '## 样品'}
        assert chat_history.get_conversation(conversation_id)['messages'] == []
        rest = [json.loads(event) for event in events]
    assert rest[0] == {'type': 'delta', 'text': '结果'}
    assert rest[-1]['type'] == 'complete'
    assert rest[-1]['conversation']['messages'][-1]['content'] == '## 样品结果'
    assert requests[0]['stream'] is True
    assert upstream.closed


def test_stream_assembles_tool_arguments_and_keeps_text_with_confirmation(client, monkeypatch):
    first = ModelStream(
        ({'content': '正在读取'}, None),
        ({'tool_calls': [
            {'index': 1, 'id': 'read', 'type': 'function',
             'function': {'name': 'read_samples', 'arguments': '{"sample_ids":'}},
            {'index': 0, 'id': 'find', 'type': 'function',
             'function': {'name': 'search_samples', 'arguments': '{"query":"FeSe",'}},
        ]}, None),
        ({'tool_calls': [
            {'index': 1, 'function': {'arguments': '["NEW"]}'}},
            {'index': 0, 'function': {'arguments': '"offset":0}'}},
        ]}, None),
        ({}, 'tool_calls'),
    )
    second = ModelStream(
        ({'content': '建议新建 **NEW**。', 'tool_calls': [
            {'index': 0, 'id': 'proposal', 'type': 'function',
             'function': {'name': 'propose_sample_change', 'arguments': '{"operation":"create",'}},
        ]}, None),
        ({'tool_calls': [
            {'index': 0, 'function': {'arguments': '"sample_id":"NEW","changes":{"target_product":"FeSe"}}'}},
        ]}, None),
        ({'content': '目标产物为 FeSe。'}, 'tool_calls'),
    )
    requests = model_streams(monkeypatch, first, second)
    _, response = start_reply(client)
    with response:
        events = [json.loads(event) for event in response.response]
    visible_events = [event for event in events if event['type'] in ('delta', 'reset')]
    assert visible_events == [
        {'type': 'delta', 'text': '正在读取'},
        {'type': 'reset'},
        {'type': 'delta', 'text': '建议新建 **NEW**。'},
        {'type': 'delta', 'text': '目标产物为 FeSe。'},
    ]
    tool_results = [m for m in requests[1]['messages'] if m['role'] == 'tool']
    assert [m['tool_call_id'] for m in tool_results] == ['find', 'read']
    assert json.loads(tool_results[1]['content'])['missing_ids'] == ['NEW']
    assert events[-1]['type'] == 'complete'
    card = events[-1]['conversation']['messages'][-1]
    assert card['state'] == 'pending'
    assert card['content'] == (
        '建议新建 **NEW**。目标产物为 FeSe。\n\n'
        '请逐个核对下方方案；每个样品点击确认保存后才会写入。'
    )
    assert models.get_sample('NEW') is None
    assert client.post('/api/chat/confirm', json={'token': card['proposal']['token']}).status_code == 201
    assert models.get_sample('NEW')['target_product'] == 'FeSe'


def test_closing_stream_releases_upstream_and_discards_unfinished_turn(client, monkeypatch):
    upstream = ModelStream(({'content': '片段'}, None), ({'content': '未读取'}, None), ({}, 'stop'))
    requests = model_streams(monkeypatch, upstream)
    conversation_id = client.post('/api/chat/conversations').get_json()['id']
    response = client.post('/api/chat', data={
        'conversation_id': conversation_id, 'revision': '0', 'message': '请看图片', 'images': image_file(),
    }, headers={'Accept': 'application/x-ndjson'}, buffered=False)
    events = iter(response.response)
    next(events)
    assert json.loads(next(events)) == {'type': 'delta', 'text': '片段'}
    response.close()
    assert upstream.closed
    assert any(part['type'] == 'image_url' for part in requests[0]['messages'][-1]['content'])
    assert uploaded_images() == []
    conversation = chat_history.get_conversation(conversation_id)
    assert conversation['revision'] == 0
    assert conversation['messages'] == []


def test_stream_ending_without_finish_reason_does_not_save_partial_reply(client, monkeypatch):
    model_streams(monkeypatch, ModelStream(({'content': '未完成'}, None)))
    conversation_id, response = start_reply(client)
    with response:
        events = [json.loads(event) for event in response.response]
    assert events[-1] == {'type': 'error', 'error': 'AI 回复未完整结束，请重试'}
    assert chat_history.get_conversation(conversation_id)['messages'] == []
