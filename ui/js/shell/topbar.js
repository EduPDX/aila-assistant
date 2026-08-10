// ============================================================
//  Topbar — cluster de estado sempre visível: conexão · modelo
//  (local/cloud) · rede (offline/hybrid) · autonomia (L1–L5).
//  É o poller ÚNICO de /api/status (alimenta o State global).
// ============================================================
import { byId } from '../dom.js';
import { State } from '../state.js';
import { api } from '../core/api.js';
import { providerLabel, isLocalProvider } from '../core/humanize.js';

const AUTONOMY = { 1: 'Assistente', 2: 'Executor', 3: 'Desenvolvedor', 4: 'Autônomo', 5: 'Auto-melhoria' };

export function initTopbar() {
  const box = byId('topbar-status');
  if (!box) return;
  box.innerHTML = `
    <span class="conn-dot" id="tc-conn" title="Conexão"></span>
    <button class="tchip" id="tc-model" title="Modelo ativo"><b>—</b></button>
    <button class="tchip" id="tc-net"   title="Modo de rede">—</button>
    <button class="tchip" id="tc-auto"  title="Nível de autonomia">—</button>`;

  State.on(render);
  render(State.get());

  refreshStatus();
  setInterval(refreshStatus, 8000);
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
