// ============================================================
//  AVATAR DEBUG MODE (P0) — visualiza o esqueleto, alvos de IK, colliders de
//  auto-colisão, o alvo de LookAt e o estado ao vivo (emoção/gesto/estado/
//  camadas). DESLIGADO por padrão; liga com a tecla D, com ?debug=1 ou via
//  window.ailaDebug.toggle(). Não altera o pipeline de animação — só lê.
// ============================================================
import * as THREE from 'three';

export class AvatarDebug {
  constructor(scene, camera, overlayEl) {
    this.scene = scene;
    this.camera = camera;
    this.overlay = overlayEl || null;
    this.on = false;
    this.controller = null;
    this.skel = null;

    this.group = new THREE.Group();
    this.group.visible = false;
    scene.add(this.group);

    this._matGaze = new THREE.MeshBasicMaterial({ color: 0x35d0ba, wireframe: true, depthTest: false });
    this._matIk = new THREE.MeshBasicMaterial({ color: 0xffcc44, wireframe: true, depthTest: false });
    this._matCol = new THREE.MeshBasicMaterial({ color: 0xe06c75, wireframe: true, transparent: true, opacity: 0.45 });

    // alvo de LookAt (esfera pequena) + alvos de IK das mãos
    this._gaze = new THREE.Mesh(new THREE.SphereGeometry(0.02, 8, 6), this._matGaze);
    this.group.add(this._gaze);
    this._ik = { left: this._sphere(0.035, this._matIk), right: this._sphere(0.035, this._matIk) };

    this._colPool = [];          // esferas reusadas p/ desenhar os colliders
    this._unit = new THREE.SphereGeometry(1, 12, 8);   // esfera unitária (escala = raio)
  }

  _sphere(r, mat) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(r, 8, 6), mat);
    m.visible = false;
    this.group.add(m);
    return m;
  }

  /** liga ao controller atual e cria o SkeletonHelper do VRM carregado. */
  attach(controller) {
    this.controller = controller;
    if (this.skel) { this.scene.remove(this.skel); this.skel.dispose?.(); this.skel = null; }
    const root = controller?.rig?.vrm?.scene;
    if (root) {
      this.skel = new THREE.SkeletonHelper(root);
      this.skel.visible = this.on;
      this.scene.add(this.skel);
    }
  }

  toggle(force) {
    this.on = force === undefined ? !this.on : !!force;
    this.group.visible = this.on;
    if (this.skel) this.skel.visible = this.on;
    if (this.overlay) this.overlay.style.display = this.on ? 'block' : 'none';
    return this.on;
  }

  /** chamado a cada frame (barato quando desligado: retorna cedo). */
  update() {
    if (!this.on || !this.controller) return;
    const c = this.controller, rig = c.rig;

    // alvo de LookAt (olhos)
    this._gaze.position.copy(rig.gazeTarget.position);

    // alvos de IK das mãos
    for (const side of ['left', 'right']) {
      const t = rig.buffer.ik.get(side);
      const m = this._ik[side];
      if (t) { m.visible = true; m.position.set(t.x, t.y, t.z); } else { m.visible = false; }
    }

    // colliders da auto-colisão (reconstruídos sempre, mesmo sem gesto)
    const cols = c.collision?.colliders ? c.collision.colliders(rig) : [];
    this._syncColliders(cols);

    if (this.overlay) this.overlay.innerHTML = this._text(c);
  }

  _syncColliders(cols) {
    // cada collider = esfera(s) wireframe (raio real). Cápsula = 2 esferas nas
    // pontas (aproxima o volume; suficiente p/ inspeção).
    const need = cols.length * 2;
    while (this._colPool.length < need) {
      const s = new THREE.Mesh(this._unit, this._matCol);
      s.visible = false; this.group.add(s); this._colPool.push(s);
    }
    let i = 0;
    for (const col of cols) {
      const a = this._colPool[i++];
      a.visible = true; a.position.copy(col.a); a.scale.setScalar(col.r);
      const b = this._colPool[i++];
      if (col.type === 1) { b.visible = true; b.position.copy(col.b); b.scale.setScalar(col.r); }
      else { b.visible = false; }
    }
    for (; i < this._colPool.length; i++) this._colPool[i].visible = false;
  }

  _text(c) {
    const ctx = c.ctx;
    const layers = (c.layers || []).map((l) => l.name).join(' · ');
    const ik = [...c.rig.buffer.ik.keys()].join(', ') || '—';
    const anim = ctx.anim ? ctx.anim.type : '—';
    return '<b>AVATAR DEBUG</b> · tecla D p/ ligar/desligar'
      + `<br>estado: <b>${ctx.status}</b> · emoção: <b>${ctx.emotionKey}</b> · gesto: <b>${ctx.gesture}</b> · anim: ${anim}`
      + `<br>fala: ${ctx.speech.toFixed(2)} · olhar: ${ctx.gazeMode} · alvos IK: ${ik}`
      + `<br><span style="color:#35d0ba">●</span> lookAt &nbsp; <span style="color:#ffcc44">●</span> IK &nbsp; <span style="color:#e06c75">●</span> colliders`
      + `<br>camadas: ${layers}`;
  }
}
