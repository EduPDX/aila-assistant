// ============================================================
//  Mini-subconsciente (Fase 11, v2) — um GRAFO pequeno no canto superior
//  esquerdo do palco, sempre em leve movimento e "pensando" (pulsa nós
//  aleatórios), como se a Aila estivesse processando. Mesmo renderizador
//  da aba 🧠 (canvas, sem deps). 100% pointer-events:none.
// ============================================================
import { api } from '../core/api.js';
import { ForceGraph } from '../graph/forcegraph.js';

let fg = null;

export function initSubconscious() {
  const stage = document.querySelector('.content.stage');
  if (!stage || document.getElementById('subc')) return;

  const el = document.createElement('div');
  el.className = 'subc';
  el.id = 'subc';
  el.innerHTML =
    `<div class="subc-cv"><canvas id="subc-canvas"></canvas></div>
     <div class="subc-cap"><span class="subc-dot"></span>subconsciente</div>`;
  stage.appendChild(el);

  fg = new ForceGraph(document.getElementById('subc-canvas'), { mini: true });
  load();
  // "pensa" periodicamente: destaca um nó, dando a sensação de processar
  setInterval(() => { if (fg && document.getElementById('subc')?.offsetParent) fg.think(); }, 2600);
}

async function load() {
  try {
    const d = await api.graph('code', 120);      // amostra pequena p/ o canto
    if (d.nodes && d.nodes.length) fg.setData(d);
  } catch (e) { /* offline: mantém vazio */ }
}
