#!/usr/bin/env python3
"""Isolated Pi smoke: real local Ollama through authenticated Gateway -> Console RAG.

Only loopback HTTP, temporary SQLite, and ephemeral in-memory credentials.
No containers, production databases, .env files, or external networks are touched.
No model downloads. Run only if the model is already installed and Pi RAM permits.
"""
from __future__ import annotations

import argparse
import http.cookiejar
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

from gateway import Server as GatewayServer  # noqa: E402
from server import Server as ConsoleServer, hash_password  # noqa: E402
from memdb import connect  # noqa: E402
from knowledge import add_document  # noqa: E402
from semantic import OllamaEmbedder, pending_index  # noqa: E402

OLLAMA = "http://127.0.0.1:11434"
MODEL_NAME = re.compile(r"^[A-Za-z0-9_.:/-]{1,128}$")
QUESTION = "Welche Aufgabe hat die Hydraulikpumpe beim Bagger?"
DOCUMENT = ("Die Hydraulikpumpe des Baggers erzeugt Öldruck. "
            "Mit diesem Öldruck bewegen Hydraulikzylinder den Ausleger. "
            "Dies ist eine harmlose lokale Testdatei.")


def post(opener, url, data, csrf=None):
    headers = {"Content-Type": "application/json", "Origin": url.split("/api/")[0]}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    req = urllib.request.Request(url, json.dumps(data).encode("utf-8"),
                                 headers=headers, method="POST")
    return opener.open(req, timeout=195)


def installed_model(model):
    no_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with no_proxy.open(OLLAMA + "/api/tags", timeout=6) as response:
        tags = json.load(response)
    found = {x.get("name") for x in tags.get("models", []) if isinstance(x, dict)}
    if model not in found:
        print("ABBRUCH: Modell nicht lokal installiert:", model)
        print("Installierte Namen:", ", ".join(sorted(str(x) for x in found)))
        return False
    return True


