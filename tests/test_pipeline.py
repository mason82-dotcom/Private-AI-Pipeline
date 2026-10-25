import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gateway'))
from memdb import connect, remember, forget, search, ingest_directory, entries_count, validate_namespace
from gateway import Server, allowed_local_target, enriched_body
from mcp_stdio import dispatch

TOKEN = 'a' * 64


class FakeOllamaHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return
    def do_GET(self):
        if self.path == '/v1/models':
            body = json.dumps({'object': 'list', 'data': [{'id': 'qwen3:1.7b'}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)
    def do_POST(self):
        n = int(self.headers['Content-Length'])
        payload = json.loads(self.rfile.read(n))
        FakeOllamaHandler.last_payload = payload
        if payload.get('stream'):
            body = b'data: {"choices":[]}\n\ndata: [DONE]\n\n'
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = json.dumps({'choices': [{'message': {'content': 'lokal'}}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)


class Tests(unittest.TestCase):
    def test_target_restrictions(self):
        for target in ['https://api.openai.com', 'http://8.8.8.8:11434',
                       'http://user:pass@ollama:11434', 'http://ollama:11434/evil',
                       'http://169.254.169.254:80', 'http://224.0.0.1:11434']:
            with self.subTest(target=target), self.assertRaises(ValueError):
                allowed_local_target(target)
        self.assertEqual(allowed_local_target('http://ollama:11434'), 'http://ollama:11434')
        self.assertEqual(allowed_local_target('http://192.168.1.22:11434'), 'http://192.168.1.22:11434')

    def test_fts_and_ingest(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d, 'docs'); docs.mkdir()
            (docs / 'fleet.md').write_text('Die Drohne Matrice verwendet eine lokale Datenbank.')
            (docs / '.env').write_text('SECRETS=do_not_index')
            (docs / 'skip.txt').symlink_to(docs / 'fleet.md')
            with connect(str(Path(d, 'db.sqlite'))) as db:
                remember(db, 'note:pi', 'Der Pi hostet Open WebUI.')
                self.assertEqual(search(db, 'Pi WebUI')[0]['source'], 'note:pi')
                self.assertEqual(ingest_directory(db, str(docs))['files'], 1)
                self.assertIn('Matrice', search(db, 'Matrice')[0]['body'])
                self.assertEqual(search(db, 'do_not_index'), [])
                self.assertEqual(ingest_directory(db, str(docs))['files'], 1)
                self.assertEqual(db.execute('SELECT count(*) FROM entries_v2').fetchone()[0], 2)
                self.assertEqual(forget(db, 'note:pi'), 1)
                (docs / 'fleet.md').unlink()
                self.assertEqual(ingest_directory(db, str(docs))['chunks'], 0)
                self.assertEqual(search(db, 'Matrice'), [])

    def test_mcp_memory(self):
        with tempfile.TemporaryDirectory() as d:
            dbpath = str(Path(d, 'data.db'))
            self.assertEqual(dispatch({'method': 'initialize'})['serverInfo']['name'], 'private-ai-memory')
            self.assertEqual(len(dispatch({'method': 'tools/list'}, dbpath)['tools']), 1)
            self.assertEqual(len(dispatch({'method': 'tools/list'}, dbpath, readonly=False)['tools']), 3)
            dispatch({'method': 'tools/call', 'params': {'name': 'memory_remember', 'arguments': {'name': 'station', 'text': 'Die Station hat einen Pi.'}}}, dbpath, readonly=False)
            found = dispatch({'method': 'tools/call', 'params': {'name': 'memory_search', 'arguments': {'query': 'Station'}}}, dbpath)
            self.assertIn('note:station', found['content'][0]['text'])
            dispatch({'method': 'tools/call', 'params': {'name': 'memory_forget', 'arguments': {'name': 'station'}}}, dbpath, readonly=False)
            self.assertEqual(dispatch({'method': 'tools/call', 'params': {'name': 'memory_search', 'arguments': {'query': 'Station'}}}, dbpath)['content'][0]['text'], '[]')

    def test_enrichment(self):
        with tempfile.TemporaryDirectory() as d:
            dbpath = str(Path(d, 'data.db'))
            with connect(dbpath) as db:
                remember(db, 'note:local', 'Der Modellserver ist offline verfügbar.', 'webui')
            body = json.dumps({'messages': [{'role': 'user', 'content': 'Wo ist der Modellserver?'}]}).encode()
            result = json.loads(enriched_body(body, dbpath, True))
            self.assertEqual(result['messages'][0]['role'], 'system')
            self.assertIn('note:local', result['messages'][0]['content'])
            self.assertEqual(enriched_body(body, dbpath, False), body)

    def test_http_proxy_nonstream_and_stream(self):
        with tempfile.TemporaryDirectory() as d:
            upstream = ThreadingHTTPServer(('127.0.0.1', 0), FakeOllamaHandler)
            threading.Thread(target=upstream.serve_forever, daemon=True).start()
            gateway = Server(('127.0.0.1', 0), f'http://127.0.0.1:{upstream.server_port}', TOKEN, str(Path(d, 'db')), False)
            threading.Thread(target=gateway.serve_forever, daemon=True).start()
            base = f'http://127.0.0.1:{gateway.server_port}'
            try:
                self.assertEqual(json.load(urllib.request.urlopen(base + '/health'))['status'], 'ok')
                with self.assertRaises(urllib.error.HTTPError) as bad:
                    urllib.request.urlopen(base + '/v1/models')
                self.assertEqual(bad.exception.code, 401)
                self.assertEqual(json.load(urllib.request.urlopen(urllib.request.Request(base + '/v1/models', headers={'Authorization': 'Bearer ' + TOKEN})))['data'][0]['id'], 'qwen3:1.7b')
                for stream in (False, True):
                    body = json.dumps({'model': 'qwen3:1.7b', 'stream': stream, 'messages': [{'role': 'user', 'content': 'Hallo'}]}).encode()
                    req = urllib.request.Request(base + '/v1/chat/completions', data=body, headers={'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        data = response.read()
                        self.assertIn(b'choices', data)
                        if stream:
                            self.assertIn(b'[DONE]', data)
            finally:
                gateway.shutdown(); upstream.shutdown()
                gateway.server_close(); upstream.server_close()


if __name__ == '__main__':
    unittest.main()
