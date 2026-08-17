// Settings Center (⚙️): Geral · Aparência · Modelos e IA · Voz · Avatar ·
// Autonomia · Rede & Privacidade · Sistema. Só o que o backend suporta.
import { byId, $$, el } from './dom.js';
import { State } from './state.js';
import { avatarReload } from './avatar.js';
import { renderProviders } from './views/providers.js';
import { api } from './core/api.js';
import { confirmDialog } from './ui.js';
import { CATEGORIES, CUSTOM_HTML } from './settings-schema.js';

const THEMES = [
  { id: 'aqua', c: '#38e1d0' }, { id: 'cyber', c: '#c257ff' }, { id: 'rose', c: '#ff6fae' },
  { id: 'forest', c: '#43e08a' }, { id: 'light', c: '#0bb3a0' },
];

export function setTheme(id) {
  document.documentElement.setAttribute('data-theme', id);
  localStorage.setItem('aila-theme', id);
  $$('.swatch').forEach((s) => s.classList.toggle('active', s.dataset.id === id));
}

export const openSettings = () => { byId('settings-overlay').classList.add('show'); loadConfig().then(renderAllFields); };
export const closeSettings = () => byId('settings-overlay').classList.remove('show');

// renderers dos blocos "custom" (widgets já prontos), por nome
const CUSTOM_RENDER = {
  providers: renderProviders, memory: renderMemory, autonomy: renderAutonomy,
  permissions: renderPermissions, network: renderNetwork, system: loadStatus,
};

export function settingsTab(p) {
  $$('.snav').forEach((b) => b.classList.toggle('active', b.dataset.p === p));
  $$('.spane').forEach((s) => s.classList.toggle('active', s.id === 'sp-' + p));
  const cat = CATEGORIES.find((c) => c.id === p); if (!cat) return;
  for (const b of cat.blocks) if (b.custom && CUSTOM_RENDER[b.custom]) CUSTOM_RENDER[b.custom]();
}

/* ---------- editor de config (schema → PATCH /api/config) ---------- */
let _cfg = {};
const getPath = (o, path) => path.split('.').reduce((x, k) => (x == null ? undefined : x[k]), o);
async function loadConfig() { try { _cfg = await api.config(); } catch { _cfg = {}; } }

function commit(path, value) {
  const patch = {}; let cur = patch; const parts = path.split('.');
  parts.forEach((k, i) => { if (i === parts.length - 1) cur[k] = value; else cur = (cur[k] = {}); });
  api.patchConfig(patch).catch(() => {});
}
function showRestart() { byId('cfg-restart')?.classList.add('show'); }

function control(f) {
  const v = getPath(_cfg, f.path);
  const onChange = (val) => { commit(f.path, val); if (f.restart) showRestart(); };
  if (f.type === 'toggle') {
    const t = el('div', { class: 'toggle' + (v ? ' on' : ''), onclick: () => { const on = !t.classList.contains('on'); t.classList.toggle('on', on); onChange(on); } }, el('div', { class: 'sw' }));
    return t;
  }
  if (f.type === 'select') {
    const s = el('select', { class: 'cfg-input' });
    (f.options || []).forEach((o) => s.append(el('option', { value: o }, o)));
    s.value = v ?? (f.options?.[0] ?? '');
    s.onchange = () => onChange(s.value);
    return s;
  }
  if (f.type === 'textarea') {
    const a = el('textarea', { class: 'cfg-input cfg-area', rows: 3 }); a.value = v ?? '';
    a.onchange = () => onChange(a.value);
    return a;
  }
  if (f.type === 'tags') {
    const i = el('input', { class: 'cfg-input', type: 'text' }); i.value = Array.isArray(v) ? v.join(', ') : (v ?? '');
    i.onchange = () => onChange(i.value.split(',').map((x) => x.trim()).filter(Boolean));
    return i;
  }
  // number | text
  const i = el('input', { class: 'cfg-input', type: f.type === 'number' ? 'number' : 'text' });
  if (f.min != null) i.min = f.min; if (f.max != null) i.max = f.max; if (f.step != null) i.step = f.step;
  i.value = v ?? '';
  i.onchange = () => onChange(f.type === 'number' ? Number(i.value) : i.value);
  return i;
}

