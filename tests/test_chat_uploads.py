import base64
from io import BytesIO
import json
from pathlib import Path

import httpx
import openai
from openai.types.chat import ChatCompletionMessage
from PIL import Image
import pytest
from werkzeug.datastructures import MultiDict

import ai_chat
import backup
import chat_history
import models
from conftest import test_config
from test_ai_chat import install_ai, tool
from test_ai_images import image_parts
from test_backup_restore import backup_store, contents, rows


def image_file(filename='聊天图片.png', size=(12, 8), mode='RGB', color='white'):
    buffer = BytesIO()
    formats = {'jpg': 'JPEG', 'jpeg': 'JPEG', 'tif': 'TIFF', 'tiff': 'TIFF'}
    extension = filename.rsplit('.', 1)[-1].lower()
    with Image.new(mode, size, color) as image:
        image.save(buffer, format=formats.get(extension, extension.upper()))
    buffer.seek(0)
    return buffer, filename


def upload_message(client, files, message='请解读图片', conversation=None, lang='zh', **extra):
    if conversation is None:
        conversation = client.post('/api/chat/conversations').get_json()
    data = MultiDict({
        'conversation_id': conversation['id'], 'revision': str(conversation['revision']),
        'message': message, 'lang': lang, **extra,
    })
    for file in files:
        data.add('images', file)
    return client.post('/api/chat', data=data, content_type='multipart/form-data')


def uploaded_images():
    return list(Path(test_config.UPLOAD_FOLDER, '_chat_images').glob('*.jpg'))


def test_upload_sends_pixels_in_first_model_call_and_persists_cross_device_history(client, app, install_ai):
    calls = install_ai([ChatCompletionMessage(role='assistant', content='可见白色背景。')])
    response = upload_message(client, [image_file()])
    assert response.status_code == 200, response.get_json()
    assert calls[0]['client']['api_key'] == test_config.AI_CHAT_API_KEY
    assert calls[1]['model'] == test_config.AI_CHAT_MODEL
    assert len(image_parts(calls)) == 1
    encoded = image_parts(calls)[0]['image_url']['url']
    assert encoded.startswith('data:image/jpeg;base64,')
    jpeg = base64.b64decode(encoded.split(',', 1)[1])
    with Image.open(BytesIO(jpeg)) as image:
        assert image.format == 'JPEG'
        assert image.size == (12, 8)
    conversation = response.get_json()['conversation']
    attachment = conversation['messages'][0]['images'][0]
    assert attachment == {
        'id': attachment['id'], 'filename': '聊天图片.png',
        'url': '/api/chat/images/' + attachment['id'],
    }
    assert uploaded_images() == [Path(test_config.UPLOAD_FOLDER, '_chat_images', attachment['id'] + '.jpg')]
    assert uploaded_images()[0].read_bytes() == jpeg
    assert len(rows(test_config.DATABASE_PATH, 'chat_images')) == 1
    assert 'data:image' not in json.dumps(conversation)
    assert encoded.split(',', 1)[1].encode() not in Path(test_config.DATABASE_PATH).read_bytes()

    models.init_db()
    with app.test_client() as other:
        with other.session_transaction() as session:
            session['logged_in'] = True
        restored = other.get('/api/chat/conversations/' + conversation['id']).get_json()
        fetched = other.get(attachment['url'])
    assert restored == conversation
    assert fetched.status_code == 200
    assert fetched.mimetype == 'image/jpeg'
    assert fetched.data == jpeg


