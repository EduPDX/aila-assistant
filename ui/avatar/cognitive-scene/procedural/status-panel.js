// ============================================================
//  STATUS PANEL — 2ª tela com os dados REAIS do sistema (antes nos HUDs
//  laterais). Duas colunas: ESQUERDA = medidores (GPU/CPU/VRAM/RAM),
//  DIREITA = leituras (MODEL/TOKENS/UPTIME/REDE/AUTONOMIA/EMOÇÃO).
//  setMetrics(m) alimenta com o snapshot de /api/metrics (+ estado).
// ============================================================
import * as THREE from 'three';
import { HOLO, lineMat, fillMat, frameLines, corners, textPlane, hbar, disposeObject } from './primitives.js';

const fmtUptime = (sec) => {
  const s = Math.max(0, sec | 0), h = (s / 3600) | 0, m = ((s % 3600) / 60) | 0;
  return h ? `${h}h${m}m` : `${m}m${String(s % 60).padStart(2, '0')}s`;
};

export function createStatusPanel({ width = 1.06, height = 0.98 } = {}) {
  const group = new THREE.Group();
  const at = (o, x, y, z = 0.006) => { o.position.set(x, y, z); group.add(o); return o; };

  // base + moldura + cantos + título + divisórias
  at(new THREE.Mesh(new THREE.PlaneGeometry(width, height), fillMat(HOLO.dim, 0.16)), 0, 0, 0);
  group.add(frameLines(width, height, lineMat(HOLO.teal, 0.7)));
  group.add(corners(width, height, 0.08, lineMat(HOLO.teal, 0.95)));
  const title = textPlane('SYSTEM // STATUS', { width: width * 0.6, px: 512, size: 38, color: HOLO.text });
  at(title.mesh, -width * 0.19, height * 0.42, 0.007);
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-width * 0.46, height * 0.36, 0.006), new THREE.Vector3(width * 0.46, height * 0.36, 0.006)]), lineMat(HOLO.teal, 0.4)));
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([  // divisória vertical entre colunas
    new THREE.Vector3(0, height * 0.34, 0.006), new THREE.Vector3(0, -height * 0.46, 0.006)]), lineMat(HOLO.teal, 0.22)));

  // -------- coluna ESQUERDA: medidores (barra + %) --------
  const cw = width * 0.42, cx = -width * 0.25;
  const meter = (label, y, color = HOLO.teal) => {
    const l = textPlane(label, { width: cw * 0.6, px: 256, size: 26, color: HOLO.textDim });
    at(l.mesh, cx - cw * 0.20, y + 0.04, 0.007);
    const v = textPlane('—', { width: cw * 0.7, px: 320, size: 26, align: 'right', color: HOLO.text });
    at(v.mesh, cx + cw * 0.30, y + 0.04, 0.007);
    const bar = hbar(cw, 0.026, color);
    at(bar.group, cx, y - 0.012, 0.007);
    return { set: bar.set, setText: v.setText };
  };
  const mGpu = meter('GPU', height * 0.20);
  const mCpu = meter('CPU', height * 0.02);
  const mVram = meter('VRAM', -height * 0.16, HOLO.blue);
  const mRam = meter('RAM', -height * 0.34, HOLO.blue);

  // -------- coluna DIREITA: leituras texto --------
  const rx = width * 0.26;
  const line = (label, y, valColor = HOLO.text) => {
    const l = textPlane(label, { width: width * 0.24, px: 256, size: 24, color: HOLO.textDim });
    at(l.mesh, rx - width * 0.13, y, 0.007);
    const v = textPlane('—', { width: width * 0.36, px: 384, size: 26, align: 'right', color: valColor });
    at(v.mesh, rx + width * 0.10, y, 0.007);
    return v.setText;
  };
  const vModel = line('MODEL', height * 0.24);
  const vTps = line('TOKENS/S', height * 0.12);
  const vUp = line('UPTIME', height * 0.00);
  const vNet = line('REDE', -height * 0.12);
  const vAut = line('AUTONOMIA', -height * 0.24);
  const vEmo = line('EMOÇÃO', -height * 0.36, HOLO.amberText);

  function update() { }   // reservado

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
