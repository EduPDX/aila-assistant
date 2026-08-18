// ============================================================
//  MONITOR — monitor/holograma procedural (sem modelo externo).
//  Constrói: vidro + moldura + cantos HUD + grid + scanlines animadas +
//  título + painéis + barra de confiança. Conteúdo da Fase 1 é REPRESENTATIVO
//  e estático; a Fase 2 troca o conteúdo por estado (search/analysis/…).
//  Expõe update(dt) (scanline/flicker) e um REGISTRO de âncoras nomeadas
//  (sub-elementos) p/ o InteractionTarget/IK das próximas fases.
// ============================================================
import * as THREE from 'three';
import { HOLO, lineMat, fillMat, glowMat, frameLines, grid, corners, textPlane, disposeObject } from './primitives.js';

function scanlineTexture() {
  const cv = document.createElement('canvas');
  cv.width = 4; cv.height = 64;
  const ctx = cv.getContext('2d');
  for (let y = 0; y < cv.height; y += 3) {
    ctx.fillStyle = 'rgba(120,200,255,0.10)';
    ctx.fillRect(0, y, cv.width, 1);
  }
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(1, 22);
  return t;
}

export function createMonitor({ width = 1.7, height = 0.96 } = {}) {
  const group = new THREE.Group();
  const anchors = new Map();          // id -> Object3D (posição p/ gaze/IK futuros)
  const reg = (id, obj) => { anchors.set(id, obj); obj.userData.anchorId = id; return obj; };

  // vidro (fundo translúcido) + leve profundidade
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(width, height), fillMat(HOLO.dim, 0.16));
  group.add(glass);

  // grid interno (dados)
  const g = grid(width * 0.94, height * 0.78, 14, 8, lineMat(HOLO.blue, 0.14));
  g.position.set(0, -0.02, 0.002);
  group.add(g);

  // scanlines animadas (plano aditivo por cima do grid)
  const scanTex = scanlineTexture();
  const scan = new THREE.Mesh(new THREE.PlaneGeometry(width * 0.94, height * 0.78),
    new THREE.MeshBasicMaterial({ map: scanTex, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
  scan.position.set(0, -0.02, 0.004);
  group.add(scan);

  // moldura + cantos HUD
  group.add(frameLines(width, height, lineMat(HOLO.teal, 0.7)));
  group.add(corners(width, height, 0.09, lineMat(HOLO.teal, 0.95)));

  // título (canto superior esquerdo)
  const title = textPlane('AILA // COGNITIVE SCENE', { width: width * 0.72, px: 768, size: 44, color: HOLO.text });
  title.mesh.position.set(-width * 0.13, height * 0.40, 0.006);
  group.add(title.mesh);
  reg('title', title.mesh);

  // dois painéis (representativos na Fase 1)
  const panel = (label, x, y, w, h, id) => {
    const p = new THREE.Group();
    p.add(frameLines(w, h, lineMat(HOLO.blue, 0.5)));
    p.add(new THREE.Mesh(new THREE.PlaneGeometry(w, h), fillMat(HOLO.blue, 0.06)));
    const t = textPlane(label, { width: w * 0.9, px: 256, size: 40, align: 'center', color: HOLO.text });
    t.mesh.position.set(0, h * 0.5 - 0.045, 0.003);
    p.add(t.mesh);
    p.position.set(x, y, 0.006);
    group.add(p);
    return reg(id, p);
  };
  panel('MEMORY', -width * 0.28, 0.02, width * 0.30, height * 0.34, 'panel_memory');
  panel('ANALYSIS', width * 0.24, 0.02, width * 0.34, height * 0.34, 'panel_analysis');

  // seta de fluxo entre os painéis
  const arrow = new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-width * 0.12, 0.02, 0.007), new THREE.Vector3(width * 0.06, 0.02, 0.007)]),
    lineMat(HOLO.teal, 0.8));
  group.add(arrow);

  // barra de confiança (fundo + preenchimento) — valor estático na Fase 1
  const barW = width * 0.62, barH = 0.03, barY = -height * 0.34;
  group.add(new THREE.Mesh(new THREE.PlaneGeometry(barW, barH), fillMat(HOLO.blue, 0.12)).translateX(0).translateY(barY).translateZ(0.006));
  const fill = new THREE.Mesh(new THREE.PlaneGeometry(barW, barH), glowMat(HOLO.teal, 0.8));
  const setConfidence = (v) => {
    const c = Math.max(0, Math.min(1, v));
    fill.scale.x = c || 1e-3;
    fill.position.set(-barW / 2 + (barW * c) / 2, barY, 0.007);
  };
  group.add(fill);
  setConfidence(0.87);
  const conf = textPlane('CONFIDENCE  87%', { width: width * 0.5, px: 384, size: 38, color: HOLO.text });
  conf.mesh.position.set(-width * 0.20, barY + 0.055, 0.007);
  group.add(conf.mesh);
  reg('confidence', fill);

  // animação sutil (scanline scroll + flicker discreto do brilho)
  let t = 0;
  function update(dt) {
    t += dt;
    scanTex.offset.y = (scanTex.offset.y - dt * 0.35) % 1;
    scan.material.opacity = 0.42 + Math.sin(t * 2.1) * 0.06;   // flicker leve
  }

  function dispose() { disposeObject(group); scanTex.dispose(); }

  return { group, anchors, update, dispose, setConfidence };
}
