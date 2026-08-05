// CAMADA: Emotion (face) — interpola as expressões faciais VRM em direção à
//  emoção atual. Só a face aqui; a POSTURA da emoção vive na PostureLayer e os
//  RITMOS no controller (motion).
import { FACE_EXPRESSIONS } from '../profiles.js';

export function createEmotionLayer() {
  const cur = {};
  for (const e of FACE_EXPRESSIONS) cur[e] = 0;

  return {
    name: 'emotion',
    update(rig, buf, ctx, dt) {
      const target = ctx.emotion.face;
      const k = Math.min(1, dt * 8);
      for (const e of FACE_EXPRESSIONS) {
        const goal = e === target ? 0.85 : 0.0;
        cur[e] += (goal - cur[e]) * k;
        if (cur[e] > 0.001) buf.setExpr(e, cur[e]);
      }
    },
  };
}