function renderAllFields() {
  $$('.cfg-fields').forEach((box) => {
    const fields = JSON.parse(box.dataset.fields || '[]');
    box.innerHTML = '';
    fields.forEach((f) => box.append(
      el('div', { class: 'cfg-row' },
        el('div', { class: 'cfg-meta' },
          el('label', { class: 'cfg-label' }, f.label + (f.restart ? ' ↻' : '')),
          f.hint ? el('div', { class: 'cfg-hint muted' }, f.hint) : null),
        el('div', { class: 'cfg-ctl' }, control(f)),
      )));
  });
}

function prefToggle(p) {
  const on = (localStorage.getItem(p.key) ?? String(p.default)) === 'true';
  const t = el('div', { class: 'toggle' + (on ? ' on' : ''), onclick: () => {
    const now = !t.classList.contains('on'); t.classList.toggle('on', now);
    localStorage.setItem(p.key, String(now));
  } }, el('div', { class: 'sw' }));
  return el('div', { class: 'cfg-row' },
    el('div', { class: 'cfg-meta' }, el('label', { class: 'cfg-label' }, p.label)),
    el('div', { class: 'cfg-ctl' }, t));
}

/* gera a navegação + os painéis a partir do schema (uma vez) */
function buildSettings() {
  const nav = byId('settings-nav'); const main = byId('settings-main');
  if (!nav || !main) return;
  nav.innerHTML = '<div class="settings-title">⚙️ Configurações</div>';
  main.innerHTML = '<div class="cfg-restart" id="cfg-restart">↻ Reinicie a Aila para aplicar algumas mudanças.</div>';

  CATEGORIES.forEach((cat, idx) => {
    nav.append(el('button', { class: 'snav' + (idx === 0 ? ' active' : ''), 'data-p': cat.id,
      onclick: () => settingsTab(cat.id) }, `${cat.icon} ${cat.label}`));

    const pane = el('section', { class: 'spane' + (idx === 0 ? ' active' : ''), id: 'sp-' + cat.id },
      el('h3', {}, cat.label));
    cat.blocks.forEach((b) => {
      if (b.title) pane.append(el('div', { class: 'cfg-block-t' }, b.title));
      if (b.fields) pane.append(el('div', { class: 'cfg-fields', 'data-fields': JSON.stringify(b.fields) }));
      if (b.custom) pane.append(el('div', { class: 'html', html: CUSTOM_HTML[b.custom] || '' }));
      if (b.pref) b.pref.forEach((p) => pane.append(prefToggle(p)));
      if (b.note) pane.append(el('p', { class: 'muted cfg-note' }, b.note));
    });
    main.append(pane);
  });
  nav.append(el('div', { class: 'spacer' }));
  nav.append(el('button', { class: 'btn', id: 'btn-settings-close', onclick: closeSettings }, 'Fechar'));
}

/* ---------- Memória (/api/memory — leitura) ---------- */
const KIND_LABEL = { chat: 'Conversa', fact: 'Fato', preference: 'Preferência',
                     project: 'Projeto', semantic: 'Semântica' };
let _mems = [];
async function renderMemory() {
  const box = byId('memory-list'); if (!box) return;
  box.textContent = 'carregando…';
  try {
    const d = await api.memory(50);
    byId('memory-count').textContent = d.count ?? 0;
    if (!d.enabled) { box.innerHTML = ''; box.append(el('div', { class: 'act-empty' }, 'Memória desativada na configuração.')); return; }
    _mems = d.recent || [];
    drawMemory(byId('mem-search')?.value || '');
  } catch { box.textContent = 'não foi possível carregar a memória.'; }
}

function drawMemory(q) {
  const box = byId('memory-list'); if (!box) return;
  box.innerHTML = '';
  const ql = (q || '').trim().toLowerCase();
  const list = _mems.filter((m) => !ql || (m.text || '').toLowerCase().includes(ql));
  if (!list.length) {
    box.append(el('div', { class: 'act-empty' }, ql ? 'nada encontrado' : 'Nenhuma memória ainda.'));
    return;
  }
  list.forEach((m) => box.append(el('div', { class: 'mem-item', 'data-kind': m.kind },
    el('span', { class: 'mem-kind' }, KIND_LABEL[m.kind] || m.kind || 'memória'),
    el('div', { class: 'mem-text' }, (m.text || '').replace(/\s+/g, ' ').slice(0, 220)),
    el('button', { class: 'mem-del', title: 'Esquecer esta memória', onclick: () => delMemory(m.id) }, '🗑'),
  )));
}

