// Painel de status (direita): estado global + métricas reais do sistema.
import { byId } from './dom.js';
import { State, STATUS_LABEL } from './state.js';

const fmtUptime = (s) => {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m ${s % 60}s`;
};

// slug de capacidade → [ícone, rótulo pt-BR]. As capacidades vêm do self-model
// (derivadas das ferramentas reais) e chegam uma vez no connect (aila.capabilities).
const CAP = {
  pesquisa_web: ['🔎', 'Pesquisa na web'],
  visao: ['👁', 'Visão'],
  programacao: ['💻', 'Programação'],
  arquivos: ['📁', 'Arquivos'],
  controle_do_pc: ['🖥', 'Controle do PC'],
  controle_do_corpo: ['🧍', 'Corpo / avatar'],
  memoria: ['🧠', 'Memória'],
  git: ['🔀', 'Git'],
  projetos: ['📦', 'Projetos'],
};

export function initStatusPanel(target) {
  const box = target || byId('statuspanel');
  if (!box) return;
  box.innerHTML = `
    <div class="sp-title">SISTEMA</div>
    <div class="sp-state" id="sp-state"><span class="sp-dot"></span><span id="sp-state-label">Ocioso</span></div>
    <div class="sp-tool" id="sp-tool"></div>
    <div class="sp-grid">
      <div class="sp-card"><div class="sp-k">Emoção</div><div class="sp-v" id="sp-emotion">neutral</div></div>
      <div class="sp-card"><div class="sp-k">Tokens/s</div><div class="sp-v" id="sp-tps">—</div></div>
      <div class="sp-card"><div class="sp-k">Modelo</div><div class="sp-v sm" id="sp-model">—</div></div>
      <div class="sp-card"><div class="sp-k">Uptime</div><div class="sp-v" id="sp-uptime">—</div></div>
    </div>
    <div class="sp-meters">
      ${['gpu', 'vram', 'cpu', 'ram'].map((k) => `
        <div class="sp-meter">
          <div class="sp-mrow"><span>${k.toUpperCase()}</span><span id="sp-${k}-v" class="muted">—</span></div>
          <div class="sp-bar"><i id="sp-${k}-bar"></i></div>
        </div>`).join('')}
    </div>
    <div class="sp-title sp-caps-title">O QUE EU SEI FAZER</div>
    <div class="sp-caps" id="sp-caps"></div>`;

  // Fonte única: estado + métricas vêm do State (o poller vive no HUD do palco,
  // shell/hud.js, que escreve State.metrics). Aqui só renderizamos.
  State.on(render);
  render(State.get());
}

function render(s) {
  updateState(s);
  renderMeters(s.metrics || {});
  renderCaps(s.capabilities || []);
}

function renderCaps(caps) {
  const box = byId('sp-caps');
  if (!box) return;
  const list = Array.isArray(caps) ? caps : [];
  if (!list.length) { box.innerHTML = '<span class="sp-cap-empty">descobrindo…</span>'; return; }
  box.innerHTML = list.map((c) => {
    const [icon, label] = CAP[c] || ['•', c];
    return `<span class="chip sp-cap" title="${label}">${icon} ${label}</span>`;
  }).join('');
}

function updateState(s) {
  const st = s.status || 'IDLE';
  byId('sp-state').dataset.status = st;
  byId('sp-state-label').textContent = STATUS_LABEL[st] || st;
  byId('sp-emotion').textContent = s.emotion || 'neutral';
  const tool = byId('sp-tool');
  if (s.tool) { tool.textContent = '⚙ ' + s.tool; tool.classList.add('show'); }
  else tool.classList.remove('show');
}

function setMeter(k, pct, label) {
  byId(`sp-${k}-v`).textContent = label;
  byId(`sp-${k}-bar`).style.width = Math.min(100, Math.max(0, pct || 0)) + '%';
}

function renderMeters(m) {
  byId('sp-model').textContent = m.model || '—';
  byId('sp-tps').textContent = m.tps ? m.tps.toFixed(0) : '—';
  byId('sp-uptime').textContent = m.uptime_s != null ? fmtUptime(m.uptime_s) : '—';
  setMeter('cpu', m.cpu, m.cpu != null ? `${m.cpu.toFixed(0)}%` : '—');
  setMeter('ram', m.ram?.percent, m.ram ? `${m.ram.used_gb}/${m.ram.total_gb} GB` : '—');
  if (m.gpu) {
    setMeter('gpu', m.gpu.util, `${m.gpu.util.toFixed(0)}%`);
    const vp = m.gpu.vram_total_mb ? (m.gpu.vram_used_mb / m.gpu.vram_total_mb) * 100 : 0;
    setMeter('vram', vp, `${(m.gpu.vram_used_mb / 1024).toFixed(1)}/${(m.gpu.vram_total_mb / 1024).toFixed(1)} GB`);
  } else {
    setMeter('gpu', 0, 'n/d'); setMeter('vram', 0, 'n/d');
  }
}
