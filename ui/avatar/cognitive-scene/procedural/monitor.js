// ============================================================
//  MONITOR — tela holográfica PRINCIPAL, maior e mais detalhada.
//  Zonas: nav rail (GRAPH/DATA/SEARCH/CONTEXT) · cabeçalho c/ status ·
//  CONTEXT (MEMORY mini-grafo → ANALYSIS waveform) · DATA STREAM (log) ·
//  rodapé (barras · PROCESSING · CONFIDENCE) · leituras numéricas.
//  Tudo procedural, materiais compartilhados, buffers/textos atualizados (0 GC).
//  Conteúdo da Fase 1 é representativo; a Fase 2 troca por estado (intent).
// ============================================================
import * as THREE from 'three';
import {
  HOLO, lineMat, fillMat, glowMat, frameLines, grid, corners, textPlane,
  lineGraph, barMeter, nodeCluster, dataStream, disposeObject,
} from './primitives.js';

function scanlineTexture() {
  const cv = document.createElement('canvas'); cv.width = 4; cv.height = 64;
  const ctx = cv.getContext('2d');
  for (let y = 0; y < cv.height; y += 3) { ctx.fillStyle = 'rgba(120,200,255,0.08)'; ctx.fillRect(0, y, cv.width, 1); }
  const t = new THREE.CanvasTexture(cv); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(1, 28);
  return t;
}

