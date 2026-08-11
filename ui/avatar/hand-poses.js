// ============================================================
//  HAND POSES — poses de mão (dedos) + a camada que as aplica.
//
//  Regra 8 (não assumir eixos): os eixos são DERIVADOS da geometria real do
//  rig. Os 4 dedos dobram na "linha dos nós" (index→little). O POLEGAR tem
//  DOIS eixos próprios: FLEXÃO (dir. do polegar × normal da palma) e ADUÇÃO
//  (normal da palma — traz o polegar p/ junto da mão, corrigindo o repouso do
//  VRoid em que ele fica esticado p/ fora). Sinais detectados empiricamente
//  (distância ponta→mão p/ flexão; ponta do polegar→indicador p/ adução).
//  Tudo em espaço de MUNDO, convertido p/ o frame local de cada osso.
//
//  A camada escreve Euler no PoseBuffer (como as demais). Os dedos não têm
//  outro escritor nem clamp em joint-limits → "set" suavizado, sem conflito.
// ============================================================
import * as THREE from 'three';
import { DEG, damp } from './rig-core.js';
import { FINGERS, fingerBones, SIDES } from './bones.js';

// curl por dedo (0 = reto, 1 = dobrado). _thumbAdduct: quanto o polegar recolhe
// p/ junto da mão (0 = aberto/livre, 1 = colado). Poses previsíveis (regra 9).
export const HAND_POSES = {
  open:      { Thumb: 0.00, Index: 0.00, Middle: 0.00, Ring: 0.00, Little: 0.00, _thumbAdduct: 0.35 },
  relaxed:   { Thumb: 0.22, Index: 0.35, Middle: 0.42, Ring: 0.50, Little: 0.58, _thumbAdduct: 0.72 },
  closed:    { Thumb: 0.62, Index: 0.95, Middle: 0.95, Ring: 0.95, Little: 0.95, _thumbAdduct: 0.60 },
  point:     { Thumb: 0.42, Index: 0.00, Middle: 0.95, Ring: 0.95, Little: 0.95, _thumbAdduct: 0.60 },
  thumbs_up: { Thumb: 0.00, Index: 0.95, Middle: 0.95, Ring: 0.95, Little: 0.95, _thumbAdduct: 0.00 },
  thinking:  { Thumb: 0.30, Index: 0.20, Middle: 0.55, Ring: 0.65, Little: 0.72, _thumbAdduct: 0.60 },
};

// ângulo máximo de dobra por segmento (graus), escalado pelo curl 0..1
const SEG_MAX = [72, 92, 58];          // proximal, intermediate/médio, distal
const THUMB_MAX = [26, 42, 42];        // polegar: metacarpal, proximal, distal
const ADDUCT_MAX = [40, 12, 0];        // adução do polegar por segmento (graus)

