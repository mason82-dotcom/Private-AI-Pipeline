#!/usr/bin/env python3
"""Opt-in Pi P2.3 FTS5 RAG smoke; transient HTTP servers, database and credentials.

No Docker, .env, persistent files, external downloads or modification of Ollama
model inventory. Runs one local qwen3:0.6b inference after safety preflight.
"""
from __future__ import annotations

import http.cookiejar
import json
import secrets
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'gateway'))
sys.path.insert(0, str(ROOT / 'console'))
from gateway import Server as GatewayServer  # noqa: E402
from server import Server as ConsoleServer, hash_password  # noqa: E402
from memdb import connect, remember  # noqa: E402
from knowledge import add_document, add_pdf_pages  # noqa: E402
from pdf_extract import extract_pdf  # noqa: E402
from pypdf import PdfWriter  # noqa: E402
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject  # noqa: E402

OLLAMA = 'http://127.0.0.1:11434'
MODEL = 'qwen3:0.6b'
MIN_AVAILABLE_KIB = 1_500_000
MAX_STREAM_BYTES = 256 * 1024


def no_proxy_opener(*handlers):
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), *handlers)


def ollama_json(path):
    with no_proxy_opener().open(OLLAMA + path, timeout=5) as response:
        return json.load(response)


def meminfo():
    values = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, _, raw = line.partition(':')
        values[key] = int(raw.strip().split()[0])
    return values


def preflight():
    before = meminfo()
    available = before['MemAvailable']
    print(f'Pi-RAM vor Test: {available/1048576:.2f} GiB verfügbar; '
          f'Swap benutzt: {(before["SwapTotal"]-before["SwapFree"])/1048576:.2f} GiB')
    if available < MIN_AVAILABLE_KIB:
        raise RuntimeError('Weniger als 1,43 GiB RAM verfügbar: Modelltest aus Sicherheitsgründen abgebrochen')
    installed = ollama_json('/api/tags').get('models', [])
    if MODEL not in {m.get('name') for m in installed if isinstance(m, dict)}:
        raise RuntimeError(f'Modell {MODEL} nicht installiert; kein automatischer Download')
    loaded = ollama_json('/api/ps').get('models', [])
    other = [m.get('name') for m in loaded if m.get('name') != MODEL]
    if other:
        raise RuntimeError('Andere Modelle geladen; Abbruch ohne Modell-Entladen: '+', '.join(str(x) for x in other))
    print('Modell vorhanden, keine konkurrierenden geladenen Modelle')
    return before


def make_two_page_pdf():
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica')}))
    for text in ('Werkzeugkasten enthaelt Schraubenschluessel.',
                 'Die Hydraulikpumpe erzeugt Druckoel fuer die Baggerzylinder.'):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 72 700 Td ({text}) Tj ET'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def request(opener, base, path, body=None, csrf=None, timeout=205):
    headers = {'Accept': 'application/json, text/event-stream',
               'Content-Type': 'application/json', 'Origin': base}
    if csrf:
        headers['X-CSRF-Token'] = csrf
    raw = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(base + path, raw, headers, method='POST' if raw else 'GET')
    return opener.open(req, timeout=timeout)


def parse_stream(response):
    if response.headers.get_content_type() != 'text/event-stream':
        raise RuntimeError('Console antwortete nicht mit text/event-stream')
    seen = []
    total = 0
    while True:
        line = response.readline(65537)
        if not line:
            break
        total += len(line)
        if len(line) > 65536 or total > MAX_STREAM_BYTES:
            raise RuntimeError('SSE überschreitet Testlimit')
        seen.append(line.decode('utf-8'))
        if line.strip() == b'data: [DONE]':
            break
    raw = ''.join(seen)
    if 'data: [DONE]' not in raw:
        raise RuntimeError('SSE ohne gültigen Abschluss [DONE]')
    sources = None
    delta = []
    for evt in raw.replace('\r\n', '\n').split('\n\n'):
        if evt.startswith('event: rag_sources\n'):
            data = next((x[5:].strip() for x in evt.split('\n') if x.startswith('data:')), None)
            if data is None:
                raise RuntimeError('SSE-Quellen ohne Daten')
            sources = json.loads(data).get('sources')
        elif evt.startswith('data: '):
            payload = evt[6:].strip()
            if payload and payload != '[DONE]':
                obj = json.loads(payload)
                part = obj.get('choices', [{}])[0].get('delta', {}).get('content')
                if isinstance(part, str):
                    delta.append(part)
    return sources, ''.join(delta)


def assess_fixture_answer(answer, sources):
    """Fixture-specific quality check; NOT a general factuality verifier."""
    import unicodedata
    folded=unicodedata.normalize('NFKD',answer.lower())
    folded=''.join(c for c in folded if not unicodedata.combining(c))
    cited=any('['+s['id']+']' in answer for s in sources
              if isinstance(s,dict) and s.get('id')=='Q1')
    fact=('druck' in folded and 'zylinder' in folded)
    refusal=('keine antwort' in folded or 'nicht beantwortbar' in folded)
    return {'citation_present':cited,'fixture_fact_present':fact,'unsupported_refusal':refusal,
            'quality_pass':bool(cited and fact and not refusal)}


