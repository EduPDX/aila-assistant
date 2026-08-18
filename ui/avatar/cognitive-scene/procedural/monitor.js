// ============================================================
//  MONITOR — monitor/holograma procedural (sem modelo externo).
//  Vidro + moldura + cantos HUD + grid + scanlines + título + LEITURAS
//  numéricas + painel MEMORY (mini-grafo) + painel ANALYSIS (waveform) +
//  barras de atividade + status PROCESSING + barra de confiança.
//  Conteúdo da Fase 1 é REPRESENTATIVO; a Fase 2 troca por estado (intent).
//  Tudo procedural, materiais compartilhados, buffers atualizados (0 GC).
//  Expõe update(dt) e um REGISTRO de âncoras nomeadas (p/ IK/gaze futuros).
// ============================================================
import * as THREE from 'three';
import {
  HOLO, lineMat, fillMat, glowMat, frameLines, grid, corners, textPlane,
  lineGraph, barMeter, nodeCluster, disposeObject,
} from './primitives.js';

function scanlineTexture() {
  const cv = document.createElement('canvas');
  cv.width = 4; cv.height = 64;
  const ctx = cv.getContext('2d');
  for (let y = 0; y < cv.height; y += 3) { ctx.fillStyle = 'rgba(120,200,255,0.10)'; ctx.fillRect(0, y, cv.width, 1); }
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(1, 22);
  return t;
}

