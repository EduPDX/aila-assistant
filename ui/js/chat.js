// Chat: renderização de mensagens, envio e anexos.
import { byId } from './dom.js';
import { State } from './state.js';
import { wsSend, wsReady } from './ws.js';
import { speak } from './voice.js';

let aiBubble = null;
let attached = [];

const chatEl = () => byId('chat');
function scroll() { const c = chatEl(); c.scrollTop = c.scrollHeight; }

export function addBubble(role, text, extra = '') {
  const w = document.createElement('div'); w.className = 'msg ' + role;
  const b = document.createElement('div'); b.className = 'bubble ' + extra; b.textContent = text;
  w.appendChild(b); chatEl().appendChild(w); scroll(); return b;
}
export function clearChat() { chatEl().innerHTML = ''; aiBubble = null; }
export function renderMessages(msgs) {
  clearChat();
  (msgs || []).forEach((m) => addBubble(m.role === 'user' ? 'user' : 'ai', m.content));
}

// eventos do WS
export function onToken(m) { if (!aiBubble) aiBubble = addBubble('ai', ''); aiBubble.textContent += m.text; scroll(); }
export function onMessage(m) {
  if (!aiBubble) addBubble('ai', m.text);
  aiBubble = null;
  if (State.get('voiceOut') && m.text) speak(m.text);
}
export function onTool(text) { addBubble('ai', text, 'tool'); }
export function onSys(text) { addBubble('sys', text); aiBubble = null; }

// envio
function _send(fullText, label) {
  addBubble('user', label);
  aiBubble = null;
  wsSend({ type: 'user.message', text: fullText, mode: 'auto' });
}
/** envia um texto simples (usado pelo microfone) */
export function sendUserText(t) { if (!t || !wsReady()) return; _send(t, t); }

export function send() {
  const input = byId('input');
  const t = input.value.trim();
  if (!t && !attached.length) return;
  let payload = '';
  for (const a of attached) {
    payload += `\n[Anexo: ${a.name} — salvo no workspace em: ${a.path}]\n`;
    payload += (a.text != null)
      ? '```\n' + a.text.slice(0, 20000) + '\n```\n'
      : '(arquivo binário; use os agentes de arquivo/binário para inspecioná-lo)\n';
  }
  const full = (payload ? payload + '\n' : '') + t;
  const label = attached.map((a) => '📎 ' + a.name).join('  ') + (t ? (attached.length ? '\n' : '') + t : '');
  _send(full, label || '(anexos)');
  input.value = ''; input.style.height = 'auto';
  attached = []; renderChips();
}

// anexos
function renderChips() {
  byId('attachments').innerHTML = attached
    .map((a, i) => `<span class="chip">📎 ${a.name}<button data-i="${i}" title="remover">✕</button></span>`)
    .join('');
  byId('attachments').querySelectorAll('button').forEach((b) =>
    b.onclick = () => { attached.splice(+b.dataset.i, 1); renderChips(); });
}
export async function attachFiles(files, onDone) {
  for (const f of files) {
    const fd = new FormData(); fd.append('file', f, f.name);
    try { const j = await (await fetch('/api/upload/file', { method: 'POST', body: fd })).json(); if (j.path) attached.push(j); }
    catch (e) { onSys('falha ao anexar ' + f.name); }
  }
  renderChips(); if (onDone) onDone();
}
