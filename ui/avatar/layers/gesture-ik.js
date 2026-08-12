// CAMADA: Gesto por IK — traduz o gesto ativo (ctx.gesture) num ALVO DE MÃO
//  (mundo) + pose de dedos, e escreve no PoseBuffer (buf.ik + ctx.handPose). O
//  solver de IK do controller resolve o braço até o alvo, com cotovelo natural.
//
//  Frame do avatar DERIVADO DO RIG (regra 8, sem assumir eixos):
//    direita = ombro dir - ombro esq · cima = pescoço - quadril · frente = dir × cima
//  Peso de IK com ramp (entra/sai suave). Ao sair, mira o ÚLTIMO alvo com peso
//  decrescente → o braço volta ao repouso (FK da postura) sem "pop".
import * as THREE from 'three';
import { DEG } from '../rig-core.js';
import { GESTURES } from '../gestures.js';
import { GESTURE_ALIASES } from '../profiles.js';

export function createGestureIKLayer() {
  const V = () => new THREE.Vector3();
  const RU = V(), LU = V(), NK = V(), HP = V(), S = V(), E = V(), H = V();
  const right = V(), up = V(), fwd = V(), off = V(), world = V();
  const w = { left: 0, right: 0 };
  const last = { left: V(), right: V() };
  const hasLast = { left: false, right: false };

  const wp = (rig, n, o) => { const b = rig.bone(n); return b ? o.setFromMatrixPosition(b.matrixWorld) : null; };

  return {
    name: 'gesture-ik',
    update(rig, buf, ctx, dt) {
      const name = GESTURE_ALIASES[ctx.gesture] || ctx.gesture;
      const g = GESTURES[name] || null;

      // frame do avatar (do rig)
      if (!wp(rig, 'rightUpperArm', RU) || !wp(rig, 'leftUpperArm', LU)
        || !wp(rig, 'neck', NK) || !wp(rig, 'hips', HP)) return;
      right.copy(RU).sub(LU).normalize();     // aponta p/ o lado da mão direita
      up.copy(NK).sub(HP).normalize();
      fwd.copy(up).cross(right).normalize();  // up × right = frente do avatar (+Z)

      for (const side of ['left', 'right']) {
        const active = !!g && (g.side === side || g.side === 'both');
        w[side] += ((active ? 1 : 0) - w[side]) * Math.min(1, dt * 8);   // ramp
        if (!active && w[side] < 0.02) { hasLast[side] = false; continue; }

        if (active) {
          const upper = rig.bone(side + 'UpperArm'), lower = rig.bone(side + 'LowerArm'), hand = rig.bone(side + 'Hand');
          if (!upper || !lower || !hand) continue;
          S.setFromMatrixPosition(upper.matrixWorld);
          E.setFromMatrixPosition(lower.matrixWorld);
          H.setFromMatrixPosition(hand.matrixWorld);
          const armLen = S.distanceTo(E) + E.distanceTo(H);
          const mir = side === 'left' ? -1 : 1;
          off.set(0, 0, 0)
            .addScaledVector(right, g.target[0] * mir * armLen)
            .addScaledVector(up, g.target[1] * armLen)
            .addScaledVector(fwd, g.target[2] * armLen);
          world.copy(S).add(off);
          last[side].copy(world); hasLast[side] = true;
          ctx.handPose[side] = g.hand || 'relaxed';
          if (g.head) buf.addRot('head', g.head[0] * DEG, g.head[1] * DEG, g.head[2] * DEG);
        } else {
          ctx.handPose[side] = 'relaxed';
        }

        const tgt = active ? world : (hasLast[side] ? last[side] : null);
        if (tgt) buf.setHandTarget(side, tgt.x, tgt.y, tgt.z, w[side]);
      }
    },
  };
}