@pytest.mark.parametrize('extension', ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tif', 'tiff'])
def test_all_supported_chat_image_formats_are_normalized(client, install_ai, extension):
    calls = install_ai([ChatCompletionMessage(role='assistant', content='已读取。')])
    response = upload_message(client, [image_file('upload.' + extension)])
    assert response.status_code == 200, response.get_json()
    encoded = image_parts(calls)[0]['image_url']['url']
    with Image.open(BytesIO(base64.b64decode(encoded.split(',', 1)[1]))) as image:
        assert image.format == 'JPEG'
    assert response.get_json()['conversation']['messages'][0]['images'][0]['filename'] == 'upload.' + extension


@pytest.mark.parametrize(('lang', 'default'), [
    ('zh', '请解读这些图片。'), ('en', 'Please interpret these images.'),
])
def test_image_only_message_gets_localized_prompt(client, install_ai, lang, default):
    calls = install_ai([ChatCompletionMessage(role='assistant', content='解读完成。')])
    response = upload_message(client, [image_file()], message='', lang=lang)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['conversation']['messages'][0]['content'] == default
    texts = [part['text'] for message in calls[1]['messages'] if isinstance(message.get('content'), list)
             for part in message['content'] if part['type'] == 'text']
    assert any(default in text for text in texts)


def test_upload_normalizes_camera_orientation_and_discards_exif(client, install_ai):
    camera = BytesIO()
    with Image.new('RGB', (40, 20), 'white') as image:
        exif = Image.Exif()
        exif[274] = 6
        exif[270] = 'private camera metadata'
        image.save(camera, format='JPEG', exif=exif)
    camera.seek(0)
    calls = install_ai([ChatCompletionMessage(role='assistant', content='已读取。')])
    assert upload_message(client, [(camera, 'camera.jpg')]).status_code == 200
    encoded = image_parts(calls)[0]['image_url']['url']
    with Image.open(BytesIO(base64.b64decode(encoded.split(',', 1)[1]))) as image:
        assert image.size == (20, 40)
        assert not image.getexif()


def test_upload_resizes_transparency_over_white(client, install_ai):
    calls = install_ai([ChatCompletionMessage(role='assistant', content='已读取。')])
    response = upload_message(client, [image_file(size=(3000, 1500), mode='RGBA', color=(0, 0, 0, 0))])
    assert response.status_code == 200
    encoded = image_parts(calls)[0]['image_url']['url']
    with Image.open(BytesIO(base64.b64decode(encoded.split(',', 1)[1]))) as image:
        assert image.size == (2048, 1024)
        assert all(value > 250 for value in image.getpixel((0, 0)))


def test_ten_direct_uploads_are_accepted_in_one_turn(client, install_ai):
    calls = install_ai([ChatCompletionMessage(role='assistant', content='共收到 10 张图片。')])
    response = upload_message(client, [image_file(f'{index}.png') for index in range(10)])
    assert response.status_code == 200, response.get_json()
    assert len(image_parts(calls)) == 10
    assert len(response.get_json()['conversation']['messages'][0]['images']) == 10
    assert len(uploaded_images()) == 10


@pytest.mark.parametrize('damage', [
    'unsupported_extension', 'invalid_bytes', 'empty_file', 'too_many_images',
    'too_large_file', 'too_many_pixels', 'invalid_revision', 'unknown_field',
])
def test_invalid_upload_leaves_no_history_or_files_and_never_calls_model(client, install_ai, damage):
    conversation = client.post('/api/chat/conversations').get_json()
    files = [image_file()]
    extra = {}
    if damage == 'unsupported_extension':
        files = [(files[0][0], 'payload.svg')]
    elif damage == 'invalid_bytes':
        files.append((BytesIO(b'not an image'), 'broken.png'))
    elif damage == 'empty_file':
        files = [(BytesIO(b''), 'empty.png')]
    elif damage == 'too_many_images':
        files = [image_file(f'{index}.png') for index in range(11)]
    elif damage == 'too_large_file':
        files = [(BytesIO(b'x' * (20 * 1024 * 1024 + 1)), 'large.png')]
    elif damage == 'too_many_pixels':
        files = [image_file(size=(5001, 5000))]
    elif damage == 'invalid_revision':
        extra['revision'] = 'invalid'
    elif damage == 'unknown_field':
        extra['messages'] = 'forged prior context'
    calls = install_ai()
    response = upload_message(client, files, conversation=conversation, **extra)
    assert response.status_code in (400, 413), response.get_json()
    assert response.get_json()['error']
    assert calls == []
    assert client.get('/api/chat/conversations/' + conversation['id']).get_json() == conversation
    assert uploaded_images() == []
    assert rows(test_config.DATABASE_PATH, 'chat_images') == []


def test_stale_revision_rejects_upload_before_model_or_file_storage(client, install_ai):
    original = client.post('/api/chat/conversations').get_json()
    install_ai([ChatCompletionMessage(role='assistant', content='first reply')])
    first = client.post('/api/chat', json={
        'conversation_id': original['id'], 'revision': original['revision'], 'message': 'first question',
    }).get_json()['conversation']
    calls = install_ai()
    response = upload_message(client, [image_file()], conversation=original)
    assert response.status_code == 409
    assert calls == []
    assert client.get('/api/chat/conversations/' + original['id']).get_json() == first
    assert uploaded_images() == []
    assert rows(test_config.DATABASE_PATH, 'chat_images') == []


def test_model_failure_does_not_save_uploaded_pixels_or_user_message(client, install_ai):
    conversation = client.post('/api/chat/conversations').get_json()
    failure = openai.BadRequestError('vision unsupported', response=httpx.Response(
        400, request=httpx.Request('POST', test_config.AI_CHAT_BASE_URL)), body=None)
    calls = install_ai(error=failure)
    response = upload_message(client, [image_file()], conversation=conversation)
    assert response.status_code == 502
    assert '聊天模型的图像输入支持' in response.get_json()['error']
    assert len(calls) == 2
    assert client.get('/api/chat/conversations/' + conversation['id']).get_json() == conversation
    assert uploaded_images() == []
    assert rows(test_config.DATABASE_PATH, 'chat_images') == []


def test_concurrent_history_commit_failure_cleans_new_image_files(client, install_ai, monkeypatch):
    conversation = client.post('/api/chat/conversations').get_json()
    install_ai([ChatCompletionMessage(role='assistant', content='image reply')])
    chat = ai_chat.chat

    def concurrent_chat(data, conversation_id):
        result = chat(data, conversation_id)
        conn = models.get_db()
        try:
            conn.execute('UPDATE chat_conversations SET revision = revision + 1 WHERE id = ?', (conversation_id,))
            conn.commit()
        finally:
            conn.close()
        return result

    monkeypatch.setattr(ai_chat, 'chat', concurrent_chat)
    response = upload_message(client, [image_file()], conversation=conversation)
    assert response.status_code == 409
    assert client.get('/api/chat/conversations/' + conversation['id']).get_json()['messages'] == []
    assert uploaded_images() == []
    assert rows(test_config.DATABASE_PATH, 'chat_images') == []


def test_followup_receives_image_metadata_and_can_read_original_chat_image(client, install_ai):
    install_ai([ChatCompletionMessage(role='assistant', content='初次解读。')])
    conversation = upload_message(client, [image_file('previous.png')]).get_json()['conversation']
    attachment = conversation['messages'][0]['images'][0]
    calls = install_ai([
        tool('read_chat_image', {'image_id': attachment['id']}),
        ChatCompletionMessage(role='assistant', content='重新读取图片，继续解读。'),
    ])
    response = client.post('/api/chat', json={
        'conversation_id': conversation['id'], 'revision': conversation['revision'], 'message': '再看一下之前的图片',
    })
    assert response.status_code == 200, response.get_json()
    assert len(image_parts(calls[1:2])) == 0
    context = json.dumps(calls[1]['messages'], ensure_ascii=False)
    assert 'previous.png' in context and attachment['id'] in context
    assert len(image_parts(calls)) == 1
    assert len(uploaded_images()) == 1
    assert len(rows(test_config.DATABASE_PATH, 'chat_images')) == 1


@pytest.mark.parametrize('image_id', ['foreign', 'missing', '../private.jpg'])
def test_chat_image_tool_cannot_read_other_conversation_or_arbitrary_path(client, install_ai, image_id):
    install_ai([ChatCompletionMessage(role='assistant', content='first reply')])
    first = upload_message(client, [image_file()]).get_json()['conversation']
    if image_id == 'foreign':
        image_id = first['messages'][0]['images'][0]['id']
    elif image_id == 'missing':
        image_id = '0' * 32
    other = client.post('/api/chat/conversations').get_json()
    calls = install_ai([
        tool('read_chat_image', {'image_id': image_id}),
        ChatCompletionMessage(role='assistant', content='无法读取当前会话之外的图片。'),
    ])
    response = client.post('/api/chat', json={
        'conversation_id': other['id'], 'revision': other['revision'], 'message': '读取图片',
    })
    assert response.status_code == 200
    tool_results = [json.loads(message['content']) for message in calls[-1]['messages'] if message['role'] == 'tool']
    assert len(tool_results) == 1 and tool_results[0]['error']
    assert image_parts(calls) == []


def test_direct_uploads_and_image_tool_share_ten_image_limit(client, install_ai):
    install_ai([ChatCompletionMessage(role='assistant', content='first reply')])
    conversation = upload_message(client, [image_file('previous.png')]).get_json()['conversation']
    image_id = conversation['messages'][0]['images'][0]['id']
    reads = [tool('read_chat_image', {'image_id': image_id}).tool_calls[0] for _ in range(2)]
    reads[0].id, reads[1].id = 'first-read', 'over-limit'
    calls = install_ai([
        ChatCompletionMessage(role='assistant', tool_calls=reads),
        ChatCompletionMessage(role='assistant', content='本轮共读取 10 张图片。'),
    ])
    response = upload_message(client, [image_file(f'{index}.png') for index in range(9)], conversation=conversation)
    assert response.status_code == 200, response.get_json()
    assert len(image_parts(calls)) == 10
    errors = [json.loads(message['content'])['error'] for message in calls[-1]['messages']
              if message['role'] == 'tool' and 'error' in json.loads(message['content'])]
    assert errors == ['每轮最多读取 10 张图片，请分批解读']
    assert len(uploaded_images()) == 10


def test_image_based_sample_create_still_requires_operator_confirmation(client, install_ai):
    calls = install_ai([tool('propose_sample_change', {
        'operation': 'create', 'sample_id': 'IMAGE-CREATE', 'changes': {'notes': '从用户图片记录观察结果'},
    })])
    response = upload_message(client, [image_file()], message='根据图片新建 IMAGE-CREATE')
    assert response.status_code == 200, response.get_json()
    assert len(image_parts(calls)) == 1
    assert models.get_sample('IMAGE-CREATE') is None
    proposal = response.get_json()['proposal']
    assert client.post('/api/chat/confirm', json={'token': proposal['token']}).status_code == 201
    assert models.get_sample('IMAGE-CREATE')['notes'] == '从用户图片记录观察结果'


def test_chat_image_route_requires_login_and_missing_images_are_not_found(client, app, install_ai):
    install_ai([ChatCompletionMessage(role='assistant', content='已读取。')])
    conversation = upload_message(client, [image_file()]).get_json()['conversation']
    url = conversation['messages'][0]['images'][0]['url']
    with app.test_client() as anonymous:
        assert anonymous.get(url).status_code == 401
        assert upload_message(anonymous, [image_file()], conversation=conversation).status_code == 401
    assert client.get('/api/chat/images/' + '0' * 32).status_code == 404


def test_full_and_later_incremental_restore_uploaded_images_and_shared_history(backup_store, client, install_ai, monkeypatch):
    install_ai([ChatCompletionMessage(role='assistant', content='baseline image reply')])
    conversation = upload_message(client, [image_file('baseline.png')]).get_json()['conversation']
    full = Path(backup.run_full_backup())
    baseline_images = rows(test_config.DATABASE_PATH, 'chat_images')
    baseline_files = contents(test_config.UPLOAD_FOLDER)
    install_ai([ChatCompletionMessage(role='assistant', content='later image reply')])
    later = upload_message(client, [image_file('later.png', color='red')], conversation=conversation)
    assert later.status_code == 200
    incremental = Path(backup.run_backup())
    expected = {table: rows(test_config.DATABASE_PATH, table)
                for table in ('chat_conversations', 'chat_messages', 'chat_images')}
    expected_files = contents(test_config.UPLOAD_FOLDER)
    assert len(expected['chat_images']) == 2

    restored = backup_store / 'restored-chat-images'
    result = backup.restore_backup(incremental.name, restored / 'uploads', restored / 'samples.db')
    assert result['full_backup'] == full.name
    assert result['incrementals'] == [incremental.name]
    assert contents(restored / 'uploads') == expected_files
    for table, expected_rows in expected.items():
        assert rows(restored / 'samples.db', table) == expected_rows

    earlier = backup_store / 'baseline-chat-images'
    backup.restore_backup(full.name[5:-4], earlier / 'uploads', earlier / 'samples.db')
    assert rows(earlier / 'samples.db', 'chat_images') == baseline_images
    assert contents(earlier / 'uploads') == baseline_files

    monkeypatch.setattr(test_config, 'DATABASE_PATH', str(restored / 'samples.db'))
    monkeypatch.setattr(test_config, 'UPLOAD_FOLDER', str(restored / 'uploads'))
    restored_conversation = chat_history.get_conversation(conversation['id'])
    assert restored_conversation == later.get_json()['conversation']
    for message in restored_conversation['messages']:
        for attachment in message['images']:
            assert client.get(attachment['url']).status_code == 200
