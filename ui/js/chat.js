// Chat: renderização de mensagens, envio e anexos.
import { byId } from './dom.js';
import { State } from './state.js';
import { wsSend, wsReady } from './ws.js';
import { speak } from './voice.js';
import { renderMarkdown, enhanceCodeBlocks } from './markdown.js';

let aiBubble = null;
let attached = [];
let streamRaw = '';   // texto cru acumulado durante o streaming (p/ render final)
let reasoningEl = null;   // bloco colapsável de "raciocínio" (modelos thinking)
let reasoningRaw = '';

const chatEl = () => byId('chat');
function scroll() { const c = chatEl(); c.scrollTop = c.scrollHeight; }

export function addBubble(role, text, extra = '') {
  const w = document.createElement('div'); w.className = 'msg ' + role;
  const b = document.createElement('div'); b.className = 'bubble ' + extra; b.textContent = text;
  w.appendChild(b); chatEl().appendChild(w); scroll(); return b;
}
export function clearChat() { chatEl().innerHTML = ''; aiBubble = null; streamRaw = ''; reasoningEl = null; reasoningRaw = ''; }

// renderiza markdown (+ realce + botões) dentro de uma bolha existente
function renderInto(bubble, text) {
  const { html, blocks } = renderMarkdown(text);
  bubble.classList.add('md');
  bubble.innerHTML = html;
  enhanceCodeBlocks(bubble, blocks, runCode);
}

export function renderMessages(msgs) {
  clearChat();
  (msgs || []).forEach((m) => {
    if (m.role === 'user') { addBubble('user', m.content); }
    else { const b = addBubble('ai', ''); renderInto(b, m.content); }
  });
  scroll();
}

// eventos do WS
/** "pensar" de modelos thinking (ex.: Nemotron): bloco colapsável ANTES da
 *  resposta, que streama enquanto a Aila raciocina e colapsa quando ela responde. */
export function onReasoning(m) {
  if (!reasoningEl) {
    const w = document.createElement('div'); w.className = 'msg ai';
    const box = document.createElement('div'); box.className = 'reasoning open';
    box.innerHTML = '<button class="reasoning-head"><span class="reasoning-ico">💭</span>'
      + '<span class="reasoning-lbl">Raciocínio</span><span class="reasoning-tog">▾</span></button>'
      + '<div class="reasoning-body"></div>';
    box.querySelector('.reasoning-head').onclick = () => box.classList.toggle('open');
    w.appendChild(box); chatEl().appendChild(w);
    reasoningEl = box; reasoningRaw = '';
  }
  reasoningRaw += m.text;
  reasoningEl.querySelector('.reasoning-body').textContent = reasoningRaw;
  scroll();
}
export function onToken(m) {
  if (!aiBubble) {
    if (reasoningEl) reasoningEl.classList.remove('open');   // resposta começou → colapsa o raciocínio
    aiBubble = addBubble('ai', ''); streamRaw = ''; aiBubble.classList.add('streaming');
  }
  streamRaw += m.text;
  aiBubble.textContent = streamRaw;   // durante o stream: texto puro (rápido)
  scroll();
}
export function onMessage(m) {
  const text = m.text ?? streamRaw;
  const bubble = aiBubble || addBubble('ai', '');
  bubble.classList.remove('streaming');
  renderInto(bubble, text);           // ao concluir: markdown + realce + botões
  scroll();
  aiBubble = null; streamRaw = '';
  reasoningEl = null; reasoningRaw = '';   // fim do turno (mantém o bloco no DOM, solta a ref)
  if (State.get('voiceOut') && text) speak(text);
}

// ▶ Executar: manda o código pra Aila rodar (passa pelo fluxo de permissão do backend)
function runCode(code, lang) {
  const verb = lang === 'python' ? 'Rode este código Python' : 'Rode este comando no shell';
  _send(`${verb}:\n\`\`\`${lang}\n${code}\n\`\`\``, `▶ Executar (${lang})`);
  showChatTab();
}
function showChatTab() { const t = byId('tab-chat'); if (t) t.click(); }
export function onTool(text) { addBubble('ai', text, 'tool'); }
export function onSys(text) { addBubble('sys', text); aiBubble = null; }

// envio
function _send(fullText, label) {
  addBubble('user', label);
  aiBubble = null; reasoningEl = null; reasoningRaw = '';
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
