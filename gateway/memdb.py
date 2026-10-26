"""Opt-in, project-isolated FTS5 memory. No network access, embedding downloads or auto-capture.

Database migration is additive: legacy v0.1 'entries' stay intact and are copied into
namespace 'legacy'. A v0.2 writer never modifies the legacy table.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DEFAULT_DB = '/data/memory.sqlite3'
EXTENSIONS = frozenset({'.md', '.txt', '.rst', '.py', '.go', '.rs', '.js', '.ts', '.tsx', '.jsx', '.sh', '.yaml', '.yml', '.css', '.html'})
MAX_FILE_BYTES = 1024 * 1024
MAX_FILES = 500
MAX_CHARS = 1600
NAMESPACE_PATTERN = re.compile(r'[a-z0-9][a-z0-9_-]{0,63}\Z')


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def validate_namespace(namespace: str) -> str:
    if not isinstance(namespace, str) or not NAMESPACE_PATTERN.fullmatch(namespace):
        raise ValueError('Namespace: 1-64 Zeichen a-z, 0-9, _ oder -; Beginn alphanumerisch')
    return namespace


def connect(db_path: str | None = None):
    path = db_path or os.getenv('MEMORY_DB', DEFAULT_DB)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, factory=ClosingConnection)
    try:
        db.execute('PRAGMA busy_timeout=10000')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS memory_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS entries_v2 USING fts5(namespace UNINDEXED, source UNINDEXED, body, tokenize="unicode61")')
        # Serialize the first-run migration, even if multiple processes connect simultaneously.
        db.execute('BEGIN IMMEDIATE')
        migrated = db.execute("SELECT value FROM memory_meta WHERE key='v01_import'").fetchone()
        if not migrated:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='entries' AND type='table'").fetchone()
            if exists:
                db.execute("INSERT INTO entries_v2(namespace, source, body) SELECT 'legacy', source, body FROM entries")
            db.execute("INSERT INTO memory_meta(key,value) VALUES('v01_import','done')")
        db.commit()
        return db
    except Exception:
        db.close()
        raise


def remember(db, source: str, body: str, namespace='personal'):
    namespace = validate_namespace(namespace)
    if not isinstance(source, str) or not source or len(source) > 300:
        raise ValueError('Ungültige Quelle')
    if not isinstance(body, str) or not body.strip() or len(body) > 10000:
        raise ValueError('Text muss 1 bis 10.000 Zeichen enthalten')
    db.execute('DELETE FROM entries_v2 WHERE namespace=? AND source=?', (namespace, source))
    db.execute('INSERT INTO entries_v2(namespace, source, body) VALUES (?, ?, ?)', (namespace, source, body.strip()))
    db.commit()


def forget(db, source: str, namespace='personal'):
    namespace = validate_namespace(namespace)
    count = db.execute('SELECT count(*) FROM entries_v2 WHERE namespace=? AND source=?', (namespace, source)).fetchone()[0]
    db.execute('DELETE FROM entries_v2 WHERE namespace=? AND source=?', (namespace, source))
    db.commit()
    return count


def search(db, question: str, limit=4, namespace='personal'):
    namespace = validate_namespace(namespace)
    if not isinstance(question, str) or len(question) > 2000:
        raise ValueError('Ungültige Suchanfrage')
    tokens = list(dict.fromkeys(re.findall(r'(?u)\w+', question.lower())))
    tokens = [word for word in tokens if len(word) >= 3][:12]
    if not tokens:
        return []
    query = ' OR '.join('"' + word.replace('"', '') + '"' for word in tokens)
    rows = db.execute('SELECT source, body FROM entries_v2 WHERE entries_v2 MATCH ? AND namespace=? ORDER BY bm25(entries_v2) LIMIT ?',
                      (query, namespace, min(max(int(limit), 1), 10))).fetchall()
    return [{'source': source, 'body': body[:1700]} for source, body in rows]


def chunks(content: str):
    content = content.strip()
    cursor = 0
    while cursor < len(content):
        end = min(cursor + MAX_CHARS, len(content))
        yield content[cursor:end]
        if end == len(content):
            break
        cursor = end - 160


def ingest_directory(db, root: str, ceiling: int = MAX_FILES, namespace='personal'):
    namespace = validate_namespace(namespace)
    base = Path(root).resolve(strict=True)
    if not base.is_dir():
        raise ValueError('Importziel muss ein Ordner sein')
    count_files = count_chunks = 0
    # A snapshot only replaces documents inside the current namespace.
    try:
        db.execute("DELETE FROM entries_v2 WHERE namespace=? AND source GLOB 'doc:*'", (namespace,))
        for file in sorted(base.rglob('*')):
            if count_files >= min(ceiling, MAX_FILES):
                break
            if file.is_symlink() or not file.is_file() or file.suffix.lower() not in EXTENSIONS:
                continue
            rel = file.relative_to(base)
            if any(x.startswith('.') or x.lower() in {'node_modules', 'vendor', 'dist', 'build', '__pycache__'} for x in rel.parts):
                continue
            if file.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                text = file.read_text(encoding='utf-8')
            except (UnicodeError, OSError):
                continue
            for idx, block in enumerate(chunks(text)):
                if block:
                    db.execute('INSERT INTO entries_v2(namespace, source, body) VALUES (?, ?, ?)',
                               (namespace, 'doc:' + rel.as_posix() + '#' + str(idx), block))
                    count_chunks += 1
            count_files += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'namespace': namespace, 'files': count_files, 'chunks': count_chunks}


def entries_count(db, namespace='personal'):
    return db.execute('SELECT count(*) FROM entries_v2 WHERE namespace=?', (validate_namespace(namespace),)).fetchone()[0]
