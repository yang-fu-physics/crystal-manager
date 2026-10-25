from pathlib import Path

from openai.types.chat import ChatCompletionMessage
import pytest
from werkzeug.exceptions import Conflict

import ai_chat
import backup
import chat_history
import models
from conftest import test_config
from test_ai_chat import install_ai, propose
from test_backup_restore import backup_store, contents, rows
from test_chat_uploads import image_file, upload_message


def test_delete_removes_shared_messages_cards_and_chat_images_only(client, app, install_ai):
    models.create_sample({'id': 'KEEP', 'notes': 'sample is independent of chat'})
    photo = Path(test_config.UPLOAD_FOLDER, 'KEEP', 'photos', 'sample.png')
    photo.parent.mkdir(parents=True)
    photo.write_bytes(image_file()[0].getvalue())
    models.add_photo('KEEP', 'sample.png', str(photo))
    before = models.get_sample('KEEP')
    proposal, _ = propose(client, install_ai, {'notes': 'not saved'}, operation='create', sample_id='PENDING')
    pending = chat_history.get_action(proposal['token'])
    conversation = chat_history.get_conversation(pending['conversation_id'])
    image_id = 'a' * 32
    image = chat_history.image_path(image_id)
    image.parent.mkdir(parents=True)
    image.write_bytes(b'chat image')
    conn = models.get_db()
    try:
        user = conn.execute('SELECT id FROM chat_messages WHERE conversation_id = ? AND role = ?',
                            (conversation['id'], 'user')).fetchone()
        conn.execute('INSERT INTO chat_images (id, message_id, filename) VALUES (?, ?, ?)',
                     (image_id, user['id'], 'chat.png'))
        conn.commit()
    finally:
        conn.close()
    other = client.post('/api/chat/conversations').get_json()
    install_ai([ChatCompletionMessage(role='assistant', content='keep this history')])
    other = upload_message(client, [image_file('other.png')], conversation=other).get_json()['conversation']
    other_image = other['messages'][0]['images'][0]

    deleted = client.delete('/api/chat/conversations/' + conversation['id'], json={'revision': conversation['revision']})
    assert deleted.status_code == 200, deleted.get_json()
    assert deleted.get_json() == {'deleted': True}
    assert not image.exists()
    assert client.get('/api/chat/images/' + image_id).status_code == 404
    assert client.get('/api/chat/conversations/' + conversation['id']).status_code == 404
    assert client.post('/api/chat/confirm', json={'token': proposal['token']}).status_code == 400
    assert models.get_sample('PENDING') is None
    assert models.get_sample('KEEP') == before and photo.exists()
    assert client.get('/api/chat/conversations/' + other['id']).get_json() == other
    assert client.get(other_image['url']).status_code == 200
    assert len(rows(test_config.DATABASE_PATH, 'chat_images')) == 1
    with app.test_client() as device:
        with device.session_transaction() as session:
            session['logged_in'] = True
        assert [item['id'] for item in device.get('/api/chat/conversations').get_json()] == [other['id']]
        assert device.get('/api/chat/conversations/' + conversation['id']).status_code == 404


def test_delete_saved_conversation_keeps_sample_and_invalidates_undo(client, install_ai):
    proposal, _ = propose(client, install_ai, {'notes': 'saved sample'}, operation='create')
    saved = client.post('/api/chat/confirm', json={'token': proposal['token']}).get_json()
    before = models.get_sample('TEST-001')
    conversation = chat_history.get_conversation(saved['conversation_id'])
    assert client.delete('/api/chat/conversations/' + conversation['id'],
                         json={'revision': conversation['revision']}).status_code == 200
    assert client.post('/api/chat/undo', json={'token': saved['undo_token']}).status_code == 400
    assert models.get_sample('TEST-001') == before
    assert rows(test_config.DATABASE_PATH, 'chat_messages') == []


@pytest.mark.parametrize('payload', [None, [], {}, {'revision': '0'}, {'revision': True},
                                     {'revision': 0, 'confirmed': True}])
