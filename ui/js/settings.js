// Settings Center (⚙️): Geral · Aparência · Modelos e IA · Voz · Avatar ·
// Autonomia · Rede & Privacidade · Sistema. Só o que o backend suporta.
import { byId, $$, el } from './dom.js';
import { State } from './state.js';
import { avatarReload, avatarTheme } from './avatar.js';
import { renderProviders } from './views/providers.js';
import { api } from './core/api.js';
import { confirmDialog } from './ui.js';
import { CATEGORIES, CUSTOM_HTML, KNOWN_AGENTS } from './settings-schema.js';

const THEMES = [
  { id: 'aqua', label: 'Aqua', c: '#38e1d0', c2: '#4aa8ff', tone: '#070b12' },
  { id: 'cobalt', label: 'Cobalto', c: '#55a7ff', c2: '#58e6ff', tone: '#050b18' },
  { id: 'cyber', label: 'Cyber', c: '#c257ff', c2: '#ff5cd6', tone: '#0a0713' },
  { id: 'rose', label: 'Rose', c: '#ff6fae', c2: '#ffa96f', tone: '#120a0f' },
  { id: 'forest', label: 'Floresta', c: '#43e08a', c2: '#a9e04b', tone: '#071410' },
  { id: 'amber', label: 'Âmbar', c: '#ffbd45', c2: '#ff7a45', tone: '#100c06' },
  { id: 'crimson', label: 'Crimson', c: '#ff526f', c2: '#ff8a4c', tone: '#11070a' },
  { id: 'graphite', label: 'Grafite', c: '#b8c4d1', c2: '#6fdaff', tone: '#090b0e' },
  { id: 'light', label: 'Claro', c: '#0bb3a0', c2: '#2f7cf6', tone: '#f2f5f9' },
];

export function setTheme(id) {
  if (!THEMES.some((t) => t.id === id)) id = 'aqua';
  document.documentElement.setAttribute('data-theme', id);
  localStorage.setItem('aila-theme', id);
  $$('.swatch').forEach((s) => s.classList.toggle('active', s.dataset.id === id));
  sendAvatarTheme();
}

function currentThemePayload() {
  const css = getComputedStyle(document.documentElement);
  const value = (name) => css.getPropertyValue(name).trim();
  return {
    id: document.documentElement.dataset.theme || 'aqua',
    bg: value('--bg'), bg2: value('--bg-2'), panel: value('--panel'),
    panel2: value('--panel-2'), border: value('--border'), text: value('--text'),
    muted: value('--muted'), accent: value('--accent'), accent2: value('--accent-2'),
    warn: value('--warn'),
  };
}

function sendAvatarTheme() {
  // Aguarda o style recalculado para color-mix e variáveis herdadas refletirem o tema.
  requestAnimationFrame(() => avatarTheme(currentThemePayload()));
}

function applyAppearancePrefs() {
  const root = document.documentElement;
  root.dataset.uiDensity = localStorage.getItem('aila.ui.density') || 'confortável';
  root.dataset.uiGlow = localStorage.getItem('aila.ui.glow') || 'normal';
  root.dataset.uiScanlines = localStorage.getItem('aila.ui.scanlines') ?? 'true';
}

let _settingsFocus = null;
let _saveSeq = 0;
const CATEGORY_DESCRIPTIONS = {
  aparencia: 'Personalize o ambiente visual e o grafo cognitivo.',
  geral: 'Defina o modo como Aila conversa e se apresenta.',
  modelos: 'Gerencie modelos locais, provedores e roteamento cognitivo.',
  voz: 'Configure fala, escuta, voz e processamento de áudio.',
  avatar: 'Escolha o corpo virtual e sua expressão de repouso.',
  memoria: 'Controle o que Aila guarda, recupera e relaciona.',
  autonomia: 'Escolha até onde Aila pode agir por conta própria.',
  agentes: 'Ative as capacidades e ferramentas disponíveis.',
  seguranca: 'Revise proteções, confirmações e níveis de risco.',
  rede: 'Controle quando dados podem usar serviços externos.',
  tarefas: 'Ajuste limites que evitam loops e travamentos.',
  sistema: 'Consulte o estado dos principais serviços da Aila.',
  dev: 'Opções técnicas para diagnóstico e desenvolvimento.',
};
export const openSettings = () => {
  const overlay = byId('settings-overlay');
  _settingsFocus = document.activeElement;
  overlay.classList.add('show'); overlay.setAttribute('aria-hidden', 'false');
  overlay.querySelector('.settings')?.focus();
  loadConfig().then(renderAllFields);
};
export const closeSettings = () => {
  const overlay = byId('settings-overlay');
  overlay.classList.remove('show'); overlay.setAttribute('aria-hidden', 'true');
  _settingsFocus?.focus?.(); _settingsFocus = null;
};

