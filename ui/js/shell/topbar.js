// ============================================================
//  Topbar — cluster de estado sempre visível: conexão · modelo
//  (local/cloud) · rede (offline/hybrid) · autonomia (L1–L5).
//  É o poller ÚNICO de /api/status (alimenta o State global).
// ============================================================
import { byId } from '../dom.js';
import { State } from '../state.js';
import { api } from '../core/api.js';
import { providerLabel, isLocalProvider } from '../core/humanize.js';
import { contextMenu, confirmDialog } from '../ui.js';

const AUTONOMY = { 1: 'Assistente', 2: 'Executor', 3: 'Desenvolvedor', 4: 'Autônomo', 5: 'Auto-melhoria' };
const AUTONOMY_DESC = {
  1: 'só conversa e leitura', 2: 'agir no PC e arquivos', 3: 'executar/mexer em código',
  4: 'tarefas autônomas de várias etapas', 5: 'editar o próprio código (isolado, validado)',
};

export function initTopbar() {
  const box = byId('topbar-status');
  if (!box) return;
  box.innerHTML = `
    <span class="conn-dot" id="tc-conn" title="Conexão"></span>
    <button class="tchip" id="tc-model" title="Modelo ativo"><b>—</b></button>
    <button class="tchip clickable" id="tc-net"  title="Modo de rede — clique para trocar">—</button>
    <button class="tchip clickable" id="tc-auto" title="Nível de autonomia — clique para trocar">—</button>`;

  byId('tc-net').onclick = (e) => networkMenu(e.currentTarget);
  byId('tc-auto').onclick = (e) => autonomyMenu(e.currentTarget);

  State.on(render);
  render(State.get());

  refreshStatus();
  setInterval(refreshStatus, 8000);
}

/* ---------- controles runtime (rede / autonomia) ---------- */
function networkMenu(anchor) {
  contextMenu(anchor, [
    { icon: '🌐', label: 'Híbrido — usa web/nuvem quando útil', onClick: () => applyNetwork('hybrid') },
    { icon: '🔒', label: 'Offline — nada sai do PC', onClick: () => applyNetwork('offline') },
  ]);
}
async function applyNetwork(mode) {
  State.set({ networkMode: mode });                 // otimista
  try { const r = await api.setNetwork(mode); State.set({ networkMode: r.network_mode || mode }); }
  catch { refreshStatus(); }                          // falhou → ressincroniza
}

function autonomyMenu(anchor) {
  const cur = State.get('autonomy') || 3;
  const items = [1, 2, 3, 4, 5].map((n) => ({
    icon: n === cur ? '●' : '○',
    label: `L${n} · ${AUTONOMY[n]} — ${AUTONOMY_DESC[n]}`,
    danger: n >= 4,
    onClick: () => applyAutonomy(n),
  }));
  contextMenu(anchor, items);
}
async function applyAutonomy(level) {
  if (level >= 4) {
    const ok = await confirmDialog({
      title: `Ativar autonomia L${level} — ${AUTONOMY[level]}?`,
      body: level === 5
        ? 'A Aila poderá editar o PRÓPRIO código (em branch isolada, com validação por testes). Use com consciência.'
        : 'A Aila poderá executar tarefas autônomas de várias etapas por conta própria.',
      confirmLabel: `Ativar L${level}`, danger: true,
    });
    if (!ok) return;
  }
  State.set({ autonomy: level });                    // otimista
  try { const r = await api.setAutonomy(level); State.set({ autonomy: r.autonomy_level ?? level }); }
  catch { refreshStatus(); }
}

function render(s) {
  // conexão
  const conn = byId('tc-conn');
  if (conn) conn.dataset.conn = s.connection || 'connecting';

  // modelo (local vs cloud)
  const model = byId('tc-model');
  if (model) {
    const local = isLocalProvider(s.provider);
    model.dataset.kind = local ? 'local' : 'cloud';
    const label = local ? (s.model || 'local') : providerLabel(s.provider);
    model.innerHTML = `<span class="tk">${local ? 'LOCAL' : 'CLOUD'}</span><b>${esc(label)}</b>`;
    model.classList.toggle('offline', !s.llmOnline);
  }

  // rede
  const net = byId('tc-net');
  if (net) {
    const offline = s.networkMode === 'offline';
    net.dataset.mode = offline ? 'offline' : 'hybrid';
    net.textContent = offline ? 'OFFLINE' : 'HYBRID';
  }

  // autonomia
  const auto = byId('tc-auto');
  if (auto) {
    const lvl = s.autonomy || 3;
    auto.dataset.level = lvl;
    auto.innerHTML = `<span class="tk">L${lvl}</span>${esc(AUTONOMY[lvl] || '')}`;
  }
}

export async function refreshStatus() {
  try {
    const s = await api.status();
    State.set({
      llmOnline: s.llm_online,
      backend: s.llm_backend,
      model: s.model,
      providers: s.providers || [],
      networkMode: s.network_mode || 'hybrid',
      autonomy: s.autonomy_level ?? 3,
      readOnly: !!s.read_only,
      memoryCount: s.memory_count ?? 0,
      agents: s.agents || [],
      // provider ATIVO vem do evento model.selected; não sobrescrever aqui.
    });
  } catch (e) {
    State.set({ llmOnline: false });
  }
}

const esc = (s) => String(s ?? '').replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
