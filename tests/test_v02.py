import json
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'gateway'))
from memdb import connect, remember, forget, search, ingest_directory, entries_count, validate_namespace
from mcp_stdio import dispatch
from gateway import enriched_body, allowed_local_target, OPENER


class V02Tests(unittest.TestCase):
    def test_namespace_validation(self):
        for bad in ('', 'A', 'space here', 'foo/bar', '../../other', '💻', 'a'*65):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_namespace(bad)
        self.assertEqual(validate_namespace('skyhub-next'), 'skyhub-next')

    def test_namespace_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            with connect(str(Path(d, 'memo.db'))) as db:
                remember(db, 'note:common', 'RC Plus 2 Daten SkyHub', 'skyhub')
                remember(db, 'note:common', 'Temperatur der Küche', 'home')
                self.assertEqual(entries_count(db, 'skyhub'), 1)
                self.assertEqual(entries_count(db, 'home'), 1)
                self.assertEqual(search(db, 'SkyHub', namespace='home'), [])
                self.assertEqual(search(db, 'SkyHub', namespace='skyhub')[0]['source'], 'note:common')
                self.assertEqual(forget(db, 'note:common', namespace='home'), 1)
                self.assertEqual(entries_count(db, 'skyhub'), 1)

    def test_documents_snapshot_scoped(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            docs = path / 'docs'; docs.mkdir()
            (docs / 'one.md').write_text('SkyHub Matrice Antriebsdaten')
            with connect(str(path / 'memo.db')) as db:
                remember(db, 'note:keep', 'Daten behalten', 'other')
                ingest_directory(db, str(docs), namespace='skyhub')
                (docs / 'one.md').unlink()
                ingest_directory(db, str(docs), namespace='skyhub')
                self.assertEqual(search(db, 'Matrice', namespace='skyhub'), [])
                self.assertEqual(entries_count(db, 'other'), 1)

    def test_v01_migration_preserves_legacy_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d, 'old.db'))
            legacy = sqlite3.connect(path)
            legacy.execute('CREATE VIRTUAL TABLE entries USING fts5(source UNINDEXED, body)')
            legacy.execute('INSERT INTO entries(source,body) VALUES (?,?)', ('note:v01', 'Legacy M3M image processing'))
            legacy.commit(); legacy.close()
            with connect(path) as db:
                self.assertEqual(entries_count(db, 'legacy'), 1)
                self.assertEqual(entries_count(db, 'personal'), 0)
            with connect(path) as db:
                self.assertEqual(entries_count(db, 'legacy'), 1)
                self.assertEqual(db.execute('SELECT count(*) FROM entries').fetchone()[0], 1)

    def test_memory_injection_must_opt_in_and_stay_in_namespace(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d, 'db'))
            with connect(path) as db:
                remember(db, 'note:secret', 'Matrice controller pairing', 'skyhub')
            request = json.dumps({'messages': [{'role': 'user', 'content': 'Matrice'}]}).encode()
            self.assertEqual(enriched_body(request, path, False, 'skyhub'), request)
            self.assertEqual(enriched_body(request, path, True, 'webui'), request)
            output = json.loads(enriched_body(request, path, True, 'skyhub'))
            self.assertIn('note:secret', output['messages'][0]['content'])

    def test_mcp_readonly_and_fixed_namespace(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d, 'db'))
            params = {'name': 'memory_remember', 'arguments': {'name': 'new', 'text': 'Neuer Projektkontext'}}
            with self.assertRaises(PermissionError):
                dispatch({'method': 'tools/call', 'params': params}, path, namespace='skyhub', readonly=True)
            with self.assertRaises(ValueError):
                dispatch({'method': 'tools/call', 'params': {'name': 'memory_search',
                         'arguments': {'query': 'Neuer', 'namespace': 'other'}}}, path, readonly=True)
            dispatch({'method': 'tools/call', 'params': params}, path, namespace='skyhub', readonly=False)
            self.assertIn('note:new', dispatch({'method': 'tools/call', 'params': {'name': 'memory_search',
                          'arguments': {'query': 'Projektkontext'}}}, path, namespace='skyhub')['content'][0]['text'])
            self.assertEqual('[]', dispatch({'method': 'tools/call', 'params': {'name': 'memory_search',
                          'arguments': {'query': 'Projektkontext'}}}, path, namespace='personal')['content'][0]['text'])

    def test_private_upstream_and_no_proxies(self):
        for bad in ('http://evil.example:11434', 'http://ollama.lan:11434',
                    'https://192.168.0.1:11434', 'http://169.254.169.254:80'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                allowed_local_target(bad)
        from urllib.request import ProxyHandler
        self.assertFalse(any(isinstance(h, ProxyHandler) and h.proxies for h in OPENER.handlers))

    def test_compose_internal_network_and_local_only_ui(self):
        try:
            import yaml
        except ImportError:
            self.skipTest('PyYAML not installed')
        base = yaml.safe_load((ROOT / 'compose.yaml').read_text())
        lan = yaml.safe_load((ROOT / 'compose.lan.yaml').read_text())
        self.assertTrue(base['networks']['pipeline']['internal'])
        self.assertEqual(base['services']['gateway']['networks'], ['pipeline'])
        self.assertEqual(base['services']['webui']['networks'], ['pipeline'])
        self.assertTrue(base['services']['webui']['ports'][0].startswith('127.0.0.1:'))
        self.assertNotIn('ports', base['services']['gateway'])
        self.assertNotIn('ports', base['services']['ollama'])
        self.assertIn('lan_egress', lan['services']['gateway']['networks'])
        self.assertNotIn('webui', lan['services'])
        self.assertEqual(base['services']['gateway']['environment']['MEMORY_INJECTION'], '${MEMORY_INJECTION:-false}')


if __name__ == '__main__':
    unittest.main()