export function createHandPoseLayer() {
  const qFlex = new THREE.Quaternion(), qAdd = new THREE.Quaternion(), eul = new THREE.Euler();
  const axF = new THREE.Vector3(), axA = new THREE.Vector3();
  const pA = new THREE.Vector3(), pB = new THREE.Vector3(), pC = new THREE.Vector3();
  const knuckle = new THREE.Vector3(), midDir = new THREE.Vector3(), palmN = new THREE.Vector3();
  const thumbDir = new THREE.Vector3(), thumbFlex = new THREE.Vector3();
  const qPar = new THREE.Quaternion();
  const cache = {};          // boneName -> { axis, adduct?, seg, thumb, sign, adductSign? }
  const cur = {}, curA = {}; // curl / adução atuais (suavizados) por osso
  let ready = false;

  const wp = (node, out) => { node.updateWorldMatrix(true, false); return out.setFromMatrixPosition(node.matrixWorld); };
  const localAxisOf = (node, worldAxis, out) => {
    node.parent.getWorldQuaternion(qPar).invert();
    return out.copy(worldAxis).applyQuaternion(qPar).normalize();
  };
  // sinal que curva p/ a palma: reduz a distância ponta→mão
  function detectSign(prox, tip, flexWorld, handP) {
    const la = localAxisOf(prox, flexWorld, pC), saved = prox.quaternion.clone();
    prox.quaternion.setFromAxisAngle(la, 0.6); const dP = wp(tip, pA).distanceTo(handP);
    prox.quaternion.setFromAxisAngle(la, -0.6); const dM = wp(tip, pA).distanceTo(handP);
    prox.quaternion.copy(saved); prox.updateWorldMatrix(false, true);
    return dP < dM ? 1 : -1;
  }
  // sinal que aduz o polegar: reduz a distância ponta-do-polegar → indicador
  function detectAdductSign(meta, thumbTip, adductWorld, idxP) {
    const idxW = wp(idxP, pB).clone();
    const la = localAxisOf(meta, adductWorld, pC), saved = meta.quaternion.clone();
    meta.quaternion.setFromAxisAngle(la, 0.5); const dP = wp(thumbTip, pA).distanceTo(idxW);
    meta.quaternion.setFromAxisAngle(la, -0.5); const dM = wp(thumbTip, pA).distanceTo(idxW);
    meta.quaternion.copy(saved); meta.updateWorldMatrix(false, true);
    return dP < dM ? 1 : -1;
  }

  function build(rig) {
    rig.updateMatrices();
    for (const side of SIDES) {
      const idxP = rig.bone(side + 'IndexProximal'), litP = rig.bone(side + 'LittleProximal');
      const midP = rig.bone(side + 'MiddleProximal'), midD = rig.bone(side + 'MiddleDistal');
      const thmM = rig.bone(side + 'ThumbMetacarpal'), thmP = rig.bone(side + 'ThumbProximal'), thmD = rig.bone(side + 'ThumbDistal');
      const hand = rig.bone(side + 'Hand');
      if (!idxP || !litP || !midP || !midD || !thmM || !thmP || !thmD || !hand) return false;
      const handP = new THREE.Vector3().copy(wp(hand, pA));

      knuckle.copy(wp(idxP, pA)).sub(wp(litP, pB)).normalize();
      midDir.copy(wp(midD, pA)).sub(wp(midP, pB)).normalize();
      palmN.copy(knuckle).cross(midDir).normalize();                 // normal da palma (eixo de adução)
      thumbDir.copy(wp(thmD, pA)).sub(wp(thmP, pB)).normalize();
      thumbFlex.copy(thumbDir).cross(palmN).normalize();             // eixo de flexão do polegar

      const sign4 = detectSign(idxP, rig.bone(side + 'IndexDistal'), knuckle, handP);
      const signT = detectSign(thmP, thmD, thumbFlex, handP);
      const signAdd = detectAdductSign(thmM, thmD, palmN, idxP);

      for (const finger of FINGERS) {
        const isThumb = finger === 'Thumb';
        const flexWorld = isThumb ? thumbFlex : knuckle;
        const sgn = isThumb ? signT : sign4;
        fingerBones(side, finger).forEach((bn, seg) => {
          const node = rig.bone(bn);
          if (!node) return;
          const ax = localAxisOf(node, flexWorld, new THREE.Vector3());
          const rec = { axis: [ax.x, ax.y, ax.z], seg, thumb: isThumb, sign: sgn };
          if (isThumb) {
            const ad = localAxisOf(node, palmN, new THREE.Vector3());
            rec.adduct = [ad.x, ad.y, ad.z];
            rec.adductSign = signAdd;
          }
          cache[bn] = rec;
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
        const adductTarget = pose._thumbAdduct ?? 0;
        for (const finger of FINGERS) {
          const targetCurl = pose[finger] ?? 0;
          fingerBones(side, finger).forEach((bn) => {
            const info = cache[bn];
            if (!info) return;
            const c = cur[bn] = damp(cur[bn] ?? 0, targetCurl, 10, dt);
            const maxDeg = (info.thumb ? THUMB_MAX : SEG_MAX)[info.seg];
            axF.set(info.axis[0], info.axis[1], info.axis[2]);
            qFlex.setFromAxisAngle(axF, maxDeg * DEG * c * info.sign);
            if (info.thumb && info.adduct) {                    // compõe adução no polegar
              const ca = curA[bn] = damp(curA[bn] ?? 0, adductTarget, 10, dt);
              const adDeg = ADDUCT_MAX[info.seg] || 0;
              if (adDeg) {
                axA.set(info.adduct[0], info.adduct[1], info.adduct[2]);
                qAdd.setFromAxisAngle(axA, adDeg * DEG * ca * info.adductSign);
                qFlex.premultiply(qAdd);
              }
            }
            eul.setFromQuaternion(qFlex, 'XYZ');
            buf.addRot(bn, eul.x, eul.y, eul.z);
          });
        }
      }
    },
  };
}
