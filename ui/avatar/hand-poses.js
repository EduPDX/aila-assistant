// ============================================================
//  HAND POSES — poses de mão (dedos) + a camada que as aplica.
//
//  Regra 8 (não assumir eixos): o eixo de flexão é DERIVADO da geometria real
//  do rig. Os 4 dedos dobram ao redor da "linha dos nós" (index→little); o
//  POLEGAR tem eixo próprio (direção do polegar × normal da palma). O SINAL
//  (curvar p/ a palma vs esticar) é detectado empiricamente medindo a distância
//  ponta→mão. Tudo em espaço de MUNDO, convertido para o frame local de cada
//  osso → vale p/ qualquer VRM, sem chutar X/Y/Z.
//
//  A camada escreve Euler no PoseBuffer (como as demais). Os dedos não têm
//  outro escritor nem clamp em joint-limits → é um "set" suavizado, sem
//  conflito. Fase B: só CURL (dobra); spread (abrir dedos) fica p/ depois.
// ============================================================
import * as THREE from 'three';
import { DEG, damp } from './rig-core.js';
import { FINGERS, fingerBones, SIDES } from './bones.js';

// curl por dedo (0 = reto, 1 = totalmente dobrado). Poses previsíveis (regra 9).
export const HAND_POSES = {
  open:      { Thumb: 0.00, Index: 0.00, Middle: 0.00, Ring: 0.00, Little: 0.00 },
  relaxed:   { Thumb: 0.28, Index: 0.35, Middle: 0.42, Ring: 0.50, Little: 0.58 },
  closed:    { Thumb: 0.75, Index: 0.95, Middle: 0.95, Ring: 0.95, Little: 0.95 },
  point:     { Thumb: 0.55, Index: 0.00, Middle: 0.95, Ring: 0.95, Little: 0.95 },
  thumbs_up: { Thumb: 0.00, Index: 0.95, Middle: 0.95, Ring: 0.95, Little: 0.95 },
  thinking:  { Thumb: 0.30, Index: 0.20, Middle: 0.55, Ring: 0.65, Little: 0.72 },
};

// ângulo máximo de dobra por segmento (graus), escalado pelo curl 0..1
const SEG_MAX = [72, 92, 58];          // proximal, intermediate/médio, distal
const THUMB_MAX = [26, 42, 42];        // polegar: metacarpal, proximal, distal

export function createHandPoseLayer() {
  const qDelta = new THREE.Quaternion(), eul = new THREE.Euler(), axis = new THREE.Vector3();
  const pA = new THREE.Vector3(), pB = new THREE.Vector3(), pC = new THREE.Vector3();
  const knuckle = new THREE.Vector3(), midDir = new THREE.Vector3(), palmN = new THREE.Vector3();
  const thumbDir = new THREE.Vector3(), thumbFlex = new THREE.Vector3();
  const qPar = new THREE.Quaternion();
  const cache = {};          // boneName -> { axis:[x,y,z], seg:0..2, thumb, sign }
  const cur = {};            // boneName -> curl atual (suavizado)
  let ready = false;

  const wp = (node, out) => { node.updateWorldMatrix(true, false); return out.setFromMatrixPosition(node.matrixWorld); };
  // eixo de mundo no frame LOCAL do osso (via quaternion do PAI)
  const localAxisOf = (node, worldAxis, out) => {
    node.parent.getWorldQuaternion(qPar).invert();
    return out.copy(worldAxis).applyQuaternion(qPar).normalize();
  };
  // sinal que curva p/ a palma: o que reduz a distância ponta→mão
  function detectSign(prox, tip, flexWorld, handP) {
    const la = localAxisOf(prox, flexWorld, pC);
    const saved = prox.quaternion.clone();
    prox.quaternion.setFromAxisAngle(la, 0.6);
    const dPlus = wp(tip, pA).distanceTo(handP);
    prox.quaternion.setFromAxisAngle(la, -0.6);
    const dMinus = wp(tip, pA).distanceTo(handP);
    prox.quaternion.copy(saved); prox.updateWorldMatrix(false, true);
    return dPlus < dMinus ? 1 : -1;
  }

  function build(rig) {
    rig.updateMatrices();
    for (const side of SIDES) {
      const idxP = rig.bone(side + 'IndexProximal'), litP = rig.bone(side + 'LittleProximal');
      const midP = rig.bone(side + 'MiddleProximal'), midD = rig.bone(side + 'MiddleDistal');
      const thmP = rig.bone(side + 'ThumbProximal'), thmD = rig.bone(side + 'ThumbDistal');
      const hand = rig.bone(side + 'Hand');
      if (!idxP || !litP || !midP || !midD || !thmP || !thmD || !hand) return false;
      const handP = new THREE.Vector3().copy(wp(hand, pA));

      // 4 dedos: linha dos nós (index→little)
      knuckle.copy(wp(idxP, pA)).sub(wp(litP, pB)).normalize();
      // normal da palma = linha dos nós × direção do dedo médio
      midDir.copy(wp(midD, pA)).sub(wp(midP, pB)).normalize();
      palmN.copy(knuckle).cross(midDir).normalize();
      // polegar: eixo próprio = direção do polegar × normal da palma
      thumbDir.copy(wp(thmD, pA)).sub(wp(thmP, pB)).normalize();
      thumbFlex.copy(thumbDir).cross(palmN).normalize();

      const sign4 = detectSign(idxP, rig.bone(side + 'IndexDistal'), knuckle, handP);
      const signT = detectSign(thmP, thmD, thumbFlex, handP);

      for (const finger of FINGERS) {
        const isThumb = finger === 'Thumb';
        const flexWorld = isThumb ? thumbFlex : knuckle;
        const sgn = isThumb ? signT : sign4;
        fingerBones(side, finger).forEach((bn, seg) => {
          const node = rig.bone(bn);
          if (!node) return;
          const ax = localAxisOf(node, flexWorld, new THREE.Vector3());
          cache[bn] = { axis: [ax.x, ax.y, ax.z], seg, thumb: isThumb, sign: sgn };
        });
      }
    }
    return true;
  }

  return {
    name: 'hand-pose',
    update(rig, buf, ctx, dt) {
      if (!ready) { ready = build(rig); if (!ready) return; }
      const hp = ctx.handPose || {};
      for (const side of SIDES) {
        const pose = HAND_POSES[hp[side]] || HAND_POSES.relaxed;
        for (const finger of FINGERS) {
          const targetCurl = pose[finger] ?? 0;
          fingerBones(side, finger).forEach((bn) => {
            const info = cache[bn];
            if (!info) return;
            const c = cur[bn] = damp(cur[bn] ?? 0, targetCurl, 10, dt);
            const maxDeg = (info.thumb ? THUMB_MAX : SEG_MAX)[info.seg];
            const ang = maxDeg * DEG * c * info.sign;
            axis.set(info.axis[0], info.axis[1], info.axis[2]);
            qDelta.setFromAxisAngle(axis, ang);
            eul.setFromQuaternion(qDelta, 'XYZ');
            buf.addRot(bn, eul.x, eul.y, eul.z);
          });
        }
      }
    },
  };
}
