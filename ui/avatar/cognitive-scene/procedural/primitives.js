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
  amber: 0xffb15e,    // destaque/atenção (mais claro p/ ler no escuro)
  dim: 0x1b3a66,      // vidro/preenchimento sutil
  text: '#dff3ee',    // texto principal (claro, alto contraste)
  textDim: '#9fd0c6',   // texto secundário (ainda legível, nunca "preto")
  amberText: '#ffcf9a', // texto de atenção
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

/** TEXTO como plano com CanvasTexture (cacheada). Devolve {mesh, setText}.
 *  Barato: desenha num canvas 2D e usa como mapa aditivo. setText redesenha só
 *  quando o valor muda (não recriar por frame — atualizar em baixa frequência). */
export function textPlane(text, { width = 1, px = 256, align = 'left', color = HOLO.text, size = 40, font = 'ui-monospace, monospace' } = {}) {
  const cv = document.createElement('canvas');
  const ratio = 0.25;                          // altura relativa do canvas
  cv.width = px; cv.height = Math.round(px * ratio);
  const ctx = cv.getContext('2d');
  const tex = new THREE.CanvasTexture(cv);
  tex.minFilter = THREE.LinearFilter;
  const tx = align === 'center' ? cv.width / 2 : align === 'right' ? cv.width - 8 : 8;
  const maxW = cv.width - 16;
  let _last = null;
  function draw(str) {
    if (str === _last) return; _last = str;
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.fillStyle = color; ctx.textBaseline = 'middle'; ctx.textAlign = align;
    let fs = size; ctx.font = `${fs}px ${font}`;
    const w = ctx.measureText(str).width;         // auto-encolhe p/ caber
    if (w > maxW) { fs = Math.max(9, Math.floor(size * maxW / w)); ctx.font = `${fs}px ${font}`; }
    ctx.fillText(str, tx, cv.height / 2);
    tex.needsUpdate = true;
  }
  draw(text);
  // TEXTO com blending NORMAL (não aditivo): fica CROCANTE e legível no fundo
  // escuro — o aditivo lavava a cor (o "texto quase preto" que o usuário viu).
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, width * ratio), mat);
  mesh.userData._tex = tex;
  return { mesh, texture: tex, canvas: cv, setText: draw };
}

/** GRÁFICO DE LINHA atualizável (waveform). set(fn) reescreve os Y (0 GC). */
export function lineGraph(w, h, n, mat) {
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { pos[i * 3] = -w / 2 + (w * i) / (n - 1); }
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const line = new THREE.Line(geo, mat);
  const set = (fn) => { for (let i = 0; i < n; i++) pos[i * 3 + 1] = (fn(i / (n - 1)) - 0.5) * h; geo.attributes.position.needsUpdate = true; };
  return { line, set, n };
}

/** MEDIDOR DE BARRAS (algumas barras verticais). set(arr 0..1) escala a altura.
 *  Geometria compartilhada ancorada na base → escala em Y só estica pra cima. */
export function barMeter(count, w, h, mat) {
  const g = new THREE.Group();
  const bw = (w / count) * 0.55;
  const geo = new THREE.PlaneGeometry(bw, h); geo.translate(0, h / 2, 0);   // base na origem
  const bars = [];
  for (let i = 0; i < count; i++) {
    const m = new THREE.Mesh(geo, mat);
    m.position.x = -w / 2 + (i + 0.5) * (w / count);
    m.position.y = -h / 2;
    g.add(m); bars.push(m);
  }
  const set = (arr) => bars.forEach((m, i) => { m.scale.y = Math.max(0.02, arr[i] || 0); });
  return { group: g, set };
}

/** DATA STREAM — várias linhas de "log" monoespaçado que ROLAM (as de cima mais
 *  fracas). Barato: setText só na mudança + poucas linhas. */
export function dataStream(nRows, w, { color = HOLO.textDim, size = 28, rowH = 0.058, hz = 1.6 } = {}) {
  const g = new THREE.Group();
  const rows = [];
  for (let i = 0; i < nRows; i++) {
    const tp = textPlane('', { width: w, px: 640, size, align: 'left', color });
    tp.mesh.position.y = -i * rowH;
    tp.mesh.material.opacity = 0.35 + 0.65 * (i / (nRows - 1));   // topo mais fraco (efeito de rolagem)
    g.add(tp.mesh); rows.push(tp);
  }
  const texts = new Array(nRows).fill('');
  const setLines = (values = []) => {
    const clean = values.slice(-nRows).map((v) => String(v || '').slice(0, 54));
    while (clean.length < nRows) clean.unshift('');
    for (let i = 0; i < nRows; i++) {
      texts[i] = clean[i];
      rows[i].setText(clean[i]);
    }
  };
  return { group: g, update() {}, setLines };
}

/** BARRA horizontal (fundo + preenchimento). set(0..1) escala o preenchimento. */
export function hbar(w, h, fillColor = HOLO.teal, bgColor = HOLO.blue) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.PlaneGeometry(w, h), fillMat(bgColor, 0.14)));
  const fill = new THREE.Mesh(new THREE.PlaneGeometry(w, h), glowMat(fillColor, 0.85));
  fill.position.z = 0.001; g.add(fill);
  const set = (v) => { const c = Math.max(0, Math.min(1, v)); fill.scale.x = c || 1e-3; fill.position.x = -w / 2 + (w * c) / 2; };
  set(0);
  return { group: g, set };
}

/** MINI-GRAFO de nós (pontos + arestas de vizinhança) com jitter sutil. */
export function nodeCluster(nCount, radius, ptMat, lnMat) {
  const g = new THREE.Group();
  const base = [];
  for (let i = 0; i < nCount; i++) base.push(new THREE.Vector3((Math.random() - 0.5) * radius * 2, (Math.random() - 0.5) * radius * 2, 0));
  const pgeo = new THREE.BufferGeometry().setFromPoints(base.map((v) => v.clone()));
  const points = new THREE.Points(pgeo, ptMat);
  const ep = [];
  for (let i = 0; i < nCount; i++) for (let j = i + 1; j < nCount; j++) if (base[i].distanceTo(base[j]) < radius * 0.85) ep.push(base[i].x, base[i].y, 0.001, base[j].x, base[j].y, 0.001);
  const egeo = new THREE.BufferGeometry(); egeo.setAttribute('position', new THREE.Float32BufferAttribute(ep, 3));
  g.add(new THREE.LineSegments(egeo, lnMat)); g.add(points);
  const a = pgeo.attributes.position;
  const update = (t) => {
    for (let i = 0; i < nCount; i++) a.setXY(i, base[i].x + Math.sin(t * 1.3 + i) * radius * 0.04, base[i].y + Math.cos(t * 1.1 + i * 1.7) * radius * 0.04);
    a.needsUpdate = true;
  };
  return { group: g, update };
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
