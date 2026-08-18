// ============================================================
//  CENTRAL DE COMANDO (sidebar): Projetos, Tarefas e "O que ela sabe" — visão
//  do que dá pra fazer AGORA. Reaproveita /api/projects, /api/tasks, /api/memory.
//  As conversas viram uma seção COLAPSÁVEL no rodapé (sidebar.js cuida delas).
// ============================================================
import { byId } from './dom.js';
import { api } from './core/api.js';
import * as mind from './mind.js';
import * as chat from './chat.js';

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const goMind = () => { if (window.showTab) window.showTab('mind'); };

export async function loadCentral() {
  renderProjects();
  renderTasks();
  renderMemory();
}

async function renderProjects() {
  const box = byId('cx-projects'); if (!box) return;
  let r; try { r = await api.projects(); } catch (e) { r = { projects: [] }; }
  const ps = r.projects || [], active = r.active;
  if (!ps.length) { box.innerHTML = '<div class="cx-empty">nenhum projeto — clique ＋ para anexar uma pasta.</div>'; return; }
  box.innerHTML = ps.map((p) =>
    `<div class="cx-item${p.slug === active ? ' cx-on' : ''}" data-slug="${esc(p.slug)}" title="${esc(p.name)} · ${p.nodes || 0} nós">
       <span class="cx-item-t">🗂️ ${esc(p.name)}</span>
       ${p.slug === active ? '<span class="cx-badge">ativo</span>' : ''}
     </div>`).join('');
  box.querySelectorAll('.cx-item').forEach((el) => {
    el.onclick = () => { goMind(); mind.showProject(el.dataset.slug); };
  });
}

async function renderTasks() {
  const box = byId('cx-tasks'); if (!box) return;
  let r; try { r = await api.tasks(); } catch (e) { r = { tasks: [] }; }
  const all = r.tasks || [];
  const live = all.filter((t) => ['running', 'pending', 'planning'].includes((t.state || '').toLowerCase()));
  const show = (live.length ? live : all).slice(0, 5);
  if (!show.length) { box.innerHTML = '<div class="cx-empty">nenhuma tarefa em andamento.</div>'; return; }
  box.innerHTML = show.map((t) =>
    `<div class="cx-item" title="${esc(t.goal || '')}">
       <span class="cx-item-t">⚡ ${esc((t.goal || 'tarefa').slice(0, 42))}</span>
       <span class="cx-badge">${esc(t.state || '')}</span>
     </div>`).join('');
}

async function renderMemory() {
  const box = byId('cx-memory'); if (!box) return;
  let r; try { r = await api.memory(16); } catch (e) { r = { recent: [] }; }
  // "o que ela sabe" = memória DURÁVEL (fatos/preferências/projeto), não trechos de conversa
  const durable = (r.recent || []).filter((m) => ['fact', 'preference', 'project', 'semantic'].includes(m.kind)).slice(0, 6);
  if (!durable.length) { box.innerHTML = '<div class="cx-empty">ainda aprendendo sobre você.</div>'; return; }
  box.innerHTML = durable.map((m) =>
    `<div class="cx-fact" title="${esc(m.text || '')}">🧩 ${esc((m.text || '').slice(0, 72))}</div>`).join('');
}

// liga os botões/toggles da Central (uma vez, no boot)
export function initCentral() {
  const addp = byId('cx-addproj');
  if (addp) addp.onclick = async (e) => { e.stopPropagation(); await mind.addProject(); renderProjects(); };

  const dir = byId('btn-attachdir-side');
  if (dir) dir.onclick = () => { if (window.showTab) window.showTab('chat'); chat.attachFolder(); };

  const convH = byId('cx-conv-h'), convBody = byId('cx-conv-body'), chev = byId('cx-conv-chev');
  if (convH && convBody) {
    convH.onclick = () => {
      const open = convBody.classList.toggle('cx-collapsed');
      if (chev) chev.textContent = open ? '▸' : '▾';
    };
  }
  loadCentral();
}
