"""Bounded, optional text-layer PDF extraction; no OCR or external resources."""
from __future__ import annotations
from io import BytesIO
import json
import sys

MAX_PDF_BYTES = 1_048_576
MAX_PAGES = 16
MAX_TEXT_BYTES = 96 * 1024

def extract_pdf(data: bytes) -> list[dict]:
    if not isinstance(data, bytes) or len(data) > MAX_PDF_BYTES or len(data) < 16 or not data.startswith(b'%PDF-'):
        raise ValueError('Ungültige PDF-Datei oder Datei größer als 1 MiB')
    from pypdf import PdfReader
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError('Verschlüsselte PDFs sind nicht erlaubt')
        count = len(reader.pages)
        if not 1 <= count <= MAX_PAGES:
            raise ValueError('PDF muss 1 bis 16 Seiten enthalten')
        pages = []
        total = 0
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text(extraction_mode='plain') or ''
            if '\x00' in text:
                raise ValueError('Ungültiger Text im PDF')
            total += len(text.encode('utf-8'))
            if total > MAX_TEXT_BYTES:
                raise ValueError('PDF enthält mehr als 96 KiB extrahierten Text')
            if text.strip():
                pages.append({'page': page_num, 'text': text})
        if not pages:
            raise ValueError('PDF enthält keine durchsuchbare Textebene; OCR wird nicht unterstützt')
        return pages
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('PDF konnte nicht sicher gelesen werden') from exc

def main():
    try:
        raw=sys.stdin.buffer.read(MAX_PDF_BYTES+1)
        result=extract_pdf(raw)
        sys.stdout.write(json.dumps({'pages':result},ensure_ascii=False))
    except Exception as exc:
        sys.stdout.write(json.dumps({'error':str(exc) if isinstance(exc,ValueError) else 'PDF-Verarbeitung fehlgeschlagen'}))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