// renderers dos blocos "custom" (widgets já prontos), por nome
const CUSTOM_RENDER = {
  providers: renderProviders, memory: renderMemory, autonomy: renderAutonomy,
  permissions: renderPermissions, network: renderNetwork, system: loadStatus,
  agents: renderAgents, reset: renderReset, rebuild: renderRebuild,
};

/* ---------- Reconstruir grafo de Conhecimento (backfill) ---------- */
function renderRebuild() {
  const b = byId('btn-rebuild-kg'); if (!b || b._wired) return;
  b._wired = true;
  const note = byId('rebuild-note');
  b.onclick = async () => {
    const orig = b.textContent;
    b.disabled = true; b.textContent = 'reconstruindo…';
    if (note) note.textContent = 'lendo memórias e extraindo tópicos…';
    try {
      const r = await api.rebuildKnowledge();
      if (note) note.textContent = `pronto: ${r.nodes} conceitos, ${r.edges} ligações `
        + `(${r.backfilled} memórias processadas).`;
    } catch {
      if (note) note.textContent = 'falhou — verifique se a memória está ativa.';
    } finally {
      b.disabled = false; b.textContent = orig;
    }
  };
}

/* ---------- Apagar tudo (recomeçar do zero) ---------- */
function renderReset() {
  const b = byId('btn-reset-all'); if (!b || b._wired) return;
  b._wired = true;
  b.onclick = async () => {
    const ok = await confirmDialog({
      title: 'Apagar tudo e recomeçar?',
      body: 'Memórias, grafo de Conhecimento e TODAS as conversas serão apagados. '
        + 'Isso NÃO afeta o código da Aila. Não tem volta.',
      confirmLabel: 'Apagar tudo', danger: true,
    });
    if (!ok) return;
    b.textContent = 'apagando…';
    try { await api.reset(); location.reload(); }
    catch { b.textContent = '🗑 Apagar tudo e recomeçar'; }
  };
}

/* ---------- Agentes (lista com toggles) — grava agents.enabled ---------- */
function renderAgents() {
  const box = byId('agents-list'); if (!box) return;
  const enabled = new Set((getPath(_cfg, 'agents.enabled')) || []);
  box.innerHTML = '';
  KNOWN_AGENTS.forEach(([id, label, desc]) => {
    const on = enabled.has(id);
    const t = el('button', { class: 'toggle toggle-button' + (on ? ' on' : ''), type: 'button',
      role: 'switch', 'aria-checked': String(on), 'aria-label': `${label}: ${on ? 'ativado' : 'desativado'}`, onclick: () => {
      const now = !t.classList.contains('on'); t.classList.toggle('on', now);
      t.setAttribute('aria-checked', String(now));
      t.setAttribute('aria-label', `${label}: ${now ? 'ativado' : 'desativado'}`);
      now ? enabled.add(id) : enabled.delete(id);
      commit('agents.enabled', [...enabled]); showRestart();
    } }, el('span', { class: 'sw', 'aria-hidden': 'true' }));
    box.append(el('div', { class: 'agent-item' },
      el('div', { class: 'agent-info' },
        el('div', { class: 'agent-name' }, label),
        el('div', { class: 'agent-desc muted' }, desc)),
      t));
  });
}

export function settingsTab(p) {
  $$('.snav').forEach((b) => {
    const active = b.dataset.p === p;
    b.classList.toggle('active', active);
    b.setAttribute('aria-current', active ? 'page' : 'false');
  });
  $$('.spane').forEach((s) => {
    const active = s.id === 'sp-' + p;
    s.classList.toggle('active', active);
    s.setAttribute('aria-hidden', String(!active));
  });
  const cat = CATEGORIES.find((c) => c.id === p); if (!cat) return;
  byId('settings-main')?.setAttribute('data-active-pane', p);
  for (const b of cat.blocks) if (b.custom && CUSTOM_RENDER[b.custom]) CUSTOM_RENDER[b.custom]();
}