def main():
    start = time.monotonic()
    preflight()
    with tempfile.TemporaryDirectory(prefix='pai-p23-real-smoke-') as tmp:
        dbpath = str(Path(tmp) / 'knowledge.sqlite3')
        with connect(dbpath) as db:
            add_document(db, 'hardwaretest', 'werkstatt.txt',
                         'In der Werkstatt werden Schrauben und Muttern gelagert.')
            pdf = make_two_page_pdf()
            pages = extract_pdf(pdf)
            assert [p['page'] for p in pages] == [1, 2]
            add_pdf_pages(db, 'hardwaretest', 'rag-hardwaretest.pdf', pdf, pages)
            remember(db, 'user:never-source', 'NICHT_FREIGEBEN_MEMORY', 'hardwaretest')
            add_document(db, 'other-namespace', 'unavailable.txt',
                         'Hydraulikpumpe NICHT_FREIGEBEN_NAMENSRAUM')
        token = secrets.token_hex(32)
        knowledge_token = secrets.token_hex(32)
        password = secrets.token_urlsafe(24)
        gateway = GatewayServer(('127.0.0.1', 0), OLLAMA, token, dbpath, False,
                                knowledge_token=knowledge_token, knowledge_namespace='hardwaretest',
                                import_enabled=False, semantic_enabled=False)
        console = None
        workers = []
        try:
            console = ConsoleServer(('127.0.0.1', 0),
                                    f'http://127.0.0.1:{gateway.server_port}', token,
                                    hash_password(password), knowledge_token=knowledge_token,
                                    import_enabled=False, rag_enabled=True)
            for server in (gateway, console):
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                workers.append(worker)
            base = f'http://127.0.0.1:{console.server_port}'
            opener = no_proxy_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            with request(opener, base, '/api/login', {'password': password}, timeout=8) as r:
                csrf = json.load(r)['csrf']
            with request(opener, base, '/api/rag-config', timeout=8) as r:
                assert json.load(r)['enabled'] is True
            payload = {'model': MODEL, 'messages': [{'role': 'user', 'content':
                       'Welche Aufgabe hat die Hydraulikpumpe beim Bagger?'}],
                       'rag': True, 'rag_mode': 'fts'}
            try:
                with request(opener, base, '/api/chat', payload, timeout=8):
                    pass
            except urllib.error.HTTPError as e:
                assert e.code == 403, f'CSRF-Schutz fehlgeschlagen: HTTP {e.code}'
            else:
                raise RuntimeError('Anfrage ohne CSRF wurde angenommen')
            try:
                no_hit = dict(payload, messages=[{'role':'user','content':'nirgendwoerwaehnterbegriffx98765'}])
                with request(opener, base, '/api/chat', no_hit, csrf=csrf, timeout=8):
                    pass
            except urllib.error.HTTPError as e:
                assert e.code == 409, f'Fail-Closed ohne Fundstelle fehlgeschlagen: HTTP {e.code}'
            else:
                raise RuntimeError('RAG ohne Fundstelle wurde angenommen')
            probe_at = time.monotonic()
            with request(opener, base, '/api/chat', payload, csrf=csrf) as r:
                sources, answer = parse_stream(r)
            elapsed = time.monotonic() - probe_at
            assert isinstance(sources, list) and 1 <= len(sources) <= 3
            assert sources[0].get('filename') == 'rag-hardwaretest.pdf', sources
            assert sources[0].get('page') == 2, sources
            assert 'NICHT_FREIGEBEN_' not in json.dumps(sources, ensure_ascii=False)
            assert answer.strip(), 'Lokales Modell hat keine sichtbaren Antwort-Tokens geliefert'
            print(f'Quellennachweis: {sources[0]["filename"]}, Seite {sources[0]["page"]}, '
                  f'{sources[0]["id"]} (Quellen-ID, nicht automatisch verifiziert)')
            print(f'LLM-SSE vollständig; Token-Text {len(answer)} Zeichen; Antwortzeit {elapsed:.1f} s')
            print('Modellantwort (gekürzt):', answer[:450].replace('\n', ' '))
            quality=assess_fixture_answer(answer,sources)
            print('Quellenzitat im Modelltext:', quality['citation_present'])
            print('P2.3 REAL LOCAL FTS5 RAG TRANSPORT: PASS')
            print('P2.3 FIXTURE ANSWER QUALITY:', 'PASS' if quality['quality_pass'] else 'FAIL')
            if not quality['quality_pass']:
                print('Qualitaetsdetails:', json.dumps(quality, ensure_ascii=False))
                raise RuntimeError('Quellenbelegte inhaltliche Antwort fehlt; Transport war erfolgreich')
        finally:
            for server in (console, gateway):
                if server:
                    server.shutdown()
                    server.server_close()
            for worker in workers:
                worker.join(timeout=3)
    after = meminfo()
    print(f'RAM nach Test: {after["MemAvailable"]/1048576:.2f} GiB verfügbar; '
          f'Swap benutzt: {(after["SwapTotal"]-after["SwapFree"])/1048576:.2f} GiB')
    print(f'Gesamtdauer: {time.monotonic()-start:.1f} s')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'P2.3 LIVE SMOKE: FAIL ({type(exc).__name__}): {exc}', file=sys.stderr)
        raise SystemExit(1)
