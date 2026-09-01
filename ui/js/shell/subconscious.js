// ============================================================
//  Mini-subconsciente — grafo real no canto superior esquerdo do palco.
//  Mesmo renderizador da aba Mente, sem dependências e sem interação.
// ============================================================
import { api } from '../core/api.js';
import { ForceGraph } from '../graph/forcegraph.js';

let fg = null;
let signature = '';

export function initSubconscious() {
  const stage = document.querySelector('.content.stage');
  if (!stage || document.getElementById('subc')) return;
  const el = document.createElement('div');
  el.className = 'subc'; el.id = 'subc';
  el.innerHTML = `<div class="subc-cv"><canvas id="subc-canvas"></canvas></div>
    <div class="subc-cap"><span class="subc-dot"></span>subconsciente</div>`;
  stage.appendChild(el);
  fg = new ForceGraph(document.getElementById('subc-canvas'), { mini: true });
  const applyPref = () => { el.style.display = localStorage.getItem('aila.subc.mini') === 'false' ? 'none' : ''; };
  applyPref();
  window.addEventListener('aila:pref', (event) => {
    if (event.detail?.key === 'aila.subc.mini') applyPref();
  });
  load();
  setInterval(() => { if (fg && el.offsetParent) fg.think(); }, 2600);
  setInterval(load, 20000);
}

async function load() {
  try {
    let data = await api.graph('knowledge', 160);
    if (!data.nodes || data.nodes.length < 3) data = await api.graph('code', 120);
    if (!data.nodes?.length) return;
    const next = `${data.kind}:${data.nodes.length}:${data.edges.length}`;
    if (next === signature) return;
    signature = next; fg.setData(data);
  } catch (_) { /* offline: mantém o último estado válido */ }
}
