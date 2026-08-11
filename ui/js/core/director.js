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
import { byId } from '../dom.js';
import { humanizeState, humanizeTool } from './humanize.js';

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

// estados de "trabalho" onde vale mostrar a ferramenta específica
const TOOLY = new Set(['TOOL_RUNNING', 'CODING', 'SEARCHING', 'READING_FILE', 'ANALYZING_IMAGE']);

// linha de presença: o que a Aila está fazendo, em linguagem humana
function presenceText(s) {
  if (s.pendingPermission) return 'Aguardando sua autorização';
  if (!s.status || s.status === 'IDLE') return '';
  if (s.tool && TOOLY.has(s.status)) return humanizeTool(s.tool) + '…';
  return humanizeState(s.status) + (s.status === 'ERROR' ? '' : '…');
}

let applying = false;

export function initDirector() {
  const presence = byId('presence');
  const ptxt = presence && presence.querySelector('.presence-txt');

  const apply = () => {
    if (applying) return;              // evita reentrância do State.set abaixo
    applying = true;
    const s = State.get();
    const mode = computeMode(s);
    document.body.dataset.mode = mode;
    document.body.dataset.status = s.status || 'IDLE';

    if (presence) {                    // presença = "Pensando…" / "Rodando um comando…" / …
      const txt = presenceText(s);
      if (ptxt) ptxt.textContent = txt;
      presence.classList.toggle('show', !!txt);
      presence.dataset.tone = mode;
    }

    if (s.uiMode !== mode) State.set({ uiMode: mode });  // director é o único a escrever uiMode
    applying = false;
  };
  State.on(apply);
  apply();
}
