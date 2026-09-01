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
import { createRigProfile } from './rig-profile.js';

const _poseEuler = new THREE.Euler(0, 0, 0, 'XYZ');

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
    this._restQ = new Map();          // rotação LOCAL de repouso dos normalized bones
    this.buffer = new PoseBuffer();
    // alvo de olhar dos olhos (VRM lookAt): um Object3D na cena, movido a cada frame
    this.gazeTarget = new THREE.Object3D();
    scene.add(this.gazeTarget);
    try { if (vrm.lookAt) vrm.lookAt.target = this.gazeTarget; } catch (e) { /* modelo sem lookAt */ }
    this._v = new THREE.Vector3();    // reuso p/ math (0 GC)
    this._qDelta = new THREE.Quaternion();
    this.profile = createRigProfile(vrm);
    this._captureRestPose();
    // sinal de rotação dos braços, MEDIDO no modelo (ver calibrateArms)
    this.armZSign = 1;
    try { this.calibrateArms(); } catch (e) { /* modelo atípico: mantém 1 */ }
  }

  /** Congela a pose-base normalizada antes que qualquer camada/clip a altere.
   *  Em VRM 1 ela é a referência canônica para toda pose relativa. */
  _captureRestPose() {
    const rest = this.humanoid.normalizedRestPose || {};
    for (const name of Object.keys(this.humanoid.normalizedHumanBones || {})) {
      const node = this.bone(name);
      if (!node) continue;
      const rotation = rest[name]?.rotation;
      this._restQ.set(name, rotation
        ? new THREE.Quaternion().fromArray(rotation)
        : node.quaternion.clone());
    }
  }

  restQuaternion(name) {
    let q = this._restQ.get(name);
    if (!q) {
      const node = this.bone(name);
      q = node ? node.quaternion.clone() : new THREE.Quaternion();
      this._restQ.set(name, q);
    }
    return q;
  }

  /** Calibra os braços MEDINDO o modelo (roda 1x, no load).
   *
   *  As poses não podem ser ângulos fixos: cada VRM tem sua convenção. Aqui
   *  varremos os três eixos LOCAIS, relativos à pose-base, e escolhemos o que
   *  oferece a maior faixa vertical sem cruzar o corpo. Isso evita assumir Z
   *  e mantém compatibilidade com modelos VRM 1 exportados por ferramentas
   *  diferentes. Anotamos qual valor deixa a mão mais
   *  ALTA e qual a deixa mais BAIXA — descartando os que cruzam o corpo (foi
   *  isso que fazia a mão direita ir para o lado esquerdo).
   *
   *  Resultado: ``rig.armZ[side] = {up, down}`` em graus, e ``armZSign`` (compat
   *  para os ossos menores). Poses passam a ser ELEVAÇÃO (-1 abaixado .. +1
   *  erguido) e viram graus por :meth:`armAngle`. */
  calibrateArms() {
    const out = {};
    const axes = [
      new THREE.Vector3(1, 0, 0),
      new THREE.Vector3(0, 1, 0),
      new THREE.Vector3(0, 0, 1),
    ];
    const qDelta = new THREE.Quaternion();
    for (const side of ['left', 'right']) {
      const up = this.bone(side + 'UpperArm'), hand = this.bone(side + 'Hand');
      if (!up || !hand) continue;
      const keep = up.quaternion.clone();
      const rest = this.restQuaternion(side + 'UpperArm');
      this.vrm.scene.updateMatrixWorld(true);
      const ladoDoOmbro = Math.sign(up.matrixWorld.elements[12]) || 1;
      let best = null;
      for (let ai = 0; ai < axes.length; ai++) {
        let upA = 0, upY = -1e9, downA = 0, downY = 1e9, valid = 0;
        for (let d = -150; d <= 150; d += 5) {
          qDelta.setFromAxisAngle(axes[ai], d * DEG);
          // three-vrm define pose relativa como: delta * rest.
          up.quaternion.copy(qDelta).multiply(rest);
          this.vrm.scene.updateMatrixWorld(true);
          const hx = hand.matrixWorld.elements[12], hy = hand.matrixWorld.elements[13];
          if (Math.abs(hx) > 0.03 && Math.sign(hx) !== ladoDoOmbro) continue;
          valid++;
          if (hy > upY) { upY = hy; upA = d; }
          if (hy < downY) { downY = hy; downA = d; }
        }
        const span = upY - downY;
        if (valid > 4 && (!best || span > best.span)) best = { axis: ai, up: upA, down: downA, span };
      }
      up.quaternion.copy(keep);
      if (best) out[side] = best;
    }
    this.vrm.scene.updateMatrixWorld(true);
    this.armCalibration = out;
    this.armZ = out; // alias temporário para solvers/debug antigos
    // compat (ossos menores, ex.: antebraço): sinal de "para baixo" no braço esq.
    // O rig normalizado do VRM 1 já possui convenção estável. O espelhamento
    // legado do antebraço só é necessário para alguns exports VRM 0.
    this.armZSign = this.profile.version === '0' && out.left && out.left.axis === 2 && out.left.down > 0 ? -1 : 1;
  }

  /** Elevação (-1 abaixado .. 0 na horizontal .. +1 erguido) → graus deste modelo. */
  armAngle(side, elev) {
    const c = this.armZ && this.armZ[side];
    if (!c) return 0;
    const e = elev < -1 ? -1 : elev > 1 ? 1 : elev;
    return e >= 0 ? c.up * e : c.down * (-e);
  }

  /** Elevação normalizada → delta Euler (graus) no eixo medido deste braço. */
  armRotation(side, elev, offsetDeg = 0, out = [0, 0, 0]) {
    out[0] = 0; out[1] = 0; out[2] = 0;
    const c = this.armZ && this.armZ[side];
    if (!c) return out;
    out[c.axis ?? 2] = this.armAngle(side, elev) + offsetDeg;
    return out;
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
    // Clavículas podem receber assistência direta do IK. Retornam sempre ao
    // repouso antes da composição; clips VRMA ainda podem sobrescrevê-las depois.
    for (const name of ['leftShoulder', 'rightShoulder']) {
      const shoulder = this.bone(name);
      if (shoulder) shoulder.quaternion.copy(this.restQuaternion(name));
    }
    for (const [name, v] of this.buffer.rot) {
      const n = this.bone(name);
      if (!n) continue;
      // PoseBuffer contém DELTAS. O three-vrm define a pose normalizada como
      // delta * rest; substituir Euler diretamente descartava a pose-base do
      // modelo e fazia certos VRM 1 carregarem com braços levantados/invertidos.
      this._qDelta.setFromEuler(_poseEuler.set(v[0], v[1], v[2], 'XYZ'));
      n.quaternion.copy(this._qDelta).multiply(this.restQuaternion(name));
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
