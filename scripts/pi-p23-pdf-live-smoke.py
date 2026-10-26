#!/usr/bin/env python3
"""Isolated real-PDF P2.3 RAG acceptance: in-memory 3-page PDF -> Console -> Ollama.

Uses only loopback servers, an ephemeral SQLite DB and already-installed Ollama.
Does not modify production containers, .env files, repositories or data volumes.
"""
from __future__ import annotations

import argparse
import base64
import http.cookiejar
from io import BytesIO
import json
import re
import secrets
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "console"))
sys.path.insert(0, str(ROOT / "gateway"))

from gateway import Server as GatewayServer
from server import Server as ConsoleServer, hash_password
from memdb import connect
from knowledge import add_document
from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject

OLLAMA = "http://127.0.0.1:11434"
MODEL_RE = re.compile(r"^[A-Za-z0-9_.:/-]{1,128}$")
PAGES = (
    "Motorwartung umfasst Filterwechsel und Inspektionen.",
    "Die Hydraulikpumpe erzeugt Oeldruck. Hydraulikzylinder "
    "nutzen den Oeldruck und bewegen dadurch den Baggerausleger.",
    "Reifenkontrolle umfasst Reifenprofil und Luftdruckmessung.",
)
QUESTION = "Was macht die Hydraulikpumpe?"


