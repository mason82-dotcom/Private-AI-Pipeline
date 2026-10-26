"""Local stdio MCP memory with a fixed per-process namespace and optional read-only mode.

Neither the RPC arguments nor untrusted agent text can select another namespace.
Supports legacy initialize clients (protocol version 2025-06-18). It is NOT a
complete implementation of newer MCP protocol revisions.
"""
from __future__ import annotations

import json
import os
import sys
from memdb import connect, forget, remember, search, validate_namespace

SEARCH_TOOL = {
    'name': 'memory_search',
    'description': 'Search only explicitly saved notes and imported documents in the configured local namespace.',
    'inputSchema': {'type': 'object', 'properties': {'query': {'type': 'string'}},
                    'required': ['query'], 'additionalProperties': False},
}
WRITE_TOOLS = [
    {'name': 'memory_remember', 'description': 'Store a note explicitly in the configured namespace.',
     'inputSchema': {'type': 'object', 'properties': {'name': {'type': 'string'}, 'text': {'type': 'string'}},
                     'required': ['name', 'text'], 'additionalProperties': False}},
    {'name': 'memory_forget', 'description': 'Forget one note in the configured namespace.',
     'inputSchema': {'type': 'object', 'properties': {'name': {'type': 'string'}},
                     'required': ['name'], 'additionalProperties': False}},
]


def dispatch(message, db_path=None, namespace=None, readonly=None):
    namespace = validate_namespace(namespace if namespace is not None else os.getenv('MEMORY_NAMESPACE', 'personal'))
    readonly = (os.getenv('MCP_READONLY', 'true').lower() == 'true') if readonly is None else readonly
    method = message.get('method')
    params = message.get('params', {}) or {}
    if method == 'initialize':
        return {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}},
                'serverInfo': {'name': 'private-ai-memory', 'version': '0.2.0'}}
    if method == 'ping':
        return {}
    if method == 'tools/list':
        return {'tools': [SEARCH_TOOL] + ([] if readonly else WRITE_TOOLS)}
    if method == 'tools/call':
        name = params.get('name') if isinstance(params, dict) else None
        args = params.get('arguments', {}) if isinstance(params, dict) else None
        if not isinstance(args, dict):
            raise ValueError('Argumente müssen ein JSON-Objekt sein')
        if name == 'memory_search':
            if set(args) != {'query'} or not isinstance(args.get('query'), str) or len(args['query']) > 1000:
                raise ValueError('Ungültige Suchanfrage')
            with connect(db_path) as db:
                content = json.dumps(search(db, args['query'], 8, namespace), ensure_ascii=False)
        elif name in ('memory_remember', 'memory_forget'):
            if readonly:
                raise PermissionError('Nur-Lese-Modus; Schreiben ist gesperrt')
            if set(args) != ({'name', 'text'} if name == 'memory_remember' else {'name'}):
                raise ValueError('Ungültige Parameter')
            memo = args['name']
            if not isinstance(memo, str) or ':' in memo or not 0 < len(memo) <= 250:
                raise ValueError('Ungültiger Notizname')
            with connect(db_path) as db:
                if name == 'memory_remember':
                    if not isinstance(args['text'], str):
                        raise ValueError('Ungültiger Notiztext')
                    remember(db, 'note:' + memo, args['text'], namespace)
                    content = 'Notiz gespeichert: ' + memo
                else:
                    content = 'Gelöscht: ' + str(forget(db, 'note:' + memo, namespace))
        else:
            raise NotImplementedError('Methode nicht unterstützt')
        return {'content': [{'type': 'text', 'text': content}]}
    raise NotImplementedError('Methode nicht unterstützt')


def main():
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if not isinstance(message, dict) or 'id' not in message:
                continue
            ident = message['id']
            if not isinstance(ident, (str, int)) and ident is not None:
                continue
            try:
                result = dispatch(message)
                out = {'jsonrpc': '2.0', 'id': ident, 'result': result}
            except (ValueError, PermissionError) as exc:
                out = {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32602, 'message': str(exc)}}
            except NotImplementedError as exc:
                out = {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': str(exc)}}
            except Exception:
                out = {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32603, 'message': 'Interner Fehler'}}
            print(json.dumps(out, ensure_ascii=False), flush=True)
        except (ValueError, UnicodeError):
            continue


if __name__ == '__main__':
    main()
