// ============================================================
//  Aba 🧠 Subconsciente (Fase 12, v2) — VISUALIZAÇÃO EM GRAFO estilo
//  Graphify: nós coloridos por comunidade, física, painel de comunidades,
//  clique p/ ver vizinhos, busca, e seletor Código ↔ Conhecimento.
//  Fonte: GET /api/graph. Renderizador próprio (canvas, sem deps).
// ============================================================
import { api } from './core/api.js';
import { ForceGraph } from './graph/forcegraph.js';
import { ForceGraph3D } from './graph/forcegraph3d.js';
import { graphThumbnail } from './graph/thumbnail.js';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

let fg = null;
let kind = 'code';
let communities = [];
let visible = null;          // Set de comunidades visíveis
let built = false;
let currentProject = null;   // slug do projeto aberto (só quando kind='project')
let projectList = [];        // cache dos projetos (nome/contagens p/ a grade)

export function showMind(on) {
  if (on && !built) build();
}

/** abre já num grafo específico: 'code' (arquivos internos) | 'knowledge' (conversa) */
export function showKind(k) {
  kind = (k === 'knowledge') ? 'knowledge' : 'code';
  if (!built) build();           // build() lê `kind` e carrega o certo
  else { updateKindButtons(); refresh(); }
}

// roteia a view conforme o `kind`: 'project' sem projeto aberto → grade;
// projeto aberto ou code/knowledge → grafo único.
function refresh() {
  if (kind === 'project' && !currentProject) { showGrid(); return; }
  load(kind);
}

// alterna entre a GRADE de projetos e a view de GRAFO único (esconde/mostra os
// elementos certos: canvas, painel lateral, stats, botão voltar).
function setMode(mode) {
  const grid = mode === 'grid';
  $('mind-grid').hidden = !grid;
  const side = document.querySelector('.mind-side');
  if (side) side.style.display = grid ? 'none' : '';
  const cv = $('mind-canvas'); if (cv) cv.style.visibility = grid ? 'hidden' : '';
  $('mind-stats').style.display = grid ? 'none' : '';
  $('mind-back').hidden = !(mode === 'graph' && currentProject);
  if (grid) $('mind-empty').hidden = true;
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
      if (kind !== 'project') currentProject = null;
      $('mind-kindsel').querySelectorAll('button').forEach((x) => x.classList.toggle('active', x === b));
      refresh();
    };
  });
  $('mind-back').onclick = () => { currentProject = null; refresh(); };
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
  refresh();
}

async function load(k) {
  setMode('graph');
  let data;
  try {
    data = (k === 'project')
      ? await api.graph('project', 1500, currentProject)
      : await api.graph(k, 1500);
  } catch (e) { data = { nodes: [], edges: [], communities: [] }; }
  communities = data.communities || [];
  visible = null;
  const empty = $('mind-empty');
  if (!data.nodes || !data.nodes.length) {
    empty.hidden = false;
    empty.innerHTML = k === 'knowledge'
      ? '🌙 O grafo de conhecimento ainda está vazio.<br><span class="muted">A Aila constrói isso conforme conversa e consolida o que aprende.</span>'
      : k === 'project'
        ? 'sem código Python mapeável neste projeto'
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

// ---------------------------------------------------------------- Projetos
async function showGrid() {
  setMode('grid');
  const grid = $('mind-grid');
  grid.innerHTML = '<div class="muted" style="padding:20px">carregando projetos…</div>';
  try { projectList = (await api.projects()).projects || []; }
  catch (e) { projectList = []; }
  renderCards();
}

function cardHTML(p) {
  return `<div class="mind-card" data-slug="${esc(p.slug)}">
      <button class="mind-card-del" title="Remover projeto">✕</button>
      <div class="mind-card-thumb"><img alt=""></div>
      <div class="mind-card-body">
        <div class="mind-card-name" title="${esc(p.name)}">${esc(p.name)}</div>
        <div class="mind-card-meta">${p.nodes || 0} nós · ${p.edges || 0} arestas · ${p.files || 0} arq.</div>
        <button class="mind-card-work">Trabalhar no projeto</button>
      </div>
    </div>`;
}

function renderCards() {
  const grid = $('mind-grid');
  const add = '<div class="mind-addcard" id="mind-addproj">'
    + '<div class="plus">+</div><div>Adicionar projeto</div>'
    + '<div class="muted" style="font-size:11px">anexe uma pasta pra ela mapear</div></div>';
  grid.innerHTML = add + projectList.map(cardHTML).join('');
  $('mind-addproj').onclick = addProjectFlow;
  grid.querySelectorAll('.mind-card').forEach((cardEl) => {
    const slug = cardEl.dataset.slug;
    const p = projectList.find((x) => x.slug === slug) || {};
    const open = () => openProject(slug);
    cardEl.querySelector('.mind-card-thumb').onclick = open;
    cardEl.querySelector('.mind-card-name').onclick = open;
    cardEl.querySelector('.mind-card-work').onclick = (e) => { e.stopPropagation(); open(); };
    cardEl.querySelector('.mind-card-del').onclick = (e) => { e.stopPropagation(); removeProjectFlow(slug, p.name); };
  });
  fillThumbs();
}

// gera as miniaturas uma a uma (sequencial → não martela o backend nem a CPU)
async function fillThumbs() {
  for (const p of projectList) {
    const img = document.querySelector(`.mind-card[data-slug="${cssq(p.slug)}"] img`);
    if (!img) continue;
    try {
      const data = await api.graph('project', 800, p.slug);
      img.src = graphThumbnail(data, 156);
    } catch (e) { /* miniatura é best-effort */ }
  }
}

async function openProject(slug) {
  currentProject = slug;
  kind = 'project';
  updateKindButtons();
  await load('project');
}

async function addProjectFlow() {
  const path = window.prompt('Caminho da pasta do projeto\n(ex.: E:\\Projetos\\meu-app):');
  if (!path || !path.trim()) return;
  const add = $('mind-addproj');
  if (add) add.innerHTML = '<div class="mind-card-building">construindo grafo…</div>';
  try {
    await api.addProject(path.trim(), null);
    await showGrid();
  } catch (e) {
    window.alert('Não consegui anexar essa pasta. Verifique se o caminho existe e tem código Python.');
    renderCards();
  }
}

async function removeProjectFlow(slug, name) {
  if (!window.confirm(`Remover o projeto "${name || slug}"?\nO grafo dele será apagado — a pasta original NÃO é tocada.`)) return;
  try { await api.removeProject(slug); } catch (e) { /* ignora */ }
  await showGrid();
}

// escapa aspas p/ usar o slug num seletor CSS
function cssq(s) { return String(s).replace(/["\\]/g, '\\$&'); }
