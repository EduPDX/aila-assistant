// ============================================================
//  Schema das Configurações — declara as CATEGORIAS e os CAMPOS.
//  O settings.js gera a tela a partir daqui e grava via PATCH /api/config
//  (nada de controle falso: todo `path` existe na config real).
//
//  field: { path, type, label, hint?, options?, min?, max?, step?, unit?, signed?, str?, restart? }
//    type: toggle | slider | number | text | textarea | select | tags
//    slider: barra deslizante. `str:true` grava string formatada (ex.: "+10%").
//    restart: true → só entra em vigor ao reiniciar (lido no boot).
//  bloco: { title? , fields? | custom? | pref? | note? }
// ============================================================

const EMBED_MODELS = ['nomic-embed-text', 'mxbai-embed-large', 'all-minilm', 'bge-m3', 'snowflake-arctic-embed'];

export const CATEGORIES = [
  { id: 'aparencia', icon: '🎨', label: 'Aparência', blocks: [
    { title: 'Tema', custom: 'themes' },
    { title: 'Visualização do grafo (subconsciente)', pref: [
      { key: 'aila.graph.mode', type: 'select', options: ['2d', '3d'], default: '2d',
        label: 'Modo de visualização', hint: '3D = grafo dentro de um cubo que você gira com o mouse (mais bonito, usa a GPU).' },
      { key: 'aila.graph.edges', type: 'select', options: ['coloridas', 'cinza'], default: 'coloridas',
        label: 'Ligações entre os nós', hint: 'Coloridas = a linha usa a cor do nó de origem (como no Graphify).' },
      { key: 'aila.graph.drag', type: 'toggle', default: true,
        label: 'Arrastar nós com o mouse', hint: 'Desligue se o grafo se mexe demais ao arrastar.' },
      { key: 'aila.graph.spin', type: 'toggle', default: false,
        label: 'Movimento contínuo (respira/gira)', hint: 'Deixa o grafo em leve movimento, como se estivesse pensando.' },
      { key: 'aila.subc.mini', type: 'toggle', default: true,
        label: 'Mostrar o mini-subconsciente no palco', hint: 'O grafo pequeno no canto do avatar.' },
    ] },
  ] },

  { id: 'geral', icon: '💬', label: 'Comportamento', blocks: [
    { fields: [
      { path: 'app.persona', type: 'textarea', label: 'Personalidade (persona)',
        hint: 'Instrução base que define como a Aila fala e se comporta.', restart: true },
    ] },
  ] },

  { id: 'modelos', icon: '🧠', label: 'Modelos e IA', blocks: [
    { title: 'Modelo local (Ollama)', fields: [
      { path: 'llm.model', type: 'text', label: 'Modelo de chat', hint: 'Modelo do Ollama para conversar (ex.: qwen2.5:7b-instruct).', restart: true },
      { path: 'llm.code_model', type: 'text', label: 'Modelo de código', hint: 'Usado pelo agente de código.', restart: true },
      { path: 'llm.vision_model', type: 'text', label: 'Modelo de visão', hint: 'Usado para analisar imagens (ex.: llava).', restart: true },
      { path: 'llm.temperature', type: 'slider', min: 0, max: 2, step: 0.1, label: 'Temperatura',
        hint: 'Criatividade das respostas. Baixo = focado/objetivo; alto = criativo/variado.', restart: true },
      { path: 'llm.num_ctx', type: 'slider', min: 2048, max: 32768, step: 2048, label: 'Janela de contexto',
        hint: 'Quantos tokens de histórico o modelo enxerga. Maior = lembra mais, usa mais memória/VRAM.', unit: ' tok', restart: true },
      { path: 'llm.max_tokens', type: 'slider', min: 256, max: 8192, step: 256, label: 'Máx. tokens de resposta',
        hint: 'Tamanho máximo de cada resposta.', unit: ' tok', restart: true },
    ] },
    { title: 'Provedores de nuvem (API keys)', custom: 'providers' },
    { title: 'Roteamento por tarefa', fields: [
      { path: 'routing.enabled', type: 'toggle', label: 'Ativar roteamento',
        hint: 'Escolhe o provedor conforme o tipo de tarefa (chat/código/visão) em vez de usar sempre o mesmo.', restart: true },
      { path: 'routing.default', type: 'text', label: 'Provedor padrão', hint: 'Usado quando nenhuma regra se aplica (ex.: local).', restart: true },
    ] },
  ] },

  { id: 'voz', icon: '🔊', label: 'Voz', blocks: [
    { custom: 'voicetoggle' },
    { fields: [
      { path: 'voice.enabled', type: 'toggle', label: 'Sistema de voz habilitado', hint: 'Liga STT (ouvir) e TTS (falar).', restart: true },
      { path: 'voice.tts.output_enabled', type: 'toggle', label: 'Falar as respostas automaticamente', hint: 'Se desligado, ela só fala quando você pedir.', restart: true },
    ] },
    { title: 'Síntese de voz (TTS)', fields: [
      { path: 'voice.tts.engine', type: 'select', options: ['auto', 'edge', 'sapi', 'piper'], label: 'Motor de voz',
        hint: 'edge = vozes neurais online (Microsoft); sapi = do Windows; piper = local offline.', restart: true },
      { path: 'voice.tts.voice', type: 'text', label: 'Voz', hint: 'Nome da voz. Ex. (Edge): pt-BR-FranciscaNeural, pt-BR-AntonioNeural.', restart: true },
      { path: 'voice.tts.edge_rate', type: 'slider', min: -50, max: 50, step: 5, unit: '%', signed: true, str: true,
        label: 'Velocidade da fala', hint: 'Mais rápido (+) ou mais devagar (−) que o normal.', restart: true },
      { path: 'voice.tts.edge_pitch', type: 'slider', min: -50, max: 50, step: 5, unit: 'Hz', signed: true, str: true,
        label: 'Tom da voz (pitch)', hint: 'Mais fino/agudo (+) ou mais grave (−). Ex.: +30Hz soa mais "anime".', restart: true },
    ] },
    { title: 'Reconhecimento de fala (STT)', fields: [
      { path: 'voice.stt.model', type: 'select', options: ['tiny', 'base', 'small', 'medium'], label: 'Modelo (Whisper)',
        hint: 'Maior = transcreve melhor, porém mais lento/pesado.', restart: true },
      { path: 'voice.stt.language', type: 'text', label: 'Idioma', hint: 'Código do idioma da sua fala (ex.: pt, en).', restart: true },
      { path: 'voice.stt.device', type: 'select', options: ['auto', 'cuda', 'cpu'], label: 'Processamento',
        hint: 'cuda = usa a GPU (mais rápido); cpu = sem GPU.', restart: true },
    ] },
  ] },

  { id: 'avatar', icon: '🧍', label: 'Avatar', blocks: [
    { title: 'Modelo 3D', custom: 'vrm' },
    { fields: [
      { path: 'avatar.default_emotion', type: 'select',
        options: ['neutral', 'happy', 'sad', 'angry', 'relaxed', 'surprised'],
        label: 'Emoção padrão', hint: 'Expressão de repouso do avatar.', restart: true },
    ] },
    { note: 'Escala, câmera, física, colisão e gestos são controlados pelo motor de animação — ajuste pela interface ainda não disponível.' },
  ] },

  { id: 'memoria', icon: '📓', label: 'Memória', blocks: [
    { fields: [
      { path: 'memory.enabled', type: 'toggle', label: 'Memória de longo prazo', hint: 'Guarda fatos, preferências e trechos de conversa entre sessões.', restart: true },
      { path: 'memory.store_conversations', type: 'toggle', label: 'Aprender das conversas', hint: 'Grava cada troca automaticamente — é o que alimenta o grafo de Conversa.', restart: true },
      { path: 'memory.embed_model', type: 'select', options: EMBED_MODELS, label: 'Modelo de embeddings',
        hint: 'Modelo do Ollama que transforma texto em vetor (usado pra buscar memórias parecidas). Precisa estar baixado: ollama pull <modelo>.', restart: true },
      { path: 'memory.top_k', type: 'slider', min: 1, max: 20, step: 1, label: 'Memórias por resposta',
        hint: 'Quantas memórias relevantes ela injeta no contexto a cada resposta (RAG).', restart: true },
      { path: 'memory.min_score', type: 'slider', min: 0, max: 1, step: 0.05, label: 'Similaridade mínima',
        hint: 'Quão parecida uma memória precisa ser pra entrar. Alto = só o muito relevante.', restart: true },
    ] },
    { title: 'Memórias guardadas', custom: 'memory' },
  ] },

  { id: 'autonomia', icon: '🎚️', label: 'Autonomia', blocks: [
    { note: 'O quanto a Aila pode agir sozinha. Cada nível destrava mais capacidades — você escolhe. (Aplica na hora.)' },
    { custom: 'autonomy' },
  ] },

  { id: 'agentes', icon: '🤖', label: 'Agentes', blocks: [
    { note: 'Ligue/desligue as capacidades da Aila. Cada agente é um conjunto de ferramentas.' },
    { custom: 'agents' },
  ] },

  { id: 'seguranca', icon: '🔒', label: 'Segurança', blocks: [
    { fields: [
      { path: 'security.read_only', type: 'toggle', label: 'Somente leitura', hint: 'Bloqueia qualquer escrita/ação — a Aila só lê e conversa.', restart: true },
      { path: 'security.confirm_review', type: 'toggle', label: 'Confirmar ações de REVIEW', hint: 'Pede sua permissão até para ações comuns de escrita.', restart: true },
      { path: 'security.confirm_destructive', type: 'toggle', label: 'Confirmar ações DANGER', hint: 'Pede permissão para ações destrutivas (rodar comando, apagar…). Recomendado ligado.', restart: true },
      { path: 'security.guardrails', type: 'toggle', label: 'Guardrails (proteger segredos)', hint: 'Redige chaves/tokens que apareçam na resposta antes de mostrar/falar/gravar.', restart: true },
    ] },
    { title: 'Níveis de risco', custom: 'permissions' },
  ] },

  { id: 'rede', icon: '🌐', label: 'Rede & Privacidade', blocks: [
    { note: 'Controla se seus dados podem sair do computador. (Aplica na hora.)' },
    { custom: 'network' },
  ] },

  { id: 'tarefas', icon: '📋', label: 'Tarefas', blocks: [
    { note: 'Limites das tarefas autônomas (várias etapas). Protegem contra loops e travamentos.' },
    { fields: [
      { path: 'security.max_tool_calls', type: 'slider', min: 1, max: 60, step: 1, label: 'Máx. de ferramentas por tarefa',
        hint: 'Orçamento de ações que uma tarefa autônoma pode usar antes de parar.', restart: true },
      { path: 'security.max_repeated_calls', type: 'slider', min: 1, max: 10, step: 1, label: 'Máx. repetições da mesma ação',
        hint: 'Se repetir a mesma ferramenta+argumentos além disso, considera loop e para.', restart: true },
      { path: 'security.tool_timeout', type: 'slider', min: 0, max: 600, step: 10, unit: ' s', label: 'Timeout por ferramenta',
        hint: 'Tempo máximo de uma ação antes de abortar. 0 = sem limite.', restart: true },
    ] },
    { note: 'As tarefas em andamento aparecem no painel de Atividade → Tarefas (botão ▤).' },
  ] },

  { id: 'sistema', icon: '📊', label: 'Sistema', blocks: [{ custom: 'system' }] },

  { id: 'dev', icon: '🛠', label: 'Desenvolvedor', blocks: [
    { fields: [
      { path: 'log_level', type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR'], label: 'Nível de log',
        hint: 'DEBUG mostra tudo (útil pra investigar); INFO é o normal.', restart: true },
    ] },
    { note: 'Eventos / observability ao vivo no painel de Atividade (botão ▤).' },
  ] },
];

