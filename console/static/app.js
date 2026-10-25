'use strict';
// This frontend never knows PIPELINE_TOKEN. All requests are same-origin and authenticated.
const $ = sel => document.querySelector(sel);
const state = { view:'overview',tab:{knowledge:'documents',system:'services'},csrf:null,status:null,models:[],modelsError:null,modelsChecked:null,model:null,history:[],busy:false,abort:null,checked:null,knowledge:{documents:[],memories:[],results:[],error:null,loading:false,importEnabled:false,scope:null,query:''} };
const labels={overview:'Übersicht',chat:'Chat',knowledge:'Wissen & Gedächtnis',agents:'Agenten',system:'System'};
const navigation=[['overview','Übersicht'],['chat','Chat'],['knowledge','Wissen & Gedächtnis'],['agents','Agenten'],['system','System'],['system:models','Modelle'],['system:backups','Sicherungen']];
const html=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let timer;
function toast(s){const el=$('#toast');el.textContent=s;el.classList.add('visible');clearTimeout(timer);timer=setTimeout(()=>el.classList.remove('visible'),3800)}
function flag(s,ok){return `<span class="flag ${ok===true?'ok':ok===false?'bad':''}">${html(s)}</span>`}
function card(name,value,desc,cls=''){return `<article class="card metric"><span>${html(name)}</span><strong class="${cls}">${html(value)}</strong><small>${html(desc)}</small></article>`}
function title(a,b){return `<div class="page-head"><div><div class="eyebrow">PRIVATE AI / LIGHT CONSOLE · P1/P2</div><h1>${html(a)}</h1><p>${html(b)}</p></div></div>`}
function tabs(area,values){return `<div class="tabs" role="tablist" aria-label="${html(labels[area])}">${values.map(([key,label])=>`<button type="button" role="tab" data-tab="${html(key)}" data-area="${area}" aria-selected="${state.tab[area]===key}" class="${state.tab[area]===key?'active':''}">${html(label)}</button>`).join('')}</div>`}
function planned(name,explanation){return `<div class="readonly-note">Konzept / noch nicht angebunden · Schreibzugriffe sind gesperrt.</div><section class="card planned"><div class="planned-icon" aria-hidden="true">◇</div><h2>${html(name)}</h2><p>${html(explanation)}</p>${flag('Geplant · keine Live-Daten')}</section>`}
function modelObserved(){return state.status?.checks?.inference?.observed_at||state.modelsChecked;}
function checkedLabel(){return state.status?.observed_at?new Date(state.status.observed_at).toLocaleString('de-DE'):'Nicht geprüft'}
function render(){
  document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===state.view));
  $('#crumb').textContent=labels[state.view];
  const box=$('#main');
  if(state.view==='overview'){
    const gateway=state.status?.gateway||'Ungeprüft';
    const modelState=state.status?.inference==='unreachable'?'Nicht erreichbar':state.status?.inference==='no_models'?'Keine installiert':state.status?.inference==='ok'?`${state.models.length} gemeldet`:'Nicht geprüft';
    box.innerHTML=title('Übersicht','Handlungsorientierter Status für das lokale System; keine erfundenen Live-Daten.')+
      `<div class="warning" ${gateway==='ok'&&state.status?.inference==='ok'&&!state.modelsError?'hidden':''}><strong>Jetzt wichtig:</strong> ${gateway!=='ok'?'Gateway nicht erreichbar. Lokalen Dienst prüfen.':state.status?.inference==='no_models'?'Modellhost erreichbar, aber keine Modelle installiert.':state.status?.inference!=='ok'||state.modelsError?'Lokalen Modellhost prüfen. Kein Cloud-Fallback.':'Keine offenen Verbindungsprobleme gemeldet.'} <button class="subtle" data-go="system">Diagnose ansehen</button></div>`+
      `<div class="metrics">${card('Console','Angemeldet','Authentifizierte Sitzung')}${card('Gateway',gateway,'Quelle: /health')}${card('Lokale Modelle',modelState,'Quelle: Gateway /v1/models')}${card('Projekt-Kontext','Einzelinstanz','Projektbasierte Rechte noch nicht angebunden')}</div>`+
      `<div class="columns"><section class="card"><h2>Verbindungsstatus</h2>${statusRows()}<p class="status-time">Gateway geprüft: ${html(checkedLabel())}<br>Modellhost geprüft: ${html(modelObserved()?new Date(modelObserved()).toLocaleString('de-DE'):'Nicht geprüft')}</p><p class="hint">Der Systemstatus ist kein Nachweis einer Offline-Firewall, eines funktionierenden Backups oder einer serverseitigen Projektisolation.</p></section><section class="card"><h2>Schnellaktionen</h2><button class="action" data-go="chat">Lokalen Chat öffnen <span>→</span></button><button class="action" data-go="system:models">Lokale Modelle ansehen <span>→</span></button><button class="action" data-go="system">Verbindungsdetails prüfen <span>→</span></button></section></div>`;
  } else if(state.view==='chat'){
    box.innerHTML=title('Chat','Flüchtige Unterhaltung mit dem lokalen Modell. Eine eigene Chat-Historie wird nicht dauerhaft gespeichert.')+
    `<div class="readonly-note">Einzelinstanz; aktuell kein echter Projektfilter. Der bestehende Open-WebUI-Chatverlauf wird separat von Open WebUI verwaltet.</div>`+
    `<section class="card chat"><div class="chatbar"><span>${flag(state.modelsError?'Modellliste offline':state.models.length?'Modell vorhanden':'Kein Modell gemeldet',state.modelsError?false:state.models.length>0)}</span><select id="model" aria-label="Lokales Sprachmodell auswählen">${state.models.map(m=>`<option value="${html(m.id)}" ${state.model===m.id?'selected':''}>${html(m.id)}</option>`).join('')}</select></div>
    <div class="messages" id="messages" aria-live="polite">${state.history.length?state.history.map(m=>`<div class="msg ${m.role}"><span>${m.role==='user'?'Sie':'Lokales Modell'}</span><div>${html(m.content)}</div></div>`).join(''):'<div class="empty">Noch keine Nachrichten. Wählen Sie ein lokales Modell und stellen Sie eine Frage.</div>'}</div>
    <form id="chatForm"><label for="prompt" class="sr">Nachricht</label><textarea id="prompt" maxlength="4000" placeholder="Frage an Ihr lokales Modell …" required></textarea><div class="chat-actions"><span>Kein Cloud-Fallback · lokaler Browser-Sitzungsverlauf</span><button type="button" id="stop" ${state.busy?'':'hidden'}>Stoppen</button><button class="primary" id="send" type="submit" ${!state.model||state.busy?'disabled':''}>${state.busy?'Antwort läuft …':'Senden →'}</button></div></form></section>`;
    const messages=$('#messages');messages.scrollTop=messages.scrollHeight;
  } else if(state.view==='knowledge'){
    const t=tabs('knowledge',[['documents','Dokumente'],['memory','Erinnerungen']]);
    const k=state.knowledge, memory=state.tab.knowledge==='memory';
    let content='';
    if(k.loading)content='<section class="card empty" role="status">Wissensdaten werden lokal geladen …</section>';
    else if(k.error)content=`<section class="card empty"><strong>Wissensdienst nicht verfügbar</strong><p>${html(k.error)}</p><button class="subtle" id="retryKnowledge">Erneut versuchen</button></section>`;
    else if(memory)content=`<section class="card"><div class="section-head"><h2>Gespeicherte Erinnerungen · ${html(k.scope||'Einzelinstanz')}</h2>${flag('Nur lesen')}</div><p class="hint">Keine automatische Mitschrift; Bearbeiten und Löschen nicht über diese Oberfläche freigeschaltet.</p><label class="field-label" for="knowledgeQuery">Erinnerungen durchsuchen</label><input id="knowledgeQuery" maxlength="200" placeholder="Suchbegriff" value="${html(k.query)}"/><button class="subtle" id="searchKnowledge">Suchen</button>${k.memories.length?k.memories.map(m=>`<article class="memory-row"><strong>${html(m.source)}</strong><p>${html(m.body)}</p></article>`).join(''):'<p class="empty">Keine Erinnerungen gefunden.</p>'}</section>`;
    else content=`<section class="card"><div class="section-head"><h2>Lokale Wissensdokumente · ${html(k.scope||'Einzelinstanz')}</h2>${flag(k.importEnabled?'Import freigeschaltet':'Import gesperrt')}</div><p class="hint">Indizierte UTF-8-Texte und textbasierte PDFs (max. 1 MiB, 16 Seiten). Gescannte PDFs benötigen eine spätere OCR-Erweiterung.</p><div class="knowledge-actions"><label for="knowledgeQuery" class="sr">Dokumentinhalt suchen</label><input id="knowledgeQuery" maxlength="200" placeholder="Quellen durchsuchen …" value="${html(k.query)}"><button id="searchKnowledge" class="subtle">Suchen</button>${k.importEnabled?'<label class="import-button">Datei importieren <input type="file" id="importFile" accept=".md,.txt,.rst,.pdf,text/plain,application/pdf" /></label>':''}</div><div class="knowledge-table" role="list">${k.documents.length?k.documents.map(d=>`<div class="document-row" role="listitem"><span class="file-icon">▤</span><span><strong>${html(d.filename)}</strong><small>ID ${html(d.id)} · ${html(d.chunks)} Textabschnitte · ${html(d.format||'text')} · ${html(d.imported_at)}</small></span>${flag('Indiziert',true)}</div>`).join(''):'<p class="empty">Noch keine Dokumente importiert.</p>'}</div>${k.results.length?`<h2>Fundstellen</h2>${k.results.map(r=>`<div class="memory-row"><strong>${html(r.filename||r.source)}${Number.isInteger(r.page)?' · Seite '+r.page:''}</strong><small>${html(r.source)}</small><p>${html(r.excerpt)}</p></div>`).join('')}`:''}</section>`;
    box.innerHTML=title('Wissen & Gedächtnis','Lokale Quellen und bewusst gespeicherte Erinnerungen. Zugriff ausschließlich für die konfigurierte Einzelinstanz.')+t+`<div class="readonly-note">Keine projektübergreifende Multiuser-Freigabe. Schreibende Memory-Funktionen bleiben deaktiviert.</div>`+content;
  } else if(state.view==='agents'){
    box.innerHTML=title('Agenten','MCP-Clients und Werkzeuge benötigen serverseitig erzwungene, projektbezogene Richtlinien.')+
      `<div class="readonly-note">Standard: READ nur innerhalb ausdrücklich erlaubter Bereiche. WRITE, EXEC und NETWORK bleiben gesperrt. Diese Ansicht allein erzwingt keine Sicherheitsrichtlinie.</div>`+
      `<section class="card"><h2>Werkzeugberechtigungen – Zielkonzept, nicht Live-Zustand</h2>${[['Lesen','Nur nach Scope-Prüfung'],['Schreiben','Nicht freigeschaltet'],['Befehle ausführen','Nicht freigeschaltet'],['Netzwerk','Nicht freigeschaltet']].map(([a,b])=>`<div class="keyline"><span>${html(a)}</span>${flag(b)}</div>`).join('')}</section>`;
  } else if(state.view==='system'){
    const t=tabs('system',[['services','Dienste'],['models','Modelle'],['network','Netzwerk'],['backups','Sicherungen'],['settings','Einstellungen']]);
    let content='';
    if(state.tab.system==='services')content=`<div class="columns"><section class="card"><h2>Geprüfte Verbindungen</h2>${statusRows()}<p class="status-time">${diagnosticsDetail()}</p></section><section class="card"><h2>Grenzen der Diagnose</h2><div class="keyline"><span>Gateway-Token</span>${flag('Nur serverseitig')}</div><div class="keyline"><span>Schreibende Memory-API</span>${flag('Nicht exponiert')}</div><div class="keyline"><span>Pi-Ressourcen</span>${flag('Nicht erhoben')}</div><div class="keyline"><span>Firewall-Egress</span>${flag('Nicht auditiert')}</div></section></div>`;
    if(state.tab.system==='models')content=`<section class="card"><div class="section-head"><h2>Von der lokalen Gateway-API gemeldete Modelle</h2>${flag(state.modelsError?'Abfrage fehlgeschlagen':`${state.models.length} gemeldet`,state.modelsError?false:null)}</div>${state.modelsError?'<p class="empty">Keine Modellliste erreichbar. Gateway und Ollama prüfen.</p>':state.models.length?state.models.map(m=>`<button class="model" data-model="${html(m.id)}"><span><strong>${html(m.id)}</strong><small>Quelle: lokale Gateway-Modellliste</small></span><span>${state.model===m.id?flag('Ausgewählt',true):'Auswählen →'}</span></button>`).join(''):'<p class="empty">Keine Modelle gemeldet.</p>'}</section>`;
    if(state.tab.system==='network')content=planned('Netzwerknachweis steht aus','Das Gateway wird auf ein explizites lokales Ziel konfiguriert. Das UI kann aus dieser Konfiguration keine tatsächliche WAN-Isolation nachweisen. Dafür ist ein Host-Egress-Test erforderlich.');
    if(state.tab.system==='backups')content=planned('Sicherungen nicht live angebunden','Erst ein geprüfter Restore-Test belegt die Wiederherstellbarkeit. Backup- und Restore-Status bleiben bis zur echten Integration unbekannt.');
    if(state.tab.system==='settings')content=planned('Administrative Einstellungen gesperrt','Die Oberfläche hat noch keine autorisierte API zum Ändern von Infrastruktur, Modellen oder Berechtigungen. Änderungen erfolgen weiterhin durch den Betreiber in der lokalen Konfiguration.');
    box.innerHTML=title('System','Dienste, Modelle und Betriebsnachweise – mit expliziten Grenzen der Messung.')+t+content;
  }

}
function diagnosticsDetail(){
 const checks=state.status?.checks||{};
 return ['gateway','inference'].map(key=>{const c=checks[key];if(!c)return (key==='gateway'?'Gateway':'Modellhost')+': nicht geprüft';const t=Date.parse(c.observed_at);const stale=!Number.isFinite(t)||Date.now()-t>60000;return `${key==='gateway'?'Gateway':'Modellhost'} · ${html(c.source)} · ${html(new Date(c.observed_at).toLocaleString('de-DE'))} · ${Number.isFinite(c.latency_ms)?c.latency_ms+' ms':'Laufzeit unbekannt'}${stale?' · VERALTET':''}`}).join('<br>');
}
function statusRows(){const gs=state.status?.gateway||'Nicht geprüft';const im=state.status?.inference||'not_checked';const ms={'ok':'Erreichbar','no_models':'Erreichbar, keine Modelle','unreachable':'Nicht erreichbar','not_checked':'Nicht geprüft'}[im]||'Unbekannt';return [['Light Console','Authentifiziert',true],['Gateway',gs,gs==='ok'?true:gs==='unreachable'?false:null],['Ollama-Modellserver',ms,im==='ok'||im==='no_models'?true:im==='unreachable'?false:null],['SQLite / MCP','Nicht abgefragt',null]].map(([n,v,s])=>`<div class="keyline"><span>${html(n)}</span>${flag(v,s)}</div>`).join('')}

