"""Opt-in local embedding index and bounded cosine search over document chunks only.

Does not index memories, perform background downloads or inject model prompts.
Semantic search is a separate read-only capability; indexing is operator CLI only.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import sys
import urllib.error
import urllib.request
from memdb import connect, validate_namespace

MAX_INDEX_BATCH = 32
MAX_SCAN = 512
MAX_QUERY = 200
ALLOWED_MODELS = frozenset({'nomic-embed-text:latest', 'bge-m3:latest'})
DOC_FILTER = "(source GLOB 'upload:*' OR source GLOB 'doc:*' OR source GLOB 'pdf:*')"

class EmbedUnavailable(Exception):
    pass


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS semantic_vectors (
        namespace TEXT NOT NULL, source TEXT NOT NULL, model TEXT NOT NULL,
        digest TEXT NOT NULL, dimension INTEGER NOT NULL, vector BLOB NOT NULL,
        PRIMARY KEY(namespace, source, model))''')
    db.commit()


def normalized(values):
    if not isinstance(values, list) or not 32 <= len(values) <= 2048:
        raise EmbedUnavailable('Ungültige Embedding-Dimension')
    try:
        floats = [float(x) for x in values]
    except (TypeError, ValueError, OverflowError) as exc:
        raise EmbedUnavailable('Ungültiger Embedding-Wert') from exc
    if any(not math.isfinite(x) or abs(x) > 1e10 for x in floats):
        raise EmbedUnavailable('Nicht-endliches Embedding')
    norm = math.sqrt(sum(x*x for x in floats))
    if not math.isfinite(norm) or norm <= 1e-12:
        raise EmbedUnavailable('Leerer Embedding-Vektor')
    return tuple(x / norm for x in floats)


def encode(values):
    return struct.pack('<%sf' % len(values), *values)


def decode(raw, count):
    if not isinstance(raw, bytes) or not isinstance(count, int) or not 32 <= count <= 2048 or len(raw) != count*4:
        return None
    values = struct.unpack('<%sf' % count, raw)
    return values if all(math.isfinite(x) for x in values) else None


class OllamaEmbedder:
    def __init__(self, url, model='nomic-embed-text:latest', timeout=30):
        if model not in ALLOWED_MODELS:
            raise ValueError('Embedding-Modell nicht freigegeben')
        # URL is validated by Gateway allowed_local_target; never supplied by HTTP clients.
        self.base = url.rstrip('/')
        self.model = model
        self.timeout = min(max(float(timeout), 1), 90)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def __call__(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 1700:
            raise ValueError('Embedding-Eingabe ungültig')
        raw = json.dumps({'model': self.model, 'input': text, 'truncate': True,
                          'options': {'num_ctx': 1024}, 'keep_alive': '2m'}).encode('utf-8')
        req = urllib.request.Request(self.base+'/api/embed', raw,
                {'Content-Type': 'application/json', 'Accept': 'application/json'}, method='POST')
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                payload = response.read(300_001)
            if len(payload) > 300_000:
                raise EmbedUnavailable('Embedding-Antwort zu groß')
            result=json.loads(payload)
            return normalized(result['embeddings'][0])
        except (urllib.error.URLError, TimeoutError, OSError, IndexError, KeyError,
                TypeError, ValueError, json.JSONDecodeError) as exc:
            raise EmbedUnavailable('Lokales Embedding-Modell nicht erreichbar oder Antwort ungültig') from exc

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def pending_index(db, namespace, embedder, limit=8):
    """Operator-invoked batch; never index memory entries or send whole private DB."""
    namespace = validate_namespace(namespace)
    initialize(db)
    if not isinstance(limit, int) or not 1 <= limit <= MAX_INDEX_BATCH:
        raise ValueError('Index-Limit 1 bis 32')
    rows=db.execute('''SELECT e.source,e.body,v.digest FROM entries_v2 e
        LEFT JOIN semantic_vectors v ON v.namespace=e.namespace
         AND v.source=e.source AND v.model=?
        WHERE e.namespace=? AND ''' + DOC_FILTER.replace("source ", "e.source ") + ''' ORDER BY e.rowid LIMIT ?''',
        (embedder.model, namespace, MAX_SCAN)).fetchall()
    updated=[]
    for source, body, old_digest in rows:
        digest=_digest(body)
        if digest==old_digest:
            continue
        vec=normalized(list(embedder(body)))
        updated.append((namespace,source,embedder.model,digest,len(vec),encode(vec)))
        if len(updated)>=limit:
            break
    if updated:
        db.executemany('''INSERT OR REPLACE INTO semantic_vectors
            (namespace,source,model,digest,dimension,vector) VALUES(?,?,?,?,?,?)''',updated)
        db.commit()
    return {'indexed':len(updated), 'examined':len(rows), 'model':embedder.model,
            'namespace':namespace, 'limit':limit}


def semantic_search(db, namespace, query, embedder, limit=5):
    namespace=validate_namespace(namespace)
    if not isinstance(query,str) or not query.strip() or len(query)>MAX_QUERY:
        raise ValueError('Suchanfrage ungültig')
    if not 1<=limit<=10:
        raise ValueError('Ergebnislimit ungültig')
    initialize(db)
    query_vec=normalized(list(embedder(query)))
    rows=db.execute('''SELECT v.source,v.digest,v.dimension,v.vector,e.body FROM semantic_vectors v
        JOIN entries_v2 e ON e.namespace=v.namespace AND e.source=v.source
        WHERE v.namespace=? AND v.model=? AND '''+DOC_FILTER.replace('source ', 'e.source ')+''' LIMIT ?''',
        (namespace,embedder.model,MAX_SCAN)).fetchall()
    ranked=[]
    for source,digest,dimension,blob,body in rows:
        if digest!=_digest(body) or dimension!=len(query_vec):
            continue
        vec=decode(blob,dimension)
        if vec is None:
            continue
        score=sum(a*b for a,b in zip(query_vec,vec))
        if math.isfinite(score):
            ranked.append({'source':source,'excerpt':body[:400],
                           'score':round(max(-1,min(1,score)),4)})
    ranked.sort(key=lambda d:d['score'],reverse=True)
    return ranked[:limit]


def main():
    import argparse
    from gateway import allowed_local_target
    p=argparse.ArgumentParser(description='Operator-only opt-in P2 embedding batch')
    p.add_argument('action',choices=['index'])
    p.add_argument('--limit',type=int,default=8)
    args=p.parse_args()
    if os.getenv('SEMANTIC_SEARCH_ENABLED','false').lower()!='true':
        raise SystemExit('Semantische Suche deaktiviert: SEMANTIC_SEARCH_ENABLED=false')
    model=os.getenv('SEMANTIC_MODEL','nomic-embed-text:latest')
    url=allowed_local_target(os.getenv('OLLAMA_URL','http://ollama:11434'))
    embedder=OllamaEmbedder(url,model,timeout=60)
    with connect(os.getenv('MEMORY_DB','/data/memory.sqlite3')) as db:
        result=pending_index(db,os.getenv('KNOWLEDGE_NAMESPACE','personal'),embedder,args.limit)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    main()