def test_delete_rejects_invalid_revision_without_removing_conversation(client, payload):
    conversation = client.post('/api/chat/conversations').get_json()
    assert client.delete('/api/chat/conversations/' + conversation['id'], json=payload).status_code == 400
    assert chat_history.get_conversation(conversation['id']) == conversation


def test_delete_requires_login_and_reports_missing_or_stale_conversation(client, app):
    conversation = client.post('/api/chat/conversations').get_json()
    url = '/api/chat/conversations/' + conversation['id']
    with app.test_client() as guest:
        assert guest.delete(url, json={'revision': 0}).status_code == 401
    assert client.delete(url, json={'revision': 1}).status_code == 409
    assert chat_history.get_conversation(conversation['id']) == conversation
    assert client.delete(url, json={'revision': 0}).status_code == 200
    assert client.delete(url, json={'revision': 0}).status_code == 404


@pytest.mark.parametrize('state', ['confirming', 'undoing'])
def test_delete_during_sample_save_or_undo_is_rejected(client, install_ai, state):
    proposal, _ = propose(client, install_ai, {}, operation='create')
    message = chat_history.get_action(proposal['token'])
    chat_history.transition(message, 'pending', state)
    conversation = chat_history.get_conversation(message['conversation_id'])
    response = client.delete('/api/chat/conversations/' + conversation['id'],
                             json={'revision': conversation['revision']})
    assert response.status_code == 409
    assert '正在处理' in response.get_json()['error']
    assert chat_history.get_conversation(conversation['id']) == conversation


def test_deleted_card_cannot_be_claimed_by_another_device(client, install_ai):
    proposal, _ = propose(client, install_ai, {}, operation='create')
    message = chat_history.get_action(proposal['token'])
    conversation = chat_history.get_conversation(message['conversation_id'])
    assert client.delete('/api/chat/conversations/' + conversation['id'],
                         json={'revision': conversation['revision']}).status_code == 200
    with pytest.raises(Conflict):
        chat_history.transition(message, 'pending', 'confirming')
    assert models.get_sample('TEST-001') is None


def test_chat_response_cannot_resurrect_a_conversation_deleted_during_generation(client, monkeypatch):
    conversation = client.post('/api/chat/conversations').get_json()

    def delete_while_generating(data, conversation_id):
        chat_history.delete_conversation(conversation_id, data['revision'])
        return {'reply': 'late response', 'proposals': []}

    monkeypatch.setattr(ai_chat, 'chat', delete_while_generating)
    response = upload_message(client, [image_file()], conversation=conversation)
    assert response.status_code == 409
    assert rows(test_config.DATABASE_PATH, 'chat_conversations') == []
    assert rows(test_config.DATABASE_PATH, 'chat_messages') == []
    assert rows(test_config.DATABASE_PATH, 'chat_images') == []
    assert list(Path(test_config.UPLOAD_FOLDER, '_chat_images').glob('*.jpg')) == []


def test_incremental_backup_restores_conversation_and_image_deletions(backup_store, client, install_ai):
    models.create_sample({'id': 'KEEP', 'notes': 'keep the sample'})
    install_ai([ChatCompletionMessage(role='assistant', content='image reply')])
    conversation = upload_message(client, [image_file()]).get_json()['conversation']
    full = Path(backup.run_full_backup())
    baseline_files = contents(test_config.UPLOAD_FOLDER)
    assert baseline_files
    assert client.delete('/api/chat/conversations/' + conversation['id'],
                         json={'revision': conversation['revision']}).status_code == 200
    incremental = Path(backup.run_backup())
    later = backup_store / 'after-deletion'
    backup.restore_backup(incremental.name, later / 'uploads', later / 'db.sqlite')
    assert contents(later / 'uploads') == {}
    for table in ('chat_conversations', 'chat_messages', 'chat_images'):
        assert rows(later / 'db.sqlite', table) == []
    assert rows(later / 'db.sqlite', 'samples') == rows(test_config.DATABASE_PATH, 'samples')
    earlier = backup_store / 'before-deletion'
    backup.restore_backup(full.name[5:-4], earlier / 'uploads', earlier / 'db.sqlite')
    assert len(rows(earlier / 'db.sqlite', 'chat_conversations')) == 1
    assert contents(earlier / 'uploads') == baseline_files
