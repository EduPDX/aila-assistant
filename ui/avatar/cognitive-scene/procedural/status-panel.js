// ============================================================
//  STATUS PANEL — 2ª tela com os dados REAIS do sistema (antes nos HUDs
//  laterais). Coluna ÚNICA e compacta (tudo DENTRO da moldura): cada linha =
//  rótulo à esquerda + (barra) + valor à direita. setMetrics(m) alimenta com o
//  snapshot de /api/metrics (+ estado).
// ============================================================
import * as THREE from 'three';
import { HOLO, lineMat, fillMat, frameLines, corners, textPlane, hbar, disposeObject } from './primitives.js';

const fmtUptime = (sec) => {
  const s = Math.max(0, sec | 0), h = (s / 3600) | 0, m = ((s % 3600) / 60) | 0;
  return h ? `${h}h${m}m` : `${m}m${String(s % 60).padStart(2, '0')}s`;
};

export function createStatusPanel({ width = 0.9, height = 1.12 } = {}) {
  const group = new THREE.Group();
  const at = (o, x, y, z = 0.006) => { o.position.set(x, y, z); group.add(o); return o; };
  // margens internas (tudo fica dentro de ±mx)
  const mx = width * 0.42;

  at(new THREE.Mesh(new THREE.PlaneGeometry(width, height), fillMat(HOLO.dim, 0.16)), 0, 0, 0);
  group.add(frameLines(width, height, lineMat(HOLO.teal, 0.7)));
  group.add(corners(width, height, 0.08, lineMat(HOLO.teal, 0.95)));
  const title = textPlane('SYSTEM // STATUS', { width: width * 0.66, px: 512, size: 34, color: HOLO.text });
  at(title.mesh, -width * 0.14, height * 0.44, 0.007);
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-mx, height * 0.39, 0.006), new THREE.Vector3(mx, height * 0.39, 0.006)]), lineMat(HOLO.teal, 0.4)));

  // linha de MEDIDOR: rótulo (esq) + barra (centro) + valor (dir), tudo dentro.
  const meter = (label, y, color = HOLO.teal) => {
    at(textPlane(label, { width: width * 0.26, px: 256, size: 22, color: HOLO.textDim }).mesh, -mx + width * 0.13, y, 0.007);
    const bar = hbar(width * 0.32, 0.022, color);
    at(bar.group, -width * 0.02, y, 0.007);
    const v = textPlane('—', { width: width * 0.26, px: 256, size: 22, align: 'right', color: HOLO.text });
    at(v.mesh, mx - width * 0.13, y, 0.007);
    return { set: bar.set, setText: v.setText };
  };
  // linha de TEXTO: rótulo (esq) + valor (dir).
  const line = (label, y, valColor = HOLO.text) => {
    at(textPlane(label, { width: width * 0.34, px: 320, size: 22, color: HOLO.textDim }).mesh, -mx + width * 0.17, y, 0.007);
    const v = textPlane('—', { width: width * 0.40, px: 448, size: 22, align: 'right', color: valColor });
    at(v.mesh, mx - width * 0.20, y, 0.007);
    return v.setText;
  };

  // 10 linhas empilhadas dentro da área útil
  let y = height * 0.30; const step = height * 0.084;
  const mGpu = meter('GPU', y); y -= step;
  const mCpu = meter('CPU', y); y -= step;
  const mVram = meter('VRAM', y, HOLO.blue); y -= step;
  const mRam = meter('RAM', y, HOLO.blue); y -= step * 1.15;
  const vModel = line('MODEL', y); y -= step;
  const vTps = line('TOKENS/S', y); y -= step;
  const vUp = line('UPTIME', y); y -= step;
  const vNet = line('REDE', y); y -= step;
  const vAut = line('AUTONOMIA', y); y -= step;
  const vEmo = line('EMOÇÃO', y, HOLO.amberText);

  function update() { }

  function setMetrics(m) {
    if (!m) return;
    const g = m.gpu;
    if (g) {
      mGpu.set((g.util || 0) / 100); mGpu.setText(`${Math.round(g.util || 0)}%`);
      if (g.vram_total_mb) { mVram.set(g.vram_used_mb / g.vram_total_mb); mVram.setText(`${(g.vram_used_mb / 1024).toFixed(1)}/${(g.vram_total_mb / 1024).toFixed(1)}G`); }
    }
    if (m.cpu != null) { mCpu.set(m.cpu / 100); mCpu.setText(`${Math.round(m.cpu)}%`); }
    if (m.ram) { mRam.set((m.ram.percent || 0) / 100); mRam.setText(`${m.ram.used_gb}/${m.ram.total_gb}G`); }
    if (m.model) vModel(String(m.model));
    if (m.tps != null) vTps(`${(+m.tps).toFixed(0)}`);
    if (m.uptime_s != null) vUp(fmtUptime(m.uptime_s));
    if (m.network) vNet(m.network === 'offline' ? 'LOCAL' : 'HÍBRIDO');
    if (m.autonomy != null) vAut('L' + m.autonomy);
    if (m.emotion) vEmo(String(m.emotion).toUpperCase());
  }

  function dispose() { disposeObject(group); }
  return { group, update, setMetrics, dispose };
}
