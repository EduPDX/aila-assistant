// ============================================================
//  Schema das Configurações — declara as CATEGORIAS e os CAMPOS.
//  O settings.js gera a tela a partir daqui e grava via PATCH /api/config
//  (nada de controle falso: todo `path` existe na config real). Blocos
//  `custom` reaproveitam widgets já prontos; `pref` = preferência local
//  (localStorage), pro que não tem backend.
//
//  field: { path, type, label, hint?, options?, min?, max?, step?, restart? }
//    type: toggle | number | text | textarea | select | tags
//    restart: true → só entra em vigor ao reiniciar (é lido no boot).
// ============================================================

export const CATEGORIES = [
  { id: 'geral', icon: '⚙️', label: 'Geral', blocks: [
    { fields: [
      { path: 'app.persona', type: 'textarea', label: 'Comportamento (persona)',
        hint: 'Como a Aila se comporta e fala.', restart: true },
    ] },
    { custom: 'themes', title: 'Aparência' },
  ] },

  { id: 'modelos', icon: '🧠', label: 'Modelos e IA', blocks: [
    { title: 'Modelo local (Ollama)', fields: [
      { path: 'llm.model', type: 'text', label: 'Modelo de chat', restart: true },
      { path: 'llm.code_model', type: 'text', label: 'Modelo de código', restart: true },
      { path: 'llm.vision_model', type: 'text', label: 'Modelo de visão', restart: true },
      { path: 'llm.temperature', type: 'number', label: 'Temperatura', min: 0, max: 2, step: 0.1, restart: true },
      { path: 'llm.num_ctx', type: 'number', label: 'Janela de contexto (tokens)', min: 512, step: 512, restart: true },
      { path: 'llm.max_tokens', type: 'number', label: 'Máx. tokens de resposta', min: 128, step: 128, restart: true },
    ] },
    { custom: 'providers', title: 'Provedores de nuvem (API keys)' },
    { title: 'Roteamento por tarefa', fields: [
      { path: 'routing.enabled', type: 'toggle', label: 'Ativar roteamento',
        hint: 'Escolhe o provedor conforme o tipo de tarefa (chat/código/visão).', restart: true },
      { path: 'routing.default', type: 'text', label: 'Provedor padrão', restart: true },
    ] },
  ] },

  { id: 'voz', icon: '🔊', label: 'Voz', blocks: [
    { custom: 'voicetoggle' },   // ao vivo: liga/desliga a fala agora (sem reiniciar)
    { fields: [
      { path: 'voice.enabled', type: 'toggle', label: 'Voz habilitada', restart: true },
      { path: 'voice.tts.output_enabled', type: 'toggle', label: 'Falar as respostas automaticamente', restart: true },
    ] },
    { title: 'Síntese (TTS)', fields: [
      { path: 'voice.tts.engine', type: 'select', options: ['auto', 'edge', 'sapi', 'piper'], label: 'Motor de voz', restart: true },
      { path: 'voice.tts.voice', type: 'text', label: 'Voz', hint: 'ex.: pt-BR-FranciscaNeural (Edge)', restart: true },
      { path: 'voice.tts.edge_rate', type: 'text', label: 'Velocidade (Edge)', hint: 'ex.: +10%', restart: true },
      { path: 'voice.tts.edge_pitch', type: 'text', label: 'Tom / pitch (Edge)', hint: 'ex.: +30Hz (mais fino)', restart: true },
    ] },
    { title: 'Reconhecimento (STT)', fields: [
      { path: 'voice.stt.model', type: 'select', options: ['tiny', 'base', 'small', 'medium'], label: 'Modelo (Whisper)', restart: true },
      { path: 'voice.stt.language', type: 'text', label: 'Idioma', hint: 'ex.: pt', restart: true },
      { path: 'voice.stt.device', type: 'select', options: ['auto', 'cuda', 'cpu'], label: 'Dispositivo', restart: true },
    ] },
  ] },

  { id: 'avatar', icon: '🧍', label: 'Avatar', blocks: [
    { custom: 'vrm', title: 'Modelo VRM' },
    { fields: [
      { path: 'avatar.default_emotion', type: 'text', label: 'Emoção padrão', hint: 'ex.: neutral, happy', restart: true },
    ] },
    { note: 'Escala, câmera, física, colisão e gestos são controlados pelo motor de animação — ajuste fino pela UI ainda não disponível.' },
  ] },

  { id: 'memoria', icon: '📓', label: 'Memória', blocks: [
    { fields: [
      { path: 'memory.enabled', type: 'toggle', label: 'Memória de longo prazo', restart: true },
      { path: 'memory.store_conversations', type: 'toggle', label: 'Aprender das conversas (auto-learning)', restart: true },
      { path: 'memory.embed_model', type: 'text', label: 'Modelo de embeddings', hint: 'ex.: nomic-embed-text (Ollama)', restart: true },
      { path: 'memory.top_k', type: 'number', label: 'Memórias por resposta (RAG)', min: 1, max: 20, restart: true },
      { path: 'memory.min_score', type: 'number', label: 'Similaridade mínima', min: 0, max: 1, step: 0.05, restart: true },
    ] },
    { custom: 'memory', title: 'Memórias guardadas' },
  ] },

  { id: 'subconsciente', icon: '🌙', label: 'Subconsciente', blocks: [
    { pref: [
      { key: 'subc.mini', type: 'toggle', label: 'Mostrar o mini-subconsciente no palco', default: true },
      { key: 'subc.live', type: 'toggle', label: 'Atualizar em tempo real', default: true },
    ] },
    { note: 'A visualização completa (grafos de código e conversa) fica na aba 🧠 pela sidebar.' },
  ] },

  { id: 'agentes', icon: '🤖', label: 'Agentes', blocks: [
    { custom: 'autonomy', title: 'Autonomia' },
    { fields: [
      { path: 'agents.enabled', type: 'tags', label: 'Agentes habilitados', hint: 'Separados por vírgula (ex.: file, code, documents…).', restart: true },
    ] },
  ] },

  { id: 'seguranca', icon: '🔒', label: 'Segurança', blocks: [
    { fields: [
      { path: 'security.read_only', type: 'toggle', label: 'Somente leitura (bloqueia escrita/ações)', restart: true },
      { path: 'security.confirm_review', type: 'toggle', label: 'Confirmar ações de REVIEW', restart: true },
      { path: 'security.confirm_destructive', type: 'toggle', label: 'Confirmar ações DANGER', restart: true },
      { path: 'security.guardrails', type: 'toggle', label: 'Guardrails (redigir segredos na resposta)', restart: true },
    ] },
    { custom: 'permissions', title: 'Níveis de risco' },
    { custom: 'network', title: 'Rede & Privacidade' },
  ] },

  { id: 'tarefas', icon: '📋', label: 'Tarefas', blocks: [
    { fields: [
      { path: 'security.max_tool_calls', type: 'number', label: 'Máx. de ferramentas por tarefa', min: 1, restart: true },
      { path: 'security.max_repeated_calls', type: 'number', label: 'Máx. repetições da mesma tool (anti-loop)', min: 1, restart: true },
      { path: 'security.tool_timeout', type: 'number', label: 'Timeout por ferramenta (s)', min: 0, restart: true },
    ] },
    { note: 'As tarefas em background (autônomas) aparecem no painel de Atividade → Tarefas (botão ▤).' },
  ] },

  { id: 'sistema', icon: '📊', label: 'Sistema', blocks: [{ custom: 'system' }] },

  { id: 'dev', icon: '🛠', label: 'Desenvolvedor', blocks: [
    { fields: [
      { path: 'log_level', type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR'], label: 'Nível de log', restart: true },
    ] },
    { note: 'Eventos / observability ao vivo no painel de Atividade (botão ▤).' },
  ] },
];

// HTML dos blocos "custom" (reusa os widgets já existentes; IDs preservados).
export const CUSTOM_HTML = {
  themes: '<div class="themes" id="themes"></div>',
  providers: '<div id="providers-list" class="prov-list"></div>'
    + '<p class="muted" id="prov-help" style="margin-top:14px">As chaves ficam só neste computador (config/local.yaml), nunca no repositório.</p>',
  memory: '<input id="mem-search" class="mem-search" placeholder="Buscar nas memórias…" autocomplete="off" />'
    + '<div id="memory-list" class="mem-list"></div>'
    + '<p class="muted" style="margin-top:8px">Contagem: <b id="memory-count">0</b> · clique em 🗑 para esquecer.</p>',
  autonomy: '<div id="autonomy-list" class="auto-list"></div>',
  permissions: '<div id="perm-levels" class="risk-list"></div><div class="card" id="perm-state" style="margin-top:14px"></div>',
  network: '<div id="network-list" class="net-list"></div>',
  system: '<div class="card">'
    + '<div class="row"><span>LLM</span><span id="s-llm"><span class="dot off"></span>—</span></div>'
    + '<div class="row"><span>Modelo</span><span id="s-model" class="muted">—</span></div>'
    + '<div class="row"><span>Voz</span><span id="s-voice" class="muted">—</span></div>'
    + '<div class="row"><span>🧠 Memórias</span><span id="s-mem" class="muted">—</span></div></div>'
    + '<p class="muted" style="margin-top:12px">Métricas ao vivo (CPU/GPU/VRAM/uptime) no painel de Atividade → Sistema.</p>',
  vrm: '<button class="btn accent" id="pickvrm" style="max-width:260px">📁 Escolher modelo VRM</button>'
    + '<input type="file" id="vrmfile" accept=".vrm" style="display:none" /><div id="vrmnote" class="muted" style="margin-top:8px"></div>',
  voicetoggle: '<div class="toggle on" id="tg-voice"><div class="sw"></div><span>Aila fala as respostas (agora)</span></div>',
};
