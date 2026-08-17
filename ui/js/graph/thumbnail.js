// Miniatura ESTÁTICA de um grafo (para a grade de Projetos). Faz um layout
// force-directed rápido e SÍNCRONO numa amostra (top-grau), desenha num canvas
// 2D e devolve um dataURL. Nada de WebGL — dá pra ter dezenas na grade sem
// estourar contextos. Uma moldura de cubo isométrico ecoa a estética 3D.
import { PALETTE } from './forcegraph.js';

export function graphThumbnail(data, size = 156) {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const cv = document.createElement('canvas');
  cv.width = cv.height = size * dpr;
  const ctx = cv.getContext('2d');
  ctx.scale(dpr, dpr);

  // amostra: os nós de maior grau (a forma do aglomerado já aparece)
  let nodes = (data.nodes || []).slice().sort((a, b) => (b.degree || 0) - (a.degree || 0));
  const N = Math.min(nodes.length, 220);
  nodes = nodes.slice(0, N);
  const idx = new Map(nodes.map((n, i) => [n.id, i]));
  const links = (data.edges || [])
    .filter((e) => idx.has(e.source) && idx.has(e.target))
    .map((e) => [idx.get(e.source), idx.get(e.target)]);
  const col = new Map();
  (data.communities || []).forEach((c, i) => col.set(c.id, PALETTE[i % PALETTE.length]));

  drawCube(ctx, size);
  if (!N) return cv.toDataURL('image/png');

  // ---- layout: repulsão O(n²) (n≤220), molas nas arestas, gravidade central
  const P = nodes.map(() => ({ x: (Math.random() - 0.5) * size * 0.5, y: (Math.random() - 0.5) * size * 0.5, vx: 0, vy: 0 }));
  for (let it = 0; it < 130; it++) {
    for (let i = 0; i < N; i++) {
      for (let j = i + 1; j < N; j++) {
        let dx = P[i].x - P[j].x, dy = P[i].y - P[j].y;
        const d2 = dx * dx + dy * dy || 0.01, d = Math.sqrt(d2), f = 160 / d2;
        dx = dx / d * f; dy = dy / d * f;
        P[i].vx += dx; P[i].vy += dy; P[j].vx -= dx; P[j].vy -= dy;
      }
    }
    for (const [a, b] of links) {
      let dx = P[b].x - P[a].x, dy = P[b].y - P[a].y;
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01, f = (d - 16) * 0.02;
      dx = dx / d * f; dy = dy / d * f;
      P[a].vx += dx; P[a].vy += dy; P[b].vx -= dx; P[b].vy -= dy;
    }
    for (let i = 0; i < N; i++) {
      P[i].vx -= P[i].x * 0.009; P[i].vy -= P[i].y * 0.009;
      P[i].x += P[i].vx * 0.85; P[i].y += P[i].vy * 0.85;
      P[i].vx *= 0.8; P[i].vy *= 0.8;
    }
  }

  // enquadra
  let maxr = 1;
  for (const p of P) maxr = Math.max(maxr, Math.abs(p.x), Math.abs(p.y));
  const s = (size * 0.36) / maxr, cx = size / 2, cy = size / 2;
  const X = (i) => cx + P[i].x * s, Y = (i) => cy + P[i].y * s;

  ctx.globalAlpha = 0.22; ctx.lineWidth = 0.6;
  for (const [a, b] of links) {
    ctx.strokeStyle = col.get(nodes[a].community) || '#8aa';
    ctx.beginPath(); ctx.moveTo(X(a), Y(a)); ctx.lineTo(X(b), Y(b)); ctx.stroke();
  }
  ctx.globalAlpha = 1;
  for (let i = 0; i < N; i++) {
    const r = Math.max(1.2, Math.min(4, 1.2 + Math.sqrt(nodes[i].degree || 0) * 0.5));
    ctx.fillStyle = col.get(nodes[i].community) || '#8aa';
    ctx.beginPath(); ctx.arc(X(i), Y(i), r, 0, 7); ctx.fill();
  }
  return cv.toDataURL('image/png');
}

// moldura de cubo isométrico (leve) — só decorativa, ecoa o cubo wireframe 3D
function drawCube(ctx, size) {
  const m = size * 0.1, h = size - m, off = size * 0.14;
  const F = [[m, m], [h, m], [h, h], [m, h]];                 // frente
  const B = F.map(([x, y]) => [x + off, y - off]);            // trás
  ctx.strokeStyle = 'rgba(122,184,255,0.16)'; ctx.lineWidth = 1;
  const poly = (p) => { ctx.beginPath(); p.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.closePath(); ctx.stroke(); };
  poly(B); poly(F);
  for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.moveTo(F[i][0], F[i][1]); ctx.lineTo(B[i][0], B[i][1]); ctx.stroke(); }
}
