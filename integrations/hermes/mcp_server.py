#!/usr/bin/env python3
"""Minimal MCP stdio bridge, Python 3.11+, with a fixed backend and two domain tools.

No shell execution, policy mutation, arbitrary SQL or caller-selected URLs.
The Java AgentHarness owns classification and model tool execution.
"""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

BASE = os.environ.get("TRIAGEM_URL", "http://127.0.0.1:8080").rstrip("/")
TOKEN = os.environ.get("WEBHOOK_TOKEN", "")
parsed = urlparse(BASE)
if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
    raise SystemExit("TRIAGEM_URL exige HTTPS ou loopback")
if parsed.username or parsed.password or parsed.query or parsed.fragment:
    raise SystemExit("TRIAGEM_URL não pode conter credenciais, query ou fragmento")

EVENT_FIELDS = ["source", "eventId", "ticketId", "customerId", "customerName", "whatsapp", "message", "occurredAt"]
TOOLS = [
    {"name": "receive_support_event", "description": "Registra evento de teste com nome, WhatsApp E.164 e mensagem. Use IDs e horário reais do transporte, estáveis nas repetições. Não inicia triagem.",
     "inputSchema": {"type": "object", "properties": {k: {"type": "string", "minLength": 1} for k in EVENT_FIELDS}, "required": EVENT_FIELDS, "additionalProperties": False}},
    {"name": "get_support_ticket", "description": "Consulta estado e histórico do chamado de teste pelo ID interno retornado no recebimento.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string", "minLength": 1, "maxLength": 36}}, "required": ["id"], "additionalProperties": False}},
]

def call_tool(name, args):
    if not isinstance(args, dict):
        raise ValueError("Argumentos devem ser um objeto")
    if name == "receive_support_event":
        if set(args) != set(EVENT_FIELDS) or any(not isinstance(v, str) or not v.strip() for v in args.values()):
            raise ValueError("Informe exatamente os campos obrigatórios do evento")
        data = json.dumps(args, ensure_ascii=False).encode()
        if len(data) > 65536:
            raise ValueError("Evento excede o limite de tamanho")
        headers = {"Content-Type": "application/json"}
        if TOKEN:
            headers["Authorization"] = "Bearer " + TOKEN
        request = Request(BASE + "/api/events", data=data, headers=headers, method="POST")
    elif name == "get_support_ticket":
        if set(args) != {"id"} or not isinstance(args["id"], str) or not 1 <= len(args["id"]) <= 36:
            raise ValueError("ID inválido")
        request = Request(BASE + "/api/tickets/" + quote(args["id"], safe=""))
    else:
        raise ValueError("Ferramenta não permitida")
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read(250000)), False
    except HTTPError as e:
        # Conflict has been safely recorded by Java and is not an invitation to invent new IDs.
        if e.code == 409:
            return json.loads(e.read(65536)), False
        return {"error": "Backend recusou a solicitação", "httpStatus": e.code}, True
    except (URLError, TimeoutError):
        return {"error": "Backend não confirmou a solicitação; consulte o estado e preserve os IDs antes de repetir."}, True

def dispatch(message):
    method = message.get("method")
    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "kipper-triagem", "version": "1.0.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        params = message.get("params", {})
        try:
            result, error = call_tool(params.get("name"), params.get("arguments", {}))
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": error}
        except (ValueError, TypeError, json.JSONDecodeError):
            return {"content": [{"type": "text", "text": "Ferramenta ou argumentos inválidos"}], "isError": True}
    raise ValueError("Método não suportado")

def main():
    for line in sys.stdin:
        message = None
        try:
            if len(line) > 100000:
                raise ValueError("Mensagem excede o limite")
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("Mensagem inválida")
            if "id" not in message:
                continue
            result = {"jsonrpc": "2.0", "id": message["id"], "result": dispatch(message)}
        except Exception:
            result = {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None,
                      "error": {"code": -32600, "message": "Requisição MCP inválida ou não suportada"}}
        print(json.dumps(result, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
