// ============================================================
//  Humanize — traduz nomes de ferramentas, estados e eventos
//  internos para uma linguagem natural, legível pelo usuário.
//  Ex.: file.read → "Lendo arquivo"  ·  web.search → "Pesquisando na web".
//  A UI mostra isto; os dados brutos ficam em "detalhes técnicos".
// ============================================================

const short = (s, n = 48) => {
  s = String(s || '');
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
};

// função(args) → frase, OU string fixa. Best-effort e tolerante a args ausentes.
const TOOL = {
  'web.search': (a) => `Pesquisando na web${a?.query ? `: “${short(a.query)}”` : ''}`,
  'web.fetch': (a) => `Lendo página${a?.url ? `: ${short(a.url)}` : ''}`,
  'file.read': (a) => `Lendo arquivo${a?.path ? `: ${short(a.path)}` : ''}`,
  'file.write': (a) => `Escrevendo arquivo${a?.path ? `: ${short(a.path)}` : ''}`,
  'file.list': 'Listando arquivos',
  'file.search': (a) => `Procurando nos arquivos${a?.query ? `: “${short(a.query)}”` : ''}`,
  'file.delete': (a) => `Apagando arquivo${a?.path ? `: ${short(a.path)}` : ''}`,
  'file.move': 'Movendo arquivo',
  'code.generate': 'Escrevendo código',
  'code.analyze': 'Analisando código',
  'code.fix': 'Corrigindo código',
  'code.run': 'Executando código',
  'code.execute': 'Executando código',
  'code.test': 'Rodando os testes',
  'code.read_file': (a) => `Lendo o código${a?.path ? `: ${short(a.path)}` : ''}`,
  'code.write_file': (a) => `Editando o código${a?.path ? `: ${short(a.path)}` : ''}`,
  'git.status': 'Verificando o repositório',
  'git.diff': 'Vendo as mudanças (git diff)',
  'git.log': 'Lendo o histórico do git',
  'git.current_branch': 'Verificando a branch atual',
  'git.branch_create': 'Criando uma branch',
  'git.checkout': 'Trocando de branch',
  'git.commit': 'Salvando um commit',
  'computer.screenshot': 'Capturando a tela',
  'computer.screen_info': 'Olhando a tela',
  'computer.list_windows': 'Vendo as janelas abertas',
  'computer.cursor_position': 'Localizando o cursor',
  'computer.focus_window': 'Focando uma janela',
  'computer.move_mouse': 'Movendo o mouse',
  'computer.click': 'Clicando',
  'computer.type': 'Digitando',
  'computer.hotkey': 'Usando um atalho de teclado',
  'computer.open_app': (a) => `Abrindo${a?.app ? ` ${short(a.app)}` : ' um programa'}`,
  'computer.run_command': 'Rodando um comando no terminal',
  'vision.analyze': 'Analisando a imagem',
  'vision.read_text': 'Lendo o texto da imagem',
  'vision.screenshot': 'Capturando e analisando a tela',
  'binary.identify': 'Identificando o binário',
  'binary.strings': 'Extraindo textos do binário',
  'binary.entropy': 'Medindo a entropia do binário',
  'binary.pe_info': 'Lendo o cabeçalho do executável',
  'binary.decompile': 'Descompilando o binário',
  'memory.save': 'Guardando na memória',
  'memory.search': 'Consultando a memória',
  'memory.forget': 'Esquecendo uma memória',
  'avatar.gesture': 'Fazendo um gesto',
  'avatar.list': 'Listando gestos',
};

const prettifyName = (name) =>
  String(name || '')
    .replace(/[._]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

/** Frase humana para uma chamada de ferramenta. */
export function humanizeTool(name, args) {
  const t = TOOL[name];
  if (typeof t === 'function') return t(args || {});
  if (typeof t === 'string') return t;
  return prettifyName(name);
}

// rótulos de estado do agente (mesma família do STATUS_LABEL, em voz de ação)
const STATE = {
  IDLE: 'Ociosa', LISTENING: 'Ouvindo', THINKING: 'Pensando', TOOL_RUNNING: 'Trabalhando',
  CODING: 'Programando', SEARCHING: 'Pesquisando na web', READING_FILE: 'Lendo arquivos',
  ANALYZING_IMAGE: 'Analisando imagem', SPEAKING: 'Falando', ERROR: 'Encontrou um erro',
};
export const humanizeState = (status) => STATE[status] || status || 'Ociosa';

/** Frase para um evento (usada no feed de atividade). Retorna null se não vale mostrar. */
export function humanizeEvent(m) {
  switch (m.type) {
    case 'agent.invoked': return { icon: '⚙', text: humanizeTool(m.tool, m.args), tone: 'run' };
    case 'agent.result': return {
      icon: m.ok === false ? '✕' : '✓',
      text: `${humanizeTool(m.tool)} — ${m.ok === false ? 'falhou' : 'concluído'}`,
      tone: m.ok === false ? 'error' : 'ok',
    };
    case 'model.selected': return {
      icon: '◆',
      text: m.fallback ? `Trocou para ${providerLabel(m.provider)} (fallback)` : `Usando ${providerLabel(m.provider)}`,
      tone: 'info',
    };
    case 'permission.request': return { icon: '🔒', text: `Pediu permissão: ${humanizeTool(m.action)}`, tone: 'warn' };
    case 'task.created': return { icon: '▶', text: 'Iniciou uma tarefa', tone: 'info' };
    case 'task.state': return { icon: '▹', text: `Tarefa: ${taskStateLabel(m.state)}`, tone: 'info' };
    case 'memory.recalled': return { icon: '🧠', text: `Lembrou de ${m.items?.length ?? 0} memória(s)`, tone: 'info' };
    case 'error': return { icon: '✕', text: 'Ocorreu um erro', tone: 'error' };
    default: return null;
  }
}

const PROVIDER = { local: 'modelo local', openai: 'OpenAI', gemini: 'Gemini', grok: 'Grok', deepseek: 'DeepSeek' };
export const providerLabel = (p) => PROVIDER[p] || p || 'modelo local';
export const isLocalProvider = (p) => !p || p === 'local' || p === 'default';

const TASK_STATE = {
  pending: 'na fila', running: 'em execução', waiting_permission: 'aguardando permissão',
  paused: 'pausada', failed: 'falhou', completed: 'concluída', cancelled: 'cancelada',
};
export const taskStateLabel = (s) => TASK_STATE[s] || s || '';
