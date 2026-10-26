#!/usr/bin/env python3
"""Offline Ollama HTTP fixture for the disposable P2.3 Docker QA network.

Never contacts actual Ollama, any WAN service or production containers.
"""
from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def json_response(self, code, data):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            self.json_response(200, {"status": "ok"})
        elif self.path == "/v1/models":
            self.json_response(200, {"data": [{"id": "qa-mock:latest", "object": "model"}]})
        else:
            self.json_response(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.json_response(404, {"error": "not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "-1"))
            if not 1 <= size <= 32768:
                raise ValueError("invalid size")
            payload = json.loads(self.rfile.read(size))
            messages = payload["messages"]
            assert isinstance(messages, list) and messages
            assert payload.get("stream") is True
            assert payload.get("model") == "qa-mock:latest"
            question = messages[-1]["content"]
            rag = messages[0].get("role") == "system"
            if rag:
                system = messages[0]["content"]
                assert "[Q1]" in system and "Hydraulikpumpe" in system
                assert "bagger-qa.txt" in system
                assert "Fremdquelle" not in system
            else:
                assert len(messages) == 1
        except (ValueError, TypeError, KeyError, AssertionError):
            self.json_response(400, {"error": "bad mock request"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        if question.startswith("Abbruchtest"):
            tokens = ["Abbruch ", "läuft weiter", " [Q1]"]
            pause = 4
        elif rag:
            tokens = ["Die Hydraulikpumpe erzeugt Öldruck. ", "[Q1]"]
            pause = 0
        else:
            tokens = ["Normale Antwort ohne Quellen."]
            pause = 0
        try:
            for i, token in enumerate(tokens):
                part = json.dumps({"choices": [{"delta": {"content": token}}]},
                                  ensure_ascii=False).encode("utf-8")
                self.wfile.write(b"data: " + part + b"\n\n")
                self.wfile.flush()
                if i == 0 and pause:
                    time.sleep(pause)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError):
            pass

ThreadingHTTPServer(("0.0.0.0", 11434), Handler).serve_forever()
