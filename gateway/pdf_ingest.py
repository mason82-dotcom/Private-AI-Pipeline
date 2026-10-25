"""Short-lived bounded PDF worker launcher for the local authenticated Gateway."""
from __future__ import annotations
import base64
import binascii
import json
from pathlib import Path
import resource
import subprocess
import sys

MAX_PDF_BYTES=1_048_576
MAX_PDF_BASE64=1_398_104
WORKER=Path(__file__).resolve().with_name('pdf_extract.py')

def _worker_limits():
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(12,12))
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))

def parse_base64_pdf(encoded):
    if not isinstance(encoded,str) or not encoded or len(encoded)>MAX_PDF_BASE64:
        raise ValueError('PDF-Daten überschreiten 1 MiB')
    try:
        binary=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error) as exc:
        raise ValueError('PDF-Base64 ungültig') from exc
    if not binary.startswith(b'%PDF-') or len(binary)>MAX_PDF_BYTES or len(binary)<16:
        raise ValueError('Ungültige PDF-Datei oder Datei zu groß')
    try:
        worker=subprocess.run([sys.executable,'-I',str(WORKER)],input=binary,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,check=False,timeout=18,
            env={'PYTHONIOENCODING':'utf-8','PATH':'/usr/bin:/bin'},
            preexec_fn=_worker_limits)
    except (OSError,subprocess.TimeoutExpired):
        raise ValueError('PDF-Zeitlimit oder Speichergrenze erreicht') from None
    if len(worker.stdout)>512*1024:
        raise ValueError('PDF-Verarbeitung überschreitet Antwortgrenze')
    try:
        result=json.loads(worker.stdout)
    except (UnicodeError,ValueError):
        raise ValueError('PDF-Verarbeitung fehlgeschlagen') from None
    if worker.returncode or not isinstance(result,dict) or not isinstance(result.get('pages'),list):
        raise ValueError(result.get('error','PDF-Verarbeitung fehlgeschlagen') if isinstance(result,dict) else 'PDF-Verarbeitung fehlgeschlagen')
    return binary,result['pages']
