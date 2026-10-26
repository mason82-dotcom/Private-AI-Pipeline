'use strict';
const form = document.getElementById('login');
form.addEventListener('submit', async ev => {
  ev.preventDefault();
  const submit=form.querySelector('button'); submit.disabled=true;
  const err=document.getElementById('error');err.textContent='';
  const password=document.getElementById('pw').value;
  try {
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({password})});
    if (!r.ok) throw Error(r.status===429?'Zu viele Versuche. Bitte später erneut anmelden.':'Passwort ungültig.');
    document.getElementById('pw').value='';
    location.replace('/');
  } catch(e) { err.textContent=e.message || 'Verbindung fehlgeschlagen'; }
  finally {submit.disabled=false;}
});
