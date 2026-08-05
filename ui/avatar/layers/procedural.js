// CAMADA: Movimento procedural — micro-movimentos orgânicos + deslocamento de
//  peso. Ruído de senoides incomensuráveis (nunca repete o mesmo padrão).
//  Cobre coluna, peito, pescoço, quadril e cabeça.
import { noise } from '../rig-core.js';

export function createProceduralLayer() {
  return {
    name: 'procedural',
    update(rig, buf, ctx, dt) {
      const m = ctx.motion, a = m.amp, t = ctx.t * m.speed;
      // deslocamento de peso lento (~10-14s) — corpo nunca "travado"
      const shift = noise(t * 0.11);
      const shift2 = noise(t * 0.07 + 3.3);

      buf.addRot('spine', 0, shift * 0.020 * a, shift * 0.015 * a);
      buf.addRot('chest', 0, shift2 * 0.010 * a, -shift * 0.010 * a);
      buf.addRot('hips', 0, shift * 0.015 * a, -shift * 0.020 * a);
      buf.addRot('neck', noise(t * 0.6 + 1.2) * 0.020 * a, noise(t * 0.5) * 0.030 * a, 0);
      // micro-movimentos da cabeça (aditivo sobre a postura/gaze)
      buf.addRot('head',
        noise(t * 0.53) * 0.030 * a,
        noise(t * 0.41 + 2.1) * 0.040 * a,
        noise(t * 0.33 + 4.2) * 0.020 * a);
    },
  };
}
