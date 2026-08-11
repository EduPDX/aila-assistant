// ============================================================
//  Events — camada de OBSERVAÇÃO do fluxo do WebSocket.
//  Toda mensagem do backend passa por ingest(): atualiza o State
//  global e alimenta o feed de atividade humanizado.
//  NÃO faz o dispatch de UI (chat/avatar continuam no main.js:route);
//  esta camada é aditiva e desacoplada.
// ============================================================
import { State } from '../state.js';
import { humanizeEvent } from './humanize.js';

// eventos que viram uma linha no feed de atividade
const ACTIVITY_TYPES = new Set([
  'agent.invoked', 'agent.result', 'model.selected',
  'permission.request', 'task.created', 'task.state', 'memory.recalled', 'error',
]);

export function ingest(m) {
  if (!m || !m.type) return;

  // --- reflexos no estado global ---
  switch (m.type) {
    case 'aila.state':
      State.set({ status: m.status, tool: m.tool || null });
      break;
    case 'model.selected':
      if (m.provider) State.set({ provider: m.provider });
      break;
    case 'avatar.state':
    case 'avatar.behavior':
      if (m.emotion) State.set({ emotion: m.emotion });
      break;
    case 'task.created':
    case 'task.state':
      State.upsertTask({ id: m.id, goal: m.goal, state: m.state, progress: m.progress });
      break;
    case 'permission.request':
      // WAITING_PERMISSION vira estado de 1ª classe (director → data-mode=permission)
      State.set({ pendingPermission: { id: m.id, action: m.action, risk: m.risk, params: m.params } });
      break;
    default:
      break;
  }

  // --- feed de atividade (linguagem humana) ---
  if (ACTIVITY_TYPES.has(m.type)) {
    const h = humanizeEvent(m);
    if (h) State.pushActivity({ ...h, type: m.type, raw: m });
  }
}
