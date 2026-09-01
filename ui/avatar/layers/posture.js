// CAMADA: Postura base (idle + emoção + gesto ativo).
//  Dona da pose "esquelética" suavizada dos ossos posados (braços/mãos/cabeça)
//  + inclinação de tronco/cabeça vinda da emoção. As demais camadas só somam
//  offsets por cima disto.
import { DEG, damp } from '../rig-core.js';
import { ARM_ELEVATION, CTRL_BONES, POSES, GESTURE_ALIASES } from '../profiles.js';

const POSTURES = Object.freeze({
  neutral:   { spine: 0, chest: 0, head: 0 },
  open:      { spine: -1.5, chest: -2.0, head: -1.0 },
  closed:    { spine: 3.0, chest: 2.0, head: 2.0 },
  thinking:  { spine: 2.0, chest: 1.0, head: 3.0 },
  attentive: { spine: -2.0, chest: -2.5, head: -1.5 },
});

export function createPostureLayer() {
  const cur = {};                     // rotação atual (rad) por osso, p/ suavizar
  for (const b of CTRL_BONES) cur[b] = [0, 0, 0];
  cur.spine = [0, 0, 0];
  cur.chest = [0, 0, 0];
  cur.postureHead = [0, 0, 0];
  const armTarget = [0, 0, 0];

  return {
    name: 'posture',
    update(rig, buf, ctx, dt) {
      // pose-alvo dos braços/cabeça = rest + gesto ativo (em graus)
      const gname = GESTURE_ALIASES[ctx.gesture] || ctx.gesture;
      const pose = POSES[gname] ? { ...POSES.rest, ...POSES[gname] } : POSES.rest;
      const emo = ctx.emotion;
      const k = 6;                    // velocidade de assentamento da pose
      // postura de braço da EMOÇÃO (corpo inteiro) — só na idle; gesto sobrepõe
      const gActive = gname !== 'rest';
      const [aZ, aX] = emo.arms || [0, 0];

      for (const bone of CTRL_BONES) {
        const t = pose[bone] || [0, 0, 0];
        const c = cur[bone];
        // deltas da emoção: cabeça (inclinação) + braços (abrir/fechar/dobrar)
        let dx = bone === 'head' ? emo.head[0] : 0;
        let dy = bone === 'head' ? emo.head[1] : 0;
        let dz = 0;
        if (!gActive) {
          if (bone === 'rightUpperArm') dz = aZ;
          else if (bone === 'leftUpperArm') dz = -aZ;
          else if (bone === 'rightLowerArm' || bone === 'leftLowerArm') dx += aX;
        }
        // BRAÇO (upperArm): o alvo vem da ELEVAÇÃO do gesto convertida para os
        // graus DESTE modelo — assim a mão nunca cruza para o lado errado.
        // Demais ossos (antebraço etc.): ângulo direto, só com o sinal medido.
        let alvoX = (t[0] + dx) * DEG;
        let alvoY = (t[1] + dy) * DEG;
        let alvoZ;
        if (bone.endsWith('UpperArm')) {
          const lado = bone.startsWith('left') ? 'left' : 'right';
          const elevGesto = ARM_ELEVATION[gname] || {};
          const elev = elevGesto[lado] !== undefined
            ? elevGesto[lado]
            : (ARM_ELEVATION.rest[lado] ?? -0.8);
          if (rig.armRotation) {
            rig.armRotation(lado, elev, dz * (lado === 'left' ? -1 : 1), armTarget);
            alvoX += armTarget[0] * DEG;
            alvoY += armTarget[1] * DEG;
            alvoZ = armTarget[2] * DEG;
          } else {
            alvoZ = (rig.armAngle ? rig.armAngle(lado, elev) : t[2]) * DEG
                  + dz * DEG * (lado === 'left' ? -1 : 1);
          }
        } else {
          const sz = bone.endsWith('LowerArm') ? (rig.armZSign || 1) : 1;
          alvoZ = (t[2] + dz) * DEG * sz;
        }
        c[0] = damp(c[0], alvoX, k, dt);
        c[1] = damp(c[1], alvoY, k, dt);
        c[2] = damp(c[2], alvoZ, k, dt);
        buf.addRot(bone, c[0], c[1], c[2]);
      }
      // inclinação base da coluna pela emoção (postura aberta/caída)
      const po = POSTURES[ctx.posture] || POSTURES.neutral;
      const cs = cur.spine, cc = cur.chest, ch = cur.postureHead;
      cs[0] = damp(cs[0], (emo.spine[0] + po.spine) * DEG, 4, dt);
      cc[0] = damp(cc[0], po.chest * DEG, 4, dt);
      ch[0] = damp(ch[0], po.head * DEG, 4, dt);
      buf.addRot('spine', cs[0], 0, 0);
      buf.addRot('chest', cc[0], 0, 0);
      buf.addRot('head', ch[0], 0, 0);
    },
  };
}
