// ============================================================
//  Director — camada ADAPTATIVA da interface.
//  Traduz o estado do agente (aila.state + permissão pendente) em um
//  "UI mode" e o publica como data-mode no shell. É a ÚNICA fonte da
//  adaptação de layout/densidade — NÃO duplica o avatar, que já recebe
//  o estado pela ponte existente (avatar.js → iframe).
//
//  Fluxo:  backend → WS → State.status/pendingPermission → director → data-mode
//  Nada aqui muda o visual por si só (Fatia 1): apenas expõe o modo para
//  o CSS/JS reagirem nas fatias seguintes.
// ============================================================
import { State } from '../state.js';

// aila.state (status do backend) → densidade/foco da UI
const MODE_BY_STATUS = {
  IDLE: 'idle',
  LISTENING: 'conversation',
  THINKING: 'conversation',
  SPEAKING: 'conversation',
  SEARCHING: 'working',
  READING_FILE: 'working',
  CODING: 'working',
  ANALYZING_IMAGE: 'working',
  TOOL_RUNNING: 'working',
  ERROR: 'error',
};

// prioridade: permissão pendente e erro vencem o estado corrente
function computeMode(s) {
  if (s.pendingPermission) return 'permission';
  if (s.status === 'ERROR') return 'error';
  return MODE_BY_STATUS[s.status] || 'idle';
}

let applying = false;

export function initDirector() {
  const apply = () => {
    if (applying) return;              // evita reentrância do State.set abaixo
    applying = true;
    const s = State.get();
    const mode = computeMode(s);
    document.body.dataset.mode = mode;
    document.body.dataset.status = s.status || 'IDLE';
    if (s.uiMode !== mode) State.set({ uiMode: mode });  // director é o único a escrever uiMode
    applying = false;
  };
  State.on(apply);
  apply();
}