// HTML dos blocos "custom" (reusa/expande widgets prontos; IDs preservados).
export const CUSTOM_HTML = {
  themes: '<div class="themes" id="themes"></div>',
  providers: '<div id="providers-list" class="prov-list"></div>'
    + '<p class="muted" id="prov-help" style="margin-top:14px">As chaves ficam só neste computador (config/local.yaml), nunca no repositório.</p>',
  memory: '<input id="mem-search" class="mem-search" placeholder="Buscar nas memórias…" autocomplete="off" />'
    + '<div id="memory-list" class="mem-list"></div>'
    + '<p class="muted" style="margin-top:8px">Contagem: <b id="memory-count">0</b> · clique em 🗑 para esquecer.</p>',
  autonomy: '<div id="autonomy-list" class="auto-list"></div>',
  agents: '<div id="agents-list" class="agents-list"></div>',
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

// agentes conhecidos (para a lista com toggles) — nome interno → rótulo
export const KNOWN_AGENTS = [
  ['file', '📁 Arquivos', 'Ler, escrever, organizar e buscar arquivos.'],
  ['code', '💻 Código', 'Gerar, analisar, corrigir, executar e mapear código.'],
  ['documents', '📄 Documentos', 'Ler/criar PDF, Word, Excel, PowerPoint, texto.'],
  ['git', '🔀 Git', 'Status, diff, branch, commit (backup/rollback).'],
  ['web', '🌐 Web', 'Pesquisar na internet e ler páginas.'],
  ['computer', '🖱️ Computador', 'Controlar mouse/teclado, janelas, abrir apps, terminal.'],
  ['vision', '👁️ Visão', 'Analisar imagens e ler texto de imagens (OCR).'],
  ['binary', '⚙️ Binários', 'Inspecionar executáveis (strings, entropia, decompilar).'],
  ['memory', '🧠 Memória', 'Guardar, buscar e esquecer memórias.'],
  ['avatar', '🧍 Avatar', 'Acionar gestos e expressões no avatar 3D.'],
];
