// ============================================================
//  RIG CORE — núcleo do sistema de animação em camadas.
//
//  Modelo (estilo AAA): cada camada ESCREVE num PoseBuffer (contribuições
//  aditivas por osso + pesos de blendshape + alvo de olhar). Nenhuma camada
//  toca o VRM. No fim do frame, commit() soma tudo e aplica no VRM.
//
//  - PoseBuffer: acumulador do frame (zera a cada frame, reusa objetos → 0 GC).
//  - Rig: referências do VRM (ossos em cache), o alvo de olhar e o commit final.
// ============================================================
import * as THREE from 'three';

export const DEG = Math.PI / 180;
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
// amortecimento independente de FPS (k por segundo)
export const damp = (cur, target, k, dt) => lerp(cur, target, 1 - Math.exp(-k * dt));

// ruído suave ~[-1,1]: soma de senoides incomensuráveis (não repete "na cara")
export function noise(t) {
  return (Math.sin(t) + Math.sin(t * 2.13 + 1.1) * 0.5 + Math.sin(t * 0.5 + 2.7) * 0.7) / 2.2;
}

// ------------------------------------------------------------------ //
//  PoseBuffer — o "quadro-negro" onde as camadas escrevem.
// ------------------------------------------------------------------ //
export class PoseBuffer {
  constructor() {
    this.rot = new Map();     // bone -> [x,y,z] (rad, ADITIVO no frame)
    this.expr = new Map();    // expressão -> valor 0..1 (último a escrever vence)
    this.gaze = { x: 0, y: 0, z: 0, active: false };  // alvo de olhar (mundo)
    this.ik = new Map();      // side('left'/'right') -> {x,y,z,weight} alvo da mão (mundo)
    this._w = 1;              // PESO da camada ATUAL (P5): o controller seta antes
                              // de cada layer.update; escala rot/expr/handTarget →
                              // uma camada inteira aparece/some sem "pop".
  }
  reset() {
    for (const v of this.rot.values()) { v[0] = 0; v[1] = 0; v[2] = 0; }
    this.expr.clear();
    this.gaze.active = false;
    this.ik.clear();
    this._w = 1;
  }
  /** define o alvo de mundo da MÃO (side='left'|'right'); o IK resolve o braço.
   *  orient (opcional) = {ref:'thumb'|'palm', dir:[x,y,z] mundo, weight} → o IK
   *  rola a mão p/ orientar (ex.: polegar pra cima, palma pra frente). */
  setHandTarget(side, x, y, z, weight = 1, orient = null) {
    this.ik.set(side, { x, y, z, weight: weight * this._w, orient });
  }
  /** soma rotação (rad) num osso — escalada pelo peso da camada atual (_w) */
  addRot(bone, x, y, z) {
    const w = this._w;
    let v = this.rot.get(bone);
    if (!v) { v = [0, 0, 0]; this.rot.set(bone, v); }
    v[0] += x * w; v[1] += y * w; v[2] += z * w;
  }
  /** soma rotação em GRAUS (conveniência) */
  addDeg(bone, x, y, z) { this.addRot(bone, x * DEG, y * DEG, z * DEG); }
  /** define peso de blendshape (0..1) — escalado pelo peso da camada atual */
  setExpr(name, value) { this.expr.set(name, value * this._w); }
  /** define o ponto que os olhos/corpo devem encarar (coordenadas de mundo) */
  setGaze(x, y, z) { this.gaze.x = x; this.gaze.y = y; this.gaze.z = z; this.gaze.active = true; }
}

// ------------------------------------------------------------------ //
//  Rig — encapsula o VRM: ossos em cache, alvo de olhar, commit final.
// ------------------------------------------------------------------ //
export class Rig {
  constructor(vrm, scene) {
    this.vrm = vrm;
    this.humanoid = vrm.humanoid;
    this.expr = vrm.expressionManager || null;
    this._bones = new Map();          // cache de nós (evita getNormalizedBoneNode/frame)
    this.buffer = new PoseBuffer();
    // alvo de olhar dos olhos (VRM lookAt): um Object3D na cena, movido a cada frame
    this.gazeTarget = new THREE.Object3D();
    scene.add(this.gazeTarget);
    try { if (vrm.lookAt) vrm.lookAt.target = this.gazeTarget; } catch (e) { /* modelo sem lookAt */ }
    this._v = new THREE.Vector3();    // reuso p/ math (0 GC)
  }

  bone(name) {
    let n = this._bones.get(name);
    if (n === undefined) { n = this.humanoid.getNormalizedBoneNode(name) || null; this._bones.set(name, n); }
    return n;
  }

  /** posição de mundo de um osso, sem alocar (grava em out) */
  boneWorld(name, out) {
    const n = this.bone(name);
    if (!n) return null;
    return out.setFromMatrixPosition(n.matrixWorld);
  }

  /** FASE 1 do commit: aplica as rotações FK dos ossos (do PoseBuffer). */
  applyBones() {
    for (const [name, v] of this.buffer.rot) {
      const n = this.bone(name);
      if (n) n.rotation.set(v[0], v[1], v[2]);
    }
  }

  /** atualiza as matrizes de mundo (necessário entre applyBones e os solvers
   *  que operam em posição, como o IK e a colisão). */
  updateMatrices() { this.vrm.scene.updateMatrixWorld(true); }

  /** FASE 2 do commit: blendshapes, alvo do olhar e física secundária. */
  finalize(dt) {
    const buf = this.buffer;
    if (this.expr) { for (const [name, value] of buf.expr) this.expr.setValue(name, value); }
    if (buf.gaze.active) this.gazeTarget.position.set(buf.gaze.x, buf.gaze.y, buf.gaze.z);
    this.vrm.update(dt);   // spring bones (cabelo/saia) + lookAt applier
  }
}
