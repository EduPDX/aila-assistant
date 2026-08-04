// ============================================================
//  Markdown + realce de sintaxe — 100% local (sem CDN, funciona offline).
//  renderMarkdown(texto) -> HTML seguro. Blocos de código ganham um
//  "chrome" (cabeçalho com a linguagem + botões Copiar/Salvar/Executar),
//  ligados depois por enhanceCodeBlocks().
// ============================================================

const escHtml = (s) => s
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// ---------------- realce de sintaxe ----------------
// Config mínima por linguagem: palavras-chave + estilo de comentário.
const LANGS = {
  python: { line: '#', block: false, triple: true, kw: 'def class return if elif else for while in is not and or import from as with try except finally raise lambda yield global nonlocal pass break continue None True False async await del assert' },
  javascript: { line: '//', block: true, kw: 'function return if else for while do var let const class extends new this typeof instanceof in of import from export default async await yield try catch finally throw switch case break continue null undefined true false void delete' },
  typescript: { line: '//', block: true, kw: 'function return if else for while do var let const class extends implements interface type enum new this typeof in of import from export default async await try catch finally throw switch case break continue null undefined true false void delete public private protected readonly as' },
  bash: { line: '#', block: false, kw: 'if then else elif fi for while do done case esac function in return export local echo cd ls cat sudo apt pip python git curl rm mkdir source set' },
  json: { line: false, block: false, kw: 'true false null' },
  html: { line: false, block: false, kw: '' },
  css: { line: false, block: true, kw: '' },
  sql: { line: '--', block: true, kw: 'select from where insert into values update set delete create table drop alter add primary key foreign references join left right inner outer on group by order having limit and or not null as distinct count sum avg min max' },
  yaml: { line: '#', block: false, kw: 'true false null' },
};
const ALIAS = { js: 'javascript', ts: 'typescript', py: 'python', sh: 'bash', shell: 'bash', zsh: 'bash', 'c++': 'javascript', c: 'javascript', java: 'javascript', go: 'javascript', rust: 'javascript', jsx: 'javascript', tsx: 'typescript', yml: 'yaml', xml: 'html' };

export function normLang(l) {
  l = (l || '').toLowerCase().trim();
  return ALIAS[l] || (LANGS[l] ? l : '');
}

