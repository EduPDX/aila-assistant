// ============================================================
//  Inspector — zona DIREITA do command-center. Painel contextual
//  com abas. Fatia atual: Activity (feed) + System (métricas).
//  Tasks/Memory entram como novas abas nas próximas fatias.
// ============================================================
import { byId } from '../dom.js';
import { initActivity } from '../views/activity.js';
import { initTasks } from '../views/tasks.js';
import { initStatusPanel } from '../statuspanel.js';

const TABS = [
  { id: 'activity', label: 'Atividade' },
  { id: 'tasks', label: 'Tarefas' },
  { id: 'system', label: 'Sistema' },
];

export function initInspector() {
  const box = byId('statuspanel');
  if (!box) return;
  box.classList.add('inspector');
  box.innerHTML = `
    <div class="insp-tabs" id="insp-tabs">
      ${TABS.map((t, i) => `<button class="insp-tab${i === 0 ? ' active' : ''}" data-p="${t.id}">${t.label}</button>`).join('')}
    </div>
    <div class="insp-body">
      <div class="insp-pane active" id="insp-activity"></div>
      <div class="insp-pane" id="insp-tasks"></div>
      <div class="insp-pane" id="insp-system"></div>
    </div>`;

  byId('insp-tabs').querySelectorAll('.insp-tab').forEach((b) => {
    b.onclick = () => selectTab(b.dataset.p);
  });

  initActivity(byId('insp-activity'));
  initTasks(byId('insp-tasks'));
  initStatusPanel(byId('insp-system'));
}

function selectTab(p) {
  byId('insp-tabs').querySelectorAll('.insp-tab').forEach((b) => b.classList.toggle('active', b.dataset.p === p));
  document.querySelectorAll('.insp-pane').forEach((s) => s.classList.toggle('active', s.id === 'insp-' + p));
}