export function createMonitor({ width = 2.9, height = 1.66 } = {}) {
  const group = new THREE.Group();
  const anchors = new Map();
  const reg = (id, o) => { anchors.set(id, o); o.userData.anchorId = id; return o; };
  const at = (o, x, y, z = 0.006) => { o.position.set(x, y, z); group.add(o); return o; };
  const W = width, H = height, mx = W * 0.46;

  // ---- base ----
  at(new THREE.Mesh(new THREE.PlaneGeometry(W, H), fillMat(HOLO.dim, 0.17)), 0, 0, 0);
  at(grid(W * 0.96, H * 0.9, 20, 11, lineMat(HOLO.blue, 0.10)), 0, 0, 0.002);
  const scanTex = scanlineTexture();
  const scan = at(new THREE.Mesh(new THREE.PlaneGeometry(W * 0.96, H * 0.9),
    new THREE.MeshBasicMaterial({ map: scanTex, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending, depthWrite: false })), 0, 0, 0.004);
  group.add(frameLines(W, H, lineMat(HOLO.teal, 0.75)));
  group.add(corners(W, H, 0.11, lineMat(HOLO.teal, 0.95)));

  // ---- cabeçalho: título (esq) + leituras numa linha (dir) + divisória ----
  const title = textPlane('AILA // COGNITIVE SCENE', { width: W * 0.42, px: 768, size: 40, color: HOLO.text });
  reg('title', at(title.mesh, -mx + W * 0.23, H * 0.42, 0.007));
  const readout = textPlane('', { width: W * 0.4, px: 1024, size: 28, align: 'right', color: HOLO.text });
  at(readout.mesh, mx - W * 0.23, H * 0.42, 0.007);   // right-align termina em x+larg/2 → recua p/ ficar dentro
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-mx, H * 0.35, 0.006), new THREE.Vector3(mx, H * 0.35, 0.006)]), lineMat(HOLO.teal, 0.4)));

  // ---- nav rail (esquerda) — itens re-estilizáveis (o modo/intent acende um) ----
  const NAV = ['GRAPH', 'DATA', 'SEARCH', 'CONTEXT'];
  const navX = -mx + W * 0.06, navW = W * 0.10, navH = H * 0.105;
  const navItems = NAV.map((label, i) => {
    const y = H * 0.15 - i * (navH + H * 0.045);
    const p = new THREE.Group();
    const fill = new THREE.Mesh(new THREE.PlaneGeometry(navW, navH), fillMat(HOLO.blue, 0.05));
    const frameM = lineMat(HOLO.blue, 0.4);
    p.add(fill, frameLines(navW, navH, frameM));
    const accent = new THREE.Mesh(new THREE.PlaneGeometry(0.008, navH), glowMat(HOLO.teal, 0.9));
    accent.position.x = -navW / 2; accent.visible = false; p.add(accent);
    const t = textPlane(label, { width: navW * 0.86, px: 256, size: 26, align: 'center', color: HOLO.textDim });
    t.mesh.position.z = 0.003; p.add(t.mesh);
    at(p, navX, y, 0.006); reg('nav_' + label.toLowerCase(), p);
    return { name: label.toLowerCase(), fill, frameM, accent };
  });
  const setActiveNav = (name) => navItems.forEach((it) => {
    const on = it.name === name;
    it.fill.material.color.setHex(on ? HOLO.teal : HOLO.blue); it.fill.material.opacity = on ? 0.14 : 0.05;
    it.frameM.color.setHex(on ? HOLO.teal : HOLO.blue); it.frameM.opacity = on ? 0.85 : 0.4;
    it.accent.visible = on;
  });
  setActiveNav('graph');

  // ---- painel util (moldura + rótulo + filho); guarda o retângulo p/ verificação ----
  const contentX = navX + navW * 0.5 + W * 0.03;
  const panel = (label, x, y, w, h, id, child) => {
    const p = new THREE.Group();
    p.add(new THREE.Mesh(new THREE.PlaneGeometry(w, h), fillMat(HOLO.blue, 0.05)));
    p.add(frameLines(w, h, lineMat(HOLO.blue, 0.5)));
    p.add(corners(w, h, 0.05, lineMat(HOLO.teal, 0.6)));
    const t = textPlane(label, { width: w * 0.6, px: 320, size: 28, color: HOLO.text });
    t.mesh.position.set(-w * 0.5 + w * 0.30, h * 0.5 - 0.06, 0.003); p.add(t.mesh);
    if (child) { child.position.z = 0.004; p.add(child); }
    p.position.set(x, y, 0.006); group.add(p);
    p.userData.rect = { x, y, w, h };
    return reg(id, p);
  };

  // ZONA SUPERIOR: MEMORY (mini-grafo) + ANALYSIS (waveform)
  const cluster = nodeCluster(20, H * 0.12, new THREE.PointsMaterial({ color: HOLO.teal, size: 0.02, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }), lineMat(HOLO.blue, 0.3));
  cluster.group.position.y = -0.04;
  panel('MEMORY', contentX + W * 0.17, H * 0.11, W * 0.28, H * 0.38, 'panel_memory', cluster.group);

  const wave = lineGraph(W * 0.32, H * 0.18, 60, lineMat(HOLO.teal, 0.9));
  wave.line.position.y = -0.04;
  const analysis = panel('ANALYSIS', contentX + W * 0.55, H * 0.11, W * 0.40, H * 0.38, 'panel_analysis', wave.line);
  analysis.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-W * 0.17, -0.04, 0.003), new THREE.Vector3(W * 0.17, -0.04, 0.003)]), lineMat(HOLO.blue, 0.25)));

  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([   // seta MEMORY → ANALYSIS
    new THREE.Vector3(contentX + W * 0.32, H * 0.11, 0.007), new THREE.Vector3(contentX + W * 0.35, H * 0.11, 0.007)]), lineMat(HOLO.teal, 0.8)));

  // ZONA INFERIOR: DATA STREAM (esq) · PROCESSING + barras + CONFIDENCE (dir)
  const stream = dataStream(4, W * 0.26, { size: 24, rowH: H * 0.05 });
  stream.group.position.set(0, H * 0.03, 0.004);
  panel('DATA STREAM', contentX + W * 0.17, -H * 0.30, W * 0.30, H * 0.30, 'panel_stream', stream.group);

  // faixas verticais separadas: PROCESSING (topo) · barras (meio) · CONFIDENCE (base)
  const status = textPlane('PROCESSING', { width: W * 0.22, px: 384, size: 28, align: 'left', color: HOLO.amberText });
  at(status.mesh, contentX + W * 0.46, -H * 0.20, 0.007);
  const bars = barMeter(12, W * 0.28, 0.085, glowMat(HOLO.teal, 0.7));
  at(bars.group, contentX + W * 0.54, -H * 0.34, 0.006);

  const barW = W * 0.32, barY = -H * 0.44, barX = contentX + W * 0.54;
  at(new THREE.Mesh(new THREE.PlaneGeometry(barW, 0.03), fillMat(HOLO.blue, 0.12)), barX, barY, 0.006);
  const fill = new THREE.Mesh(new THREE.PlaneGeometry(barW, 0.03), glowMat(HOLO.teal, 0.85));
  const setConfidence = (v) => { const c = Math.max(0, Math.min(1, v)); fill.scale.x = c || 1e-3; fill.position.set(barX - barW / 2 + (barW * c) / 2, barY, 0.007); };
  group.add(fill); setConfidence(0.87);
  at(textPlane('CONFIDENCE 87%', { width: W * 0.26, px: 448, size: 26, color: HOLO.text }).mesh, barX - W * 0.06, barY + 0.05, 0.007);
  reg('confidence', fill);

  // ---- MODO por intent (Fase 2): a interface representa o que a Aila faz ----
  const MODES = {
    thinking:       { nav: 'graph',   verb: 'THINKING' },
    analysis:       { nav: 'data',    verb: 'ANALYZING' },
    search:         { nav: 'search',  verb: 'SEARCHING' },
    coding:         { nav: 'data',    verb: 'COMPILING' },
    reading:        { nav: 'context', verb: 'READING' },
    tool_execution: { nav: 'data',    verb: 'EXECUTING' },
    error:          { nav: 'context', verb: 'ERROR' },
    explanation:    { nav: 'context', verb: 'EXPLAINING' },
    greeting:       { nav: 'graph',   verb: 'READY' },
    farewell:       { nav: 'graph',   verb: 'READY' },
    conversation:   { nav: 'graph',   verb: 'READY' },
  };
  let verb = 'PROCESSING';
  let _intensity = 0.6;
  let _stateVisual = null;
  function setMode(intent) {
    const m = MODES[intent] || MODES.conversation;
    setActiveNav(m.nav);
    verb = m.verb;
  }
  function setIntensity(v) { _intensity = Math.max(0, Math.min(1, v ?? 0.6)); }
  function applyStateVisuals(sv) { _stateVisual = sv; }

  // ---- animação ----
  let t = 0, tRead = 0, tDots = 0, dots = 0;
  function update(dt) {
    t += dt;
    const sv = _stateVisual;
    const scanSpd = sv ? sv.scanSpeed : 0.3;
    const glow = sv ? sv.glow : 0.6;
    scanTex.offset.y = (scanTex.offset.y - dt * scanSpd) % 1;
    scan.material.opacity = (0.36 + Math.sin(t * 2.1) * 0.05) * (_intensity / 0.6) * glow;
    cluster.update(t);
    stream.update(dt);
    wave.set((u) => 0.5 + Math.sin(u * 12 + t * 3) * 0.28 * Math.sin(u * Math.PI) + Math.sin(u * 30 + t * 5) * 0.06);
    const bh = []; for (let i = 0; i < 12; i++) bh.push(0.22 + Math.abs(Math.sin(t * 2 + i * 0.6)) * 0.72); bars.set(bh);
    tRead += dt; if (tRead > 0.4) {
      tRead = 0;
      const nodes = 880 + ((Math.random() * 8) | 0), tok = 1240 + ((Math.random() * 60) | 0), lat = 320 + ((Math.random() * 50) | 0);
      readout.setText(`NODES ${nodes}    TOKENS ${tok}    LAT ${lat}ms`);
    }
    tDots += dt; if (tDots > 0.4) { tDots = 0; dots = (dots + 1) % 4; status.setText((sv ? sv.verb : verb) + '.'.repeat(dots)); }
  }

  function dispose() { disposeObject(group); scanTex.dispose(); }
  return { group, anchors, update, dispose, setConfidence, setMode, setIntensity, applyStateVisuals };
}
