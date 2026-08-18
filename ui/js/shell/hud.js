// ============================================================
//  HUD do palco (estética FUI/sci-fi, ref. "LUCY/ONLINE").
//  Sobrepõe telemetria REAL ao redor da avatar: header de estado,
//  medidores circulares (GPU/CPU) e rails de leitura (modelo/rede/
//  autonomia/tokens/uptime/emoção). Fonte única = State; um só poller
//  de /api/metrics escreve State.metrics (o painel Sistema lê o mesmo).
//  100% pointer-events:none — nunca rouba clique do chat/composer.
// ============================================================
import { State, STATUS_LABEL } from '../state.js';
import { api } from '../core/api.js';
import { avatarVramPressure, avatarMetrics } from '../avatar.js';

const R = 26;
const C = 2 * Math.PI * R;

const fmtUptime = (s) => {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h}h${m}m` : `${m}m${String(s % 60).padStart(2, '0')}s`;
};

const ring = (id, label) => `
  <div class="hud-gauge">
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <circle class="hg-track" cx="32" cy="32" r="${R}"></circle>
      <circle class="hg-arc" id="${id}-arc" cx="32" cy="32" r="${R}"
        stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${C.toFixed(1)}"></circle>
    </svg>
    <div class="hg-c"><b id="${id}-v">—</b><span>${label}</span></div>
  </div>`;

const bar = (id, label) => `
  <div class="hud-bar">
    <div class="hud-bar-top"><span>${label}</span><span id="${id}">—</span></div>
    <div class="hud-bar-tr"><i id="${id}-bar"></i></div>
  </div>`;

const readout = (id, label) => `
  <div class="hud-ro"><span class="hud-ro-k">${label}</span><span class="hud-ro-v" id="${id}">—</span></div>`;

export function initHud() {
  const stage = document.querySelector('.content.stage');
  if (!stage || document.getElementById('hud')) return;

  const el = document.createElement('div');
  el.className = 'hud-overlay';
  el.id = 'hud';
  el.innerHTML = `
    <div class="hud-head">
      <span class="hud-brand">AILA</span><span class="hud-sep">/</span>
      <span class="hud-status" id="hud-status" data-tone="online">ONLINE</span>
    </div>
    <div class="hud-rail hud-left">
      ${ring('hud-gpu', 'GPU')}
      ${ring('hud-cpu', 'CPU')}
      <div class="hud-bars">
        ${bar('hud-vram', 'VRAM')}
        ${bar('hud-ram', 'RAM')}
      </div>
    </div>
    <div class="hud-rail hud-right">
      ${readout('hud-model', 'MODELO')}
      ${readout('hud-tps', 'TOKENS/S')}
      ${readout('hud-uptime', 'UPTIME')}
      ${readout('hud-net', 'REDE')}
      ${readout('hud-auton', 'AUTONOMIA')}
      ${readout('hud-emotion', 'EMOÇÃO')}
    </div>`;
  stage.appendChild(el);

  // Cognitive Scene ligada: os dados (GPU/CPU/VRAM/modelo/tokens) migram p/ a tela
  // de STATUS holográfica → esconde os TRILHOS laterais (mantém só o cabeçalho).
  if (localStorage.getItem('aila.scene') !== 'off') {
    el.querySelector('.hud-left')?.style.setProperty('display', 'none');
    el.querySelector('.hud-right')?.style.setProperty('display', 'none');
  }

  State.on(render);
  render(State.get());
  poll();
  setInterval(poll, 2000);
}

function setText(id, txt) { const n = document.getElementById(id); if (n) n.textContent = txt; }

function setGauge(id, pct, label) {
  const arc = document.getElementById(id + '-arc');
  if (arc) {
    const p = Math.min(100, Math.max(0, pct || 0));
    arc.style.strokeDashoffset = (C * (1 - p / 100)).toFixed(1);
  }
  setText(id + '-v', label);
}

function setBar(id, pct, label) {
  setText(id, label);
  const i = document.getElementById(id + '-bar');
  if (i) i.style.width = Math.min(100, Math.max(0, pct || 0)) + '%';
}

/** Header de estado (deriva de conexão + status). */
function renderStatus(s) {
  const el = document.getElementById('hud-status');
  if (!el) return;
  let txt = 'ONLINE', tone = 'online';
  if (s.connection === 'offline') { txt = 'OFFLINE'; tone = 'offline'; }
  else if (s.status === 'ERROR') { txt = 'ERRO'; tone = 'error'; }
  else if (s.status && s.status !== 'IDLE') { txt = (STATUS_LABEL[s.status] || s.status).toUpperCase(); tone = 'busy'; }
  el.textContent = txt;
  el.dataset.tone = tone;
}

function render(s) {
  renderStatus(s);
  setText('hud-model', s.model || '—');
  setText('hud-net', s.networkMode === 'offline' ? 'LOCAL' : 'HÍBRIDO');
  setText('hud-auton', 'L' + (s.autonomy ?? '—'));
  setText('hud-emotion', (s.emotion || 'neutral').toUpperCase());

  const m = s.metrics || {};
  setText('hud-tps', m.tps ? m.tps.toFixed(0) : '—');
  setText('hud-uptime', m.uptime_s != null ? fmtUptime(m.uptime_s) : '—');
  setGauge('hud-cpu', m.cpu, m.cpu != null ? `${Math.round(m.cpu)}%` : '—');
  setBar('hud-ram', m.ram?.percent, m.ram ? `${m.ram.used_gb}/${m.ram.total_gb}G` : '—');
  if (m.gpu) {
    setGauge('hud-gpu', m.gpu.util, `${Math.round(m.gpu.util)}%`);
    const vp = m.gpu.vram_total_mb ? (m.gpu.vram_used_mb / m.gpu.vram_total_mb) * 100 : 0;
    setBar('hud-vram', vp, `${(m.gpu.vram_used_mb / 1024).toFixed(1)}/${(m.gpu.vram_total_mb / 1024).toFixed(1)}G`);
    // "dial" de VRAM: colore a barra por estado (verde/amarelo/vermelho) e reassume
    // o estado REAL no avatar a cada poll — assim, se o backend forçou 'red' no
    // pré-voo da visão, o HUD restaura quando a VRAM libera. O avatar deduplica.
    const vs = m.gpu.state || 'green';
    document.getElementById('hud-vram')?.closest('.hud-bar')?.setAttribute('data-state', vs);
    avatarVramPressure(vs);
  } else {
    setGauge('hud-gpu', 0, 'n/d');
    setBar('hud-vram', 0, 'n/d');
  }
}

/** Único poller de métricas do app → State.metrics (o painel Sistema lê daqui). */
async function poll() {
  try {
    const m = await api.metrics();
    State.set({ metrics: m });
    // encaminha os dados REAIS p/ a tela de STATUS holográfica (Cognitive Scene)
    const s = State.get();
    avatarMetrics({ ...m, model: s.model, network: s.networkMode, autonomy: s.autonomy, emotion: s.emotion });
  } catch (e) { /* offline: mantém últimos valores */ }
}