async function fetchJSON(url,options){const r=await fetch(url,{credentials:'same-origin',cache:'no-store',...options});if(r.status===401){location.replace('/');throw Error('Sitzung abgelaufen')}const x=await r.json();if(!r.ok)throw Error(x.error||'Lokaler Fehler');return x}
async function loadKnowledge(query=''){
  const k=state.knowledge;
  k.loading=true;k.error=null;k.query=query;render();
  try {
    const kind=state.tab.knowledge==='memory'?'memory':'documents';
    const result=await fetchJSON('/api/knowledge?'+new URLSearchParams({kind,q:kind==='memory'?query:''}));
    k.scope=result.namespace;k.importEnabled=Boolean(result.import_enabled);
    k.documents=result.documents||k.documents;
    k.memories=result.memories||k.memories;
    k.results=[];
    if(kind==='documents'&&query){const found=await fetchJSON('/api/knowledge?'+new URLSearchParams({kind:'search',q:query}));k.results=found.results||[];}
  } catch(e){k.error=e.message;} finally{k.loading=false;render();}
}
async function importText(file){
  if(!file)return;
  const pdf=/\.pdf$/i.test(file.name);
  if(!(/\.(md|txt|rst)$/i.test(file.name)||pdf) || file.size>(pdf?1024*1024:48*1024)){toast('Text bis 48 KiB oder textbasiertes PDF bis 1 MiB');return;}
  try{
    let payload;
    if(pdf){
      const bytes=new Uint8Array(await file.arrayBuffer());
      if(bytes.length<16||String.fromCharCode(...bytes.subarray(0,5))!=='%PDF-')throw Error('Keine gültige PDF-Datei');
      let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
      payload={filename:file.name,pdf_base64:btoa(binary)};
    }else{
      const content=await file.text();
      if(content.includes('\uFFFD')||content.includes('\u0000'))throw Error('Datei ist kein gültiger UTF-8-Text');
      payload={filename:file.name,content};
    }
    const response=await fetchJSON('/api/documents/import',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify(payload)});
    toast(response.duplicate?'Dokument bereits vorhanden':'Dokument indiziert');
    await loadKnowledge();
  }catch(e){toast(e.message);}
}
async function refresh(){const [a,b]=await Promise.allSettled([fetchJSON('/api/status'),fetchJSON('/api/models')]);
  state.status=a.status==='fulfilled'?a.value:{gateway:'unreachable',inference:'not_checked',source:'request_failed',observed_at:null};
  state.modelsError=b.status==='rejected'?b.reason?.message||'Nicht erreichbar':null;
  state.models=b.status==='fulfilled'?b.value.models:[];
  state.modelsChecked=b.status==='fulfilled'?b.value.observed_at||null:null;
  if(!state.models.find(m=>m.id===state.model))state.model=state.models[0]?.id||null;
  state.checked=new Date().toLocaleTimeString('de-DE');render();
  if(state.modelsError)toast('Modellliste offline – keine Cloud-Ausweichroute');
}