def make_pdf():
    """Actual searchable PDF text layers; no OCR, dummy PDF or fixture files."""
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    for text in PAGES:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
        })
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 72 700 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def no_proxy_client():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(opener, base, path, payload, csrf=None):
    headers = {"Origin": base, "Content-Type": "application/json"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    request = urllib.request.Request(
        base + path, data=json.dumps(payload).encode("utf-8"),
        headers=headers, method="POST")
    return opener.open(request, timeout=195)


def model_present(name):
    with no_proxy_client().open(OLLAMA + "/api/tags", timeout=6) as response:
        data = json.load(response)
    return name in {item.get("name") for item in data.get("models", [])
                    if isinstance(item, dict)}


def read_stream(raw):
    sources = None
    text = []
    complete = False
    for event in raw.decode("utf-8").replace("\r\n", "\n").split("\n\n"):
        lines = event.split("\n")
        data = next((x[5:].strip() for x in lines if x.startswith("data:")), None)
        if data is None:
            continue
        if data == "[DONE]":
            complete = True
        elif "event: rag_sources" in lines:
            sources = json.loads(data).get("sources")
        else:
            item = json.loads(data)
            for choice in item.get("choices", []):
                delta = choice.get("delta", {}).get("content")
                if isinstance(delta, str):
                    text.append(delta)
    return sources, "".join(text), complete


def run(model):
    print("P2.3 PDF LIVE RAG SMOKE: generated 3-page text PDF, isolated SQLite, loopback only",
          flush=True)
    if not model_present(model):
        print("ABBRUCH: Lokal installiertes Ollama-Modell fehlt:", model)
        return 2
    print("Model present:", model, flush=True)
    raw_pdf = make_pdf()
    print("PDF generated, pages: 3, bytes:", len(raw_pdf), flush=True)

    with tempfile.TemporaryDirectory(prefix="pai-p23-pdf-") as root:
        database = str(Path(root) / "test.sqlite3")
        with connect(database) as db:
            add_document(db, "foreign", "foreign.txt",
                         "Diese geheime Fremdquelle darf nie erscheinen.")
        gateway_token = secrets.token_urlsafe(48)
        knowledge_token = secrets.token_urlsafe(48)
        password = secrets.token_urlsafe(24)
        gateway = GatewayServer(
            ("127.0.0.1", 0), OLLAMA, gateway_token, database, False,
            knowledge_token=knowledge_token, knowledge_namespace="pdf-smoke",
            import_enabled=True, semantic_enabled=False)
        console = None
        try:
            console = ConsoleServer(
                ("127.0.0.1", 0),
                f"http://127.0.0.1:{gateway.server_port}",
                gateway_token, hash_password(password), knowledge_token=knowledge_token,
                import_enabled=True, rag_enabled=True)
            for service in (gateway, console):
                threading.Thread(target=service.serve_forever, daemon=True).start()

            base = f"http://127.0.0.1:{console.server_port}"
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            with post(opener, base, "/api/login", {"password": password}) as response:
                csrf = json.load(response)["csrf"]

            import_data = {
                "filename": "hydraulik-dreiseitig.pdf",
                "pdf_base64": base64.b64encode(raw_pdf).decode("ascii"),
            }
            # Import must require CSRF even during this local smoke.
            try:
                with post(opener, base, "/api/documents/import", import_data):
                    raise RuntimeError("Import was allowed without CSRF")
            except urllib.error.HTTPError as exc:
                if exc.code != 403:
                    raise

            with post(opener, base, "/api/documents/import", import_data, csrf) as response:
                document = json.load(response)
            if document.get("duplicate") or document.get("chunks") != 3:
                raise RuntimeError("PDF extraction did not yield exactly three page chunks")
            print("Authenticated 3-page PDF import and CSRF: PASS", flush=True)

            query = urllib.parse.urlencode({"kind": "search", "q": "Hydraulikpumpe"})
            with opener.open(base + "/api/knowledge?" + query, timeout=8) as response:
                found = json.load(response).get("results", [])
            if (len(found) != 1 or found[0].get("filename") != import_data["filename"]
                    or found[0].get("page") != 2
                    or not found[0].get("source", "").startswith("pdf:")):
                raise RuntimeError("FTS page provenance mismatch")
            print("FTS PDF provenance, page 2: PASS", flush=True)

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": QUESTION}],
                "rag": True, "rag_mode": "fts",
            }
            started = time.monotonic()
            with post(opener, base, "/api/chat", payload, csrf) as response:
                if response.headers.get_content_type() != "text/event-stream":
                    raise RuntimeError("Expected SSE stream")
                stream = response.read(256 * 1024 + 1)
            if len(stream) > 256 * 1024:
                raise RuntimeError("Unbounded model stream")
            duration = time.monotonic() - started

            sources, answer, done = read_stream(stream)
            if not done or not isinstance(sources, list) or len(sources) != 1:
                raise RuntimeError("Missing source event or stream completion")
            item = sources[0]
            if (item.get("id") != "Q1" or item.get("page") != 2
                    or item.get("filename") != import_data["filename"]
                    or not item.get("source", "").startswith("pdf:")
                    or "Hydraulikpumpe" not in item.get("excerpt", "")):
                raise RuntimeError("SSE source lost PDF filename or page number")
            raw = stream.decode("utf-8")
            if ("Fremdquelle" in raw or gateway_token in raw
                    or knowledge_token in raw):
                raise RuntimeError("Namespace or credential leak")
            if not answer.strip():
                raise RuntimeError("Empty model answer")
            print("SSE PDF citation [Q1] with filename and page 2: PASS")
            print("SSE completed and namespace scoped: PASS")
            print("Elapsed seconds:", round(duration, 2))
            print("Model answer:", answer.strip()[:1200])
            if "[Q1]" not in answer:
                print("CONTENT REVIEW REQUIRED: model omitted [Q1]")
                return 3
            print("Model used [Q1] in answer: YES")
            print("P2.3 PDF LIVE RAG SMOKE: PASS")
            return 0
        finally:
            if console is not None:
                console.shutdown()
                console.server_close()
            gateway.shutdown()
            gateway.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:0.6b")
    args = parser.parse_args()
    if not MODEL_RE.fullmatch(args.model) or "://" in args.model:
        parser.error("Model must be an installed local Ollama name")
    try:
        sys.exit(run(args.model))
    except (ValueError, TypeError, RuntimeError, OSError,
            urllib.error.URLError, AssertionError) as exc:
        print("P2.3 PDF LIVE RAG SMOKE: FAIL:", type(exc).__name__, str(exc)[:250])
        sys.exit(1)
