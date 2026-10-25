"""P1 diagnostics and P2 knowledge integration; all network is loopback with fake Ollama."""
import http.cookiejar
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'gateway'))
sys.path.insert(0,str(ROOT/'console'))
from gateway import Server as GatewayServer
from server import Server as ConsoleServer,hash_password
from memdb import connect,remember
from knowledge import add_document,list_documents,list_memories,find_documents

TOKEN='x'*64
KNOW='k'*64

class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.path!='/v1/models':return self.send_error(404)
        payload={'object':'list','data':[{'id':'qwen3:1.7b'}]}
        raw=json.dumps(payload).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
        self.end_headers();self.wfile.write(raw)

class TestKnowledgeFunctions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=connect(str(Path(self.tmp.name)/'memory.sqlite'))
        self.addCleanup(self.db.close)

    def test_upload_idempotent_and_isolated(self):
        a=add_document(self.db,'team-a','plan.md','Geheime Alpha Richtlinien')
        self.assertFalse(a['duplicate'])
        self.assertTrue(add_document(self.db,'team-a','plan.md','Geheime Alpha Richtlinien')['duplicate'])
        self.assertEqual(len(list_documents(self.db,'team-a')),1)
        self.assertEqual(list_documents(self.db,'team-b'),[])
        self.assertEqual(len(find_documents(self.db,'team-a','Alpha')),1)
        self.assertEqual(find_documents(self.db,'team-b','Alpha'),[])
        b=add_document(self.db,'team-b','plan.md','Geheime Alpha Richtlinien')
        self.assertEqual(a['document_id'],b['document_id'])
        self.assertEqual(len(list_documents(self.db,'team-b')),1)

    def test_memory_not_mixed_with_documents(self):
        remember(self.db,'user:pref','Lieber kompakte Anzeigen','team-a')
        add_document(self.db,'team-a','test.txt','kompakte Entwickleranzeige')
        self.assertEqual(len(list_memories(self.db,'team-a')),1)
        self.assertEqual(len(list_memories(self.db,'team-b')),0)
        self.assertEqual(len(find_documents(self.db,'team-a','Entwickleranzeige')),1)
        self.assertEqual(find_documents(self.db,'team-a','Lieber'),[])

    def test_reject_paths_executables_and_empty_large_content(self):
        for filename in ('../etc/passwd','.env','exploit.py','foo/file.md','foo\\bar.txt'):
            with self.subTest(filename=filename),self.assertRaises(ValueError):
                add_document(self.db,'a',filename,'hello')
        for content in ('',' \n', 'x'*(48*1024+1),'abc\x00def'):
            with self.subTest(content_len=len(content)),self.assertRaises(ValueError):
                add_document(self.db,'a','test.txt',content)

    def test_deduplicate_even_when_filename_differs(self):
        add_document(self.db,'a','version1.md','identischer Inhalt')
        x=add_document(self.db,'a','version2.md','identischer Inhalt')
        self.assertEqual(x['filename'],'version1.md')
        self.assertTrue(x['duplicate'])

class TestKnowledgeHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        db=str(Path(self.tmp.name)/'memory.sqlite')
        with connect(db) as database:
            remember(database,'user:note','Nur privat und intern','project-alpha')
            remember(database,'user:secret','Gesondertes Beta Geheimnis','project-beta')
        self.ollama=ThreadingHTTPServer(('127.0.0.1',0),FakeOllama)
        self.gateway=GatewayServer(('127.0.0.1',0),f'http://127.0.0.1:{self.ollama.server_port}',TOKEN,db,False,
                                   knowledge_token=KNOW,knowledge_namespace='project-alpha',import_enabled=True)
        self.console=ConsoleServer(('127.0.0.1',0),f'http://127.0.0.1:{self.gateway.server_port}',TOKEN,
                                   hash_password('long-passphrase-example'),knowledge_token=KNOW,import_enabled=True)
        for srv in (self.ollama,self.gateway,self.console):
            threading.Thread(target=srv.serve_forever,daemon=True).start()
        self.addCleanup(self.close)
        self.cookies=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.base=f'http://127.0.0.1:{self.console.server_port}'
        self.gate=f'http://127.0.0.1:{self.gateway.server_port}'
        self.csrf=None

    def close(self):
        for srv in (self.console,self.gateway,self.ollama):
            srv.shutdown();srv.server_close()

    def request(self,path,body=None,auth=False,token=None,csrf=False):
        base=self.gate if token else self.base
        hdr={'Content-Type':'application/json','Origin':base}
        if token:hdr['Authorization']='Bearer '+token
        if csrf:hdr['X-CSRF-Token']=self.csrf or ''
        data=None if body is None else json.dumps(body).encode()
        opener=urllib.request.build_opener() if token else self.opener
        return opener.open(urllib.request.Request(base+path,data=data,headers=hdr),timeout=8)

    def login(self):
        with self.request('/api/login',{'password':'long-passphrase-example'}) as r:
            self.csrf=json.load(r)['csrf']

    def test_p1_diagnostic_separate_gateway_and_ollama(self):
        self.login()
        with self.request('/api/status') as r:
            d=json.load(r)
        self.assertEqual(d['gateway'],'ok')
        self.assertEqual(d['inference'],'ok')
        self.assertGreaterEqual(d['checks']['gateway']['latency_ms'],0)
        self.assertEqual(d['checks']['inference']['source'],'gateway /v1/models')
        self.ollama.shutdown();self.ollama.server_close()
        with self.request('/api/status') as r:
            d=json.load(r)
        self.assertEqual(d['gateway'],'ok')
        self.assertEqual(d['inference'],'unreachable')

    def test_p2_denies_unauthenticated_and_webui_gateway_token(self):
        for url in ('/api/knowledge?kind=documents','/api/knowledge?kind=memory'):
            with self.assertRaises(urllib.error.HTTPError) as c:self.request(url)
            self.assertEqual(c.exception.code,401)
        with self.assertRaises(urllib.error.HTTPError) as c:self.request('/private/knowledge?kind=memory',token=TOKEN)
        self.assertEqual(c.exception.code,403)
        with self.request('/private/knowledge?kind=memory',token=KNOW) as r:
            self.assertEqual(json.load(r)['memories'][0]['source'],'user:note')

    def test_p2_read_returns_only_server_scope(self):
        self.login()
        with self.request('/api/knowledge?kind=memory') as r: d=json.load(r)
        self.assertEqual(d['namespace'],'project-alpha')
        self.assertEqual([a['source'] for a in d['memories']],['user:note'])
        for suffix in ('&namespace=project-beta','&q=x&kind=memory'):
            with self.assertRaises(urllib.error.HTTPError) as c:
                self.request('/api/knowledge?kind=memory'+suffix)
            self.assertEqual(c.exception.code,400)

    def test_p2_import_requires_csrf_and_deduplicates(self):
        self.login()
        payload={'filename':'design.md','content':'Komponenten und Layouttokens'}
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.request('/api/documents/import',payload)
        self.assertEqual(c.exception.code,403)
        with self.request('/api/documents/import',payload,csrf=True) as r:
            d=json.load(r)
        self.assertFalse(d['duplicate'])
        with self.request('/api/documents/import',payload,csrf=True) as r:
            self.assertTrue(json.load(r)['duplicate'])
        with self.request('/api/knowledge?kind=documents') as r:docs=json.load(r)
        self.assertEqual(len(docs['documents']),1)
        with self.request('/api/knowledge?kind=search&q=Layouttokens') as r:results=json.load(r)
        self.assertEqual(len(results['results']),1)
        self.assertEqual(results['results'][0]['source'],f'upload:{d["document_id"]}#0')

    def test_p2_import_disabled_at_gateway_and_console(self):
        self.login()
        self.console.import_enabled=False
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.request('/api/documents/import',{'filename':'a.md','content':'a'},csrf=True)
        self.assertEqual(c.exception.code,403)
        self.console.import_enabled=True
        self.gateway.import_enabled=False
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.request('/api/documents/import',{'filename':'a.md','content':'a'},csrf=True)
        self.assertEqual(c.exception.code,503)

    def test_p2_import_bad_payload_and_denied_query(self):
        self.login()
        for payload in ({'filename':'a.sh','content':'echo hi'}, {'filename':'../x.md','content':'x'}, {'filename':'a.md','content':'x','scope':'project-beta'}):
            with self.assertRaises(urllib.error.HTTPError) as c:self.request('/api/documents/import',payload,csrf=True)
            self.assertEqual(c.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError) as c:self.request('/api/knowledge?kind=memory&namespace=project-beta')
        self.assertEqual(c.exception.code,400)

if __name__=='__main__':unittest.main()
