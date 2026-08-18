// ============================================================
//  STATUS PANEL — segunda tela (mais estreita), com os dados REAIS do sistema
//  (GPU/CPU/VRAM/RAM/modelo/tokens/uptime/rede/autonomia) que antes ficavam nos
//  painéis HUD laterais. setMetrics(m) alimenta com o snapshot de /api/metrics
//  (+ campos de estado). Mesma estética holográfica; textos legíveis (normal).
// ============================================================
import * as THREE from 'three';
import { HOLO, lineMat, fillMat, frameLines, corners, textPlane, hbar, disposeObject } from './primitives.js';

export function createStatusPanel({ width = 0.86, height = 0.96 } = {}) {
  const group = new THREE.Group();
  const at = (o, x, y, z = 0.006) => { o.position.set(x, y, z); group.add(o); return o; };

  // base
  at(new THREE.Mesh(new THREE.PlaneGeometry(width, height), fillMat(HOLO.dim, 0.16)), 0, 0, 0);
  group.add(frameLines(width, height, lineMat(HOLO.teal, 0.7)));
  group.add(corners(width, height, 0.07, lineMat(HOLO.teal, 0.95)));

  const title = textPlane('SYSTEM // STATUS', { width: width * 0.8, px: 512, size: 40, color: HOLO.text });
  at(title.mesh, -width * 0.05, height * 0.42, 0.007);
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-width * 0.44, height * 0.36, 0.006), new THREE.Vector3(width * 0.44, height * 0.36, 0.006)]), lineMat(HOLO.teal, 0.4)));

  // linha de rótulo + valor (texto) — devolve o setText do valor
  const line = (label, y, valColor = HOLO.text) => {
    const l = textPlane(label, { width: width * 0.4, px: 320, size: 30, color: HOLO.textDim });
    at(l.mesh, -width * 0.30, y, 0.007);
    const v = textPlane('—', { width: width * 0.5, px: 384, size: 30, align: 'right', color: valColor });
    at(v.mesh, width * 0.22, y, 0.007);
    return v.setText;
  };
  // medidor: rótulo + barra + valor
  const meter = (label, y, color = HOLO.teal) => {
    const l = textPlane(label, { width: width * 0.34, px: 256, size: 26, color: HOLO.textDim });
    at(l.mesh, -width * 0.32, y + 0.035, 0.007);
    const bar = hbar(width * 0.78, 0.028, color);
    at(bar.group, 0, y - 0.01, 0.007);
    const v = textPlane('—', { width: width * 0.5, px: 320, size: 26, align: 'right', color: HOLO.text });
    at(v.mesh, width * 0.20, y + 0.035, 0.007);
    return { set: bar.set, setText: v.setText };
  };

  const vModel = line('MODEL', height * 0.28, HOLO.text);
  const mGpu = meter('GPU', height * 0.14);
  const mCpu = meter('CPU', height * 0.00);
  const mVram = meter('VRAM', -height * 0.14, HOLO.blue);
  const mRam = meter('RAM', -height * 0.28, HOLO.blue);
  const vTps = line('TOKENS/S', -height * 0.40, HOLO.text);

  let t = 0;
  function update(dt) { t += dt; }   // (reservado p/ pulsos futuros)

  function setMetrics(m) {
    if (!m) return;
    if (m.model) vModel(String(m.model));
    const g = m.gpu;
    if (g) {
      mGpu.set((g.util || 0) / 100); mGpu.setText(`${Math.round(g.util || 0)}%`);
      if (g.vram_total_mb) {
        mVram.set(g.vram_used_mb / g.vram_total_mb);
        mVram.setText(`${(g.vram_used_mb / 1024).toFixed(1)}/${(g.vram_total_mb / 1024).toFixed(1)}G`);
      }
    }
    if (m.cpu != null) { mCpu.set(m.cpu / 100); mCpu.setText(`${Math.round(m.cpu)}%`); }
    if (m.ram) { mRam.set((m.ram.percent || 0) / 100); mRam.setText(`${m.ram.used_gb}/${m.ram.total_gb}G`); }
    if (m.tps != null) vTps(`${(+m.tps).toFixed(0)} t/s`);
  }

  function dispose() { disposeObject(group); }
  return { group, update, setMetrics, dispose };
}
