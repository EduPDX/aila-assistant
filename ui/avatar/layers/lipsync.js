// CAMADA: Lip-sync + ênfase corporal da fala.
//  - Boca (viseme 'aa') suave a partir do envelope de áudio (ctx.mouth).
//  - Enquanto fala: aceno leve de cabeça + GESTICULAÇÃO de braços/mãos
//    (levanta braços e dobra cotovelos ALTERNANDO no ritmo), tudo escalado
//    pelo envelope de fala. Some suave quando ela para de falar.
import { noise } from '../rig-core.js';

export function createLipSyncLayer() {
  let mouthNow = 0;
  return {
    name: 'lipsync',
    update(rig, buf, ctx, dt) {
      // boca
      mouthNow += (ctx.mouth - mouthNow) * Math.min(1, dt * 20);
      if (mouthNow > 0.001) buf.setExpr('aa', mouthNow);

      const g = Math.min(1, ctx.speech);
      if (g <= 0.05) return;

      // aceno leve da cabeça (lento, sem "tremer")
      const tt = ctx.t;
      buf.addRot('head', Math.sin(tt * 4.2) * 0.018 * g, Math.sin(tt * 2.6 + 1) * 0.028 * g, 0);

      // gesticulação de braços/mãos, alternando no beat
      const beat = Math.sin(tt * 2.3), off = noise(tt * 1.2 + 7);
      const up = Math.max(0, beat), dn = Math.max(0, -beat);
      buf.addRot('rightUpperArm', -(0.05 + 0.05 * off) * g, 0, (0.16 + 0.12 * up) * g);
      buf.addRot('rightLowerArm', -(0.30 + 0.40 * up) * g, 0.12 * beat * g, 0);
      buf.addRot('leftUpperArm', -(0.05 - 0.05 * off) * g, 0, -(0.16 + 0.12 * dn) * g);
      buf.addRot('leftLowerArm', -(0.30 + 0.40 * dn) * g, -0.12 * beat * g, 0);
    },
  };
}
