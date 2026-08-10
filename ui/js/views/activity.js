// ============================================================
//  Activity Center — feed de atividade em tempo real, humanizado.
//  Fonte: State.activity (ao vivo, via core/events.js:ingest) +
//  backfill de /api/events (histórico recente, já redigido no backend).
//  Cada item pode expandir os "detalhes técnicos" (dados brutos).
// ============================================================
import { byId, el } from '../dom.js';
import { State } from '../state.js';
import { api } from '../core/api.js';
import { humanizeEvent } from '../core/humanize.js';

const MAX_ITEMS = 60;

export function initActivity(mount) {
  mount.innerHTML = '';
  mount.append(
    el('div', { class: 'act-head' },
      el('span', { class: 'act-title' }, 'ATIVIDADE'),
      el('button', { class: 'act-clear', title: 'Limpar', onclick: () => (byId('act-list').innerHTML = '') }, '⌫'),
    ),
    el('div', { class: 'act-list', id: 'act-list' },
      el('div', { class: 'act-empty', id: 'act-empty' }, 'Sem atividade ainda. Peça algo à Aila.'),
    ),
  );

  const list = byId('act-list');

  // histórico recente (redigido) — mapeado pela MESMA humanização
  backfill(list).catch(() => {});

  // ao vivo: cada novo evento entra no topo
  State.on((_s, patch) => {
    if (patch && patch.activityAdded) prepend(list, patch.activityAdded);
  });
}

async function backfill(list) {
  const { events } = await api.events(40);
  // eventos chegam do mais antigo p/ o mais novo; humaniza e descarta o que não é "atividade"
  for (const ev of events || []) {
    const h = humanizeEvent(ev);
    if (h) prepend(list, { ...h, t: parseTs(ev.t), type: ev.type, raw: ev });
  }
}

function prepend(list, entry) {
  const empty = byId('act-empty');
  if (empty) empty.remove();
  list.prepend(renderItem(entry));
  while (list.children.length > MAX_ITEMS) list.lastChild.remove();
}

function renderItem(a) {
  const hasRaw = !!a.raw;
  const item = el('div', { class: 'act-item', 'data-tone': a.tone || 'info' },
    el('span', { class: 'act-icon' }, a.icon || '·'),
    el('div', { class: 'act-body' },
      el('div', { class: 'act-text' }, a.text || ''),
      el('div', { class: 'act-time' }, fmtTime(a.t)),
    ),
  );
  if (hasRaw) {
    item.classList.add('has-raw');
    const raw = el('pre', { class: 'act-raw' }, safeJson(a.raw));
    item.append(raw);
    item.addEventListener('click', () => item.classList.toggle('open'));
  }
  return item;
}

/* ---------- helpers ---------- */
const parseTs = (iso) => { const n = Date.parse(iso); return Number.isNaN(n) ? Date.now() : n; };

function fmtTime(t) {
  const d = new Date(t || Date.now());
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function safeJson(raw) {
  try { return JSON.stringify(raw, null, 2); }
  catch { return String(raw); }
}