async function delMemory(id) {
  try {
    const r = await api.deleteMemory(id);
    _mems = _mems.filter((m) => m.id !== id);
    byId('memory-count').textContent = r.count ?? '';
    drawMemory(byId('mem-search')?.value || '');
  } catch { /* silencioso */ }
}

/* ---------- Permissões (explicador + estado atual) ---------- */
const RISK = [
  ['safe', 'SAFE', 'Executa automaticamente — leituras, pesquisa, análise.'],
  ['review', 'REVIEW', 'Escrita comum. Confirma só se você pedir.'],
  ['danger', 'DANGER', 'Ações destrutivas (rodar comando, apagar, executar código) — pedem confirmação.'],
  ['blocked', 'BLOCKED', 'Nunca executadas pela Aila (ex.: comandos catastróficos no terminal).'],
];
function renderPermissions() {
  const box = byId('perm-levels'); if (!box) return;
  box.innerHTML = '';
  RISK.forEach(([k, name, desc]) => box.append(el('div', { class: 'risk-item', 'data-risk': k },
    el('span', { class: 'risk-badge' }, name),
    el('div', { class: 'risk-desc muted' }, desc),
  )));
  const s = State.get();
  const st = byId('perm-state');
  if (st) st.innerHTML = `
    <div class="row"><span>Somente-leitura</span><span class="muted">${s.readOnly ? 'ligado (bloqueia escrita)' : 'desligado'}</span></div>
    <div class="row"><span>Autonomia atual</span><span class="muted">L${s.autonomy || 3}</span></div>`;
}

/* ---------- Autonomia (L1–L5) — set via /api/autonomy ---------- */
const AUTO = [
  [1, 'Assistente', 'Só conversa e leitura. Nenhuma ação no computador.'],
  [2, 'Executor', 'Age no PC e nos arquivos (mouse, teclado, comandos) — com confirmação.'],
  [3, 'Desenvolvedor', 'Além disso, pode executar e mexer em código.'],
  [4, 'Autônomo', 'Executa tarefas de várias etapas por conta própria.'],
  [5, 'Auto-melhoria', 'Pode editar o próprio código, em branch isolada e validado por testes.'],
];
function renderAutonomy() {
  const box = byId('autonomy-list'); if (!box) return;
  const cur = State.get('autonomy') || 3;
  box.innerHTML = '';
  AUTO.forEach(([n, name, desc]) => {
    const active = n === cur;
    box.append(el('button',
      { class: 'auto-item' + (active ? ' active' : ''), 'data-danger': n >= 4 ? '1' : '0',
        onclick: () => setAutonomy(n) },
      el('span', { class: 'auto-badge' }, 'L' + n),
      el('div', { class: 'auto-info' },
        el('div', { class: 'auto-name' }, name),
        el('div', { class: 'auto-desc muted' }, desc)),
      active ? el('span', { class: 'auto-check' }, '●') : null,
    ));
  });
}
async function setAutonomy(n) {
  if (n === (State.get('autonomy') || 3)) return;
  if (n >= 4) {
    const ok = await confirmDialog({
      title: `Ativar autonomia L${n} — ${AUTO[n - 1][1]}?`,
      body: n === 5 ? 'A Aila poderá editar o PRÓPRIO código (branch isolada, validado por testes).'
                    : 'A Aila poderá executar tarefas autônomas de várias etapas por conta própria.',
      confirmLabel: `Ativar L${n}`, danger: true,
    });
    if (!ok) return;
  }
  State.set({ autonomy: n });
  try { const r = await api.setAutonomy(n); State.set({ autonomy: r.autonomy_level ?? n }); }
  catch { /* ignora; poll ressincroniza */ }
  renderAutonomy();
}

