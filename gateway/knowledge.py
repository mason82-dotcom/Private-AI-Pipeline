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
PDF_SUFFIX = '.pdf'
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


def add_pdf_pages(db, namespace: str, filename: str, binary: bytes, pages: list[dict]):
    """Atomically index bounded text from each page with exact page provenance."""
    namespace=validate_namespace(namespace)
    if (not isinstance(filename,str) or not NAME.fullmatch(filename)
            or not filename.lower().endswith(PDF_SUFFIX)):
        raise ValueError('Ungültiger PDF-Dateiname')
    if not isinstance(binary,bytes) or not binary.startswith(b'%PDF-') or len(binary)>1_048_576:
        raise ValueError('PDF-Bytes ungültig')
    if not isinstance(pages,list) or not 1<=len(pages)<=16:
        raise ValueError('Ungültige Seitenliste')
    number_last=0;total=0;parts=[]
    for page in pages:
        if not isinstance(page,dict) or set(page)!={'page','text'}:
            raise ValueError('Ungültige PDF-Seite')
        number,text=page['page'],page['text']
        if not isinstance(number,int) or isinstance(number,bool) or number<=number_last or number>16:
            raise ValueError('Seiten nicht geordnet')
        if not isinstance(text,str) or not text.strip() or '\x00' in text:
            raise ValueError('Seiteninhalt ungültig')
        total+=len(text.encode('utf-8'))
        if total>96*1024:
            raise ValueError('PDF-Text zu umfangreich')
        for i,part in enumerate(chunks(text)):
            if part.strip():parts.append((number,i,part))
        number_last=number
    digest=hashlib.sha256(binary).hexdigest();did=digest[:24]
    init(db)
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    try:
        db.execute('BEGIN IMMEDIATE')
        found=db.execute('SELECT filename,chunk_count FROM knowledge_documents WHERE namespace=? AND sha256=?', (namespace,digest)).fetchone()
        if found:
            db.commit()
            return {'document_id':did,'filename':found[0],'chunks':found[1],'duplicate':True,'format':'pdf'}
        for num,idx,part in parts:
            db.execute('INSERT INTO entries_v2(namespace,source,body) VALUES (?,?,?)',
                       (namespace,f'pdf:{did}:p{num}#{idx}',part))
        db.execute('INSERT INTO knowledge_documents VALUES (?,?,?,?,?,?)',
                   (namespace,did,filename,digest,now,len(parts)))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'document_id':did,'filename':filename,'chunks':len(parts),'duplicate':False,'format':'pdf'}


def list_documents(db, namespace: str):
    namespace = validate_namespace(namespace)
    init(db)
    rows = db.execute('''SELECT document_id,filename,imported_at,chunk_count FROM knowledge_documents
                      WHERE namespace=? ORDER BY imported_at DESC, filename ASC LIMIT 200''', (namespace,)).fetchall()
    return [{'id':did,'filename':name,'imported_at':when,'chunks':n,'status':'indexed','format':'pdf' if name.lower().endswith('.pdf') else 'text'} for did,name,when,n in rows]


def scoped_search(db, namespace, query, documents=False):
    namespace = validate_namespace(namespace)
    if not isinstance(query,str) or len(query)>200:
        raise ValueError('Suchanfrage ungültig')
    terms=list(dict.fromkeys(re.findall(r'(?u)\w+',query.lower())))
    terms=[term for term in terms if len(term)>=2][:12]
    if not terms:
        return []
    fts=' OR '.join('"'+token.replace('"','')+'"' for token in terms)
    scope_sql="(source GLOB 'upload:*' OR source GLOB 'doc:*' OR source GLOB 'pdf:*')" if documents else \
              "(source NOT GLOB 'upload:*' AND source NOT GLOB 'doc:*' AND source NOT GLOB 'pdf:*')"
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
                    "AND source NOT GLOB 'upload:*' AND source NOT GLOB 'pdf:*' ORDER BY rowid DESC LIMIT 100",(namespace,)).fetchall()
    return [{'source':source,'body':body[:1700]} for source,body in rows]


def cite_hit(db, namespace: str, hit: dict):
    """Add human-readable PDF provenance without exposing another namespace."""
    source = hit.get('source', '')
    if source.startswith('pdf:'):
        match = re.fullmatch(r'pdf:([a-f0-9]{24}):p([1-9][0-9]*)#([0-9]+)', source)
        if match:
            hit['document_id'] = match.group(1)
            hit['page'] = int(match.group(2))
            record = db.execute('SELECT filename FROM knowledge_documents WHERE namespace=? AND document_id=?',
                                (validate_namespace(namespace), hit['document_id'])).fetchone()
            if record:
                hit['filename'] = record[0]
    return hit


def find_documents(db, namespace: str, query: str):
    if not isinstance(query,str) or len(query)>200:
        raise ValueError('Suche zu lang')
    return [cite_hit(db,namespace,{'source':src,'excerpt':body[:400]})
            for src,body in scoped_search(db,namespace,query,True)]
