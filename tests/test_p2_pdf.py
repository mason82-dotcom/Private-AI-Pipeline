"""P2.1: bounded PDF parsing, page citations and authenticated import."""
import base64
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'gateway'))
sys.path.insert(0,str(ROOT/'tests'))
from pdf_ingest import parse_base64_pdf
from pdf_extract import extract_pdf
from knowledge import add_pdf_pages,find_documents,list_documents,list_memories
from memdb import connect
from test_p1_p2_knowledge import TestKnowledgeHTTP
from pypdf import PdfWriter
from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject

def make_pdf(texts=('alphawortpdfseiteeins','betawortpdfseitezwei')):
    writer=PdfWriter()
    font=writer._add_object(DictionaryObject({
        NameObject('/Type'):NameObject('/Font'),
        NameObject('/Subtype'):NameObject('/Type1'),
        NameObject('/BaseFont'):NameObject('/Helvetica')}))
    for text in texts:
        page=writer.add_blank_page(width=612,height=792)
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        stream=DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 72 700 Td ({text}) Tj ET'.encode('ascii'))
        page[NameObject('/Contents')]=writer._add_object(stream)
    b=BytesIO();writer.write(b)
    return b.getvalue()

class TestPDFWorker(unittest.TestCase):
    def test_page_citations_dedup_and_namespace(self):
        pdf=make_pdf()
        binary,pages=parse_base64_pdf(base64.b64encode(pdf).decode())
        self.assertEqual(binary,pdf)
        self.assertEqual([p['page'] for p in pages],[1,2])
        with tempfile.TemporaryDirectory() as root, connect(str(Path(root)/'test.sqlite')) as db:
            first=add_pdf_pages(db,'alpha','test.pdf',binary,pages)
            self.assertFalse(first['duplicate'])
            self.assertTrue(add_pdf_pages(db,'alpha','same.pdf',binary,pages)['duplicate'])
            matches=find_documents(db,'alpha','betawortpdfseitezwei')
            self.assertEqual(matches[0]['page'],2)
            self.assertEqual(matches[0]['filename'],'test.pdf')
            self.assertEqual(list_memories(db,'alpha'),[])
            self.assertEqual(list_documents(db,'beta'),[])
            self.assertEqual(len(list_documents(db,'alpha')),1)

    def test_reject_bad_encrypted_oversized_scanned(self):
        for raw in [b'hello world '+b'0'*24,b'%PDF-'+b'X'*1_048_576]:
            with self.assertRaises(ValueError):extract_pdf(raw)
        with self.assertRaises(ValueError):parse_base64_pdf('invalid!!')
        with self.assertRaisesRegex(ValueError,'Textebene'):
            parse_base64_pdf(base64.b64encode(make_pdf(('',))).decode())
        with self.assertRaises(ValueError):
            parse_base64_pdf(base64.b64encode(make_pdf(tuple('X' for _ in range(17)))).decode())
        writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.encrypt('secret')
        out=BytesIO();writer.write(out)
        with self.assertRaisesRegex(ValueError,'Verschlüsselte'):
            parse_base64_pdf(base64.b64encode(out.getvalue()).decode())

class TestPDFHTTP(unittest.TestCase):
    setUp=TestKnowledgeHTTP.setUp
    close=TestKnowledgeHTTP.close
    request=TestKnowledgeHTTP.request
    login=TestKnowledgeHTTP.login

    def test_authenticated_pdf_import_page_search(self):
        payload={'filename':'notes.pdf','pdf_base64':base64.b64encode(make_pdf()).decode()}
        self.login()
        with self.assertRaises(urllib.error.HTTPError) as exc:
            self.request('/api/documents/import',payload)
        self.assertEqual(exc.exception.code,403)
        with self.request('/api/documents/import',payload,csrf=True) as r:
            first=json.load(r)
        self.assertFalse(first['duplicate'])
        with self.request('/api/documents/import',payload,csrf=True) as r:
            self.assertTrue(json.load(r)['duplicate'])
        with self.request('/api/knowledge?kind=search&q=betawortpdfseitezwei') as r:
            hit=json.load(r)['results'][0]
        self.assertEqual(hit['page'],2)
        self.assertEqual(hit['filename'],'notes.pdf')
        self.assertEqual(hit['source'],f'pdf:{first["document_id"]}:p2#0')
        self.console.import_enabled=False
        with self.assertRaises(urllib.error.HTTPError) as exc:
            self.request('/api/documents/import',payload,csrf=True)
        self.assertEqual(exc.exception.code,403)

if __name__=='__main__':
    unittest.main()