/* ---------- Rede & Privacidade — set via /api/network ---------- */
const NET = [
  ['hybrid', '🌐 Híbrido', 'Usa o modelo local e, quando fizer sentido, a nuvem/web. Seus prompts podem sair do PC.'],
  ['offline', '🔒 Offline', 'Nada sai do computador. Só modelos e ferramentas locais.'],
];
function renderNetwork() {
  const box = byId('network-list'); if (!box) return;
  const cur = State.get('networkMode') || 'hybrid';
  box.innerHTML = '';
  NET.forEach(([mode, name, desc]) => {
    const active = mode === cur;
    box.append(el('button',
      { class: 'net-item' + (active ? ' active' : ''), 'data-mode': mode, onclick: () => setNet(mode) },
      el('div', { class: 'net-info' },
        el('div', { class: 'net-name' }, name),
        el('div', { class: 'net-desc muted' }, desc)),
      active ? el('span', { class: 'auto-check' }, '●') : null,
    ));
  });
}
async function setNet(mode) {
  State.set({ networkMode: mode });
  try { const r = await api.setNetwork(mode); State.set({ networkMode: r.network_mode || mode }); }
  catch { /* ignora */ }
  renderNetwork();
}

export function setLlm(on) {
  byId('s-llm').innerHTML = `<span class="dot ${on ? 'on' : 'off'}"></span>${on ? 'online' : 'offline'}`;
}
// status de VOZ (a topbar cuida do /api/status → State; aqui só a voz).
export async function loadStatus() {
  try {
    const v = await (await fetch('/api/voice/status')).json();
    byId('s-voice').textContent = v.enabled ? (v.tts_engine + ' · ' + (v.tts_voice || '')) : 'off';
  } catch (e) { /* offline */ }
}

// espelha o estado global (modelo/llm/memória/rede/autonomia) nas linhas.
const esc = (s) => String(s ?? '').replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
function bindStatusRows() {
  const paint = (s) => {
    setLlm(s.llmOnline);
    byId('s-model').textContent = s.model || '—';
    byId('s-mem').textContent = s.memoryCount ?? 0;
    const g = byId('geral-summary');
    if (g) {
      const local = !s.provider || s.provider === 'local' || s.provider === 'default';
      g.innerHTML = `
        <div class="row"><span>Modelo</span><span class="muted">${esc(s.model || '—')} · ${local ? 'local' : esc(s.provider)}</span></div>
        <div class="row"><span>Rede</span><span class="muted">${(s.networkMode || 'hybrid') === 'offline' ? 'Offline (local)' : 'Híbrido'}</span></div>
        <div class="row"><span>Autonomia</span><span class="muted">L${s.autonomy || 3}</span></div>
        <div class="row"><span>Conexão</span><span class="muted">${s.llmOnline ? 'online' : 'offline'}</span></div>`;
    }
  };
  State.on(paint); paint(State.get());
}

export function initSettings() {
  buildSettings();     // gera nav + painéis a partir do schema

  // swatches de tema (o container #themes é gerado no bloco custom de "Geral")
  const box = byId('themes');
  if (box) {
    THEMES.forEach((t) => {
      const s = document.createElement('div');
      s.className = 'swatch'; s.dataset.id = t.id; s.style.background = t.c; s.title = t.id;
      s.onclick = () => setTheme(t.id); box.appendChild(s);
    });
  }
  setTheme(localStorage.getItem('aila-theme') || 'aqua');

  // fechar clicando fora
  byId('settings-overlay').addEventListener('click', (e) => { if (e.target.id === 'settings-overlay') closeSettings(); });

  // busca nas memórias (filtra a lista carregada)
  byId('mem-search')?.addEventListener('input', (e) => drawMemory(e.target.value));

  // trocar VRM
  const pv = byId('pickvrm');
  if (pv) {
    pv.onclick = () => byId('vrmfile').click();
    byId('vrmfile').onchange = async (ev) => {
      const f = ev.target.files[0]; if (!f) return;
      byId('vrmnote').textContent = 'enviando…';
      try {
        const fd = new FormData(); fd.append('file', f, f.name);
        const r = await fetch('/api/avatar/vrm', { method: 'POST', body: fd });
        byId('vrmnote').textContent = r.ok ? '✓ trocado' : 'falhou';
        if (r.ok) avatarReload();
      } catch (e) { byId('vrmnote').textContent = 'falhou'; }
      setTimeout(() => byId('vrmnote').textContent = '', 4000); ev.target.value = '';
    };
  }

  // toggle de voz (ao vivo)
  const tg = byId('tg-voice');
  if (tg) {
    tg.classList.toggle('on', State.get('voiceOut') !== false);
    tg.onclick = () => {
      const on = !State.get('voiceOut'); State.set({ voiceOut: on });
      tg.classList.toggle('on', on);
    };
  }

  bindStatusRows();   // linhas do painel de Status espelham o State global
}
