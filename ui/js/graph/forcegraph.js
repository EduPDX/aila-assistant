// ============================================================
//  ForceGraph — renderizador de grafo force-directed em <canvas>,
//  VANILLA e self-contained (sem D3/CDN — CSP-safe, offline). Física
//  baseada em GRADE (repulsão só entre vizinhos próximos → O(n)), leve
//  o bastante p/ ~700 nós. Serve a aba 🧠 e o mini-subconsciente.
// ============================================================

// paleta de comunidades (colorida, estilo Graphify)
const PALETTE = [
  '#6ea8fe', '#f0a35e', '#e06c75', '#57c7b8', '#98c379', '#e5c07b',
  '#c678dd', '#f2809b', '#b08d6a', '#a8b0bd', '#4d9be6', '#d19a66',
  '#8fd3c5', '#7ab8ff', '#e88fb0', '#9aa7ff',
];

export class ForceGraph {
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.opts = opts;                      // { onNode, interactive, mini }
    this.nodes = [];
    this.links = [];
    this.byId = new Map();
    this.color = new Map();                // community -> cor
    this.visible = null;                   // Set de comunidades visíveis (null = todas)
    this.selected = null;
    this.pulse = null;                     // nó em destaque ("pensando")
    this.t = { x: 0, y: 0, k: 1 };          // pan/zoom
    this.alpha = 0;
    this._raf = null;
    this._ro = null;
    this._resize();
    if (opts.interactive) this._bindEvents();
    this._ro = new ResizeObserver(() => { this._resize(); this.kick(0.2); });
    this._ro.observe(canvas.parentElement || canvas);
    // preferências (cor das linhas / spin) mudaram → re-renderiza / re-anima
    this._onPref = () => this.kick(0.05);
    window.addEventListener('aila:pref', this._onPref);
  }

  // -------------------------------------------------------- dados
  setData(data) {
    const W = this.w || 800, H = this.h || 600;
    this.byId.clear();
    // cores por comunidade (ordem de count, já vem ordenada do backend)
    (data.communities || []).forEach((c, i) => this.color.set(c.id, PALETTE[i % PALETTE.length]));
    this.nodes = (data.nodes || []).map((n) => {
      const a = 2 * Math.PI * Math.random(), rr = Math.min(W, H) * 0.35 * Math.sqrt(Math.random());
      const node = {
        ...n, x: W / 2 + Math.cos(a) * rr, y: H / 2 + Math.sin(a) * rr, vx: 0, vy: 0,
        r: Math.max(2.5, Math.min(11, 2.5 + Math.sqrt(n.degree || 0) * 1.4)),
      };
      this.byId.set(n.id, node);
      return node;
    });
    this.links = (data.edges || []).map((e) => ({
      s: this.byId.get(e.source), t: this.byId.get(e.target), rel: e.relation,
    })).filter((l) => l.s && l.t);
    this.selected = null;
    this._fitted = false;
    this.fit();
    this.kick(1);
  }

  colorOf(node) { return this.color.get(node.community) || '#8aa'; }
  setVisible(set) { this.visible = set; this.draw(); }

  // -------------------------------------------------------- layout
  _resize() {
    const dpr = window.devicePixelRatio || 1;
    const box = (this.canvas.parentElement || this.canvas).getBoundingClientRect();
    this.w = Math.max(120, box.width); this.h = Math.max(120, box.height);
    this.canvas.width = this.w * dpr; this.canvas.height = this.h * dpr;
    this.canvas.style.width = this.w + 'px'; this.canvas.style.height = this.h + 'px';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  /** centraliza/enquadra o grafo na viewport */
  fit() {
    if (!this.nodes.length) return;
    let minx = 1e9, miny = 1e9, maxx = -1e9, maxy = -1e9;
    for (const n of this.nodes) { minx = Math.min(minx, n.x); miny = Math.min(miny, n.y); maxx = Math.max(maxx, n.x); maxy = Math.max(maxy, n.y); }
    const gw = maxx - minx || 1, gh = maxy - miny || 1;
    const k = Math.min(this.w / gw, this.h / gh) * 0.82;
    this.t.k = Math.max(0.05, Math.min(4, k));
    this.t.x = this.w / 2 - (minx + gw / 2) * this.t.k;
    this.t.y = this.h / 2 - (miny + gh / 2) * this.t.k;
  }

  kick(a = 1) { this.alpha = Math.max(this.alpha, a); if (!this._raf) this._loop(); }

  _loop() {
    const step = () => {
      let active = false;
      if (this.alpha > 0.02) { this._tick(); this.alpha *= 0.975; active = true; }
      else if (this.opts.mini) { this.alpha = 0.06; this._tick(); active = true; }  // mini nunca congela
      else if (localStorage.getItem('aila.graph.spin') === 'true') { this.alpha = 0.03; this._tick(); active = true; }  // movimento contínuo
      else if (!this._fitted) { this.fit(); this._fitted = true; }   // assentou → reenquadra 1x
      if (this.opts.mini && (((this._frame = (this._frame || 0) + 1)) % 12 === 0)) this.fit();  // mini: sempre enquadrado
      this.draw();
      this._raf = active ? requestAnimationFrame(step) : null;   // assentou → para (economiza CPU)
    };
    step();
  }

  _tick() {
    const nodes = this.nodes, N = nodes.length;
    if (!N) return;
    const mini = this.opts.mini;
    const REP = 220, R = 78, SPRING = 0.06, LEN = mini ? 14 : 24, GRAV = mini ? 0.02 : 0.004,
      COMM = 0.06, DAMP = 0.85, CREP = mini ? 0 : 32000;   // mini: blob compacto, sem explodir comunidades
    const a = this.alpha;
    // grade espacial p/ repulsão local (O(n))
    const cell = R, grid = new Map();
    const key = (cx, cy) => cx + ',' + cy;
    for (const n of nodes) {
      const gx = Math.floor(n.x / cell), gy = Math.floor(n.y / cell), k = key(gx, gy);
      let b = grid.get(k); if (!b) grid.set(k, b = []); b.push(n);
    }
    // centro global + centroides por comunidade (→ agrupamento estilo Graphify)
    let cx = 0, cy = 0;
    const cc = new Map();
    for (const n of nodes) {
      cx += n.x; cy += n.y;
      let o = cc.get(n.community); if (!o) cc.set(n.community, o = { x: 0, y: 0, n: 0 });
      o.x += n.x; o.y += n.y; o.n++;
    }
    cx /= N; cy /= N;
    for (const o of cc.values()) { o.x /= o.n; o.y /= o.n; o.fx = 0; o.fy = 0; }
    // repulsão ENTRE centroides → comunidades viram lóbulos distintos (Graphify)
    const cs = [...cc.values()];
    for (let i = 0; i < cs.length; i++) for (let j = i + 1; j < cs.length; j++) {
      const A = cs[i], B = cs[j];
      let dx = A.x - B.x, dy = A.y - B.y, d2 = dx * dx + dy * dy || 1;
      const f = CREP / d2, d = Math.sqrt(d2);
      dx /= d; dy /= d;
      A.fx += dx * f; A.fy += dy * f; B.fx -= dx * f; B.fy -= dy * f;
    }
    for (const n of nodes) {
      const gx = Math.floor(n.x / cell), gy = Math.floor(n.y / cell);
      for (let ix = -1; ix <= 1; ix++) for (let iy = -1; iy <= 1; iy++) {
        const bucket = grid.get(key(gx + ix, gy + iy)); if (!bucket) continue;
        for (const m of bucket) {
          if (m === n) continue;
          const dx = n.x - m.x, dy = n.y - m.y, d2 = dx * dx + dy * dy;
          if (d2 > R * R || d2 === 0) continue;
          const d = Math.sqrt(d2), f = REP * (1 - d / R) / d * a;
          n.vx += dx * f; n.vy += dy * f;
        }
      }
      const o = cc.get(n.community);
      n.vx += (o.x - n.x) * COMM * a; n.vy += (o.y - n.y) * COMM * a;   // coesão da comunidade
      n.vx += o.fx * a; n.vy += o.fy * a;                               // separação entre comunidades
      n.vx += (cx - n.x) * GRAV * a; n.vy += (cy - n.y) * GRAV * a;     // gravidade global
    }
    for (const l of this.links) {
      let dx = l.t.x - l.s.x, dy = l.t.y - l.s.y;
      const d = Math.hypot(dx, dy) || 0.01, f = (d - LEN) / d * SPRING * a;
      dx *= f; dy *= f;
      l.s.vx += dx; l.s.vy += dy; l.t.vx -= dx; l.t.vy -= dy;
    }
    for (const n of nodes) {
      if (n.fixed) { n.vx = n.vy = 0; continue; }
      n.x += n.vx = n.vx * DAMP; n.y += n.vy = n.vy * DAMP;
    }
  }

  // -------------------------------------------------------- render
  draw() {
    const ctx = this.ctx, { x, y, k } = this.t;
    ctx.clearRect(0, 0, this.w, this.h);
    ctx.save(); ctx.translate(x, y); ctx.scale(k, k);
    const vis = this.visible;
    const shown = (n) => !vis || vis.has(n.community);
    // arestas — coloridas (cor do nó de origem) ou cinza, conforme preferência
    const colored = (localStorage.getItem('aila.graph.edges') || 'coloridas') !== 'cinza';
    ctx.lineWidth = 0.6 / k;
    for (const l of this.links) {
      if (!shown(l.s) || !shown(l.t)) continue;
      const hot = this.selected && (l.s === this.selected || l.t === this.selected);
      if (hot) { ctx.globalAlpha = 0.7; ctx.strokeStyle = '#8fd0ff'; }
      else if (colored) { ctx.globalAlpha = this.selected ? 0.12 : 0.24; ctx.strokeStyle = this.colorOf(l.s); }
      else { ctx.globalAlpha = 1; ctx.strokeStyle = 'rgba(150,170,200,.14)'; }
      ctx.beginPath(); ctx.moveTo(l.s.x, l.s.y); ctx.lineTo(l.t.x, l.t.y); ctx.stroke();
    }
    ctx.globalAlpha = 1;
    // nós
    for (const n of this.nodes) {
      if (!shown(n)) continue;
      const sel = n === this.selected, pul = n === this.pulse;
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r + (pul ? 2 : 0), 0, 6.2832);
      ctx.fillStyle = this.colorOf(n);
      ctx.globalAlpha = (this.selected && !sel && !this._isNeighbor(n)) ? 0.35 : 1;
      ctx.fill();
      if (sel || pul) { ctx.globalAlpha = 1; ctx.lineWidth = 1.5 / k; ctx.strokeStyle = '#eaf2ff'; ctx.stroke(); }
      ctx.globalAlpha = 1;
    }
    // rótulo do selecionado
    if (this.selected) {
      const n = this.selected;
      ctx.fillStyle = '#eaf2ff'; ctx.font = `${12 / k}px ui-monospace, monospace`;
      ctx.fillText(n.label, n.x + n.r + 3 / k, n.y + 3 / k);
    }
    ctx.restore();
  }

  _isNeighbor(n) {
    if (!this.selected || !this._nbr) return false;
    return this._nbr.has(n.id);
  }

  // -------------------------------------------------------- interação
  select(node) {
    this.selected = node;
    this._nbr = new Set();
    if (node) for (const l of this.links) {
      if (l.s === node) this._nbr.add(l.t.id);
      if (l.t === node) this._nbr.add(l.s.id);
    }
    this.draw();
    if (this.opts.onNode) this.opts.onNode(node, node ? this._neighborList(node) : []);
  }

  _neighborList(node) {
    const out = [];
    for (const l of this.links) {
      if (l.s === node) out.push(l.t);
      else if (l.t === node) out.push(l.s);
    }
    return out;
  }

  selectById(id) { const n = this.byId.get(id); if (n) { this.center(n); this.select(n); } }

  center(n) { this.t.x = this.w / 2 - n.x * this.t.k; this.t.y = this.h / 2 - n.y * this.t.k; }

  _at(px, py) {
    const wx = (px - this.t.x) / this.t.k, wy = (py - this.t.y) / this.t.k;
    let best = null, bd = 12 / this.t.k;
    for (const n of this.nodes) {
      if (this.visible && !this.visible.has(n.community)) continue;
      const d = Math.hypot(n.x - wx, n.y - wy);
      if (d < Math.max(bd, n.r + 3) && (!best || d < best._d)) { best = n; best._d = d; }
    }
    return best;
  }

  _bindEvents() {
    const cv = this.canvas;
    const dragOn = () => (localStorage.getItem('aila.graph.drag') ?? 'true') !== 'false';
    let drag = null, moved = false, node = null, moveNode = false;
    cv.addEventListener('mousedown', (e) => {
      const r = cv.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top;
      node = this._at(px, py); moved = false;
      moveNode = !!node && dragOn();               // só ARRASTA o nó se a pref permitir
      drag = { px, py, tx: this.t.x, ty: this.t.y, nx: node?.x, ny: node?.y };
      if (moveNode) node.fixed = true;
    });
    window.addEventListener('mousemove', (e) => {
      if (!drag) return;
      const r = cv.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top;
      if (Math.abs(px - drag.px) + Math.abs(py - drag.py) > 3) moved = true;
      if (moveNode) {
        // move SÓ o nó arrastado, sem re-aquecer a simulação → o resto NÃO treme
        node.x = drag.nx + (px - drag.px) / this.t.k; node.y = drag.ny + (py - drag.py) / this.t.k;
        this.draw();
      } else {
        this.t.x = drag.tx + (px - drag.px); this.t.y = drag.ty + (py - drag.py); this.draw();
      }
    });
    window.addEventListener('mouseup', () => {
      if (moveNode && node) node.fixed = false;
      if (drag && node && !moved) this.select(node);
      else if (drag && !node && !moved) this.select(null);
      drag = null; node = null; moveNode = false;
    });
    cv.addEventListener('wheel', (e) => {
      e.preventDefault();
      const r = cv.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top;
      const f = e.deltaY < 0 ? 1.12 : 1 / 1.12, k2 = Math.max(0.05, Math.min(6, this.t.k * f));
      this.t.x = px - (px - this.t.x) * (k2 / this.t.k);
      this.t.y = py - (py - this.t.y) * (k2 / this.t.k);
      this.t.k = k2; this.draw();
    }, { passive: false });
    cv.style.cursor = 'grab';
  }

  /** "pensamento": destaca um nó aleatório por um instante (usado no mini) */
  think() {
    if (!this.nodes.length) return;
    this.pulse = this.nodes[(Math.random() * this.nodes.length) | 0];
    this.kick(0.15);
    clearTimeout(this._pt);
    this._pt = setTimeout(() => { this.pulse = null; }, 1400);
  }

  destroy() {
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = null; this._ro?.disconnect();
    if (this._onPref) window.removeEventListener('aila:pref', this._onPref);
    clearTimeout(this._pt);
  }
}