/* ---------- editor de config (schema → PATCH /api/config) ---------- */
let _cfg = {};
const getPath = (o, path) => path.split('.').reduce((x, k) => (x == null ? undefined : x[k]), o);
async function loadConfig() { try { _cfg = await api.config(); } catch { _cfg = {}; } }

function setSaveState(state, text) {
  const status = byId('cfg-save-status');
  if (!status) return;
  status.dataset.state = state;
  status.textContent = text;
}

async function commit(path, value) {
  const patch = {}; let cur = patch; const parts = path.split('.');
  parts.forEach((k, i) => { if (i === parts.length - 1) cur[k] = value; else cur = (cur[k] = {}); });
  const seq = ++_saveSeq;
  setSaveState('saving', 'Salvando…');
  try {
    await api.patchConfig(patch);
    let target = _cfg;
    parts.forEach((k, i) => {
      if (i === parts.length - 1) target[k] = value;
      else target = (target[k] ||= {});
    });
    if (seq === _saveSeq) setSaveState('saved', '✓ Salvo');
  } catch {
    if (seq === _saveSeq) setSaveState('error', 'Falha ao salvar');
  }
}
function showRestart() { byId('cfg-restart')?.classList.add('show'); }

function control(f) {
  const v = getPath(_cfg, f.path);
  const onChange = (val) => { commit(f.path, val); if (f.restart) showRestart(); };
  if (f.type === 'toggle') {
    const t = el('button', { class: 'toggle toggle-button' + (v ? ' on' : ''), type: 'button',
      role: 'switch', 'aria-checked': String(Boolean(v)), 'aria-label': f.label,
      onclick: () => {
        const on = !t.classList.contains('on');
        t.classList.toggle('on', on); t.setAttribute('aria-checked', String(on)); onChange(on);
      } }, el('span', { class: 'sw', 'aria-hidden': 'true' }));
    return t;
  }
  if (f.type === 'select') {
    const s = el('select', { class: 'cfg-input' });
    (f.options || []).forEach((o) => s.append(el('option', { value: o }, o)));
    s.value = v ?? (f.options?.[0] ?? '');
    s.onchange = () => onChange(s.value);
    return s;
  }
  if (f.type === 'slider') {
    const fmt = (n) => (f.signed && n >= 0 ? '+' : '') + n + (f.unit || '');
    const num = f.str ? (parseFloat(String(v ?? '').replace(/[^\d.-]/g, '')) || 0) : (v ?? f.min ?? 0);
    const range = el('input', { type: 'range', class: 'cfg-range', min: f.min, max: f.max, step: f.step || 1 });
    range.value = num;
    const out = el('span', { class: 'cfg-val' }, fmt(num));
    range.oninput = () => { out.textContent = fmt(Number(range.value)); };
    range.onchange = () => onChange(f.str ? fmt(Number(range.value)) : Number(range.value));
    return el('div', { class: 'cfg-slider' }, range, out);
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

// preferência LOCAL (localStorage) — toggle ou select. Dispara 'aila:pref' p/ quem escuta (grafo).
function renderPref(p) {
  const cur = localStorage.getItem(p.key) ?? String(p.default);
  const set = (v) => { localStorage.setItem(p.key, String(v)); window.dispatchEvent(new CustomEvent('aila:pref', { detail: { key: p.key, value: String(v) } })); };
  let ctl;
  if (p.type === 'select') {
    ctl = el('select', { class: 'cfg-input' });
    (p.options || []).forEach((o) => ctl.append(el('option', { value: o }, o)));
    ctl.value = cur; ctl.onchange = () => set(ctl.value);
  } else {
    const on = cur === 'true';
    ctl = el('button', { class: 'toggle toggle-button' + (on ? ' on' : ''), type: 'button',
      role: 'switch', 'aria-checked': String(on), 'aria-label': p.label, onclick: () => {
      const now = !ctl.classList.contains('on'); ctl.classList.toggle('on', now);
      ctl.setAttribute('aria-checked', String(now)); set(now);
    } }, el('span', { class: 'sw', 'aria-hidden': 'true' }));
  }
  return el('div', { class: 'cfg-row' },
    el('div', { class: 'cfg-meta' },
      el('label', { class: 'cfg-label' }, p.label),
      p.hint ? el('div', { class: 'cfg-hint muted' }, p.hint) : null),
    el('div', { class: 'cfg-ctl' }, ctl));
}

/* gera a navegação + os painéis a partir do schema (uma vez) */
function buildSettings() {
  const nav = byId('settings-nav'); const main = byId('settings-main');
  if (!nav || !main) return;
  nav.innerHTML = '<div class="settings-brand"><div class="settings-title">AILA // AJUSTES</div>'
    + '<div class="settings-subtitle">CENTRO DE CONTROLE</div></div>';
  main.innerHTML = '<div class="settings-toolbar"><span id="cfg-save-status" class="cfg-save-status" data-state="idle">Tudo atualizado</span>'
    + '<button class="settings-close-x" type="button" id="btn-settings-close-x" aria-label="Fechar configurações">×</button></div>'
    + '<div class="cfg-restart" id="cfg-restart">↻ Reinicie a Aila para aplicar algumas mudanças.</div>';

  CATEGORIES.forEach((cat, idx) => {
    nav.append(el('button', { class: 'snav' + (idx === 0 ? ' active' : ''), 'data-p': cat.id,
      'aria-current': idx === 0 ? 'page' : 'false',
      onclick: () => settingsTab(cat.id) }, `${cat.icon} ${cat.label}`));

    const pane = el('section', { class: 'spane' + (idx === 0 ? ' active' : ''), id: 'sp-' + cat.id,
      'aria-hidden': String(idx !== 0) },
      el('header', { class: 'settings-pane-head' },
        el('div', { class: 'settings-pane-icon', 'aria-hidden': 'true' }, cat.icon),
        el('div', {}, el('h3', {}, cat.label),
          el('p', { class: 'settings-pane-desc' }, CATEGORY_DESCRIPTIONS[cat.id] || 'Configurações da Aila.'))));
    cat.blocks.forEach((b) => {
      const section = el('div', { class: 'cfg-section' + (b.note && !b.fields && !b.custom && !b.pref ? ' cfg-section-note' : '') });
      if (b.title) section.append(el('div', { class: 'cfg-block-t' }, b.title));
      if (b.fields) section.append(el('div', { class: 'cfg-fields', 'data-fields': JSON.stringify(b.fields) }));
      if (b.custom) section.append(el('div', { class: 'html', html: CUSTOM_HTML[b.custom] || '' }));
      if (b.pref) b.pref.forEach((p) => section.append(renderPref(p)));
      if (b.note) section.append(el('p', { class: 'muted cfg-note' }, b.note));
      pane.append(section);
    });
    main.append(pane);
  });
  nav.append(el('div', { class: 'spacer' }));
  nav.append(el('div', { class: 'settings-side-foot' },
    el('span', {}, `${CATEGORIES.length} módulos`),
    el('button', { class: 'btn', id: 'btn-settings-close', onclick: closeSettings }, 'Fechar')));
  byId('btn-settings-close-x').onclick = closeSettings;
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
  byId('avatar3d')?.addEventListener('load', sendAvatarTheme);
  buildSettings();     // gera nav + painéis a partir do schema

  // swatches de tema (o container #themes é gerado no bloco custom de "Geral")
  const box = byId('themes');
  if (box) {
    THEMES.forEach((t) => {
      const s = document.createElement('button');
      s.type = 'button'; s.className = 'swatch'; s.dataset.id = t.id; s.title = `Tema ${t.label}`;
      s.style.setProperty('--swatch-a', t.c); s.style.setProperty('--swatch-b', t.c2); s.style.setProperty('--swatch-bg', t.tone);
      s.innerHTML = `<i></i><span>${t.label}</span>`;
      s.onclick = () => setTheme(t.id); box.appendChild(s);
    });
  }
  setTheme(localStorage.getItem('aila-theme') || 'aqua');
  applyAppearancePrefs();
  window.addEventListener('aila:pref', (e) => {
    if (String(e.detail?.key || '').startsWith('aila.ui.')) applyAppearancePrefs();
  });

  // fechar clicando fora
  byId('settings-overlay').addEventListener('click', (e) => { if (e.target.id === 'settings-overlay') closeSettings(); });
  byId('settings-overlay').addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { closeSettings(); return; }
    if (e.key !== 'Tab') return;
    const visible = [...byId('settings-overlay').querySelectorAll('button, input, select, textarea, [tabindex]:not([tabindex="-1"])')]
      .filter((node) => !node.disabled && node.offsetParent !== null);
    if (!visible.length) return;
    const first = visible[0]; const last = visible[visible.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

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
