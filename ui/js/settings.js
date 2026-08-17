// Settings Center (⚙️): Geral · Aparência · Modelos e IA · Voz · Avatar ·
// Autonomia · Rede & Privacidade · Sistema. Só o que o backend suporta.
import { byId, $$, el } from './dom.js';
import { State } from './state.js';
import { avatarReload } from './avatar.js';
import { renderProviders } from './views/providers.js';
import { api } from './core/api.js';
import { confirmDialog } from './ui.js';

const THEMES = [
  { id: 'aqua', c: '#38e1d0' }, { id: 'cyber', c: '#c257ff' }, { id: 'rose', c: '#ff6fae' },
  { id: 'forest', c: '#43e08a' }, { id: 'light', c: '#0bb3a0' },
];

export function setTheme(id) {
  document.documentElement.setAttribute('data-theme', id);
  localStorage.setItem('aila-theme', id);
  $$('.swatch').forEach((s) => s.classList.toggle('active', s.dataset.id === id));
}

export const openSettings = () => byId('settings-overlay').classList.add('show');
export const closeSettings = () => byId('settings-overlay').classList.remove('show');
export function settingsTab(p) {
  $$('.snav').forEach((b) => b.classList.toggle('active', b.dataset.p === p));
  $$('.spane').forEach((s) => s.classList.toggle('active', s.id === 'sp-' + p));
  if (p === 'modelos') renderProviders();     // provedores (local + nuvem)
  if (p === 'autonomia') renderAutonomy();
  if (p === 'permissoes') renderPermissions();
  if (p === 'memoria') renderMemory();
  if (p === 'rede') renderNetwork();
  if (p === 'voz') loadStatus();              // refaz o status de voz
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
  // swatches de tema
  const box = byId('themes');
  THEMES.forEach((t) => {
    const s = document.createElement('div');
    s.className = 'swatch'; s.dataset.id = t.id; s.style.background = t.c; s.title = t.id;
    s.onclick = () => setTheme(t.id); box.appendChild(s);
  });
  setTheme(localStorage.getItem('aila-theme') || 'aqua');

  // fechar clicando fora
  byId('settings-overlay').addEventListener('click', (e) => { if (e.target.id === 'settings-overlay') closeSettings(); });

  // busca nas memórias (filtra a lista carregada)
  byId('mem-search')?.addEventListener('input', (e) => drawMemory(e.target.value));

  // trocar VRM
  byId('pickvrm').onclick = () => byId('vrmfile').click();
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

  // toggle de voz
  byId('tg-voice').onclick = () => {
    const on = !State.get('voiceOut'); State.set({ voiceOut: on });
    byId('tg-voice').classList.toggle('on', on);
  };

  bindStatusRows();   // linhas do painel de Status espelham o State global
}
