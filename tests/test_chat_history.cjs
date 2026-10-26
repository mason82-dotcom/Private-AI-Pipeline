"use strict";
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../console/static/app.js'),'utf8');
// Evaluate actual frontend logic with inert DOM/network stubs, not a copied function.
const ctx={
  document:{addEventListener(){},querySelector(){return {addEventListener(){}};}},
  fetch(){return new Promise(()=>{});},
  clearTimeout,setTimeout,
};
vm.runInNewContext(source+'\nglobalThis.__buildChatMessages=buildChatMessages;globalThis.__chunkText=chunkText;globalThis.__extractEvents=extractEvents;',ctx);
const build=ctx.__buildChatMessages;
const user=content=>({role:'user',content});
const assistant=(content,failed=false)=>failed?({role:'assistant',content,failed}):({role:'assistant',content});
const send=(history,prompt)=>JSON.parse(JSON.stringify(build(history,prompt)));
assert.deepEqual(send([], 'Ping'),[user('Ping')]);
assert.deepEqual(send([user('Ping'),assistant('')],'2+2'),[user('2+2')]);
assert.deepEqual(send([user('Ping'),assistant('Antwort fehlgeschlagen: Timeout',true)],'2+2'),[user('2+2')]);
assert.deepEqual(send([user('Ping'),assistant('Teilantwort',true)],'2+2'),[user('2+2')]);
assert.deepEqual(send([user('Hallo'),assistant('Hi'),user('Ping'),assistant('')], '2+2'),[user('Hallo'),assistant('Hi'),user('2+2')]);
assert.deepEqual(send([user('Hallo'),assistant('('),user('Was ist 2+2?'),assistant('4')],'Danke'),[user('Hallo'),assistant('('),user('Was ist 2+2?'),assistant('4'),user('Danke')]);
const big=Array.from({length:40},(_,i)=>[user('Frage '+i),assistant('Antwort '+i)]).flat();
const payload=send(big,'Neu');
assert.equal(payload.length,31);
assert.equal(payload[0].content,'Frage 25');
assert.equal(payload.at(-1).content,'Neu');
assert.ok(payload.every(m=>m.content.trim().length>0));
const ragEvent='event: rag_sources\ndata: '+JSON.stringify({sources:[{id:'Q1',source:'upload:abc#0',excerpt:'Test'}]});
const parsed=ctx.__chunkText(ragEvent);
assert.equal(parsed.sources[0].id,'Q1');
assert.equal(ctx.__chunkText('data: [DONE]').done,true);
assert.equal(ctx.__chunkText('data: {"choices":[{"delta":{"content":"ok"}}]}').text,'ok');
const ragPair=ctx.__extractEvents(ragEvent+'\n\ndata: [DONE]\n\n',false);
assert.equal(ragPair.events.length,2);
assert.equal(ragPair.buffer,'');
console.log('Chat context and RAG SSE regression tests OK (11 cases)');
