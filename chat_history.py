"""Shared, authenticated chat history and persistent operation-card states."""

import json
import time
import uuid

from werkzeug.exceptions import BadRequest, Conflict, NotFound

import config
import models


def list_conversations():
    conn = models.get_db()
    try:
        return [dict(row) for row in conn.execute(
            'SELECT * FROM chat_conversations ORDER BY updated_at DESC, rowid DESC')]
    finally:
        conn.close()


def get_conversation(conversation_id):
    conn = models.get_db()
    try:
        conn.execute('BEGIN')
        row = conn.execute('SELECT * FROM chat_conversations WHERE id = ?', (conversation_id,)).fetchone()
        if row is None:
            raise NotFound('会话不存在')
        conversation = dict(row)
        messages = [dict(row) for row in conn.execute(
            'SELECT * FROM chat_messages WHERE conversation_id = ? ORDER BY rowid', (conversation_id,))]
    finally:
        conn.close()
    now = time.time()
    for message in messages:
        message['proposal'] = json.loads(message['proposal']) if message['proposal'] is not None else None
        message['can_confirm'] = message['state'] == 'pending' and message['proposal_expires'] > now
        message['can_undo'] = message['state'] == 'saved' and message['undo_expires'] > now
    conversation['messages'] = messages
    return conversation


def create_conversation():
    conversation_id = uuid.uuid4().hex
    now = config.get_local_now().isoformat()
    conn = models.get_db()
    try:
        conn.execute('INSERT INTO chat_conversations (id, created_at, updated_at) VALUES (?, ?, ?)',
                     (conversation_id, now, now))
        conn.commit()
    finally:
        conn.close()
    return get_conversation(conversation_id)


def model_messages(conversation, content):
    """Keep full UI history, but send only the recent context within the API budget."""
    history = [{'role': 'user', 'content': content}]
    size = len(content)
    for message in reversed(conversation['messages']):
        text = message['content']
        if message['proposal'] is not None:
            proposal = message['proposal']
            text += '\nOperation card state: ' + message['state'] + '\n' + json.dumps({
                'operation': proposal['operation'], 'sample_id': proposal['sample_id'], 'diff': proposal['diff'],
            }, ensure_ascii=False)
        if len(text) > 12000:
            text = text[:11980] + '\n[truncated]'
        if len(history) == 30 or size + len(text) > 60000:
            break
        history.append({'role': message['role'], 'content': text})
        size += len(text)
    return list(reversed(history))


def append_turn(conversation, content, result):
    conn = models.get_db()
    now = config.get_local_now().isoformat()
    proposal = result['proposal']
    try:
        conn.execute('BEGIN IMMEDIATE')
        updated = conn.execute(
            "UPDATE chat_conversations SET revision = revision + 1, updated_at = ?, "
            "title = CASE WHEN title = '' THEN ? ELSE title END WHERE id = ? AND revision = ?",
            (now, ' '.join(content.split())[:60], conversation['id'], conversation['revision']))
        if updated.rowcount != 1:
            raise Conflict('会话已在其他页面更新，请重新加载后继续')
        conn.execute("UPDATE chat_messages SET state = 'superseded' WHERE conversation_id = ? AND state = 'pending'",
                     (conversation['id'],))
        conn.execute('INSERT INTO chat_messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)',
                     (uuid.uuid4().hex, conversation['id'], 'user', content, now))
        conn.execute(
            'INSERT INTO chat_messages (id, conversation_id, role, content, proposal, proposal_token, proposal_expires, state, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (uuid.uuid4().hex, conversation['id'], 'assistant', result['reply'],
             json.dumps(proposal, ensure_ascii=False) if proposal is not None else None,
             proposal['token'] if proposal is not None else None,
             time.time() + 1800 if proposal is not None else None,
             'pending' if proposal is not None else 'complete', now))
        conn.commit()
    finally:
        conn.close()
    return get_conversation(conversation['id'])


def get_action(token, undo=False):
    if not isinstance(token, str):
        raise BadRequest('缺少操作凭据')
    column = 'undo_token' if undo else 'proposal_token'
    conn = models.get_db()
    try:
        row = conn.execute(f'SELECT * FROM chat_messages WHERE {column} = ?', (token,)).fetchone()
        if row is None:
            raise BadRequest('操作凭据无效或记录不存在')
        return dict(row)
    finally:
        conn.close()


def transition(message, expected, state, *, undo_token=None, outcome=''):
    """Atomically claim/finalize a card so two devices cannot apply it twice."""
    conn = models.get_db()
    try:
        conn.execute('BEGIN IMMEDIATE')
        updated = conn.execute(
            'UPDATE chat_messages SET state = ?, undo_token = COALESCE(?, undo_token), '
            'undo_expires = CASE WHEN ? IS NOT NULL THEN ? ELSE undo_expires END, outcome = ? '
            'WHERE id = ? AND state = ?',
            (state, undo_token, undo_token, time.time() + 1800, outcome, message['id'], expected))
        if updated.rowcount != 1:
            raise Conflict('此操作已处理或被后续消息替代，请重新加载会话')
        conn.execute('UPDATE chat_conversations SET revision = revision + 1, updated_at = ? WHERE id = ?',
                     (config.get_local_now().isoformat(), message['conversation_id']))
        conn.commit()
    finally:
        conn.close()
