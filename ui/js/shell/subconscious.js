// ============================================================
//  Mini-subconsciente (Fase 11) — sobrepõe ao palco, de forma SUTIL,
//  a "atividade mental" da Aila: memórias recuperadas, consolidação
//  ("dreaming"), atualizações do grafo, guardrail e skills. Fonte:
//  GET /api/cognition (só metadados — nunca o conteúdo das memórias).
//  100% pointer-events:none — nunca rouba clique. Quando quieto, fica
//  esmaecido (vivo mas silencioso), sem poluir a tela.
// ============================================================
import { api } from '../core/api.js';

const ICON = {
  'memory.recalled': '🧠', 'memory.consolidated': '🌙', 'graph.updated': '🔗',
  'guardrail.triggered': '🛡', 'skill.ran': '⚙',
};

const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

function label(e) {
  switch (e.type) {
    case 'memory.recalled': return `lembrou ${e.count ?? ''}`.trim();
    case 'memory.consolidated': return `consolidou · ${e.merged || 0} fundidas`;
    case 'graph.updated': return `grafo · ${e.nodes || 0} nós`;
    case 'guardrail.triggered': return `protegeu · ${(e.kinds || []).join(', ') || 'segredo'}`;
    case 'skill.ran': return `skill · ${e.skill || '—'}`;
    default: return e.type;
  }
}

let _sig = '';

export function initSubconscious() {
  const stage = document.querySelector('.content.stage');
  if (!stage || document.getElementById('subc')) return;
  const el = document.createElement('div');
  el.className = 'subc empty';
  el.id = 'subc';
  el.innerHTML =
    `<div class="subc-h"><span class="subc-dot"></span>SUBCONSCIENTE</div>
     <div class="subc-feed" id="subc-feed"></div>`;
  stage.appendChild(el);
  poll();
  setInterval(poll, 3000);
}

async function poll() {
  try {
    const c = await api.cognition(8);
    render(c.recent || []);
  } catch (e) { /* offline: mantém o último estado */ }
}

function render(recent) {
  const feed = document.getElementById('subc-feed');
  const subc = document.getElementById('subc');
  if (!feed || !subc) return;

  const last = recent.slice(-4).reverse();            // mais recentes primeiro
  const sig = last.map((e) => (e.t || '') + e.type).join('|');
  if (sig === _sig) return;                            // nada novo → não re-renderiza
  const isNew = _sig !== '' && last.length > 0;
  _sig = sig;

  subc.classList.toggle('empty', last.length === 0);
  feed.innerHTML = last.map((e, i) =>
    `<div class="subc-item${i === 0 && isNew ? ' pulse' : ''}">
       <span class="subc-ic">${ICON[e.type] || '·'}</span>${esc(label(e))}
     </div>`).join('');
}
