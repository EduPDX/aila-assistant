// ============================================================
//  STATUS PANEL — 2ª tela com os dados REAIS do sistema (antes nos HUDs
//  laterais). Coluna ÚNICA e compacta (tudo DENTRO da moldura): cada linha =
//  rótulo à esquerda + (barra) + valor à direita. setMetrics(m) alimenta com o
//  snapshot de /api/metrics (+ estado).
// ============================================================
import * as THREE from 'three';
import { HOLO, lineMat, fillMat, glowMat, frameLines, corners, textPlane, hbar, disposeObject } from './primitives.js';

const fmtUptime = (sec) => {
  const s = Math.max(0, sec | 0), h = (s / 3600) | 0, m = ((s % 3600) / 60) | 0;
  return h ? `${h}h${m}m` : `${m}m${String(s % 60).padStart(2, '0')}s`;
};

export function createStatusPanel({ width = 1.18, height = 1.38 } = {}) {
  const group = new THREE.Group();
  const at = (o, x, y, z = 0.006) => { o.position.set(x, y, z); group.add(o); return o; };
  // margens internas (tudo fica dentro de ±mx)
  const mx = width * 0.43;

  at(new THREE.Mesh(new THREE.PlaneGeometry(width * 1.035, height * 1.035), fillMat(HOLO.dim, 0.055)), 0.015, -0.015, -0.015);
  at(new THREE.Mesh(new THREE.PlaneGeometry(width, height), fillMat(HOLO.dim, 0.18)), 0, 0, 0);
  group.add(frameLines(width, height, lineMat(HOLO.teal, 0.7)));
  const outerFrame = frameLines(width * 1.035, height * 1.035, lineMat(HOLO.blue, 0.24));
  outerFrame.position.set(0.015, -0.015, -0.012); group.add(outerFrame);
  group.add(corners(width, height, 0.09, lineMat(HOLO.teal, 0.95)));
  const title = textPlane('AILA // TELEMETRY', { width: width * 0.70, px: 640, size: 38, color: HOLO.text });
  at(title.mesh, -width * 0.12, height * 0.44, 0.007);
  const liveDot = new THREE.Mesh(new THREE.CircleGeometry(0.012, 16), glowMat(HOLO.teal, 1));
  at(liveDot, mx - 0.018, height * 0.44, 0.009);
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-mx, height * 0.38, 0.006), new THREE.Vector3(mx, height * 0.38, 0.006)]), lineMat(HOLO.teal, 0.4)));

  // linha de MEDIDOR: rótulo (esq) + barra (centro) + valor (dir), tudo dentro.
  const meter = (label, y, color = HOLO.teal) => {
    at(textPlane(label, { width: width * 0.24, px: 256, size: 32, color: HOLO.textDim }).mesh, -mx + width * 0.12, y, 0.007);
    const bar = hbar(width * 0.30, 0.028, color);
    at(bar.group, -width * 0.02, y, 0.007);
    const v = textPlane('—', { width: width * 0.28, px: 320, size: 32, align: 'right', color: HOLO.text });
    at(v.mesh, mx - width * 0.14, y, 0.007);
    return { set: bar.set, setText: v.setText };
  };
  // linha de TEXTO: rótulo (esq) + valor (dir).
  const line = (label, y, valColor = HOLO.text) => {
    at(textPlane(label, { width: width * 0.34, px: 384, size: 32, color: HOLO.textDim }).mesh, -mx + width * 0.17, y, 0.007);
    const v = textPlane('—', { width: width * 0.44, px: 512, size: 32, align: 'right', color: valColor });
    at(v.mesh, mx - width * 0.22, y, 0.007);
    return v.setText;
  };

  const sectionLabel = (label, y) => {
    const t = textPlane(label, { width: width * 0.36, px: 384, size: 25, color: HOLO.text });
    at(t.mesh, -mx + width * 0.18, y, 0.007);
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-mx, y - 0.035, 0.006), new THREE.Vector3(mx, y - 0.035, 0.006),
    ]), lineMat(HOLO.blue, 0.24)));
  };

  // Dados reais, agrupados por função para leitura mais rápida.
  sectionLabel('HARDWARE', height * 0.325);
  let y = height * 0.245; const step = height * 0.071;
  const mGpu = meter('GPU', y); y -= step;
  const mCpu = meter('CPU', y); y -= step;
  const mVram = meter('VRAM', y, HOLO.blue); y -= step;
  const mRam = meter('RAM', y, HOLO.blue); y -= step * 0.90;
  sectionLabel('RUNTIME', y); y -= step * 0.78;
  const vModel = line('MODEL', y); y -= step;
  const vTps = line('TOKENS/S', y); y -= step;
  const vUp = line('UPTIME', y); y -= step;
  const vNet = line('REDE', y); y -= step;
  const vAut = line('AUTONOMIA', y); y -= step;
  const vEmo = line('EMOÇÃO', y, HOLO.amberText);

  let elapsed = 0;
  function update(dt = 0) {
    elapsed += dt;
    liveDot.material.opacity = 0.62 + Math.sin(elapsed * 3.4) * 0.32;
    liveDot.scale.setScalar(0.88 + Math.sin(elapsed * 3.4) * 0.12);
  }

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
