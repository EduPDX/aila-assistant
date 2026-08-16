// CAMADA: Emotion (face) — interpola as expressões faciais VRM em direção à
//  emoção atual. Só a face aqui; a POSTURA da emoção vive na PostureLayer e os
//  RITMOS no controller (motion).
import { FACE_EXPRESSIONS } from '../profiles.js';

export function createEmotionLayer() {
  const cur = {};
  for (const e of FACE_EXPRESSIONS) cur[e] = 0;
  let speaking = 0;   // envelope suave da fala (sobe rápido, cai devagar)

  return {
    name: 'emotion',
    update(rig, buf, ctx, dt) {
      // Expressões como 'happy' fecham os OLHOS e abrem a BOCA no VRM. Durante a
      // fala isso trava os olhos fechados e some com o lip-sync. Então, enquanto
      // ela fala, reduzimos a intensidade da face → o blink reabre os olhos e a
      // boca passa a ser dirigida pelo lip-sync ('aa').
      const m = ctx.mouth || 0;
      const rising = m > 0.06;
      speaking += ((rising ? 1 : 0) - speaking) * Math.min(1, dt * (rising ? 10 : 2.5));
      const cap = 0.85 - 0.60 * speaking;   // ~0.85 parada · ~0.25 falando

      const target = ctx.emotion.face;
      const k = Math.min(1, dt * 8);
      for (const e of FACE_EXPRESSIONS) {
        const goal = e === target ? cap : 0.0;
        cur[e] += (goal - cur[e]) * k;
        if (cur[e] > 0.001) buf.setExpr(e, cur[e]);
      }
    },
  };
}
