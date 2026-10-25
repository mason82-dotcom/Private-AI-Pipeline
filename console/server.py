"""Private AI Light Console: authenticated, same-origin, read-mostly BFF.

Only the console server knows PIPELINE_TOKEN. The browser never receives it.
No external dependencies or cloud fallback. Default session state is RAM-only.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
import hmac
import http.client
import ipaddress
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY = 64 * 1024
SESSION_TTL = 8 * 3600
MODEL_RE = re.compile(r"^(?!.*://)(?!.*//)[A-Za-z0-9_.:/-]{1,128}$")
FILES = {'/': ('index.html', 'text/html; charset=utf-8'),
         '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
         '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
         '/login.js': ('login.js', 'text/javascript; charset=utf-8')}


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 12:
        raise ValueError('Passwort muss mindestens 12 Zeichen haben')
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return 'scrypt:' + salt.hex() + ':' + derived.hex()


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt, expected = encoded.split(':')
        if scheme != 'scrypt' or len(salt) != 32 or len(expected) != 64:
            return False
        derived = hash_password(password, bytes.fromhex(salt)).split(':')[2]
        return hmac.compare_digest(derived, expected)
    except (ValueError, MemoryError):
        return False


def check_gateway_url(value: str) -> str:
    """Only internal Compose service, loopback, or explicit RFC1918 destination."""
    url = urllib.parse.urlsplit(value)
    if (url.scheme != 'http' or url.username or url.password or url.query or url.fragment
            or url.path not in ('', '/') or not url.hostname):
        raise ValueError('Ungültiges internes Gateway-Ziel')
    host = url.hostname.lower()
    if host != 'gateway':
        try:
            addr = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError('Nur Gateway oder private IP erlaubt') from exc
        if not (addr.is_loopback or addr.is_private and not addr.is_link_local):
            raise ValueError('Gateway-Ziel muss privat sein')
    try:
        port = url.port or 8000
    except ValueError as exc:
        raise ValueError('Ungültiger Gateway-Port') from exc
    return f'http://{host}:{port}'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        return None


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'PrivateAIConsole/0.3'
    sys_version = ''

    def log_message(self, fmt, *args):
        # Do not log prompts, passwords, cookies, routes, or content.
        pass

    def headers_common(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")

    def json_response(self, status, body, cookie=None):
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.headers_common()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, path, mimetype):
        raw = (STATIC_DIR / path).read_bytes()
        self.send_response(200)
        self.headers_common()
        self.send_header('Content-Type', mimetype)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def current_session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            return None
        val = cookie.get('pai_session')
        if not val:
            return None
        with self.server.mutex:
            record = self.server.sessions.get(val.value)
            if not record or record['expires'] <= time.monotonic():
                self.server.sessions.pop(val.value, None)
                return None
            return record

    def cookie_string(self, value, expired=False):
        secure = '; Secure' if self.server.secure_cookie else ''
        return 'pai_session=' + value + '; Path=/; HttpOnly; SameSite=Strict' + secure + ('; Max-Age=0' if expired else f'; Max-Age={SESSION_TTL}')

    def valid_origin(self):
        # SameSite cookies + strict CSRF check for all state-changing operations.
        origin = self.headers.get('Origin')
        referer = self.headers.get('Referer')
        host = self.headers.get('Host', '')
        if not host or any(c in host for c in '/\\@, \r\n'):
            return False
        allowed = {f'http://{host}', f'https://{host}'}
        fetchsite = self.headers.get('Sec-Fetch-Site')
        if fetchsite not in (None, 'same-origin', 'none'):
            return False
        if origin:
            return origin in allowed
        if referer:
            return any(referer.startswith(x + '/') for x in allowed)
        # Non-browser client may omit Origin; authenticated POST still requires CSRF.
        return True

    def csrf_ok(self, session):
        return session is not None and hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), session['csrf'])

    def read_json(self):
        try:
            size = int(self.headers.get('Content-Length', '-1'))
        except ValueError as exc:
            raise ValueError('Ungültige Requestgröße') from exc
        if not 0 < size <= MAX_BODY:
            raise ValueError('Request zu groß oder leer')
        data = self.rfile.read(size)
        if len(data) != size:
            raise ValueError('Request unvollständig')
        try:
            value = json.loads(data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError('JSON ungültig') from exc
        if not isinstance(value, dict):
            raise ValueError('JSON-Objekt erwartet')
        return value

    def upstream(self, endpoint, body=None, timeout=8):
        request = urllib.request.Request(self.server.gateway_url + endpoint,
                                         data=body,
                                         headers={'Authorization': 'Bearer ' + self.server.gateway_token,
                                                  'Accept': 'application/json, text/event-stream',
                                                  'Content-Type': 'application/json'},
                                         method='POST' if body is not None else 'GET')
        return OPENER.open(request, timeout=timeout)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if self.path != path and path != '/api/knowledge':
            self.json_response(404, {'error': 'Unbekannter Pfad'})
            return
        if path == '/health':
            self.json_response(200, {'status': 'ok', 'service': 'private-ai-console'})
            return
        session = self.current_session()
        if path == '/api/session':
            self.json_response(200 if session else 401,
                               {'authenticated': bool(session), 'csrf': session['csrf'] if session else None})
            return
        if path in FILES:
            self.send_file('login.html', 'text/html; charset=utf-8') if path == '/' and not session else self.send_file(*FILES[path])
            return
        if not session:
            self.json_response(401, {'error': 'Anmeldung erforderlich'})
            return
        if path == '/api/status':
            # Checked independently: a healthy gateway does not imply a working Ollama.
            result={'console':'ok','gateway':'unreachable','inference':'not_checked',
                    'source':'gateway_health',
                    'observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    'checks':{}}
            start=time.monotonic()
            try:
                with self.upstream('/health',timeout=3) as response:
                    raw=response.read(4097)
                    health=json.loads(raw) if len(raw)<=4096 else {}
                result['gateway']='ok' if health.get('status')=='ok' else 'unknown'
            except Exception:
                result['gateway']='unreachable'
            result['checks']['gateway']={'state':result['gateway'],'source':'gateway /health',
                                         'observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                         'latency_ms':round((time.monotonic()-start)*1000)}
            if result['gateway']=='ok':
                start=time.monotonic()
                try:
                    with self.upstream('/v1/models',timeout=4) as response:
                        raw=response.read(512*1024+1)
                    if len(raw)>512*1024: raise ValueError('Modellliste zu groß')
                    data=json.loads(raw)
                    if not isinstance(data,dict) or not isinstance(data.get('data'),list):
                        raise ValueError('Modellliste ungültig')
                    result['inference']='ok' if data['data'] else 'no_models'
                except Exception:
                    result['inference']='unreachable'
                result['checks']['inference']={'state':result['inference'],
                                               'source':'gateway /v1/models',
                                               'observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                               'latency_ms':round((time.monotonic()-start)*1000)}
            self.json_response(200,result)
            return
        if path == '/api/knowledge':
            if not self.server.knowledge_token:
                self.json_response(503,{'error':'Wissens-API nicht konfiguriert'})
                return
            try:
                params=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                if set(params)-{'kind','q'} or any(len(v)!=1 for v in params.values()):
                    raise ValueError()
                kind=params.get('kind',['documents'])[0]
                q=params.get('q',[''])[0]
                if kind not in ('documents','memory','search') or len(q)>200: raise ValueError()
                query=urllib.parse.urlencode({'kind':kind,'q':q})
                with self.knowledge_upstream('GET','/private/knowledge?'+query) as response:
                    raw=response.read(128*1024+1)
                if len(raw)>128*1024: raise ValueError()
                self.json_response(200,json.loads(raw))
            except ValueError:
                self.json_response(400,{'error':'Ungültiger Wissensfilter'})
            except Exception:
                self.json_response(503,{'error':'Lokale Wissens-API nicht erreichbar'})
            return
        if path == '/api/models':
            try:
                with self.upstream('/v1/models',timeout=6) as response:
                    raw = response.read(512 * 1024 + 1)
                data = json.loads(raw) if len(raw) <= 512 * 1024 else {}
                models = [{'id': item['id']} for item in data.get('data', [])
                          if isinstance(item, dict) and isinstance(item.get('id'), str) and MODEL_RE.fullmatch(item['id'])]
                self.json_response(200, {'models': models[:128], 'source': 'gateway_model_list',
                                         'observed_at': datetime.now(timezone.utc).isoformat(timespec='seconds')})
            except Exception:
                self.json_response(503, {'error': 'Lokale Modellliste nicht erreichbar. Kein Cloud-Fallback.'})
            return
        self.json_response(404, {'error': 'Route nicht vorhanden'})

    def knowledge_upstream(self,method,endpoint,body=None):
        request=urllib.request.Request(self.server.gateway_url+endpoint,data=body,
            headers={'Authorization':'Bearer '+self.server.knowledge_token,
                     'Content-Type':'application/json','Accept':'application/json'}, method=method)
        return OPENER.open(request,timeout=8)

    def do_POST(self):
        if not self.valid_origin():
            self.json_response(403, {'error': 'Cross-Origin-Zugriff verweigert'})
            return
        path = self.path
        if path == '/api/login':
            with self.server.mutex:
                key = self.client_address[0]
                fail = self.server.failed.get(key)
                if fail and fail[0] >= 5 and time.monotonic() - fail[1] < 120:
                    self.json_response(429, {'error': 'Anmeldung vorübergehend gesperrt'})
                    return
            try:
                payload = self.read_json()
            except ValueError:
                self.json_response(400, {'error': 'Ungültige Anmeldung'})
                return
            if not isinstance(payload.get('password'), str) or not verify_password(payload['password'], self.server.password_hash):
                with self.server.mutex:
                    previous = self.server.failed.get(key, (0, time.monotonic()))
                    n = previous[0] + 1 if time.monotonic() - previous[1] < 120 else 1
                    self.server.failed[key] = (n, time.monotonic())
                self.json_response(401, {'error': 'Anmeldung fehlgeschlagen'})
                return
            sid = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            with self.server.mutex:
                self.server.failed.pop(key, None)
                self.server.sessions[sid] = {'csrf': csrf, 'expires': time.monotonic() + SESSION_TTL}
            self.json_response(200, {'authenticated': True, 'csrf': csrf}, self.cookie_string(sid))
            return
        session = self.current_session()
        if not session:
            self.json_response(401, {'error': 'Anmeldung erforderlich'})
            return
        if not self.csrf_ok(session):
            self.json_response(403, {'error': 'CSRF-Schutz: Anfrage verweigert'})
            return
        if path == '/api/logout':
            cookie = SimpleCookie()
            cookie.load(self.headers.get('Cookie', ''))
            sid = cookie.get('pai_session')
            with self.server.mutex:
                if sid:
                    self.server.sessions.pop(sid.value, None)
            self.json_response(200, {'authenticated': False}, self.cookie_string('', True))
            return
        if path == '/api/chat':
            self.proxy_chat()
            return
        if path == '/api/documents/import':
            if not self.server.knowledge_token or not self.server.import_enabled:
                self.json_response(403,{'error':'Dokumentenimport ist deaktiviert'})
                return
            try:
                data=self.read_json()
                if set(data) != {'filename','content'} or not isinstance(data['filename'],str) or not isinstance(data['content'],str):
                    raise ValueError('Ungültige Datei')
                if len(data['content'].encode('utf-8')) > 48*1024:
                    raise ValueError('Maximal 48 KiB UTF-8 erlaubt')
                raw=json.dumps(data,ensure_ascii=False).encode('utf-8')
                with self.knowledge_upstream('POST','/private/knowledge',raw) as response:
                    result=json.load(response)
                self.json_response(200,result)
            except (ValueError,UnicodeError):
                self.json_response(400,{'error':'Ungültiger UTF-8-Import'})
            except urllib.error.HTTPError as exc:
                self.json_response(400 if exc.code==400 else 503,{'error':'Import vom Wissensdienst abgelehnt'})
            except Exception:
                self.json_response(503,{'error':'Wissens-API nicht erreichbar'})
            return
        self.json_response(404, {'error': 'Schreibzugriffe sind gesperrt'})

    def proxy_chat(self):
        self._headers_sent_flag = False
        try:
            payload = self.read_json()
            model = payload.get('model')
            msgs = payload.get('messages')
            if not isinstance(model, str) or not MODEL_RE.fullmatch(model):
                raise ValueError('Modellname ungültig')
            if not isinstance(msgs, list) or not 1 <= len(msgs) <= 32:
                raise ValueError('1 bis 32 Nachrichten erforderlich')
            clean = []
            for item in msgs:
                if not isinstance(item, dict) or item.get('role') not in ('user', 'assistant'):
                    raise ValueError('Nur user/assistant-Nachrichten erlaubt')
                content = item.get('content')
                if not isinstance(content, str) or not 0 < len(content) <= 4000:
                    raise ValueError('Nachrichtenlänge ungültig')
                clean.append({'role': item['role'], 'content': content})
            raw = json.dumps({'model': model, 'messages': clean, 'stream': True}, ensure_ascii=False).encode()
        except ValueError as exc:
            self.json_response(400, {'error': str(exc)})
            return
        try:
            with self.upstream('/v1/chat/completions', raw,timeout=180) as upstream:
                if upstream.headers.get_content_type() != 'text/event-stream':
                    self.json_response(502, {'error': 'Upstream hat keinen SSE-Stream geliefert'})
                    return
                self.send_response(200)
                self.headers_common()
                self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                self.send_header('Transfer-Encoding', 'chunked')
                self.end_headers()
                self._headers_sent_flag = True
                total = 0
                try:
                    while True:
                        line = upstream.readline(64 * 1024 + 1)
                        if not line:
                            break
                        total += len(line)
                        if len(line) > 64 * 1024 or total > 8 * 1024 * 1024:
                            self.close_connection = True
                            return
                        self.wfile.write(f'{len(line):X}\r\n'.encode() + line + b'\r\n')
                        self.wfile.flush()
                    self.wfile.write(b'0\r\n\r\n')
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    self.close_connection = True
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError):
            # urllib HTTPError is a URLError subclass. Avoid prompt disclosure.
            if not self.headers_sent():
                self.json_response(503, {'error': 'Lokales Modell nicht erreichbar; kein Cloud-Fallback'})
            else:
                self.close_connection = True

    def headers_sent(self):
        # Used for upstream exceptions after streaming began.
        return getattr(self, '_headers_sent_flag', False)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, gateway_url, gateway_token, password_hash, secure_cookie=False, knowledge_token="", import_enabled=False):
        if len(gateway_token) < 32:
            raise ValueError('PIPELINE_TOKEN fehlt')
        # Validate stored hash structure even if no valid password supplied.
        parts = password_hash.split(':')
        if len(parts) != 3 or parts[0] != 'scrypt' or len(parts[1]) != 32 or len(parts[2]) != 64:
            raise ValueError('CONSOLE_PASSWORD_HASH ungültig')
        bytes.fromhex(parts[1]); bytes.fromhex(parts[2])
        self.gateway_url = check_gateway_url(gateway_url)
        self.gateway_token = gateway_token
        self.knowledge_token = knowledge_token if len(knowledge_token)>=32 else ''
        self.import_enabled = bool(import_enabled)
        self.password_hash = password_hash
        self.secure_cookie = secure_cookie
        self.sessions = {}
        self.failed = {}
        self.mutex = threading.RLock()
        super().__init__(address, Handler)


def main():
    server = Server(('0.0.0.0', 8085), os.getenv('GATEWAY_URL', 'http://gateway:8000'),
                    os.getenv('PIPELINE_TOKEN', ''), os.getenv('CONSOLE_PASSWORD_HASH', ''),
                    os.getenv('CONSOLE_SECURE_COOKIE', 'false').lower() == 'true',
                    os.getenv('KNOWLEDGE_TOKEN', ''),
                    os.getenv('KNOWLEDGE_IMPORT_ENABLED', 'false').lower() == 'true')
    server.serve_forever()


if __name__ == '__main__':
    main()
