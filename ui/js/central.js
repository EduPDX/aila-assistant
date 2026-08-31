// ============================================================
//  CENTRAL DE COMANDO (sidebar): Projetos, Tarefas e "O que ela sabe" — visão
//  do que dá pra fazer AGORA. Reaproveita /api/projects, /api/tasks, /api/memory.
//  As conversas viram uma seção COLAPSÁVEL no rodapé (sidebar.js cuida delas).
// ============================================================
import { byId } from './dom.js';
import { api } from './core/api.js';
import * as mind from './mind.js';

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
  if (byId('cx-project-count')) byId('cx-project-count').textContent = ps.length;
  if (!ps.length) { box.innerHTML = '<div class="cx-empty">nenhum projeto adicionado.</div>'; return; }
  box.innerHTML = ps.map((p) =>
    `<div class="cx-item${p.slug === active ? ' cx-on' : ''}" data-slug="${esc(p.slug)}" title="${esc(p.name)} · ${p.nodes || 0} nós">
       <span class="cx-project-icon">${p.source_type === 'file' ? '📄' : '📁'}</span>
       <span class="cx-project-info"><span class="cx-item-t">${esc(p.name)}</span><small>${p.nodes || 0} nós · ${p.files || 0} arq.</small></span>
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
  if (byId('cx-task-count')) byId('cx-task-count').textContent = live.length;
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
  if (byId('cx-memory-count')) byId('cx-memory-count').textContent = durable.length;
  if (!durable.length) { box.innerHTML = '<div class="cx-empty">ainda aprendendo sobre você.</div>'; return; }
  box.innerHTML = durable.map((m) =>
    `<div class="cx-fact" title="${esc(m.text || '')}">🧩 ${esc((m.text || '').slice(0, 72))}</div>`).join('');
}

// liga os botões/toggles da Central (uma vez, no boot)
export function initCentral() {
  const dir = byId('btn-attachdir-side');
  if (dir) dir.onclick = async () => {
    if (await mind.addProject()) {
      await renderProjects();
      goMind();
      mind.showProjects();
    }
  };

  loadCentral();
}
