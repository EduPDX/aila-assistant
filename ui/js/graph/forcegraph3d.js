// ============================================================
//  ForceGraph3D — grafo em 3D (three.js) dentro de um CUBO wireframe
//  transparente. Nós = esferas coloridas por comunidade; arestas =
//  linhas na cor do nó de origem; layout force-directed em 3D. O mouse
//  ROTACIONA o cubo/grafo; auto-rotação leve. O cubo CRESCE com o grafo.
//  Interface compatível com ForceGraph (setData/select/setVisible/destroy)
//  p/ a aba 🧠 alternar 2D↔3D sem mudar o resto.
//  three.js é importado por caminho (vendorizado, same-origin → CSP ok).
// ============================================================
import * as THREE from '/static/vendor/three.module.js';

const PALETTE = [
  0x6ea8fe, 0xf0a35e, 0xe06c75, 0x57c7b8, 0x98c379, 0xe5c07b,
  0xc678dd, 0xf2809b, 0xb08d6a, 0xa8b0bd, 0x4d9be6, 0xd19a66,
  0x8fd3c5, 0x7ab8ff, 0xe88fb0, 0x9aa7ff,
];

export class ForceGraph3D {
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.opts = opts;
    this.nodes = []; this.links = [];
    this.byId = new Map();
    this.color = new Map();          // community(id) -> cor CSS (p/ o painel)
    this._colHex = new Map();        // community(id) -> THREE.Color
    this.visible = null;
    this.selected = null;
    this._nbr = new Set();
    this.alpha = 0;

    this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    this.renderer.setClearColor(0x000000, 0);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(55, 1, 0.1, 20000);
    this.camera.position.set(0, 0, 600);
    this.world = new THREE.Group();
    this.scene.add(this.world);
    this.rot = { x: -0.25, y: 0.5 };
    this.autoRot = true;