export function createMonitor({ width = 1.7, height = 0.96 } = {}) {
  const group = new THREE.Group();
  const anchors = new Map();
  const reg = (id, obj) => { anchors.set(id, obj); obj.userData.anchorId = id; return obj; };
  const at = (obj, x, y, z = 0.006) => { obj.position.set(x, y, z); group.add(obj); return obj; };

  // ---- base: vidro + grid + scanlines + moldura + cantos ----
  at(new THREE.Mesh(new THREE.PlaneGeometry(width, height), fillMat(HOLO.dim, 0.16)), 0, 0, 0);
  at(grid(width * 0.94, height * 0.82, 14, 8, lineMat(HOLO.blue, 0.12)), 0, -0.02, 0.002);
  const scanTex = scanlineTexture();
  const scan = at(new THREE.Mesh(new THREE.PlaneGeometry(width * 0.94, height * 0.82),
    new THREE.MeshBasicMaterial({ map: scanTex, transparent: true, opacity: 0.45, blending: THREE.AdditiveBlending, depthWrite: false })), 0, -0.02, 0.004);
  group.add(frameLines(width, height, lineMat(HOLO.teal, 0.7)));
  group.add(corners(width, height, 0.09, lineMat(HOLO.teal, 0.95)));

  // ---- título (topo-esquerda) + divisória ----
  const title = textPlane('AILA // COGNITIVE SCENE', { width: width * 0.62, px: 768, size: 42, color: HOLO.text });
  reg('title', at(title.mesh, -width * 0.18, height * 0.41, 0.007));
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-width * 0.46, height * 0.34, 0.006), new THREE.Vector3(width * 0.10, height * 0.34, 0.006)]), lineMat(HOLO.teal, 0.4)));

  // ---- leituras numéricas (topo-direita), atualizam em baixa frequência ----
  const readouts = [
    { label: 'NODES', base: 884, span: 6, unit: '', y: height * 0.42 },
    { label: 'TOKENS', base: 1240, span: 60, unit: '', y: height * 0.35 },
    { label: 'LATENCY', base: 340, span: 40, unit: 'ms', y: height * 0.28 },
  ].map((r) => {
    const tp = textPlane(`${r.label} ${r.base}${r.unit}`, { width: width * 0.32, px: 448, size: 34, align: 'right', color: HOLO.text });
    at(tp.mesh, width * 0.30, r.y, 0.007);
    return { ...r, tp };
  });

  // ---- painel util (moldura + rótulo no topo + filho embutido) ----
  const panel = (label, x, y, w, h, id, child) => {
    const p = new THREE.Group();
    p.add(frameLines(w, h, lineMat(HOLO.blue, 0.5)));
    p.add(new THREE.Mesh(new THREE.PlaneGeometry(w, h), fillMat(HOLO.blue, 0.05)));
    const t = textPlane(label, { width: w * 0.85, px: 256, size: 34, align: 'center', color: HOLO.text });
    t.mesh.position.set(0, h * 0.5 - 0.05, 0.003); p.add(t.mesh);
    if (child) { child.position.z = 0.004; p.add(child); }
    p.position.set(x, y, 0.006); group.add(p);
    return reg(id, p);
  };

  // MEMORY: mini-grafo de nós
  const cluster = nodeCluster(16, height * 0.13, new THREE.PointsMaterial({ color: HOLO.teal, size: 0.02, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }), lineMat(HOLO.blue, 0.3));
  cluster.group.position.y = -0.03;
  panel('MEMORY', -width * 0.27, 0.03, width * 0.32, height * 0.44, 'panel_memory', cluster.group);

  // ANALYSIS: waveform (gráfico de linha animado)
  const wave = lineGraph(width * 0.30, height * 0.20, 48, lineMat(HOLO.teal, 0.85));
  wave.line.position.y = -0.03;
  panel('ANALYSIS', width * 0.26, 0.03, width * 0.36, height * 0.44, 'panel_analysis', wave.line);

  // seta de fluxo entre os painéis
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-width * 0.10, 0.02, 0.007), new THREE.Vector3(width * 0.05, 0.02, 0.007)]), lineMat(HOLO.teal, 0.8)));

  // ---- barras de atividade (base-esquerda) ----
  const bars = barMeter(8, width * 0.28, 0.11, glowMat(HOLO.teal, 0.7));
  at(bars.group, -width * 0.28, -height * 0.36, 0.006);

  // ---- status PROCESSING (centro-baixo) ----
  const status = textPlane('PROCESSING', { width: width * 0.26, px: 320, size: 32, align: 'left', color: HOLO.amberText });
  at(status.mesh, -width * 0.06, -height * 0.30, 0.007);

  // ---- barra de confiança (base-direita) ----
  const barW = width * 0.42, barH = 0.028, barY = -height * 0.40, barX = width * 0.20;
  at(new THREE.Mesh(new THREE.PlaneGeometry(barW, barH), fillMat(HOLO.blue, 0.12)), barX, barY, 0.006);
  const fill = new THREE.Mesh(new THREE.PlaneGeometry(barW, barH), glowMat(HOLO.teal, 0.85));
  const setConfidence = (v) => { const c = Math.max(0, Math.min(1, v)); fill.scale.x = c || 1e-3; fill.position.set(barX - barW / 2 + (barW * c) / 2, barY, 0.007); };
  group.add(fill); setConfidence(0.87);
  const conf = textPlane('CONFIDENCE 87%', { width: width * 0.34, px: 384, size: 30, align: 'left', color: HOLO.text });
  at(conf.mesh, barX - width * 0.05, barY + 0.05, 0.007);
  reg('confidence', fill);

  // ---- animação (barata) ----
  let t = 0, tRead = 0, tDots = 0, dots = 0;
  function update(dt) {
    t += dt;
    scanTex.offset.y = (scanTex.offset.y - dt * 0.35) % 1;
    scan.material.opacity = 0.4 + Math.sin(t * 2.1) * 0.06;
    cluster.update(t);
    wave.set((u) => 0.5 + Math.sin(u * 12 + t * 3) * 0.28 * Math.sin(u * Math.PI) + Math.sin(u * 30 + t * 5) * 0.06);
    const bh = []; for (let i = 0; i < 8; i++) bh.push(0.25 + Math.abs(Math.sin(t * 2 + i * 0.7)) * 0.7); bars.set(bh);
    // leituras numéricas: atualiza ~4x/s
    tRead += dt;
    if (tRead > 0.25) {
      tRead = 0;
      for (const r of readouts) r.tp.setText(`${r.label} ${Math.round(r.base + (Math.random() - 0.5) * r.span)}${r.unit}`);
    }
    // status PROCESSING com "…" pulsando
    tDots += dt;
    if (tDots > 0.4) { tDots = 0; dots = (dots + 1) % 4; status.setText('PROCESSING' + '.'.repeat(dots)); }
  }

  function dispose() { disposeObject(group); scanTex.dispose(); }
  return { group, anchors, update, dispose, setConfidence };
}
