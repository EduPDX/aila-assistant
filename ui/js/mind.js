// ============================================================
//  Aba 🧠 Subconsciente (Fase 12, v2) — VISUALIZAÇÃO EM GRAFO estilo
//  Graphify: nós coloridos por comunidade, física, painel de comunidades,
//  clique p/ ver vizinhos, busca, e seletor Código ↔ Conhecimento.
//  Fonte: GET /api/graph. Renderizador próprio (canvas, sem deps).
// ============================================================
import { api } from './core/api.js';
import { ForceGraph } from './graph/forcegraph.js';
import { ForceGraph3D } from './graph/forcegraph3d.js';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

let fg = null;
let kind = 'code';
let communities = [];
let visible = null;          // Set de comunidades visíveis
let built = false;

export function showMind(on) {
  if (on && !built) build();
}

/** abre já num grafo específico: 'code' (arquivos internos) | 'knowledge' (conversa) */
export function showKind(k) {
  kind = (k === 'knowledge') ? 'knowledge' : 'code';
  if (!built) build();           // build() lê `kind` e carrega o certo
  else { updateKindButtons(); load(kind); }
}

function updateKindButtons() {
  $('mind-kindsel')?.querySelectorAll('button')
    .forEach((b) => b.classList.toggle('active', b.dataset.k === kind));
}

// cria o renderizador conforme a preferência (2D canvas ou 3D three.js). Como um
// <canvas> não troca de contexto (2d↔webgl), sempre uso um canvas NOVO.
function makeGraph() {
  const old = $('mind-canvas');
  const cv = document.createElement('canvas'); cv.id = 'mind-canvas';
  old.replaceWith(cv);
  const Renderer = localStorage.getItem('aila.graph.mode') === '3d' ? ForceGraph3D : ForceGraph;
  return new Renderer(cv, { interactive: true, onNode: renderNodeInfo });
}

function build() {
  built = true;
  fg = makeGraph();
  // trocar 2D↔3D nas Configurações → recria o grafo e recarrega
  window.addEventListener('aila:pref', (e) => {
    if (e.detail?.key !== 'aila.graph.mode' || !built) return;
    try { fg.destroy(); } catch (_) {}
    fg = makeGraph(); load(kind);
  });

  $('mind-kindsel').querySelectorAll('button').forEach((b) => {
    b.onclick = () => {
      kind = b.dataset.k;
      $('mind-kindsel').querySelectorAll('button').forEach((x) => x.classList.toggle('active', x === b));
      load(kind);
    };
  });
  $('mind-all').onchange = (e) => {
    const on = e.target.checked;
    visible = on ? null : new Set();
    $('mind-comm').querySelectorAll('input').forEach((c) => { c.checked = on; });
    fg.setVisible(visible);
  };
  const search = $('mind-search');
  search.addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(search.value); });
  search.addEventListener('input', () => { if (!search.value) fg.select(null); });

  updateKindButtons();
  load(kind);
}

async function load(k) {
  let data;
  try { data = await api.graph(k, 1500); } catch (e) { data = { nodes: [], edges: [], communities: [] }; }
  communities = data.communities || [];
  visible = null;
  const empty = $('mind-empty');
  if (!data.nodes || !data.nodes.length) {
    empty.hidden = false;
    empty.innerHTML = k === 'knowledge'
      ? '🌙 O grafo de conhecimento ainda está vazio.<br><span class="muted">A Aila constrói isso conforme conversa e consolida o que aprende.</span>'
      : 'sem dados de código';
    $('mind-stats').textContent = '';
    fg.setData({ nodes: [], edges: [], communities: [] });
    renderCommunities();
    return;
  }
  empty.hidden = true;
  fg.setData(data);
  renderCommunities();
  renderNodeInfo(null);
  const c = data.counts || {};
  $('mind-stats').textContent = `${c.nodes || 0} nós · ${c.edges || 0} arestas · ${c.communities || 0} comunidades`;
  if ($('mind-all')) $('mind-all').checked = true;
}

function renderCommunities() {
  const box = $('mind-comm'); if (!box) return;
  if (!communities.length) { box.innerHTML = '<div class="muted" style="padding:8px">—</div>'; return; }
  box.innerHTML = communities.map((c) =>
    `<label class="mind-crow">
       <input type="checkbox" data-c="${esc(c.id)}" checked>
       <span class="mind-dot" style="background:${fg.color.get(c.id) || '#8aa'}"></span>
       <span class="mind-clabel">${esc(c.label)}</span>
       <span class="mind-ccount">${c.count}</span>
     </label>`).join('');
  box.querySelectorAll('input').forEach((cb) => {
    cb.onchange = () => {
      const on = new Set();
      box.querySelectorAll('input').forEach((x) => { if (x.checked) on.add(x.dataset.c); });
      visible = on.size === communities.length ? null : on;
      fg.setVisible(visible);
      $('mind-all').checked = visible === null;
    };
  });
}

function renderNodeInfo(node, neighbors = []) {
  const box = $('mind-nodeinfo'); if (!box) return;
  if (!node) {
    box.innerHTML = '<div class="muted">clique num nó para ver detalhes</div>';
    return;
  }
  const nb = neighbors.slice(0, 30).map((n) =>
    `<div class="mind-nb" data-id="${esc(n.id)}"><span class="mind-dot" style="background:${fg.color.get(n.community) || '#8aa'}"></span>${esc(n.label)}</div>`).join('');
  box.innerHTML =
    `<div class="mind-ni-name">${esc(node.label)}</div>
     <div class="mind-ni-k">tipo <b>${esc(node.type || '—')}</b></div>
     <div class="mind-ni-k">comunidade <b>${esc(node.community || '—')}</b></div>
     <div class="mind-ni-k">grau <b>${node.degree || 0}</b></div>
     <div class="mind-ni-h">Vizinhos (${neighbors.length})</div>
     <div class="mind-nbs">${nb || '<span class="muted">nenhum</span>'}</div>`;
  box.querySelectorAll('.mind-nb').forEach((el) => { el.onclick = () => fg.selectById(el.dataset.id); });
}

function doSearch(q) {
  q = (q || '').trim().toLowerCase(); if (!q || !fg) return;
  const hit = fg.nodes.find((n) => (n.label || '').toLowerCase() === q)
    || fg.nodes.find((n) => (n.label || '').toLowerCase().includes(q));
  if (hit) fg.selectById(hit.id);
}
