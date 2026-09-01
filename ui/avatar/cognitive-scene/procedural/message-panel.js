// ============================================================
//  MESSAGE PANEL — "balão" holográfico estilo Jarvis: mostra o RESUMO curto que
//  a Aila fala (sem código/textão), aparece com fade, segura alguns segundos e
//  some. Texto com quebra de linha (word-wrap) numa CanvasTexture. Não é o chat
//  completo — esse fica na aba Conversa.
// ============================================================
import * as THREE from 'three';
import { HOLO, lineMat, fillMat, glowMat, frameLines, corners } from './primitives.js';

export function createMessagePanel({ width = 1.5, height = 0.62 } = {}) {
  const group = new THREE.Group();
  group.visible = false;

  // vidro + moldura + cantos + acento no topo
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(width, height), fillMat(HOLO.dim, 0.22));
  const frame = frameLines(width, height, lineMat(HOLO.teal, 0.85));
  const cor = corners(width, height, 0.07, lineMat(HOLO.teal, 1));
  const accent = new THREE.Mesh(new THREE.PlaneGeometry(width, 0.01), glowMat(HOLO.teal, 0.9)); accent.position.y = height * 0.5 - 0.006;
  group.add(glass, frame, cor, accent);

  // texto (CanvasTexture com word-wrap)
  const cv = document.createElement('canvas');
  cv.width = 1024; cv.height = Math.round(1024 * (height / width));
  const ctx = cv.getContext('2d');
  const tex = new THREE.CanvasTexture(cv);
  tex.minFilter = THREE.LinearFilter;
  tex.colorSpace = THREE.SRGBColorSpace;
  const textMesh = new THREE.Mesh(new THREE.PlaneGeometry(width * 0.92, height * 0.92),
    new THREE.MeshBasicMaterial({
      map: tex, transparent: true, depthWrite: false, toneMapped: false,
    }));
  textMesh.position.z = 0.004;
  group.add(textMesh);

  const parts = [glass, frame, cor, accent, textMesh];
  const baseOp = parts.map((p) => p.material.opacity);

  function drawWrapped(text) {
    ctx.clearRect(0, 0, cv.width, cv.height);
    const pad = 46, maxW = cv.width - pad * 2;
    // cabeçalho
    ctx.fillStyle = '#ffffff'; ctx.font = '700 34px ui-monospace, monospace'; ctx.textBaseline = 'top';
    ctx.fillText('AILA', pad, 24);
    // corpo com quebra de linha
    ctx.fillStyle = '#ffffff'; ctx.font = '500 40px "Segoe UI", system-ui, sans-serif';
    const words = String(text).split(/\s+/);
    const lines = []; let line = '';
    for (const w of words) {
      const test = line ? line + ' ' + w : w;
      if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; } else line = test;
    }
    if (line) lines.push(line);
    const lineH = 50, top = 82, maxLines = Math.floor((cv.height - top - 20) / lineH);
    const shown = lines.slice(0, maxLines);
    if (lines.length > maxLines) shown[maxLines - 1] = shown[maxLines - 1].replace(/.{0,3}$/, '…');
    shown.forEach((l, i) => ctx.fillText(l, pad, top + i * lineH));
    tex.needsUpdate = true;
  }

  let alpha = 0, hold = 0;
  function setAlpha(a) { parts.forEach((p, i) => { p.material.opacity = baseOp[i] * a; }); }

  function show(text) {
    if (!text) return;
    drawWrapped(text);
    group.visible = true;
    alpha = Math.max(alpha, 0.001); hold = Math.min(11, 3.5 + String(text).length / 26);
    setAlpha(alpha);
  }

  function update(dt) {
    if (!group.visible) return;
    if (alpha < 1 && hold > 0) alpha = Math.min(1, alpha + dt * 3);   // fade-in
    else { hold -= dt; if (hold <= 0) alpha = Math.max(0, alpha - dt * 1.4); }   // segura, depois fade-out
    setAlpha(alpha);
    if (alpha <= 0.001 && hold <= 0) group.visible = false;
  }

  function dispose() { parts.forEach((p) => { p.geometry?.dispose?.(); p.material?.map?.dispose?.(); p.material?.dispose?.(); }); tex.dispose(); }
  return { group, show, update, dispose };
}
