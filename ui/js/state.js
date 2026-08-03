// ============================================================
//  Estado GLOBAL da Aila — fonte única da verdade.
//  Avatar, chat e painel de status apenas ASSINAM este store.
//  status: IDLE | LISTENING | THINKING | TOOL_RUNNING | CODING |
//          SEARCHING | READING_FILE | ANALYZING_IMAGE | SPEAKING | ERROR
// ============================================================
const _state = {
  status: 'IDLE',
  tool: null,          // ferramenta em execução (quando TOOL_RUNNING/etc.)
  emotion: 'neutral',
  voiceOut: true,      // Aila fala as respostas
  activeSession: null,
  metrics: {},         // preenchido pelo painel de status (fase 2)
};

const _subs = new Set();

export const State = {
  get(key) { return key === undefined ? _state : _state[key]; },
  set(patch) {
    let changed = false;
    for (const k in patch) if (_state[k] !== patch[k]) { _state[k] = patch[k]; changed = true; }
    if (changed) _subs.forEach((fn) => { try { fn(_state, patch); } catch (e) { console.error(e); } });
  },
  /** assina mudanças; retorna função para cancelar */
  on(fn) { _subs.add(fn); return () => _subs.delete(fn); },
};

// rótulos amigáveis por estado (usado na topbar e no painel)
export const STATUS_LABEL = {
  IDLE: 'Ocioso', LISTENING: 'Ouvindo', THINKING: 'Pensando', TOOL_RUNNING: 'Executando',
  CODING: 'Programando', SEARCHING: 'Pesquisando', READING_FILE: 'Lendo arquivo',
  ANALYZING_IMAGE: 'Analisando imagem', SPEAKING: 'Falando', ERROR: 'Erro',
};
