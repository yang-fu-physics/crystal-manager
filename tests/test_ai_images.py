import base64
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
from openai.types.chat import ChatCompletionMessage
from PIL import Image
import pytest

import ai_chat
import models
from conftest import test_config
from test_ai_chat import ask, install_ai, tool


@pytest.fixture
def stored_image(client):
    def create(sample_id='IMG-001', collection='photos', filename='saved.png', size=(12, 8), mode='RGB', color='white'):
        if models.get_sample(sample_id) is None:
            models.create_sample({'id': sample_id, 'notes': 'preserve'})
        path = Path(test_config.UPLOAD_FOLDER, sample_id, collection, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        with Image.new(mode, size, color) as image:
            image.save(path, format='PNG' if path.suffix == '.dat' else None)
        add = {'photos': models.add_photo, 'edx_images': models.add_edx_image,
               'xrd_images': models.add_xrd_image, 'data_files': models.add_data_file,
               'other_files': models.add_other_file}[collection]
        image_id = add(sample_id, filename, str(path))
        return {'sample_id': sample_id, 'collection': collection, 'image_id': image_id}, path
    return create


def image_parts(calls):
    return [part for message in calls[-1]['messages'] if isinstance(message.get('content'), list)
            for part in message['content'] if part['type'] == 'image_url']


def test_list_saved_images_from_every_attachment_area_without_sending_pixels(client, stored_image, install_ai):
    images = [stored_image(collection=collection) for collection in ai_chat.IMAGE_COLLECTIONS]
    stored_image(collection='xrd_images', filename='raw.dat')
    before = models.get_sample('IMG-001')
    calls = install_ai([
        tool('list_sample_images', {'sample_id': 'IMG-001'}),
        ChatCompletionMessage(role='assistant', content='找到 5 张图片，可选择解读。'),
    ])
    response = ask(client, {'message': '列出 IMG-001 已保存的图片'})
    assert response.status_code == 200
    result = json.loads(calls[-1]['messages'][-1]['content'])
    assert result['sample_id'] == 'IMG-001'
    assert result['images'] == [{**{key: value for key, value in request.items() if key != 'sample_id'},
                                 'filename': path.name} for request, path in images]
    assert image_parts(calls) == []
    assert str(test_config.UPLOAD_FOLDER) not in json.dumps(calls[1:], ensure_ascii=False)
    assert models.get_sample('IMG-001') == before


@pytest.mark.parametrize('collection', ai_chat.IMAGE_COLLECTIONS)
def test_saved_image_is_sent_to_chat_model_and_history_keeps_only_text_sources(client, app, stored_image, install_ai, collection):
    request, path = stored_image(collection=collection, filename='中文图像.png')
    original_bytes = path.read_bytes()
    before = models.get_sample('IMG-001')
    calls = install_ai([
        tool('read_sample_image', request),
        ChatCompletionMessage(role='assistant', content='可见白色背景，未作任何样品修改。'),
    ])
    response = ask(client, {'message': '解读 IMG-001 的这张图片'})
    assert response.status_code == 200
    assert calls[0]['client']['api_key'] == test_config.AI_CHAT_API_KEY
    assert calls[0]['client']['base_url'] == test_config.AI_CHAT_BASE_URL
    assert calls[-1]['model'] == test_config.AI_CHAT_MODEL
    parts = image_parts(calls)
    assert len(parts) == 1
    encoded = parts[0]['image_url']['url']
    assert encoded.startswith('data:image/jpeg;base64,')
    with Image.open(BytesIO(base64.b64decode(encoded.split(',', 1)[1]))) as image:
        assert image.size == (12, 8)
        assert image.format == 'JPEG'
    assert str(path) not in json.dumps(calls[1:], ensure_ascii=False)
    result = response.get_json()
    assert result['proposals'] == []
    assert f"IMG-001 · {ai_chat.IMAGE_COLLECTIONS[collection][0]} #{request['image_id']} · 中文图像.png" in result['reply']
    assert models.get_sample('IMG-001') == before
    assert path.read_bytes() == original_bytes
    models.init_db()
    with app.test_client() as other:
        with other.session_transaction() as session:
            session['logged_in'] = True
        history = other.get('/api/chat/conversations/' + result['conversation']['id']).get_json()
    assert history['messages'][-1]['content'] == result['reply']
    assert 'data:image' not in json.dumps(history)
    assert encoded.split(',', 1)[1] not in json.dumps(history)


@pytest.mark.parametrize('extension', ['jpg', 'webp', 'gif', 'bmp', 'tif'])
def test_image_formats_are_converted_to_jpeg_without_changing_original(client, stored_image, install_ai, extension):
    request, path = stored_image(filename='saved.' + extension)
    original = path.read_bytes()
    calls = install_ai([tool('read_sample_image', request), ChatCompletionMessage(role='assistant', content='已读取。')])
    assert ask(client, {'message': '解读图片', 'lang': 'en'}).status_code == 200
    assert image_parts(calls)[0]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert path.read_bytes() == original


def test_large_transparent_image_is_resized_on_white_background(client, stored_image, install_ai):
    request, path = stored_image(size=(3000, 1500), mode='RGBA', color=(0, 0, 0, 0))
    original = path.read_bytes()
    calls = install_ai([tool('read_sample_image', request), ChatCompletionMessage(role='assistant', content='已读取。')])
    assert ask(client, {'message': '解读图片'}).status_code == 200
    encoded = image_parts(calls)[0]['image_url']['url'].split(',', 1)[1]
    with Image.open(BytesIO(base64.b64decode(encoded))) as image:
        assert image.size == (2048, 1024)
        assert all(value > 250 for value in image.getpixel((0, 0)))
    assert path.read_bytes() == original


def test_camera_orientation_is_applied_and_exif_not_forwarded(client, stored_image, install_ai):
    request, path = stored_image(filename='rotated.jpg', size=(40, 20))
    with Image.new('RGB', (40, 20), 'white') as image:
        exif = Image.Exif()
        exif[274] = 6
        exif[270] = 'private camera metadata'
        image.save(path, exif=exif)
    calls = install_ai([tool('read_sample_image', request), ChatCompletionMessage(role='assistant', content='已读取。')])
    assert ask(client, {'message': '解读照片'}).status_code == 200
    encoded = image_parts(calls)[0]['image_url']['url'].split(',', 1)[1]
    with Image.open(BytesIO(base64.b64decode(encoded))) as image:
        assert image.size == (20, 40)
        assert not image.getexif()


def test_multi_page_image_uses_first_page(client, stored_image, install_ai):
    request, path = stored_image(filename='pages.tif')
    with Image.new('RGB', (12, 8), 'red') as first, Image.new('RGB', (12, 8), 'blue') as second:
        first.save(path, save_all=True, append_images=[second])
    original = path.read_bytes()
    calls = install_ai([tool('read_sample_image', request), ChatCompletionMessage(role='assistant', content='第一页为红色。')])
    assert ask(client, {'message': '解读图片'}).status_code == 200
    encoded = image_parts(calls)[0]['image_url']['url'].split(',', 1)[1]
    with Image.open(BytesIO(base64.b64decode(encoded))) as image:
        red, green, blue = image.getpixel((0, 0))
        assert red > 240 and green < 20 and blue < 20
    assert path.read_bytes() == original


@pytest.mark.parametrize('damage', [
    'wrong_sample', 'missing_sample', 'wrong_id', 'wrong_collection', 'bad_collection_type',
    'bad_id_type', 'extra_path', 'missing_file', 'invalid_bytes', 'outside_root',
    'unsupported_attachment', 'too_large_bytes', 'too_many_pixels',
])
def test_invalid_image_reads_are_explicit_and_send_no_pixels(client, stored_image, install_ai, tmp_path, damage):
    request, path = stored_image(
        filename='raw.dat' if damage == 'unsupported_attachment' else 'saved.png',
        size=(5001, 5000) if damage == 'too_many_pixels' else (12, 8),
    )
    if damage == 'wrong_sample':
        models.create_sample({'id': 'OTHER'})
        request['sample_id'] = 'OTHER'
    elif damage == 'missing_sample':
        request['sample_id'] = 'MISSING'
    elif damage == 'wrong_id':
        request['image_id'] += 100
    elif damage == 'wrong_collection':
        request['collection'] = '../private'
    elif damage == 'bad_collection_type':
        request['collection'] = []
    elif damage == 'bad_id_type':
        request['image_id'] = True
    elif damage == 'extra_path':
        request['filepath'] = str(tmp_path / 'private.png')
    elif damage == 'missing_file':
        path.unlink()
    elif damage == 'invalid_bytes':
        path.write_bytes(b'not an image')
    elif damage == 'outside_root':
        outside = tmp_path / 'private.png'
        outside.write_bytes(path.read_bytes())
        conn = models.get_db()
        try:
            conn.execute('UPDATE photos SET filepath = ? WHERE id = ?', (str(outside), request['image_id']))
            conn.commit()
        finally:
            conn.close()
    elif damage == 'too_large_bytes':
        path.write_bytes(b'x' * (20 * 1024 * 1024 + 1))
    calls = install_ai([
        tool('read_sample_image', request),
        ChatCompletionMessage(role='assistant', content='无法读取指定图片，请核对附件。'),
    ])
    response = ask(client, {'message': '解读指定图片'})
    assert response.status_code == 200
    error = json.loads(calls[-1]['messages'][-1]['content'])['error']
    assert error
    if damage == 'too_many_pixels':
        assert '2500 万像素' in error
    if damage == 'too_large_bytes':
        assert '20 MB' in error
    assert image_parts(calls) == []
    assert response.get_json()['proposals'] == []
    assert str(test_config.UPLOAD_FOLDER) not in json.dumps(calls[1:], ensure_ascii=False)
    assert models.get_sample('IMG-001')['notes'] == 'preserve'


def test_image_based_changes_still_require_confirmation(client, stored_image, install_ai):
    request, _ = stored_image()
    install_ai([
        tool('read_sample_image', request),
        tool('propose_sample_change', {'operation': 'update', 'sample_id': 'IMG-001',
                                       'changes': {'notes': 'operator-requested visual observation'}}),
    ])
    response = ask(client, {'message': '解读图片，并准备将观察写入备注'})
    assert response.status_code == 200
    assert models.get_sample('IMG-001')['notes'] == 'preserve'
    assert '已读取图片' in response.get_json()['reply']
    proposal = response.get_json()['proposal']
    assert client.post('/api/chat/confirm', json={'token': proposal['token']}).status_code == 200
    assert models.get_sample('IMG-001')['notes'] == 'operator-requested visual observation'


def test_proposal_in_same_round_as_image_read_is_not_returned_before_model_sees_pixels(client, stored_image, install_ai):
    request, _ = stored_image()
    image_call = tool('read_sample_image', request).tool_calls[0]
    proposal_call = tool('propose_sample_change', {'operation': 'update', 'sample_id': 'IMG-001',
                                                  'changes': {'notes': 'blind guess'}}).tool_calls[0]
    image_call.id, proposal_call.id = 'read-image', 'blind-proposal'
    calls = install_ai([
        ChatCompletionMessage(role='assistant', tool_calls=[image_call, proposal_call]),
        ChatCompletionMessage(role='assistant', content='已看到图片，先说明观察结果。'),
    ])
    response = ask(client, {'message': '解读图片'})
    assert response.status_code == 200
    assert len(image_parts(calls)) == 1
    assert response.get_json()['proposals'] == []
    assert models.get_sample('IMG-001')['notes'] == 'preserve'
    assert 'No proposal from this round was retained or saved' in calls[-1]['messages'][-1]['content']


def test_image_read_limit_is_cumulative_across_tool_rounds_and_parallel_calls(client, stored_image, install_ai):
    requests = [stored_image(filename=f'image-{index}.png')[0] for index in range(11)]
    tool_calls = []
    for index, request in enumerate(requests):
        call = tool('read_sample_image', request).tool_calls[0]
        call.id = str(index)
        tool_calls.append(call)
    calls = install_ai([
        ChatCompletionMessage(role='assistant', tool_calls=tool_calls[:6]),
        ChatCompletionMessage(role='assistant', tool_calls=tool_calls[6:]),
        ChatCompletionMessage(role='assistant', content='本次读取 10 张，第 11 张超出上限，请下轮继续。'),
    ])
    response = ask(client, {'message': '解读这些图片'})
    assert response.status_code == 200
    assert len(image_parts(calls)) == 10
    errors = [json.loads(message['content'])['error'] for message in calls[-1]['messages']
              if message['role'] == 'tool' and 'error' in json.loads(message['content'])]
    assert errors == ['每轮最多读取 10 张图片，请分批解读']
    assert 'image-10.png' not in response.get_json()['reply']


def test_image_upstream_failure_is_explicit_and_does_not_fall_back_to_edx(client, stored_image, install_ai, monkeypatch):
    request, _ = stored_image()
    install_ai()
    count = []

    def create(self, **kwargs):
        count.append(kwargs)
        if len(count) == 1:
            return SimpleNamespace(choices=[SimpleNamespace(message=tool('read_sample_image', request))])
        raise openai.BadRequestError('vision unsupported', response=httpx.Response(
            400, request=httpx.Request('POST', test_config.AI_CHAT_BASE_URL)), body=None)

    monkeypatch.setattr(ai_chat.OpenAI, 'create', create)
    response = ask(client, {'message': '解读图片'})
    assert response.status_code == 502
    assert '聊天模型的图像输入支持' in response.get_json()['error']
    assert len(count) == 2
    assert all(call['model'] == test_config.AI_CHAT_MODEL for call in count)
    assert models.get_sample('IMG-001')['notes'] == 'preserve'
