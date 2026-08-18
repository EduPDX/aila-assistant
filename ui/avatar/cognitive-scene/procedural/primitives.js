// ============================================================
//  PRIMITIVES — helpers procedurais compartilhados da Cognitive Scene.
//  Estética: holográfica/HUD (teal + azul), aditiva, limpa. Sem texturas
//  externas, sem GC no loop (geometria/material criados 1x e reusados).
//  Tudo em METROS (mesma escala do VRM: chão y=0, avatar ~1.5m).
// ============================================================
import * as THREE from 'three';

export const HOLO = {
  teal: 0x35d0ba,     // acento principal (mesmo do app)
  blue: 0x7ab8ff,     // linhas/dados
  amber: 0xf0a35e,    // destaque/atenção
  dim: 0x1b3a66,      // vidro/preenchimento sutil
  text: '#bfe9e2',    // texto na CanvasTexture
};

/** material de LINHA holográfica (aditivo, brilho sem bloom). */
export function lineMat(color = HOLO.teal, opacity = 0.6) {
  return new THREE.LineBasicMaterial({
    color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false,
  });
}

/** material de PREENCHIMENTO translúcido (vidro/painel). */
export function fillMat(color = HOLO.dim, opacity = 0.14) {
  return new THREE.MeshBasicMaterial({
    color, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false,
  });
}

/** material EMISSIVO aditivo (borda/indicador que "brilha"). */
export function glowMat(color = HOLO.teal, opacity = 0.85) {
  return new THREE.MeshBasicMaterial({
    color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false,
  });
}

/** retângulo só de BORDAS (moldura) a partir de w×h no plano XY. */
export function frameLines(w, h, mat) {
  const x = w / 2, y = h / 2;
  const g = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-x, -y, 0), new THREE.Vector3(x, -y, 0),
    new THREE.Vector3(x, y, 0), new THREE.Vector3(-x, y, 0), new THREE.Vector3(-x, -y, 0),
  ]);
  return new THREE.Line(g, mat);
}

/** GRID no plano XY (linhas finas), como LineSegments — 1 draw call. */
export function grid(w, h, cols, rows, mat) {
  const pts = [];
  for (let i = 0; i <= cols; i++) { const x = -w / 2 + (w * i) / cols; pts.push(x, -h / 2, 0, x, h / 2, 0); }
  for (let j = 0; j <= rows; j++) { const y = -h / 2 + (h * j) / rows; pts.push(-w / 2, y, 0, w / 2, y, 0); }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  return new THREE.LineSegments(g, mat);
}

/** CANTOS em L estilo HUD nos 4 vértices de um retângulo w×h. */
export function corners(w, h, L, mat) {
  const x = w / 2, y = h / 2, pts = [];
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
    const cx = sx * x, cy = sy * y;
    pts.push(cx, cy, 0, cx - sx * L, cy, 0);
    pts.push(cx, cy, 0, cx, cy - sy * L, 0);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  return new THREE.LineSegments(g, mat);
}

/** TEXTO como plano com CanvasTexture (cacheada). Devolve {mesh, texture}.
 *  Barato: desenha 1x num canvas 2D e usa como mapa aditivo. Não recriar por frame. */
export function textPlane(text, { width = 1, px = 256, align = 'left', color = HOLO.text, size = 40, font = 'ui-monospace, monospace' } = {}) {
  const cv = document.createElement('canvas');
  const ratio = 0.25;                          // altura relativa do canvas
  cv.width = px; cv.height = Math.round(px * ratio);
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.fillStyle = color;
  ctx.textBaseline = 'middle';
  ctx.textAlign = align;
  // auto-encolhe a fonte p/ o texto CABER na largura (fim do título cortado)
  const maxW = cv.width - 16;
  let fs = size;
  ctx.font = `${fs}px ${font}`;
  const w = ctx.measureText(text).width;
  if (w > maxW) { fs = Math.max(9, Math.floor(size * maxW / w)); ctx.font = `${fs}px ${font}`; }
  const tx = align === 'center' ? cv.width / 2 : align === 'right' ? cv.width - 8 : 8;
  ctx.fillText(text, tx, cv.height / 2);
  const tex = new THREE.CanvasTexture(cv);
  tex.minFilter = THREE.LinearFilter;
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
  const geo = new THREE.PlaneGeometry(width, width * ratio);
  const mesh = new THREE.Mesh(geo, mat);
  mesh.userData._tex = tex;
  return { mesh, texture: tex, canvas: cv };
}

/** libera geometrias/materiais/texturas de um Object3D (evita vazamento). */
export function disposeObject(obj) {
  obj.traverse((o) => {
    o.geometry?.dispose?.();
    const m = o.material;
    if (Array.isArray(m)) m.forEach((x) => { x.map?.dispose?.(); x.dispose?.(); });
    else if (m) { m.map?.dispose?.(); m.dispose?.(); }
    o.userData?._tex?.dispose?.();
  });
}
