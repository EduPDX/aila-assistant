// ============================================================
//  Task Center — tarefas autônomas (Planner + TaskManager).
//  Fonte: /api/tasks (lista/detalhe) + eventos task.* ao vivo.
//  Ações SUPORTADAS pelo backend: criar (L4+), cancelar, ver detalhe.
//  (pausar/retomar NÃO existe no backend → não é oferecido.)
// ============================================================
import { byId, el } from '../dom.js';
import { State } from '../state.js';
import { api } from '../core/api.js';
import { taskStateLabel } from '../core/humanize.js';
import { promptDialog } from '../ui.js';

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);
const openIds = new Set();
let pollTimer = null;
let stateBound = false;

export function initTasks(mount) {
  mount.innerHTML = '';
  mount.append(
    el('div', { class: 'act-head' },
      el('span', { class: 'act-title' }, 'TAREFAS'),
      el('button', { class: 'task-new', title: 'Nova tarefa autônoma', onclick: newTask }, '＋'),
    ),
    el('div', { class: 'task-note', id: 'task-note' }),
    el('div', { class: 'task-list', id: 'task-list' }),
  );

  render();
  seed().catch(() => {});
  // Tarefas em background (via REST) publicam no Event Bus, que NÃO é ponte p/ o
  // WebSocket — então fazemos poll do /api/tasks (barato, lista em memória).
  // O ingest de task.* (core/events.js) cobre o caso de eventos que cheguem via WS.
  if (pollTimer === null) pollTimer = setInterval(() => seed().catch(() => {}), 4000);
  if (!stateBound) {
    State.on((_s, patch) => { if (patch && (patch.taskUpserted || patch.tasks)) render(); });
    stateBound = true;
  }
}

async function seed() {
  const { tasks } = await api.tasks();
  (tasks || []).forEach((t) => State.upsertTask(t));
}

function render() {
  const list = byId('task-list');
  if (!list) return;
  const tasks = Object.values(State.get('tasks'));
  tasks.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''));

  if (!tasks.length) {
    list.innerHTML = '';
    list.append(el('div', { class: 'act-empty' }, 'Nenhuma tarefa ainda. Crie uma tarefa autônoma com ＋.'));
    return;
  }
  list.innerHTML = '';
  for (const t of tasks) list.append(card(t));
}

function card(t) {
  const pct = Math.round((t.progress || 0) * 100);
  const terminal = TERMINAL.has(t.state);
  const c = el('div', { class: 'task-card', 'data-state': t.state || 'pending' },
    el('div', { class: 'task-top' },
      el('span', { class: 'task-goal', title: t.goal }, t.goal || '(sem objetivo)'),
      el('span', { class: 'task-state' }, taskStateLabel(t.state)),
    ),
    el('div', { class: 'task-bar' }, el('i', { style: `width:${pct}%` })),
    el('div', { class: 'task-actions' },
      el('button', { class: 'task-link', onclick: () => toggle(t.id) }, openIds.has(t.id) ? 'ocultar' : 'detalhes'),
      terminal ? null
        : el('button', { class: 'task-link danger', onclick: () => cancelTask(t.id) }, 'cancelar'),
      el('span', { class: 'task-pct' }, `${pct}%`),
    ),
  );
  if (openIds.has(t.id)) c.append(detail(t));
  return c;
}

function detail(t) {
  // /api/tasks já traz plan/tools_used/result/error na própria lista (poll mantém fresco).
  const box = el('div', { class: 'task-detail' });
  if (t.plan && t.plan.length) {
    const steps = el('div', { class: 'task-steps' });
    t.plan.forEach((s) => steps.append(
      el('div', { class: 'task-step', 'data-s': s.status },
        el('span', { class: 'ts-mark' }, mark(s.status)),
        el('span', { class: 'ts-desc' }, s.description),
      ),
    ));
    box.append(steps);
  }
  if (t.tools_used && t.tools_used.length) {
    box.append(el('div', { class: 'task-tools' }, '🔧 ' + [...new Set(t.tools_used)].join(', ')));
  }
  if (t.result) box.append(el('div', { class: 'task-result' }, t.result));
  if (t.error) box.append(el('div', { class: 'task-result err' }, t.error));
  if (!t.plan?.length && !t.result && !t.error) box.append(el('div', { class: 'muted' }, 'sem detalhes ainda…'));
  return box;
}

const mark = (s) => ({ done: '✓', failed: '✕', running: '→', pending: '○' }[s] || '○');

function toggle(id) {
  openIds.has(id) ? openIds.delete(id) : openIds.add(id);
  render();
}

async function cancelTask(id) {
  try { await api.cancelTask(id); } catch { /* o evento task.state cuida */ }
}

async function newTask() {
  if ((State.get('autonomy') || 3) < 4) {
    note('Tarefas autônomas exigem autonomia nível 4 (Autônomo). Ajuste em Configurações.');
    return;
  }
  const goal = await promptDialog({ title: 'Nova tarefa autônoma', placeholder: 'Ex.: pesquisar X e resumir em um arquivo' });
  if (!goal) return;
  try {
    const t = await api.startTask(goal);
    if (t && t.id) { State.upsertTask(t); note(''); }
  } catch (e) {
    note(String(e).includes('403')
      ? 'Negado: autonomia insuficiente (precisa L4).'
      : 'Falha ao criar a tarefa.');
  }
}

function note(msg) {
  const n = byId('task-note');
  if (!n) return;
  n.textContent = msg || '';
  n.classList.toggle('show', !!msg);
}
