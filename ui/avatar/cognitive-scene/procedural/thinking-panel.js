// ============================================================
//  THINKING PANEL — mostra os passos do raciocínio (Extended Thinking)
//  durante a geração de resposta. Painel lateral que aparece e desaparece
//  com animação, mostrando cada "passo" em tempo real.
// ============================================================
import * as THREE from 'three';
import {
  HOLO, lineMat, fillMat, glowMat, frameLines, corners, textPlane, disposeObject,
} from './primitives.js';

const MAX_STEPS = 8;

export function createThinkingPanel({ width = 1.1, height = 1.6 } = {}) {
  const group = new THREE.Group();
  const reg = (id, o) => { anchors.set(id, o); o.userData.anchorId = id; return o; };
  const at = (o, x, y, z = 0.006) => { o.position.set(x, y, z); group.add(o); return o; };
  const anchors = new Map();
  const W = width, H = height, mx = W / 2;

  // ---- fundo semi-transparente ----
  at(new THREE.Mesh(new THREE.PlaneGeometry(W, H), fillMat(HOLO.purple || 0x9b59b6, 0.12)), 0, 0, 0);
  group.add(frameLines(W, H, lineMat(HOLO.purple || 0x9b59b6, 0.7)));
  group.add(corners(W, H, 0.06, lineMat(HOLO.purple || 0x9b59b6, 0.9)));

  // ---- cabeçalho ----
  const header = textPlane('THINKING', { width: W * 0.8, px: 384, size: 30, color: HOLO.purple || 0x9b59b6 });
  at(header.mesh, 0, H * 0.42, 0.007);
  reg('header', header.mesh);

  // ---- linha separadora ----
  at(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-mx * 0.9, H * 0.35, 0.006),
    new THREE.Vector3(mx * 0.9, H * 0.35, 0.006),
  ]), lineMat(HOLO.purple || 0x9b59b6, 0.4)), 0, 0, 0);

  // ---- container dos passos (textos empilhados de cima pra baixo) ----
  const stepsContainer = new THREE.Group();
  stepsContainer.position.set(0, H * 0.28, 0.007);
  group.add(stepsContainer);

  // textos dos passos (pool reutilizável — sem GC)
  const stepTexts = [];
  for (let i = 0; i < MAX_STEPS; i++) {
    const tp = textPlane('', { width: W * 0.84, px: 320, size: 20, color: HOLO.text });
    tp.mesh.position.y = -i * (H * 0.085);
    tp.mesh.visible = false;
    stepsContainer.add(tp.mesh);
    stepTexts.push(tp);
  }

  // ---- barra de progresso animada ----
  const barBg = new THREE.Mesh(new THREE.PlaneGeometry(W * 0.8, 0.025), fillMat(HOLO.blue, 0.15));
  at(barBg, 0, -H * 0.38, 0.006);
  const barFill = new THREE.Mesh(new THREE.PlaneGeometry(W * 0.8, 0.025), glowMat(HOLO.purple || 0x9b59b6, 0.85));
  barFill.scale.x = 1e-3;
  at(barFill, 0, -H * 0.38, 0.007);

  // ---- estado interno ----
  let _visible = false;
  let _alpha = 0;            // fade in/out
  let _steps = [];           // textos ativos
  let _pulseT = 0;
  let _progress = 0;         // 0..1

  // ---- API pública ----
  function show() { _visible = true; }
  function hide() { _visible = false; }

  function addStep(text) {
    _steps.push(text);
    if (_steps.length > MAX_STEPS) _steps.shift();
    _renderSteps();
    _progress = Math.min(1, _steps.length / MAX_STEPS);
  }

  function clear() {
    _steps = [];
    _renderSteps();
    _progress = 0;
  }

  function setHeader(text) {
    header.setText(text);
  }

  function _renderSteps() {
    for (let i = 0; i < MAX_STEPS; i++) {
      const tp = stepTexts[i];
      if (i < _steps.length) {
        tp.setText(`${i + 1}. ${_steps[i]}`);
        tp.mesh.visible = true;
      } else {
        tp.setText('');
        tp.mesh.visible = false;
      }
    }
    // re-posicionar do topo
    const totalH = _steps.length * H * 0.085;
    stepsContainer.position.y = H * 0.28 - (totalH / 2);
  }

  // ---- animação ----
  function update(dt) {
    // fade in/out
    const target = _visible ? 1 : 0;
    _alpha += (target - _alpha) * Math.min(1, dt * 5);
    group.visible = _alpha > 0.01;
    group.scale.setScalar(_alpha);

    if (_alpha < 0.01) return;

    _pulseT += dt;

    // barra de progresso
    const targetScale = Math.max(1e-3, _progress);
    barFill.scale.x += (targetScale - barFill.scale.x) * Math.min(1, dt * 4);

    // pulse no header
    const pulse = 0.7 + Math.sin(_pulseT * 3) * 0.3;
    header.mesh.material.opacity = pulse;

    // scroll automático: empurra passos antigos pra cima quando cheio
    if (_steps.length >= MAX_STEPS) {
      const scrollOffset = (_pulseT * 0.3) % (H * 0.085);
      stepsContainer.position.y = H * 0.28 - (_steps.length * H * 0.085 / 2) - scrollOffset;
    }
  }

  function dispose() { disposeObject(group); stepTexts.forEach(t => disposeObject(t.mesh)); }

  return { group, anchors, update, dispose, show, hide, addStep, clear, setHeader };
}