// realça `code` (texto cru) da linguagem `lang`; devolve HTML já escapado.
export function highlight(code, lang) {
  const cfg = LANGS[lang];
  if (!cfg) return escHtml(code);            // linguagem desconhecida: só escapa
  const kws = new Set(cfg.kw.split(/\s+/).filter(Boolean));

  // monta as alternativas do tokenizador na ordem de prioridade
  const alts = [];
  if (cfg.triple) alts.push('"""[\\s\\S]*?"""', "'''[\\s\\S]*?'''");
  if (cfg.block) alts.push('/\\*[\\s\\S]*?\\*/');
  if (cfg.line) alts.push(cfg.line.replace(/[/\-]/g, '\\$&') + '[^\\n]*');
  alts.push('"(?:\\\\.|[^"\\\\])*"', "'(?:\\\\.|[^'\\\\])*'", '`(?:\\\\.|[^`\\\\])*`');
  alts.push('\\b\\d[\\d_.eExXa-fA-F]*\\b');   // números
  alts.push('[A-Za-z_$][\\w$]*');             // identificadores (kw/função/var)
  const re = new RegExp(alts.join('|'), 'g');

  let out = '', last = 0, m;
  while ((m = re.exec(code))) {
    out += escHtml(code.slice(last, m.index));
    const tk = m[0];
    let cls = '';
    if (/^("""|''')/.test(tk) || /^["'`]/.test(tk)) cls = 'str';
    else if (cfg.line && tk.startsWith(cfg.line)) cls = 'com';
    else if (cfg.block && tk.startsWith('/*')) cls = 'com';
    else if (/^\d/.test(tk)) cls = 'num';
    else if (kws.has(tk)) cls = 'kw';
    else if (code[re.lastIndex] === '(') cls = 'fn';   // seguido de '(' -> chamada
    out += cls ? `<span class="hl-${cls}">${escHtml(tk)}</span>` : escHtml(tk);
    last = re.lastIndex;
  }
  out += escHtml(code.slice(last));
  return out;
}

// ---------------- markdown ----------------
let _cbId = 0;

// formatação inline (negrito, itálico, código, link) — recebe texto JÁ escapado
function inline(s) {
  return s
    .replace(/`([^`]+)`/g, '<code class="ic">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

// devolve { html, blocks:[{id, code, lang}] } — os blocos são realçados depois
export function renderMarkdown(text) {
  const blocks = [];
  const src = String(text ?? '');
  const parts = [];
  const fence = /```(\w+)?[ \t]*\n?([\s\S]*?)```/g;
  let last = 0, m;
  while ((m = fence.exec(src))) {
    parts.push({ t: 'md', v: src.slice(last, m.index) });
    const lang = normLang(m[1]);
    const id = 'cb' + (++_cbId);
    blocks.push({ id, code: m[2].replace(/\n$/, ''), lang, raw: m[1] || '' });
    parts.push({ t: 'code', id });
    last = fence.lastIndex;
  }
  parts.push({ t: 'md', v: src.slice(last) });

  let html = '';
  for (const p of parts) {
    if (p.t === 'code') { html += `<div class="codeblock" data-cb="${p.id}"></div>`; continue; }
    html += renderBlocks(p.v);
  }
  return { html, blocks };
}

// blocos de linha (títulos, listas, citações, parágrafos) fora de código
function renderBlocks(md) {
  const lines = md.split('\n');
  let html = '', list = null;
  const closeList = () => { if (list) { html += `</${list}>`; list = null; } };
  for (let raw of lines) {
    const line = raw.replace(/\s+$/, '');
    if (!line.trim()) { closeList(); continue; }
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { closeList(); const n = m[1].length; html += `<h${n + 2}>${inline(escHtml(m[2]))}</h${n + 2}>`; continue; }
    if (/^\s*([-*])\s+/.test(line)) { if (list !== 'ul') { closeList(); list = 'ul'; html += '<ul>'; } html += `<li>${inline(escHtml(line.replace(/^\s*[-*]\s+/, '')))}</li>`; continue; }
    if (/^\s*\d+\.\s+/.test(line)) { if (list !== 'ol') { closeList(); list = 'ol'; html += '<ol>'; } html += `<li>${inline(escHtml(line.replace(/^\s*\d+\.\s+/, '')))}</li>`; continue; }
    if ((m = line.match(/^\s*>\s?(.*)$/))) { closeList(); html += `<blockquote>${inline(escHtml(m[1]))}</blockquote>`; continue; }
    if (/^\s*(---|\*\*\*)\s*$/.test(line)) { closeList(); html += '<hr>'; continue; }
    closeList();
    html += `<p>${inline(escHtml(line))}</p>`;
  }
  closeList();
  return html;
}

// ---------------- chrome dos blocos de código ----------------
// injeta cabeçalho + botões em cada <div class="codeblock"> do container.
// onRun(code, lang) opcional: se dado, mostra o botão ▶ Executar.
export function enhanceCodeBlocks(container, blocks, onRun) {
  for (const b of blocks) {
    const host = container.querySelector(`[data-cb="${b.id}"]`);
    if (!host) continue;
    const label = b.raw || b.lang || 'texto';
    const runnable = onRun && (b.lang === 'bash' || b.lang === 'python');
    host.innerHTML = `
      <div class="cb-head">
        <span class="cb-lang">${escHtml(label)}</span>
        <div class="cb-actions">
          ${runnable ? '<button class="cb-btn" data-a="run" title="Executar">▶ Executar</button>' : ''}
          <button class="cb-btn" data-a="save" title="Salvar arquivo">⭳ Salvar</button>
          <button class="cb-btn" data-a="copy" title="Copiar">⧉ Copiar</button>
        </div>
      </div>
      <pre class="cb-body"><code>${highlight(b.code, b.lang)}</code></pre>`;

    host.querySelector('[data-a="copy"]').onclick = (e) => copyCode(e.currentTarget, b.code);
    host.querySelector('[data-a="save"]').onclick = () => saveCode(b);
    if (runnable) host.querySelector('[data-a="run"]').onclick = () => onRun(b.code, b.lang);
  }
}

async function copyCode(btn, code) {
  try { await navigator.clipboard.writeText(code); }
  catch { const ta = document.createElement('textarea'); ta.value = code; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); }
  const old = btn.textContent; btn.textContent = '✓ Copiado'; btn.classList.add('ok');
  setTimeout(() => { btn.textContent = old; btn.classList.remove('ok'); }, 1400);
}

const EXT = { python: 'py', javascript: 'js', typescript: 'ts', bash: 'sh', json: 'json', html: 'html', css: 'css', sql: 'sql', yaml: 'yaml' };
function saveCode(b) {
  const ext = EXT[b.lang] || 'txt';
  const blob = new Blob([b.code], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = `aila-snippet.${ext}`;
  a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
