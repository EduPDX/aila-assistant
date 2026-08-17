// ============================================================
//  API — camada única de acesso REST ao backend da Aila.
//  Um só lugar para fetch + tratamento de erro. NÃO inventa
//  endpoints: todos existem em aila/api/routes.py e voice.py.
// ============================================================

async function j(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
  return r.json();
}

const jsonPost = (url, body) =>
  j(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const api = {
  // --- leitura ---
  status: () => j('/api/status'),                     // app/llm/model/providers/network_mode/autonomy_level/agent_state…
  metrics: () => j('/api/metrics'),                   // cpu/ram/gpu/vram/tps/uptime
  events: (n = 40) => j(`/api/events?n=${n}`),         // atividade recente (redigida) + state + provider
  cognition: (n = 20) => j(`/api/cognition?n=${n}`),   // feed do subconsciente: {totals, recent}
  graph: (kind = 'code', limit = 1500, project = null) =>                // {nodes,edges,communities}
    j(`/api/graph?kind=${kind}&limit=${limit}${project ? `&project=${encodeURIComponent(project)}` : ''}`),
  projects: () => j('/api/projects'),                                   // { projects: [...] }
  addProject: (path, name) => jsonPost('/api/projects', { path, name }), // anexar pasta → constrói grafo
  removeProject: (slug) => j(`/api/projects/${encodeURIComponent(slug)}`, { method: 'DELETE' }),
  activateProject: (slug) => j(`/api/projects/${encodeURIComponent(slug)}/activate`, { method: 'POST' }),  // "trabalhar no projeto"
  deactivateProject: () => j('/api/projects/deactivate', { method: 'POST' }),                              // voltar ao código da Aila
  tasks: () => j('/api/tasks'),                       // { tasks: [...] }
  task: (id) => j(`/api/tasks/${id}`),
  memory: (n = 20) => j(`/api/memory?n=${n}`),         // { enabled, count, recent }
  deleteMemory: (id) => j(`/api/memory/${id}`, { method: 'DELETE' }),   // esquecer uma memória
  reset: () => j('/api/reset', { method: 'POST' }),                     // apagar memória+conhecimento+conversas
  rebuildKnowledge: () => j('/api/knowledge/rebuild', { method: 'POST' }), // repovoar grafo de conhecimento (backfill)
  config: () => j('/api/config'),                                       // config efetiva (chaves redigidas)
  patchConfig: (patch) => j('/api/config', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) }),
  models: () => j('/api/models'),                     // { models: [...] } (Ollama)
  tools: () => j('/api/tools'),
  audit: (n = 50) => j(`/api/audit?n=${n}`),
  voiceStatus: () => j('/api/voice/status'),
  providers: () => j('/api/providers'),                          // local + nuvem (sem expor chaves)
  setProvider: (body) => jsonPost('/api/providers', body),        // salvar/ativar/desativar

  // --- controles runtime SUPORTADOS pelo backend ---
  setAutonomy: (level) => jsonPost('/api/autonomy', { level }),   // 1..5
  setNetwork: (mode) => jsonPost('/api/network', { mode }),       // 'offline' | 'hybrid'
  startTask: (goal) => jsonPost('/api/tasks', { goal }),          // 403 se autonomia < L4
  cancelTask: (id) => j(`/api/tasks/${id}/cancel`, { method: 'POST' }),
};
