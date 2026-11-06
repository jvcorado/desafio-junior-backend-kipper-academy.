"""Transport-bound reception. The model cannot supply event ids or timestamps."""
import hashlib
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PROFILE = Path('/opt/data/profiles/kipper-triagem')
STATE = PROFILE / 'kipper-support.sqlite'
SECRET = PROFILE / 'kipper-ingress.json'


def transport():
    from gateway.session_context import get_session_env
    values = {k: get_session_env('HERMES_SESSION_' + k.upper()) for k in
              ('platform', 'profile', 'chat_id', 'user_id', 'message_id')}
    if values['platform'] != 'whatsapp' or values['profile'] != 'kipper-triagem':
        raise ValueError('Esta ferramenta exige a conversa WhatsApp do perfil kipper-triagem')
    if not all(values.values()):
        raise ValueError('Identidade de transporte incompleta; não foi criado evento')
    allowed = json.loads(SECRET.read_text())['chat_id']
    if values['chat_id'] != allowed:
        raise ValueError('Conversa não habilitada para esta integração')
    return values


def connect():
    db = sqlite3.connect(STATE, timeout=10)
    STATE.chmod(0o600)
    db.execute('CREATE TABLE IF NOT EXISTS inbound (chat TEXT, sender TEXT, message_id TEXT, body TEXT, observed TEXT, seen REAL, PRIMARY KEY(chat,sender,message_id))')
    db.execute('CREATE TABLE IF NOT EXISTS submitted (chat TEXT,sender TEXT,ticket TEXT UNIQUE, PRIMARY KEY(chat,sender,ticket))')
    return db


def observe(user_message='', **kwargs):
    try:
        origin = transport()
        if not isinstance(user_message, str) or not user_message.strip():
            return
        with connect() as db:
            db.execute('INSERT OR IGNORE INTO inbound VALUES (?,?,?,?,?,?)', (
                origin['chat_id'], origin['user_id'], origin['message_id'], user_message[:24000],
                datetime.now(timezone.utc).isoformat(), time.time()))
    except Exception:
        return  # Tool fails closed when transport capture is unavailable.


def digest(*values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def event_from_messages(args, origin, rows):
    name, phone, message = (args.get(k, '').strip() for k in ('customerName', 'whatsapp', 'message'))
    if not name or len(name) > 120 or not re.fullmatch(r'\+[1-9][0-9]{7,14}', phone) or not message or len(message) > 12000:
        raise ValueError('Peça nome, WhatsApp E.164 e mensagem original')
    # All three fields must be literal text actually received from this same sender/chat.
    if not all(any(value in row['body'] for row in rows) for value in (name, phone, message)):
        raise ValueError('Os dados precisam constar literalmente nas mensagens recebidas; não invente')
    original = next(row for row in rows if message in row['body'])
    identity = digest(origin['chat_id'], origin['user_id'], original['message_id'])
    return dict(source='whatsapp-kipper', eventId='wa-' + identity, ticketId='wa-' + identity,
                customerId='wa-' + digest(origin['user_id']), customerName=name, whatsapp=phone,
                message=message, occurredAt=original['observed'])


def api(method, path, data=None):
    config = json.loads(SECRET.read_text())
    body = json.dumps(data).encode() if data is not None else None
    request = Request(config['url'] + path, data=body, method=method, headers={
        'Authorization': 'Bearer ' + config['key'], 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=350) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def register_ticket(args, **kwargs):
    try:
        origin = transport()
        with connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute('SELECT * FROM inbound WHERE chat=? AND sender=? AND seen>? ORDER BY seen DESC LIMIT 20',
                (origin['chat_id'], origin['user_id'], time.time()-86400)).fetchall()
        event = event_from_messages(args, origin, rows)
        status, receipt = api('POST', '/api/events', event)
        if status not in (200, 201):
            return json.dumps({'httpStatus': status, 'receipt': receipt})
        ticket_id = receipt['ticketId']
        with connect() as db:
            db.execute('INSERT OR IGNORE INTO submitted VALUES (?,?,?)', (origin['chat_id'], origin['user_id'], ticket_id))
        _, detail = api('GET', '/api/tickets/' + ticket_id)
        if detail['ticket']['status'] == 'RECEIVED':
            api('POST', '/api/tickets/' + ticket_id + '/process', {})
        _, detail = api('GET', '/api/tickets/' + ticket_id)
        return json.dumps({'receipt': receipt, 'ticket': detail['ticket']}, ensure_ascii=False)
    except ValueError as error:
        return json.dumps({'error': str(error)}, ensure_ascii=False)
    except Exception:
        return json.dumps({'error': 'Integração inconclusiva; consulte o chamado antes de repetir. Não confirme encaminhamento.'})


def check_ticket(args, **kwargs):
    try:
        origin = transport()
        ticket = args.get('ticketId', '')
        with connect() as db:
            found = db.execute('SELECT 1 FROM submitted WHERE chat=? AND sender=? AND ticket=?',
                (origin['chat_id'], origin['user_id'], ticket)).fetchone()
        if not found:
            raise ValueError('Chamado não pertence ao atendimento atual')
        status, detail = api('GET', '/api/tickets/' + ticket)
        return json.dumps({'httpStatus': status, 'ticket': detail.get('ticket')}, ensure_ascii=False)
    except Exception:
        return json.dumps({'error': 'Consulta indisponível para este atendimento'})


def register(ctx):
    ctx.register_hook('pre_llm_call', observe)
    ctx.register_tool(name='register_support_ticket', toolset='kipper_support', handler=register_ticket, schema={
        'name': 'register_support_ticket',
        'description': 'Registra mensagem original recebida no WhatsApp, executa triagem Java com IA real e consulta o estado confirmado do Kanban. IDs e horário são obtidos do transporte, nunca fornecidos pelo modelo. Exige os três dados literais recebidos do cliente.',
        'parameters': {'type': 'object', 'properties': {k: {'type': 'string'} for k in ('customerName','whatsapp','message')},
                       'required': ['customerName','whatsapp','message'], 'additionalProperties': False}})
    ctx.register_tool(name='check_support_ticket', toolset='kipper_support', handler=check_ticket, schema={
        'name': 'check_support_ticket', 'description': 'Consulta somente chamado registrado nesta conversa e por este remetente.',
        'parameters': {'type': 'object', 'properties': {'ticketId': {'type': 'string'}},
                       'required': ['ticketId'], 'additionalProperties': False}})