// Only complete, successful user/assistant turns belong in a new inference request.
// Failed, aborted, and still-empty model placeholders remain visible in the UI,
// but must never be replayed to the Gateway (which rejects empty messages).
function buildChatMessages(history, prompt){
  const complete=[];
  for(let i=0;i+1<history.length;i+=2){
    const user=history[i],assistant=history[i+1];
    if(user?.role!=='user'||assistant?.role!=='assistant'||assistant.failed)continue;
    if(typeof user.content!=='string'||!user.content.trim()||typeof assistant.content!=='string'||!assistant.content.trim())continue;
    complete.push({role:'user',content:user.content},{role:'assistant',content:assistant.content});
  }
  return [...complete.slice(-30),{role:'user',content:prompt}];
}

function extractEvents(buffer,flush){const out=[];let index;while((index=buffer.indexOf('\n\n'))!==-1){out.push(buffer.slice(0,index));buffer=buffer.slice(index+2)}if(flush&&buffer.trim())out.push(buffer);return {events:out,buffer}}
function chunkText(evt){for(const line of evt.split('\n')){if(!line.startsWith('data:'))continue;const v=line.slice(5).trim();if(v==='[DONE]')return {done:true};try{const msg=JSON.parse(v);const delta=msg.choices?.[0]?.delta?.content;if(typeof delta==='string')return {text:delta};}catch{throw Error('Ungültiges SSE-Paket')}}return {text:''}}
async function chatSend(e){e.preventDefault();if(state.busy||!state.model)return;const prompt=$('#prompt').value.trim();if(!prompt)return;
  const prior=buildChatMessages(state.history,prompt);
  state.history.push({role:'user',content:prompt},{role:'assistant',content:''});state.busy=true;const ctrl=new AbortController();state.abort=ctrl;render();
  try{
    const response=await fetch('/api/chat',{method:'POST',credentials:'same-origin',signal:ctrl.signal,headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify({model:state.model,messages:prior})});
    if(!response.ok){let reason='Lokaler Modellfehler';try{reason=(await response.json()).error||reason}catch{};throw Error(reason)}
    if(!response.body)throw Error('Streaming wird vom Browser nicht unterstützt');
    const reader=response.body.getReader(),decoder=new TextDecoder();let carry='',finished=false,received=0;
    while(!finished){const {value,done}=await reader.read();if(done)break;carry+=decoder.decode(value,{stream:true});carry=carry.replace(/\r\n/g,'\n');received+=value.length;
      if(received>8*1024*1024)throw Error('Antwort zu umfangreich');
      const parsed=extractEvents(carry,false);carry=parsed.buffer;
      for(const evt of parsed.events){const chunk=chunkText(evt);if(chunk.done){finished=true;break}if(chunk.text)state.history[state.history.length-1].content+=chunk.text}
      const msgs=$('#messages');if(msgs){const last=msgs.querySelector('.msg:last-child div');if(last)last.textContent=state.history[state.history.length-1].content;msgs.scrollTop=msgs.scrollHeight;}
    }
    if(!finished)throw Error('Antwortstream unvollständig; Ausgabe möglicherweise gekürzt.');
  }catch(err){
      const assistant=state.history[state.history.length-1];
      assistant.failed=true;
      if(err.name==='AbortError'){
        assistant.content ||= 'Antwort abgebrochen.';
      }else{
        // Never replay an error string or a truncated partial response as model output.
        assistant.content += (assistant.content?'\n':'')+'Antwort fehlgeschlagen: '+err.message;
        toast(err.message);
      }
    }
  finally {state.busy=false;state.abort=null;render()}
}
function closeMobile(){const rail=$('#rail');rail.classList.remove('open');$('#menu').setAttribute('aria-expanded','false');$('#scrim').hidden=true}
function navigate(view){
  if(state.abort)state.abort.abort();
  const [page,tab]=view.split(':');
  if(!labels[page])return;
  if(tab&&page==='system'&&['services','models','network','backups','settings'].includes(tab))state.tab.system=tab;
  if(tab&&page==='knowledge'&&['documents','memory'].includes(tab))state.tab.knowledge=tab;
  state.view=page;closeMobile();render();if(page==='knowledge')loadKnowledge();$('#main').focus();
}
function openPalette(){const palette=$('#palette');if(!palette.open)palette.showModal();$('#paletteQuery').value='';renderPalette();$('#paletteQuery').focus()}
function renderPalette(){const q=$('#paletteQuery').value.trim().toLocaleLowerCase('de-DE');const found=navigation.filter(([,name])=>name.toLocaleLowerCase('de-DE').includes(q));$('#paletteResults').innerHTML=found.length?found.map(([path,name])=>`<button type="button" data-find="${path}">${html(name)} <span aria-hidden="true">→</span></button>`).join(''):'<p class="empty">Keine Ansicht gefunden.</p>'}
document.addEventListener('click',e=>{
  const nav=e.target.closest('[data-view],[data-go]');if(nav)navigate(nav.dataset.view||nav.dataset.go);
  const tab=e.target.closest('[data-tab]');if(tab&&state.tab[tab.dataset.area]){state.tab[tab.dataset.area]=tab.dataset.tab;render();if(tab.dataset.area==='knowledge')loadKnowledge();}
  const route=e.target.closest('[data-find]');if(route){$('#palette').close();navigate(route.dataset.find)}
  const m=e.target.closest('[data-model]');if(m){state.model=m.dataset.model;render();toast('Modell ausgewählt');}
  if(e.target.id==='stop')state.abort?.abort();
  if(e.target.id==='retryKnowledge')loadKnowledge();
  if(e.target.id==='searchKnowledge')loadKnowledge($('#knowledgeQuery')?.value?.trim()||'');
});
document.addEventListener('change',e=>{if(e.target.id==='model')state.model=e.target.value;if(e.target.id==='importFile')importText(e.target.files?.[0]);});
document.addEventListener('submit',e=>{if(e.target.id==='chatForm')chatSend(e)});
document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openPalette();}
  if(e.key==='Escape'&&$('#rail').classList.contains('open')){closeMobile();$('#menu').focus();}
  if(e.key==='Enter'&&document.activeElement===$('#paletteQuery')&&$('#palette').open){const first=$('#paletteResults [data-find]');if(first){e.preventDefault();first.click()}}
});
$('#paletteQuery').addEventListener('input',renderPalette);
$('#quick').addEventListener('click',openPalette);
$('#closePalette').addEventListener('click',()=>$('#palette').close());
$('#palette').addEventListener('click',e=>{if(e.target===$('#palette'))$('#palette').close()});
$('#refresh').addEventListener('click',refresh);
$('#menu').addEventListener('click',()=>{const expanded=$('#rail').classList.toggle('open');$('#menu').setAttribute('aria-expanded',String(expanded));$('#scrim').hidden=!expanded});
$('#scrim').addEventListener('click',closeMobile);
$('#logout').addEventListener('click',async()=>{try{await fetchJSON('/api/logout',{method:'POST',headers:{'X-CSRF-Token':state.csrf}})}catch{}location.replace('/')});
(async()=>{try{const session=await fetchJSON('/api/session');state.csrf=session.csrf;await refresh()}catch(e){toast(e.message)}})();
