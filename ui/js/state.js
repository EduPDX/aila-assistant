// ============================================================
//  Estado GLOBAL da Aila — fonte única da verdade.
//  Avatar, chat, topbar, painéis e centers apenas ASSINAM este store.
//  status: IDLE | LISTENING | THINKING | TOOL_RUNNING | CODING |
//          SEARCHING | READING_FILE | ANALYZING_IMAGE | SPEAKING | ERROR
// ============================================================
const _state = {
  // --- agente / conversa ---
  status: 'IDLE',
  tool: null,              // ferramenta em execução (quando TOOL_RUNNING/etc.)
  emotion: 'neutral',
  voiceOut: true,          // Aila fala as respostas
  activeSession: null,

  // --- conexão (WebSocket) ---
  connection: 'connecting', // connecting | online | offline

  // --- modelo / rede / autonomia (de /api/status + evento model.selected) ---
  llmOnline: false,
  backend: null,           // 'ollama' | 'llamacpp'
  model: null,             // modelo padrão (ex.: qwen2.5-coder:7b)
  provider: 'local',       // provedor ATIVO no último turno (local|openai|gemini|grok|deepseek)
  providers: [],           // provedores externos registrados
  networkMode: 'hybrid',   // offline | hybrid
  autonomy: 3,             // 1..5
  readOnly: false,
  memoryCount: 0,
  agents: [],

  // --- tarefas (Task Center) ---
  tasks: {},               // { id: {id, goal, state, progress, …} }

  // --- métricas / atividade ---
  metrics: {},             // preenchido pelo painel de status
  activity: [],            // feed humanizado (anel; mais recente no fim)
};

const _subs = new Set();
const ACTIVITY_CAP = 60;

export const State = {
  get(key) { return key === undefined ? _state : _state[key]; },
  set(patch) {
    let changed = false;
    for (const k in patch) if (_state[k] !== patch[k]) { _state[k] = patch[k]; changed = true; }
    if (changed) _emit(patch);
  },
  /** adiciona uma entrada ao feed de atividade (imutável p/ disparar assinantes). */
  pushActivity(entry) {
    const item = { t: Date.now(), ...entry };
    _state.activity = [..._state.activity.slice(-(ACTIVITY_CAP - 1)), item];
    _emit({ activity: _state.activity, activityAdded: item });
  },
  /** cria/atualiza uma tarefa no mapa (merge). Dispara assinantes com taskUpserted. */
  upsertTask(t) {
    if (!t || !t.id) return;
    const prev = _state.tasks[t.id] || {};
    _state.tasks = { ..._state.tasks, [t.id]: { ...prev, ...t } };
    _emit({ tasks: _state.tasks, taskUpserted: t.id });
  },
  /** assina mudanças; retorna função para cancelar. */
  on(fn) { _subs.add(fn); return () => _subs.delete(fn); },
};

function _emit(patch) {
  _subs.forEach((fn) => { try { fn(_state, patch); } catch (e) { console.error(e); } });
}

// rótulos amigáveis por estado (usado na topbar e no painel)
export const STATUS_LABEL = {
  IDLE: 'Ocioso', LISTENING: 'Ouvindo', THINKING: 'Pensando', TOOL_RUNNING: 'Executando',
  CODING: 'Programando', SEARCHING: 'Pesquisando', READING_FILE: 'Lendo arquivo',
  ANALYZING_IMAGE: 'Analisando imagem', SPEAKING: 'Falando', ERROR: 'Erro',
};