def parse_sse(raw):
    sources = None
    answer = []
    done = False
    for event in raw.replace("\r\n", "\n").split("\n\n"):
        if not event.strip():
            continue
        lines = event.split("\n")
        data = next((line[5:].strip() for line in lines if line.startswith("data:")), None)
        if data is None:
            continue
        if data == "[DONE]":
            done = True
            continue
        parsed = json.loads(data)
        if any(line == "event: rag_sources" for line in lines):
            sources = parsed.get("sources")
            continue
        choices = parsed.get("choices", [])
        if choices:
            part = choices[0].get("delta", {}).get("content")
            if isinstance(part, str):
                answer.append(part)
    return sources, "".join(answer), done


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:0.6b",
                        help="Already-installed local Ollama chat model; no download")
    parser.add_argument("--mode", choices=("fts", "semantic"), default="fts",
                        help="RAG retrieval mode; semantic mode explicitly indexes isolated test data")
    parser.add_argument("--embed-model", choices=("nomic-embed-text:latest", "bge-m3:latest"),
                        default="nomic-embed-text:latest", help="Already-installed local embedding model")
    args = parser.parse_args()
    if not MODEL_NAME.fullmatch(args.model) or "://" in args.model:
        parser.error("Invalid model name")

    print("P2.3 LIVE API SMOKE: temporary database, localhost only, no Docker changes",
          flush=True)
    if not installed_model(args.model):
        return 2
    print("Model present:", args.model, flush=True)
    if args.mode == "semantic" and not installed_model(args.embed_model):
        return 2
    print("RAG retrieval mode:", args.mode, flush=True)

    with tempfile.TemporaryDirectory(prefix="pai-p23-rag-live-") as tmp:
        db_path = str(Path(tmp) / "test.sqlite3")
        with connect(db_path) as db:
            add_document(db, "p23-smoke", "hydraulik-test.txt", DOCUMENT)
            add_document(db, "other-namespace", "secret.txt",
                         "Diese Fremdquelle darf im Test niemals erscheinen.")

        if args.mode == "semantic":
            # Index only our temporary test document; never scan production memory.
            started = time.monotonic()
            with connect(db_path) as db:
                embedder = OllamaEmbedder(OLLAMA, args.embed_model, timeout=60)
                index_result = pending_index(db, "p23-smoke", embedder, limit=2)
            if index_result["indexed"] != 1 or index_result["namespace"] != "p23-smoke":
                raise RuntimeError("Isolated semantic index did not contain exactly one document")
            print("Semantic index: PASS (1/1 test chunk)", flush=True)
            print("Index elapsed seconds:", round(time.monotonic() - started, 2), flush=True)

        pipeline_token = secrets.token_urlsafe(48)
        knowledge_token = secrets.token_urlsafe(48)
        password = secrets.token_urlsafe(24)
        gateway = GatewayServer(
            ("127.0.0.1", 0), OLLAMA, pipeline_token, db_path, False,
            knowledge_token=knowledge_token, knowledge_namespace="p23-smoke",
            import_enabled=False, semantic_enabled=args.mode == "semantic",
            semantic_model=args.embed_model)
        console = None
        try:
            console = ConsoleServer(
                ("127.0.0.1", 0),
                "http://127.0.0.1:" + str(gateway.server_port),
                pipeline_token, hash_password(password),
                knowledge_token=knowledge_token, rag_enabled=True)
            for service in (gateway, console):
                threading.Thread(target=service.serve_forever, daemon=True).start()

            root = "http://127.0.0.1:" + str(console.server_port)
            jar = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                urllib.request.HTTPCookieProcessor(jar))
            try:
                with opener.open(root + "/api/rag-config", timeout=5):
                    raise AssertionError("Unauthenticated RAG configuration was accessible")
            except urllib.error.HTTPError as exc:
                if exc.code != 401:
                    raise

            with post(opener, root + "/api/login", {"password": password}) as response:
                csrf = json.load(response)["csrf"]
            with opener.open(root + "/api/rag-config", timeout=5) as response:
                assert json.load(response)["enabled"] is True

            payload = {
                "model": args.model,
                "messages": [{"role": "user", "content": QUESTION}],
                "rag": True,
                "rag_mode": args.mode,
            }
            start = time.monotonic()
            with post(opener, root + "/api/chat", payload, csrf=csrf) as response:
                assert response.headers.get_content_type() == "text/event-stream"
                raw = response.read(256 * 1024 + 1)
                if len(raw) > 256 * 1024:
                    raise RuntimeError("SSE stream exceeded test limit")
            elapsed = time.monotonic() - start

            result, answer, done = parse_sse(raw.decode("utf-8"))
            if not done or not isinstance(result, list) or len(result) != 1:
                raise RuntimeError("Missing SSE completion or exactly one RAG source")
            source = result[0]
            if (source.get("id") != "Q1" or source.get("filename") != "hydraulik-test.txt"
                    or "Hydraulikpumpe" not in source.get("excerpt", "")):
                raise RuntimeError("RAG source provenance mismatch")
            if ("Fremdquelle" in raw.decode("utf-8")
                    or pipeline_token in raw.decode("utf-8")
                    or knowledge_token in raw.decode("utf-8")):
                raise RuntimeError("Unexpected cross-namespace content or credential leakage")
            if not answer.strip():
                raise RuntimeError("The model emitted no visible answer tokens")

            print("Authenticated Console → Gateway → local Ollama: PASS")
            print("Isolated namespace, single source [Q1]: PASS")
            print("SSE completed: PASS")
            print("Elapsed seconds:", round(elapsed, 2))
            print("Model answer:", answer.strip()[:1200])
            has_citation = "[Q1]" in answer
            print("Model used [Q1] in answer:", "YES" if has_citation else "NO")
            if not has_citation:
                print("CONTENT REVIEW REQUIRED: transport passed but model omitted citation")
                return 3
            if args.mode == "semantic":
                print("P2.3 SEMANTIC RAG API SMOKE: PASS")
            else:
                print("P2.3 LIVE RAG API SMOKE: PASS")
            return 0
        finally:
            if console is not None:
                console.shutdown()
                console.server_close()
            gateway.shutdown()
            gateway.server_close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, AssertionError,
            urllib.error.URLError, json.JSONDecodeError) as exc:
        print("P2.3 LIVE RAG API SMOKE: FAIL:", type(exc).__name__, str(exc)[:250])
        sys.exit(1)
