"use strict";
/* P2.3 executable UI integration harness: actual app.js, inert DOM + streaming fetch.
   This is not a real browser / Playwright / Docker test. All sources are synthetic. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const listeners = {};
const nodes = new Map();
let chatFetch;
let assertions = 0;
function check(condition, msg) { assert.ok(condition, msg); assertions++; }
function element(key) {
  if (!nodes.has(key)) {
    const classes = new Set();
    nodes.set(key, {
      id: key, value: "", textContent: "", innerHTML: "", hidden: false,
      disabled: false, checked: false, scrollHeight: 0, scrollTop: 0,
      dataset: {}, focus() {}, setAttribute() {},
      addEventListener() {},
      classList: {add(x) {classes.add(x)}, remove(x) {classes.delete(x)},
                  toggle(x) {if(classes.has(x)){classes.delete(x);return false}
                             classes.add(x);return true},
                  contains(x) {return classes.has(x)}},
      querySelector() {return element(key + "/child")}
    });
  }
  return nodes.get(key);
}
const dom = {
  querySelector: element,
  querySelectorAll() {return []},
  addEventListener(type, handler) {listeners[type] = handler},
  activeElement: null
};
const source = fs.readFileSync(path.join(__dirname, "../console/static/app.js"), "utf8");
const context = {
  document: dom, location: {replace() {}},
  fetch(url, opts) {
    if (url === "/api/chat" && chatFetch) return chatFetch(opts);
    return new Promise(() => {}); // Suppress automatic boot refresh.
  },
  TextDecoder, TextEncoder, AbortController, URLSearchParams,
  clearTimeout, setTimeout, console
};
vm.runInNewContext(
  source + "\nglobalThis.__ui={state,render,chatSend,chunkText,extractEvents,buildChatMessages};",
  context, {filename: "app.js"});
const ui = context.__ui;

function display() {return element("#main").innerHTML}
function goToChat() {
  ui.state.view = "chat";
  ui.state.models = [{id:"qwen3:0.6b"}];
  ui.state.model = "qwen3:0.6b";
  ui.state.rag.enabled = true;
  ui.state.rag.active = true;
  ui.state.rag.mode = "fts";
  ui.state.busy = false;
}
function httpStream(events, options) {
  const encoded = new TextEncoder().encode(events);
  const mid = Math.floor(encoded.length / 3);
  const parts = [encoded.slice(0, mid), encoded.slice(mid, mid+2), encoded.slice(mid+2)];
  return {
    ok: true, status: 200,
    body: {getReader() {
      let i = 0;
      return {async read() {
        if (options?.abortSignal?.aborted)
          throw Object.assign(new Error("Aborted"), {name:"AbortError"});
        if (i < parts.length) return {done:false,value:parts[i++]};
        return {done:true};
      }};
    }}
  };
}
async function main() {
  goToChat();
  ui.state.rag.enabled = false;
  ui.state.rag.active = false;
  ui.render();
  check(display().includes('Mit Dokumenten antworten (gesperrt)'), "RAG disabled label");
  check(/id="ragToggle"[^>]*disabled/.test(display()), "disabled RAG checkbox");
  ui.state.rag.enabled = true;
  ui.state.rag.active = true;
  ui.render();
  check(/id="ragToggle"[^>]*checked/.test(display()), "RAG opt-in checkbox");
  check(display().includes('value="semantic"'), "Semantic search choice");

  // Source filename and excerpt must be HTML-escaped; citation has page.
  ui.state.history = [
    {role:"user",content:"Hydraulik?"},
    {role:"assistant",content:"Die Pumpe erzeugt Öldruck. [Q1]",
     sources:[{id:"Q1",source:"pdf:abc:p2#0",
               filename:'test<img src=x onerror="alert(1)">.pdf',
               page:2,excerpt:"A & B <script>alert('x')</script>"}]}
  ];
  ui.render();
  check(display().includes("nicht automatisch verifiziert"), "retrieval disclaimer");
  check(display().includes("Seite 2"), "PDF page displayed");
  check(display().includes("&lt;img"), "filename escaped");
  check(display().includes("&lt;script&gt;"), "excerpt escaped");
  check(!display().includes("<script>alert"), "injected markup not parsed in template");

  // Parse chunks split inside JSON and multibyte Unicode, and check RAG metadata.
  ui.state.history = [];
  ui.state.csrf = "test-csrf";
  element("#prompt").value = "Was macht die Hydraulikpumpe?";
  const event = 'event: rag_sources\ndata: '+JSON.stringify({
    sources:[{id:"Q1",source:"pdf:abc:p2#0",filename:"handbuch.pdf",
              page:2,excerpt:"Die Pumpe erzeugt Öldruck."}]
  })+'\n\n'
     +'data: {"choices":[{"delta":{"content":"Öldruck [Q1]"}}]}\n\n'
     +'data: [DONE]\n\n';
  let sent;
  chatFetch = opts => {sent=JSON.parse(opts.body);return Promise.resolve(httpStream(event))};
  await ui.chatSend({preventDefault() {}});
  check(sent.rag===true && sent.rag_mode==="fts", "opt-in request options");
  check(sent.messages.length===1 && sent.messages[0].role==="user", "chat request");
  check(ui.state.history[1].content==="Öldruck [Q1]", "stream assembled");
  check(ui.state.history[1].sources[0].page===2, "source attached");
  check(ui.state.history[1].failed!==true, "completed response kept");
  check(!ui.state.busy && ui.state.abort===null, "UI reset after completion");

  // Abort a pending read, mark that assistant turn failed and do not replay it.
  element("#prompt").value = "Stopptest";
  chatFetch = opts => Promise.resolve({
    ok:true,status:200,
    body:{getReader(){return {read(){return new Promise((resolve,reject)=>{
      if(opts.signal.aborted) {
        reject(Object.assign(new Error("aborted"),{name:"AbortError"}));return;
      }
      opts.signal.addEventListener("abort",()=>reject(Object.assign(
        new Error("aborted"),{name:"AbortError"})),{once:true});
    })}}}}
  });
  const task = ui.chatSend({preventDefault() {}});
  check(Boolean(ui.state.abort), "abort controller exposed while streaming");
  ui.state.abort.abort();
  await task;
  check(ui.state.history.at(-1).failed===true, "aborted completion fails closed");
  check(ui.state.history.at(-1).content.includes("abgebrochen"), "abort visible");
  check(!ui.state.busy && ui.state.abort===null, "UI resets after abort");
  const next = JSON.parse(JSON.stringify(ui.buildChatMessages(ui.state.history, "Nächste Frage")));
  check(next.length===3, "aborted turn excluded from context");
  check(next.at(-1).content==="Nächste Frage", "new question retained");

  // An incomplete upstream stream must never be marked as a successful response.
  element("#prompt").value="Kaputter Stream";
  chatFetch = () => Promise.resolve(httpStream(
    'data: {"choices":[{"delta":{"content":"Teilantwort"}}]}\n\n'));
  await ui.chatSend({preventDefault() {}});
  check(ui.state.history.at(-1).failed===true, "missing DONE marks failure");
  check(ui.state.history.at(-1).content.includes("unvollständig"), "truncated SSE diagnostic");
  console.log("P2.3 browser-DOM harness: PASS ("+assertions+" assertions)");
}
main().catch(error=>{console.error(error);process.exitCode=1});
