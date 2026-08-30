// ============================================================
//  Recursos — diagnóstico de Resource Intelligence (R11).
//  Torna VISÍVEL o que R2–R8 medem nos bastidores:
//    · pressão unificada GPU+RAM (R2)  · inventário de modelos (R3)
//    · saúde dos provedores/circuit-breaker (R4)  · telemetria (R8)
//  Fonte única: /api/resources (poll a cada 3 s). Só leitura.
// ============================================================
import { el } from '../dom.js';
import { api } from '../core/api.js';

const PRESS_LABEL = { normal: 'NORMAL', elevated: 'ELEVADA', high: 'ALTA', critical: 'CRÍTICA' };
const HEALTH_LABEL = { closed: 'ok', open: 'em cooldown', half_open: 'testando' };

export function initResources(mount) {
  mount.innerHTML = '';
  mount.append(
    el('div', { class: 'act-head' }, el('span', { class: 'act-title' }, 'RECURSOS')),
    el('div', { class: 'res-body', id: 'res-body' },
      el('div', { class: 'act-empty' }, 'Medindo…')),
  );
  poll();
  setInterval(poll, 3000);
}

async function poll() {
  const body = document.getElementById('res-body');
  if (!body) return;
  let data;
  try {
    data = await api.resources();
  } catch {
    return;   // offline: mantém a última foto
  }
  body.innerHTML = '';
  body.append(
    pressureCard(data.pressure || {}),
    modelsCard(data.models || {}),
    healthCard(data.health || {}),
    perfCard(data.perf || {}),
    benchCard(data.benchmark),
  );
}

/** Pressão unificada (R2): badge geral + linhas GPU/RAM. */
function pressureCard(p) {
  const lvl = p.pressure || 'normal';
  const rows = [];
  if (p.gpu) {
    const g = p.gpu;
    rows.push(meterRow('GPU', `${(g.vram_used_mb / 1024).toFixed(1)}/${(g.vram_total_mb / 1024).toFixed(1)} GB`,
      g.vram_total_mb ? (g.vram_used_mb / g.vram_total_mb) * 100 : 0, g.pressure));
  }
  if (p.ram) {
    rows.push(meterRow('RAM', `${p.ram.used_gb}/${p.ram.total_gb} GB`, p.ram.percent, p.ram.pressure));
  }
  return el('div', { class: 'res-card' },
    el('div', { class: 'res-card-head' },
      el('span', {}, 'PRESSÃO'),
      el('span', { class: 'res-badge', 'data-lvl': lvl }, PRESS_LABEL[lvl] || lvl.toUpperCase()),
    ),
    ...rows,
    p.gpu ? null : el('div', { class: 'res-note' }, 'sem GPU visível — pressão pela RAM'),
  );
}

function meterRow(label, txt, pct, lvl) {
  return el('div', { class: 'res-meter', 'data-lvl': lvl || 'normal' },
    el('div', { class: 'res-meter-top' }, el('span', {}, label), el('span', {}, txt)),
    el('div', { class: 'res-meter-tr' }, el('i', { style: `width:${Math.min(100, Math.max(0, pct || 0))}%` })),
  );
}

/** Inventário de modelos (R3): quente/frio, footprint, papel. */
function modelsCard(inv) {
  const list = inv.models || [];
  const kids = list.length
    ? list.map((m) => el('div', { class: 'res-model', 'data-hot': m.loaded ? '1' : '0' },
        el('span', { class: 'res-dot' }, m.loaded ? '●' : '○'),
        el('span', { class: 'res-model-name', title: m.name }, m.name),
        el('span', { class: 'res-model-role' }, (m.roles || []).join(', ') || (m.installed ? 'instalado' : '—')),
        el('span', { class: 'res-model-vram' }, m.loaded ? `${(m.vram_mb / 1024).toFixed(1)} GB` : (m.installed ? 'frio' : 'ausente')),
      ))
    : [el('div', { class: 'act-empty' }, inv.ollama_ok ? 'nenhum modelo listado' : 'Ollama offline')];
  return el('div', { class: 'res-card' },
    el('div', { class: 'res-card-head' },
      el('span', {}, 'MODELOS'),
      el('span', { class: 'res-sub' }, `${(inv.loaded_vram_mb / 1024).toFixed(1)} GB quentes`),
    ),
    ...kids,
  );
}

/** Saúde dos provedores (R4): só aparece se houver histórico. */
function healthCard(h) {
  const names = Object.keys(h);
  if (!names.length) return el('span');   // nada a mostrar ainda
  return el('div', { class: 'res-card' },
    el('div', { class: 'res-card-head' }, el('span', {}, 'PROVEDORES')),
    ...names.map((n) => {
      const s = h[n];
      const label = HEALTH_LABEL[s.state] || s.state;
      const extra = s.state === 'open' ? ` ${Math.round(s.cooldown_left_s)}s` : '';
      return el('div', { class: 'res-prov', 'data-state': s.state },
        el('span', { class: 'res-prov-name' }, n),
        el('span', { class: 'res-prov-state' }, label + extra),
        s.fails ? el('span', { class: 'res-prov-fails' }, `${s.fails} falha(s)`) : null,
      );
    }),
  );
}

/** Escada de modelos medida (R12, cacheada): footprint + tps do benchmark. */
function benchCard(bench) {
  if (!bench || !Array.isArray(bench.samples)) return el('span');
  const ok = bench.samples.filter((s) => s.ok);
  if (!ok.length) return el('span');
  const when = bench.ts ? new Date(bench.ts * 1000).toLocaleDateString() : '';
  // ordena pela escada (mais leve → mais pesado por footprint)
  const order = bench.ladder || ok.map((s) => s.model);
  ok.sort((a, b) => order.indexOf(a.model) - order.indexOf(b.model));
  return el('div', { class: 'res-card' },
    el('div', { class: 'res-card-head' },
      el('span', {}, 'ESCADA'),
      el('span', { class: 'res-sub' }, when ? `medida ${when}` : 'benchmark'),
    ),
    ...ok.map((s) => el('div', { class: 'res-perf' },
      el('span', { class: 'res-perf-name', title: s.model }, s.model),
      el('span', { class: 'res-perf-v' }, s.footprint_mb ? `${(s.footprint_mb / 1024).toFixed(1)} GB` : '—'),
      el('span', { class: 'res-perf-v' }, s.tps ? `${s.tps} tok/s` : '—'),
    )),
  );
}

/** Telemetria por modelo (R8): tokens/s, TTFT, taxa de fallback. */
function perfCard(perf) {
  const names = Object.keys(perf);
  if (!names.length) return el('span');
  return el('div', { class: 'res-card' },
    el('div', { class: 'res-card-head' }, el('span', {}, 'DESEMPENHO')),
    ...names.map((n) => {
      const p = perf[n];
      return el('div', { class: 'res-perf' },
        el('span', { class: 'res-perf-name', title: n }, n),
        el('span', { class: 'res-perf-v' }, p.tps ? `${p.tps} tok/s` : '—'),
        el('span', { class: 'res-perf-v' }, p.ttft_ms ? `${Math.round(p.ttft_ms)} ms` : '—'),
        p.fallback_rate ? el('span', { class: 'res-perf-fb' }, `${Math.round(p.fallback_rate * 100)}% fallback`) : null,
      );
    }),
  );
}
