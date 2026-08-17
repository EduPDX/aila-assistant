// Chat: renderização de mensagens, envio e anexos.
import { byId } from './dom.js';
import { State } from './state.js';
import { wsSend, wsReady } from './ws.js';
import { speak } from './voice.js';
import { renderMarkdown, enhanceCodeBlocks } from './markdown.js';
import { api } from './core/api.js';

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

// classificação de anexo por extensão → roteia p/ a ferramenta certa
const RE_IMG = /\.(png|jpe?g|gif|webp|bmp|tiff?)$/i;
const RE_DOC = /\.(pdf|docx?|xlsx?|pptx?|csv|md|markdown|txt|rtf|odt|json|log)$/i;
const attachIcon = (a) => (a.folder ? '📁' : RE_IMG.test(a.name) ? '🖼' : RE_DOC.test(a.name) ? '📄' : '📎');

/** Dica para a IA saber COMO ler cada anexo (Document Agent / Vision / texto). */
function attachHint(a) {
  const n = a.name, p = a.path;
  if (a.folder)                             // PASTA: a Aila lê direto do disco (sem upload)
    return `\n[Pasta anexada: ${p} — você pode LER esta pasta direto do disco. `
      + `Use file.list para ver a estrutura; leia os arquivos com file.read (texto), `
      + `docs.read (PDF/Word/Excel/PPT) ou vision.analyze_image (imagens). Foque no que o `
      + `usuário pediu; não precisa listar tudo. (Para grafo de código do projeto, há a aba Projetos.)]\n`;
  if (a.text != null)                       // texto já veio no upload → embute (sem tool)
    return `\n[Anexo: ${n} — em ${p}]\n\`\`\`\n${a.text.slice(0, 20000)}\n\`\`\`\n`;
  if (RE_IMG.test(n)) return `\n[Anexo (imagem): ${n} — em ${p}. Veja com vision.analyze_image.]\n`;
  if (RE_DOC.test(n)) return `\n[Anexo (documento): ${n} — em ${p}. Extraia o texto com docs.read.]\n`;
  return `\n[Anexo: ${n} — em ${p}. Tente docs.read; se for binário, use o Binary Agent.]\n`;
}

export function send() {
  const input = byId('input');
  const t = input.value.trim();
  if (!t && !attached.length) return;
  let payload = '';
  for (const a of attached) payload += attachHint(a);
  const full = (payload ? payload + '\n' : '') + t;
  const label = attached.map((a) => attachIcon(a) + ' ' + a.name).join('  ') + (t ? (attached.length ? '\n' : '') + t : '');
  _send(full, label || '(anexos)');
  input.value = ''; input.style.height = 'auto';
  attached = []; renderChips();
}

// anexos
function renderChips() {
  byId('attachments').innerHTML = attached
    .map((a, i) => `<span class="chip">${attachIcon(a)} ${a.name}<button data-i="${i}" title="remover">✕</button></span>`)
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

// Anexa uma PASTA para a Aila LER DIRETO DO DISCO — SEM upload (local-first).
// O caminho vira uma raiz de leitura autorizada no backend; o agente explora com
// file.list / file.read / docs.read / vision. Usa o seletor NATIVO do Electron
// (caminho absoluto); no navegador, pede o caminho. Para grafo de código de um
// projeto, o caminho é a aba 🧠 ▸ Projetos.
export async function attachFolder(onDone) {
  let path = null;
  try { if (window.aila && window.aila.pickFolder) path = await window.aila.pickFolder(); }
  catch (e) { /* sem bridge Electron */ }
  if (!path) path = window.prompt('Caminho da pasta (a Aila lê direto do disco):');
  path = (path || '').trim();
  if (!path) return;
  try {
    const r = await api.attachFolder(path);
    attached.push({ name: r.name || path, path: r.path, folder: true });
    renderChips();
    onSys(`📁 pasta anexada: ${r.name} — a Aila lê direto do disco (sem upload).`);
  } catch (e) {
    onSys('não consegui anexar essa pasta: ' + (e.message || e));
  }
  if (onDone) onDone();
}
