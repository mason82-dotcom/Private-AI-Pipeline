#!/usr/bin/env python3
"""In-container HTTP client for the disposable P2.3 Docker QA environment."""
from __future__ import annotations
import http.client
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8085"
PASSWORD = os.environ["P23_QA_PASSWORD"]
MODEL = "qa-mock:latest"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))

def get(path):
    return opener.open(BASE + path, timeout=15)

def post(path, data, csrf=None, origin=BASE):
    headers = {"Content-Type":"application/json", "Origin": origin}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    request = urllib.request.Request(BASE + path, json.dumps(data).encode("utf-8"),
                                     headers=headers, method="POST")
    return opener.open(request, timeout=20)

def rejected(code, func, reason):
    try:
        with func():
            raise AssertionError(reason + " wrongly accepted")
    except urllib.error.HTTPError as e:
        assert e.code == code, f"{reason}: expected {code}, got {e.code}"

def parse_stream(response):
    raw = response.read(65537)
    assert len(raw) < 65537
    sources, text, done = None, [], False
    for block in raw.decode("utf-8").replace("\r\n", "\n").split("\n\n"):
        lines = block.splitlines()
        data = next((line[5:].strip() for line in lines if line.startswith("data:")), None)
        if data is None: continue
        if data == "[DONE]": done=True; continue
        obj = json.loads(data)
        if "event: rag_sources" in lines:
            sources = obj.get("sources")
        else:
            for entry in obj.get("choices", []):
                delta = entry.get("delta", {}).get("content")
                if isinstance(delta, str): text.append(delta)
    return sources, "".join(text), done, raw

def main():
    with get("/health") as response:
        assert json.load(response)["status"] == "ok"
        csp = response.headers.get("Content-Security-Policy", "")
        assert "default-src 'none'" in csp and "script-src 'self'" in csp
        assert "connect-src 'self'" in csp and "'unsafe-inline'" not in csp
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
    rejected(401, lambda:get("/api/rag-config"), "Unauthenticated RAG")
    rejected(401, lambda:get("/api/session"), "Unauthenticated session")
    with post("/api/login", {"password":PASSWORD}) as response:
        csrf = json.load(response)["csrf"]
    with get("/api/session") as response:
        assert json.load(response)["authenticated"] is True
    with get("/api/rag-config") as response:
        assert json.load(response)["enabled"] is True
    with get("/") as response:
        assert b"/app.js" in response.read(20000)
    with get("/app.js") as response:
        js=response.read(100000).decode("utf-8")
        assert "Mit Dokumenten antworten" in js and "rag_sources" in js
    print("Console HTTP login, CSP, session, static UI and RAG config: PASS", flush=True)

    document = {"filename":"bagger-qa.txt",
                "content":"Die Hydraulikpumpe erzeugt Öldruck. "
                          "Die Hydraulikzylinder bewegen damit den Baggerausleger."}
    rejected(403, lambda:post("/api/documents/import", document), "Missing import CSRF")
    rejected(403, lambda:post("/api/documents/import", document, csrf,
                              "https://cross-origin.invalid"), "Wrong origin")
    with post("/api/documents/import", document, csrf) as response:
        item=json.load(response)
        assert item["duplicate"] is False and item["chunks"]==1
    with get("/api/knowledge?kind=search&q=Hydraulikpumpe") as response:
        payload=json.load(response)
        assert payload["namespace"]=="p23-docker-qa"
        assert len(payload["results"])==1
        assert payload["results"][0]["filename"]=="bagger-qa.txt"
    print("Authenticated import, CSRF, Origin and fixed namespace: PASS", flush=True)

    chat={"model":MODEL, "messages":[{"role":"user",
          "content":"Welche Aufgabe hat die Hydraulikpumpe?"}],
          "rag":True, "rag_mode":"fts"}
    rejected(403,lambda:post("/api/chat",chat),"Missing chat CSRF")
    rejected(400,lambda:post("/api/chat",dict(chat,namespace="foreign"),csrf),
             "Client-supplied namespace")
    with post("/api/chat",chat,csrf) as response:
        assert response.headers.get_content_type()=="text/event-stream"
        sources,answer,done,raw=parse_stream(response)
    assert isinstance(sources,list) and len(sources)==1
    assert sources[0]["id"]=="Q1" and sources[0]["filename"]=="bagger-qa.txt"
    assert "Hydraulikpumpe" in sources[0]["excerpt"]
    assert done and answer.endswith("[Q1]")
    assert b"Fremdquelle" not in raw
    print("Container-to-container RAG, SSE [Q1] and completion: PASS", flush=True)

    with post("/api/chat",dict(chat,rag=False),csrf) as response:
        refs,plain,complete,_=parse_stream(response)
    assert refs is None and complete and plain=="Normale Antwort ohne Quellen."
    print("Non-RAG chat unchanged: PASS", flush=True)

    # Client socket is closed mid-stream; this checks availability afterwards,
    # not the actual cancellation of upstream Ollama computation.
    aborted=dict(chat,messages=[{"role":"user","content":"Abbruchtest Hydraulikpumpe"}])
    conn=http.client.HTTPConnection("127.0.0.1",8085,timeout=12)
    cookies="; ".join(f"{c.name}={c.value}" for c in jar)
    try:
        conn.request("POST","/api/chat",body=json.dumps(aborted),headers={
            "Content-Type":"application/json","Origin":BASE,
            "Cookie":cookies,"X-CSRF-Token":csrf})
        response=conn.getresponse()
        assert response.status==200
        assert response.read(28)
    finally:
        conn.close()
    with get("/health") as response:
        assert json.load(response)["status"]=="ok"
    with get("/api/session") as response:
        assert json.load(response)["authenticated"] is True
    print("HTTP client disconnect during SSE; Console remains responsive: PASS", flush=True)
    print("P2.3 ISOLATED DOCKER HTTP SMOKE: PASS", flush=True)
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("P2.3 ISOLATED DOCKER HTTP SMOKE: FAIL:",
              type(exc).__name__,str(exc)[:250],file=sys.stderr)
        sys.exit(1)
