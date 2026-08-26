// Sidebar: histórico de conversas — busca, grupos por data, renomear, apagar.
import { byId } from './dom.js';
import { State } from './state.js';
import { wsSend, wsReady } from './ws.js';
import { contextMenu, confirmDialog, promptDialog } from './ui.js';

export function newSession() { if (wsReady()) wsSend({ type: 'session.new' }); }
export function openSession(id) { if (wsReady()) wsSend({ type: 'session.load', id }); }

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

let _sessions = [];

export async function loadSessions() {
  // o histórico saiu da barra lateral: sem a lista no DOM, não busca à toa
  if (!byId('sessions')) return;
  try {
    const r = await (await fetch('/api/sessions')).json();
    if (r.current != null) State.set({ activeSession: r.current });
    _sessions = r.sessions || [];
    renderSessions();
  } catch (e) { /* offline */ }
}

function dayGroup(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return 'Conversas';
  const startOf = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.floor((startOf(new Date()) - startOf(d)) / 86400000);
  if (diff <= 0) return 'Hoje';
  if (diff === 1) return 'Ontem';
  if (diff <= 7) return 'Últimos 7 dias';
  if (diff <= 30) return 'Últimos 30 dias';
  return 'Mais antigas';
}

export function renderSessions() {
  const box = byId('sessions'); if (!box) return;
  const q = (byId('search')?.value || '').trim().toLowerCase();
  const active = State.get('activeSession');
  const list = _sessions.filter((s) => !q || (s.title || '').toLowerCase().includes(q));

  if (!list.length) {
    box.innerHTML = `<div class="muted" style="padding:10px">${q ? 'nada encontrado' : 'sua linha do tempo aparece aqui'}</div>`;
    return;
  }
  const groups = [];
  const seen = {};
  for (const s of list) {                     // já vem ordenado por data (DESC)
    const g = dayGroup(s.created_at);
    if (!seen[g]) { seen[g] = []; groups.push([g, seen[g]]); }
    seen[g].push(s);
  }
  box.innerHTML = groups.map(([g, items]) =>
    `<div class="day">${g}</div>` + items.map((s) =>
      `<div class="session-item ${s.id === active ? 'active' : ''}" data-id="${s.id}">
         <span class="title">💬 ${esc(s.title || ('conversa ' + s.id))}</span>
         <button class="dots" data-id="${s.id}" title="Opções">⋯</button>
       </div>`).join('')).join('');

  box.querySelectorAll('.session-item').forEach((it) => {
    it.onclick = (e) => { if (!e.target.classList.contains('dots')) openSession(+it.dataset.id); };
  });
  box.querySelectorAll('.dots').forEach((btn) => {
    btn.onclick = (e) => { e.stopPropagation(); openMenu(btn, +btn.dataset.id); };
  });
}

function openMenu(anchor, id) {
  const s = _sessions.find((x) => x.id === id);
  contextMenu(anchor, [
    { icon: '✏️', label: 'Renomear episódio', onClick: () => renameSession(id, s?.title || '') },
    { icon: '🗑️', label: 'Apagar episódio', danger: true, onClick: () => deleteSession(id) },
  ]);
}

async function renameSession(id, current) {
  const title = await promptDialog({ title: 'Renomear episódio', value: current, placeholder: 'Novo título' });
  if (!title) return;
  await fetch(`/api/sessions/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }),
  });
  loadSessions();
}

async function deleteSession(id) {
  const ok = await confirmDialog({
    title: 'Apagar episódio?', body: 'Esta ação não pode ser desfeita.',
    confirmLabel: 'Apagar', danger: true,
  });
  if (!ok) return;
  const wasActive = State.get('activeSession') === id;
  await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
  await loadSessions();
  if (wasActive) newSession();   // inicia uma conversa nova (limpa o chat via session.changed)
}
