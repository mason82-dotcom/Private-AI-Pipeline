"""P2.2 regression: opt-in embeddings and source-scoped cosine search (fake Ollama)."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'gateway'))
sys.path.insert(0,str(ROOT/'tests'))
from memdb import connect,remember
from knowledge import add_document,add_pdf_pages
from semantic import (normalized,encode,decode,pending_index,semantic_search,
                      EmbedUnavailable,OllamaEmbedder)
import test_p1_p2_knowledge as base

class FakeVectors:
    model='nomic-embed-text:latest'
    def __call__(self,text):
        val=[0.0]*64
        val[0 if 'maschinen' in text.lower() else 1]=1.0
        return normalized(val)

class TestVectors(unittest.TestCase):
    def test_index_search_isolation_pdf_and_mutation(self):
        with tempfile.TemporaryDirectory() as td,connect(str(Path(td)/'db.sqlite')) as db:
            add_document(db,'team-a','machines.txt','Die Maschinen benötigen einen Motor')
            add_document(db,'team-a','weather.txt','Das Wetter wird sonnig')
            add_document(db,'team-b','secret.txt','Geheime Maschinenpläne')
            remember(db,'user:private','maschinen vertraulich','team-a')
            add_pdf_pages(db,'team-a','manual.pdf',b'%PDF-1.4\nmock content',
                          [{'page':2,'text':'Maschinen auf Seite zwei'}])
            fake=FakeVectors()
            self.assertEqual(pending_index(db,'team-a',fake,limit=1)['indexed'],1)
            self.assertEqual(pending_index(db,'team-a',fake,limit=8)['indexed'],2)
            self.assertEqual(pending_index(db,'team-a',fake,limit=8)['indexed'],0)
            hits=semantic_search(db,'team-a','maschinen',fake)
            self.assertEqual(len(hits),3)
            self.assertTrue(any(h['source'].startswith('pdf:') for h in hits))
            self.assertEqual(semantic_search(db,'team-b','maschinen',fake),[])
            self.assertFalse(any('private' in h['source'] for h in hits))
            source=hits[0]['source']
            db.execute('UPDATE entries_v2 SET body=? WHERE namespace=? AND source=?',
                       ('Text verändert','team-a',source));db.commit()
            self.assertNotIn(source,{h['source'] for h in semantic_search(db,'team-a','maschinen',fake)})
            self.assertEqual(pending_index(db,'team-a',fake,limit=4)['indexed'],1)

    def test_invalid_vectors_and_model_denied(self):
        for vec in ([],[0.0]*64,[float('nan')]*64,[float('inf')]*64,[1.0]*30):
            with self.assertRaises(EmbedUnavailable):normalized(vec)
        self.assertIsNone(decode(b'bad',64))
        self.assertEqual(len(decode(encode(normalized([1.0]*64)),64)),64)
        with self.assertRaises(ValueError):
            OllamaEmbedder('http://127.0.0.1:11434','unauthorized-model')

class FakeOllamaEmbeddings(base.FakeOllama):
    def do_POST(self):
        if self.path!='/api/embed':
            self.send_error(404);return
        size=int(self.headers['Content-Length'])
        req=json.loads(self.rfile.read(size))
        if req['model']!='nomic-embed-text:latest':
            self.send_error(400);return
        raw=json.dumps({'embeddings':[list(FakeVectors()(req['input']))]}).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

class TestSemanticHTTP(unittest.TestCase):
    close=base.TestKnowledgeHTTP.close
    request=base.TestKnowledgeHTTP.request
    login=base.TestKnowledgeHTTP.login

    def setUp(self):
        base.TestKnowledgeHTTP.setUp(self)
        self.ollama.RequestHandlerClass=FakeOllamaEmbeddings
        self.gateway.semantic_enabled=True
        self.gateway.semantic_model='nomic-embed-text:latest'
        with connect(self.gateway.memory_db) as db:
            add_document(db,'project-alpha','motor.txt','Maschinen haben einen Motor')
            pending_index(db,'project-alpha',FakeVectors(),limit=4)

    def test_console_auth_scope_and_disabled_search(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/knowledge?kind=semantic&q=maschinen')
        self.assertEqual(error.exception.code,401)
        self.login()
        with self.request('/api/knowledge?kind=semantic&q=maschinen') as r:
            data=json.load(r)
        self.assertEqual(data['search_mode'],'semantic')
        self.assertEqual(data['embedding_model'],'nomic-embed-text:latest')
        self.assertTrue(data['results'][0]['source'].startswith('upload:'))
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/private/knowledge?kind=semantic&q=maschinen',token='x'*64)
        self.assertEqual(error.exception.code,403)
        self.gateway.semantic_enabled=False
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/knowledge?kind=semantic&q=maschinen')
        self.assertEqual(error.exception.code,403)

if __name__=='__main__':unittest.main()