    this._resize();
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(canvas.parentElement || canvas);
    if (opts.interactive) this._bindEvents();
    this._loop();
  }

  colorOf(node) { return this.color.get(node.community) || '#8aa'; }

  // -------------------------------------------------------- dados
  setData(data) {
    this._clearMeshes();
    this.color.clear(); this._colHex.clear();
    (data.communities || []).forEach((c, i) => {
      const hex = PALETTE[i % PALETTE.length];
      this.color.set(c.id, '#' + hex.toString(16).padStart(6, '0'));
      this._colHex.set(c.id, new THREE.Color(hex));
    });
    const S = 260;
    this.nodes = (data.nodes || []).map((n) => ({
      ...n,
      x: (Math.random() - 0.5) * S, y: (Math.random() - 0.5) * S, z: (Math.random() - 0.5) * S,
      vx: 0, vy: 0, vz: 0, r: Math.max(3.4, Math.min(15, 3.4 + Math.sqrt(n.degree || 0) * 2.1)),
    }));
    this.byId = new Map(this.nodes.map((n) => [n.id, n]));
    this.links = (data.edges || []).map((e) => ({ s: this.byId.get(e.source), t: this.byId.get(e.target) }))
      .filter((l) => l.s && l.t);
    this._buildMeshes();
    this.selected = null; this._nbr.clear();
    this.alpha = 1;
  }

  _clearMeshes() {
    for (const m of [this._nodeMesh, this._edgeLines, this._cube]) {
      if (m) { this.world.remove(m); m.geometry?.dispose(); m.material?.dispose(); }
    }
    this._nodeMesh = this._edgeLines = this._cube = null;
  }

  _buildMeshes() {
    const N = this.nodes.length;
    // nós: esferas instanciadas, cor por comunidade, escala por grau
    const geo = new THREE.SphereGeometry(1, 10, 8);
    const mat = new THREE.MeshBasicMaterial({ transparent: true });
    this._nodeMesh = new THREE.InstancedMesh(geo, mat, N || 1);
    const dummy = new THREE.Object3D();
    const white = new THREE.Color(0xffffff);
    this.nodes.forEach((n, i) => {
      dummy.position.set(n.x, n.y, n.z); dummy.scale.setScalar(n.r); dummy.updateMatrix();
      this._nodeMesh.setMatrixAt(i, dummy.matrix);
      this._nodeMesh.setColorAt(i, this._colHex.get(n.community) || white);
    });
    this._nodeMesh.instanceMatrix.needsUpdate = true;
    if (this._nodeMesh.instanceColor) this._nodeMesh.instanceColor.needsUpdate = true;
    this.world.add(this._nodeMesh);

    // arestas: LineSegments com cor do nó de origem
    const pos = new Float32Array(this.links.length * 6);
    const col = new Float32Array(this.links.length * 6);
    this.links.forEach((l, i) => {
      const c = this._colHex.get(l.s.community) || white;
      col.set([c.r, c.g, c.b, c.r, c.g, c.b], i * 6);
    });
    const eg = new THREE.BufferGeometry();
    eg.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    eg.setAttribute('color', new THREE.BufferAttribute(col, 3));
    this._edgeLines = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({
      vertexColors: true, transparent: true, opacity: 0.32,
    }));
    this.world.add(this._edgeLines);

    // cubo wireframe (redimensionado no _fitCube)
    this._cubeMat = new THREE.LineBasicMaterial({ color: 0x7ab8ff, transparent: true, opacity: 0.18 });
    this._cubeSize = 0;
    this._fitCube(true);
  }

  _fitCube(force) {
    if (!this.nodes.length) return;
    let ext = 1;
    for (const n of this.nodes) ext = Math.max(ext, Math.abs(n.x), Math.abs(n.y), Math.abs(n.z));
    const size = Math.ceil((ext + 14) / 20) * 20 * 2;   // cubo cresce com o grafo (em degraus)
    if (!force && Math.abs(size - this._cubeSize) < this._cubeSize * 0.08) return;
    this._cubeSize = size;
    if (this._cube) { this.world.remove(this._cube); this._cube.geometry.dispose(); }
    this._cube = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(size, size, size)), this._cubeMat);
    this.world.add(this._cube);
    this.camera.position.z = size * 0.92;   // enquadra (cabe o cubo com folga)
  }

  setVisible(set) {
    this.visible = set;
    if (!this._nodeMesh) return;
    const dummy = new THREE.Object3D();
    this.nodes.forEach((n, i) => {
      const on = !set || set.has(n.community);
      dummy.position.set(n.x, n.y, n.z); dummy.scale.setScalar(on ? n.r : 0.0001); dummy.updateMatrix();
      this._nodeMesh.setMatrixAt(i, dummy.matrix);
    });
    this._nodeMesh.instanceMatrix.needsUpdate = true;
    this.kick(0.05);
  }

  // -------------------------------------------------------- física 3D
  kick(a = 1) { this.alpha = Math.max(this.alpha, a); }

  _tick() {
    const nodes = this.nodes, N = nodes.length; if (!N) return;
    const REP = 260, R = 84, SPRING = 0.05, LEN = 26, GRAV = 0.006, COMM = 0.05, DAMP = 0.85, CREP = 2.2e5;
    const a = this.alpha, cell = R;
    const grid = new Map();
    const key = (x, y, z) => x + ',' + y + ',' + z;
    for (const n of nodes) {
      const k = key(Math.floor(n.x / cell), Math.floor(n.y / cell), Math.floor(n.z / cell));
      let b = grid.get(k); if (!b) grid.set(k, b = []); b.push(n);
    }
    let cx = 0, cy = 0, cz = 0;
    const cc = new Map();
    for (const n of nodes) {
      cx += n.x; cy += n.y; cz += n.z;
      let o = cc.get(n.community); if (!o) cc.set(n.community, o = { x: 0, y: 0, z: 0, n: 0, fx: 0, fy: 0, fz: 0 });
      o.x += n.x; o.y += n.y; o.z += n.z; o.n++;
    }
    cx /= N; cy /= N; cz /= N;
    for (const o of cc.values()) { o.x /= o.n; o.y /= o.n; o.z /= o.n; }
    const cs = [...cc.values()];
    for (let i = 0; i < cs.length; i++) for (let j = i + 1; j < cs.length; j++) {
      const A = cs[i], B = cs[j];
      let dx = A.x - B.x, dy = A.y - B.y, dz = A.z - B.z, d2 = dx * dx + dy * dy + dz * dz || 1;
      const f = CREP / d2, d = Math.sqrt(d2); dx /= d; dy /= d; dz /= d;
      A.fx += dx * f; A.fy += dy * f; A.fz += dz * f; B.fx -= dx * f; B.fy -= dy * f; B.fz -= dz * f;
    }
    for (const n of nodes) {
      const gx = Math.floor(n.x / cell), gy = Math.floor(n.y / cell), gz = Math.floor(n.z / cell);
      for (let ix = -1; ix <= 1; ix++) for (let iy = -1; iy <= 1; iy++) for (let iz = -1; iz <= 1; iz++) {
        const b = grid.get(key(gx + ix, gy + iy, gz + iz)); if (!b) continue;
        for (const m of b) {
          if (m === n) continue;
          const dx = n.x - m.x, dy = n.y - m.y, dz = n.z - m.z, d2 = dx * dx + dy * dy + dz * dz;
          if (d2 > R * R || d2 === 0) continue;
          const d = Math.sqrt(d2), f = REP * (1 - d / R) / d * a;
          n.vx += dx * f; n.vy += dy * f; n.vz += dz * f;
        }
      }
      const o = cc.get(n.community);
      n.vx += (o.x - n.x) * COMM * a + o.fx * a + (cx - n.x) * GRAV * a;
      n.vy += (o.y - n.y) * COMM * a + o.fy * a + (cy - n.y) * GRAV * a;
      n.vz += (o.z - n.z) * COMM * a + o.fz * a + (cz - n.z) * GRAV * a;
    }
    for (const l of this.links) {
      let dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, dz = l.t.z - l.s.z;
      const d = Math.hypot(dx, dy, dz) || 0.01, f = (d - LEN) / d * SPRING * a;
      dx *= f; dy *= f; dz *= f;
      l.s.vx += dx; l.s.vy += dy; l.s.vz += dz; l.t.vx -= dx; l.t.vy -= dy; l.t.vz -= dz;
    }
    for (const n of nodes) {
      if (n.fixed) { n.vx = n.vy = n.vz = 0; continue; }
      n.x += n.vx *= DAMP; n.y += n.vy *= DAMP; n.z += n.vz *= DAMP;
    }
  }

  _sync() {
    if (!this._nodeMesh) return;
    const dummy = new THREE.Object3D();
    const vis = this.visible;
    this.nodes.forEach((n, i) => {
      const on = !vis || vis.has(n.community);
      const sel = n === this.selected;
      dummy.position.set(n.x, n.y, n.z);
      dummy.scale.setScalar(on ? n.r * (sel ? 1.8 : 1) : 0.0001);
      dummy.updateMatrix(); this._nodeMesh.setMatrixAt(i, dummy.matrix);
    });
    this._nodeMesh.instanceMatrix.needsUpdate = true;
    const p = this._edgeLines.geometry.getAttribute('position');
    this.links.forEach((l, i) => { p.setXYZ(i * 2, l.s.x, l.s.y, l.s.z); p.setXYZ(i * 2 + 1, l.t.x, l.t.y, l.t.z); });
    p.needsUpdate = true;
  }

  // -------------------------------------------------------- loop
  _loop() {
    const step = () => {
      const spin = localStorage.getItem('aila.graph.spin') === 'true';
      if (this.alpha > 0.02) { this._tick(); this.alpha *= 0.978; this._fitCube(false); }
      else if (spin) { this.alpha = 0.03; this._tick(); }
      this._sync();
      if (this.autoRot && !this._dragging) this.rot.y += 0.0016;
      this.world.rotation.x = this.rot.x; this.world.rotation.y = this.rot.y;
      this.renderer.render(this.scene, this.camera);
      this._raf = requestAnimationFrame(step);
    };
    step();
  }

  _resize() {
    const box = (this.canvas.parentElement || this.canvas).getBoundingClientRect();
    const w = Math.max(120, box.width), h = Math.max(120, box.height);
    this.renderer.setPixelRatio(window.devicePixelRatio || 1);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
  }

  // -------------------------------------------------------- interação
  select(node) {
    this.selected = node; this._nbr = new Set();
    const out = [];
    if (node) for (const l of this.links) {
      if (l.s === node) { this._nbr.add(l.t.id); out.push(l.t); }
      else if (l.t === node) { this._nbr.add(l.s.id); out.push(l.s); }
    }
    if (this.opts.onNode) this.opts.onNode(node, out);
  }
  selectById(id) { const n = this.byId.get(id); if (n) this.select(n); }

  _bindEvents() {
    const cv = this.canvas;
    let drag = null, moved = false;
    cv.style.cursor = 'grab';
    cv.addEventListener('mousedown', (e) => {
      const r = cv.getBoundingClientRect();
      drag = { px: e.clientX, py: e.clientY, rx: this.rot.x, ry: this.rot.y, cx: e.clientX - r.left, cy: e.clientY - r.top };
      moved = false; this._dragging = true; cv.style.cursor = 'grabbing';
    });
    window.addEventListener('mousemove', (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.px, dy = e.clientY - drag.py;
      if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
      this.rot.y = drag.ry + dx * 0.006;
      this.rot.x = Math.max(-1.4, Math.min(1.4, drag.rx + dy * 0.006));
    });
    window.addEventListener('mouseup', (e) => {
      if (drag && !moved) this._pick(drag.cx, drag.cy);
      drag = null; this._dragging = false; cv.style.cursor = 'grab';
    });
    cv.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.camera.position.z = Math.max(60, Math.min(6000, this.camera.position.z * (e.deltaY < 0 ? 0.9 : 1.11)));
    }, { passive: false });
  }

  _pick(px, py) {
    if (!this._nodeMesh) return;
    const rc = new THREE.Raycaster();
    rc.params.Points = { threshold: 6 };
    const box = (this.canvas.parentElement || this.canvas).getBoundingClientRect();
    const ndc = new THREE.Vector2((px / box.width) * 2 - 1, -(py / box.height) * 2 + 1);
    rc.setFromCamera(ndc, this.camera);
    const hit = rc.intersectObject(this._nodeMesh);
    if (hit.length && hit[0].instanceId != null) this.select(this.nodes[hit[0].instanceId]);
    else this.select(null);
  }

  destroy() {
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = null; this._ro?.disconnect();
    this._clearMeshes();
    this.renderer.dispose();
  }
}
