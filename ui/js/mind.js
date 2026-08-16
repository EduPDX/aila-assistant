// ============================================================
//  Aba 🧠 Subconsciente (Fase 12) — visão COMPLETA da cognição da Aila:
//  totais acumulados, atividade cognitiva recente e memória de longo prazo.
//  Fontes: GET /api/cognition (metadados) + GET /api/memory. Só faz poll
//  enquanto a aba está visível (economiza recursos).
// ============================================================
import { api } from './core/api.js';

const ICON = {
  'memory.recalled': '🧠', 'memory.consolidated': '🌙', 'graph.updated': '🔗',
  'guardrail.triggered': '🛡', 'skill.ran': '⚙',
};
// ordem + rótulo dos tiles de totais
const TOTALS = [
  ['memory.recalled', 'lembradas'], ['memory.consolidated', 'consolidações'],
  ['graph.updated', 'grafo'], ['guardrail.triggered', 'proteções'], ['skill.ran', 'skills'],
];

const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

function hhmm(iso) {
  const d = new Date(iso);
  return isNaN(d) ? '' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function feedLabel(e) {
  switch (e.type) {
    case 'memory.recalled': return `recuperou ${e.count ?? 0} memória(s) relevante(s)`;
    case 'memory.consolidated': return `consolidou · ${e.merged || 0} fundidas, ${e.nodes || 0} nós, ${e.edges || 0} relações`;
    case 'graph.updated': return `grafo atualizado · ${e.nodes || 0} nós / ${e.edges || 0} relações`;
    case 'guardrail.triggered': return `protegeu a saída · ${(e.kinds || []).join(', ') || 'segredo'}`;
    case 'skill.ran': return `executou skill · ${e.skill || '—'}${e.ok === false ? ' (falhou)' : ''}`;
    default: return e.type;
  }
}

let _timer = null;

/** Liga/desliga o poll conforme a aba 🧠 fica visível. */
export function showMind(on) {
  clearInterval(_timer);
  _timer = null;
  if (!on) return;
  refresh();
  _timer = setInterval(refresh, 4000);
}

async function refresh() {
  const [c, m] = await Promise.all([
    api.cognition(40).catch(() => ({ totals: {}, recent: [] })),
    api.memory(20).catch(() => ({})),
  ]);
  renderTotals(c.totals || {});
  renderFeed(c.recent || []);
  renderMem(m || {});
}

function renderTotals(totals) {
  const box = document.getElementById('mind-totals'); if (!box) return;
  box.innerHTML = TOTALS.map(([k, lbl]) =>
    `<div class="mind-tile"><span class="mt-ic">${ICON[k]}</span>
       <b>${totals[k] ?? 0}</b><span class="mt-k">${lbl}</span></div>`).join('');
}

function renderFeed(recent) {
  const box = document.getElementById('mind-feed'); if (!box) return;
  if (!recent.length) {
    box.innerHTML = '<div class="muted">sem atividade cognitiva ainda — conversa com a Aila que ela começa a "pensar" aqui</div>';
    return;
  }
  box.innerHTML = recent.slice().reverse().map((e) =>
    `<div class="mind-row"><span class="mr-ic">${ICON[e.type] || '·'}</span>
       <span>${esc(feedLabel(e))}</span><time>${hhmm(e.t)}</time></div>`).join('');
}

function renderMem(m) {
  const cnt = document.getElementById('mind-memcount');
  const box = document.getElementById('mind-mem');
  if (cnt) cnt.textContent = m.enabled === false ? '(desligada)' : `· ${m.count ?? 0} itens`;
  if (!box) return;
  const items = m.recent || [];
  if (!items.length) {
    box.innerHTML = '<div class="muted">nada guardado ainda</div>';
    return;
  }
  box.innerHTML = items.map((it) =>
    `<div class="mind-mi"><span class="k">${esc(it.kind || 'nota')}</span>
       <div>${esc(it.text || '')}</div></div>`).join('');
}
