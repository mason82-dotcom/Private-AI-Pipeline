"""Single-operator local knowledge: project-scoped metadata + FTS document chunks.

The web browser never talks to this module; the console BFF has a separate
knowledge capability token. No file paths are opened or executed during import.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re

from memdb import chunks, validate_namespace

ALLOWED_SUFFIXES = ('.md', '.txt', '.rst')
MAX_TEXT_BYTES = 48 * 1024
NAME = re.compile(r'^[^/\\\x00-\x1f]{1,120}$')


def init(db):
    db.execute('''CREATE TABLE IF NOT EXISTS knowledge_documents (
      namespace TEXT NOT NULL, document_id TEXT NOT NULL, filename TEXT NOT NULL,
      sha256 TEXT NOT NULL, imported_at TEXT NOT NULL, chunk_count INTEGER NOT NULL,
      PRIMARY KEY(namespace, document_id), UNIQUE(namespace,sha256)
    )''')
    db.commit()


def add_document(db, namespace: str, filename: str, content: str):
    namespace = validate_namespace(namespace)
    if not isinstance(filename, str) or not NAME.fullmatch(filename) or not filename.lower().endswith(ALLOWED_SUFFIXES):
        raise ValueError('Nur einfache UTF-8-Dateien .md, .txt oder .rst erlaubt')
    if not isinstance(content, str) or not content.strip() or '\x00' in content:
        raise ValueError('Leerer oder ungültiger Text')
    binary = content.encode('utf-8')
    if len(binary) > MAX_TEXT_BYTES:
        raise ValueError('Datei überschreitet 48 KiB')
    digest = hashlib.sha256(binary).hexdigest()
    document_id = digest[:24]
    init(db)
    blocks = [part for part in chunks(content) if part.strip()]
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    try:
        db.execute('BEGIN IMMEDIATE')
        # Race-free deduplication (another importer may have committed meanwhile).
        found=db.execute('SELECT filename,chunk_count FROM knowledge_documents WHERE namespace=? AND sha256=?',
                         (namespace,digest)).fetchone()
        if found:
            db.commit()
            return {'document_id':document_id,'filename':found[0],'chunks':found[1],'duplicate':True}
        # A digest is content-addressed. Content in other namespaces is NOT shared.
        for index, part in enumerate(blocks):
            db.execute('INSERT INTO entries_v2(namespace,source,body) VALUES (?,?,?)',
                       (namespace,f'upload:{document_id}#{index}',part))
        db.execute('INSERT INTO knowledge_documents VALUES (?,?,?,?,?,?)',
                   (namespace,document_id,filename,digest,now,len(blocks)))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'document_id':document_id,'filename':filename,'chunks':len(blocks),'duplicate':False}


def list_documents(db, namespace: str):
    namespace = validate_namespace(namespace)
    init(db)
    rows = db.execute('''SELECT document_id,filename,imported_at,chunk_count FROM knowledge_documents
                      WHERE namespace=? ORDER BY imported_at DESC, filename ASC LIMIT 200''', (namespace,)).fetchall()
    return [{'id':did,'filename':name,'imported_at':when,'chunks':n,'status':'indexed'} for did,name,when,n in rows]


def scoped_search(db, namespace, query, documents=False):
    namespace = validate_namespace(namespace)
    if not isinstance(query,str) or len(query)>200:
        raise ValueError('Suchanfrage ungültig')
    terms=list(dict.fromkeys(re.findall(r'(?u)\w+',query.lower())))
    terms=[term for term in terms if len(term)>=2][:12]
    if not terms:
        return []
    fts=' OR '.join('"'+token.replace('"','')+'"' for token in terms)
    scope_sql="(source GLOB 'upload:*' OR source GLOB 'doc:*')" if documents else \
              "(source NOT GLOB 'upload:*' AND source NOT GLOB 'doc:*')"
    rows=db.execute('SELECT source,body FROM entries_v2 WHERE entries_v2 MATCH ? AND namespace=? AND '+scope_sql+
                    ' ORDER BY bm25(entries_v2) LIMIT 10',(fts,namespace)).fetchall()
    return rows


def list_memories(db, namespace: str, query: str = ''):
    namespace=validate_namespace(namespace)
    if not isinstance(query,str) or len(query)>200:
        raise ValueError('Suche zu lang')
    if query.strip():
        return [{'source':s,'body':body[:1700]} for s,body in scoped_search(db,namespace,query,False)]
    rows=db.execute("SELECT source,body FROM entries_v2 WHERE namespace=? AND source NOT GLOB 'doc:*' "
                    "AND source NOT GLOB 'upload:*' ORDER BY rowid DESC LIMIT 100",(namespace,)).fetchall()
    return [{'source':source,'body':body[:1700]} for source,body in rows]


def find_documents(db, namespace: str, query: str):
    if not isinstance(query,str) or len(query)>200:
        raise ValueError('Suche zu lang')
    return [{'source':s,'excerpt':body[:400]} for s,body in scoped_search(db,namespace,query,True)]
