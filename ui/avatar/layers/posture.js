// CAMADA: Postura base (idle + emoção + gesto ativo).
//  Dona da pose "esquelética" suavizada dos ossos posados (braços/mãos/cabeça)
//  + inclinação de tronco/cabeça vinda da emoção. As demais camadas só somam
//  offsets por cima disto.
import { DEG, damp } from '../rig-core.js';
import { CTRL_BONES, POSES, GESTURE_ALIASES } from '../profiles.js';

export function createPostureLayer() {
  const cur = {};                     // rotação atual (rad) por osso, p/ suavizar
  for (const b of CTRL_BONES) cur[b] = [0, 0, 0];
  cur.spine = [0, 0, 0];

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
        // Z dos BRAÇOS: multiplicado pelo sinal medido no modelo (rig.calibrateArms).
        // Sem isso, um VRM montado "ao contrário" fica de braços LEVANTADOS.
        const sz = bone.endsWith('UpperArm') || bone.endsWith('LowerArm')
          ? (rig.armZSign || 1) : 1;
        c[0] = damp(c[0], (t[0] + dx) * DEG, k, dt);
        c[1] = damp(c[1], (t[1] + dy) * DEG, k, dt);
        c[2] = damp(c[2], (t[2] + dz) * DEG * sz, k, dt);
        buf.addRot(bone, c[0], c[1], c[2]);
      }
      // inclinação base da coluna pela emoção (postura aberta/caída)
      const cs = cur.spine;
      cs[0] = damp(cs[0], emo.spine[0] * DEG, 4, dt);
      buf.addRot('spine', cs[0], 0, 0);
    },
  };
}
