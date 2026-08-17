// CAMADA: Blink inteligente — frequência VARIA por estado (não é tempo fixo).
//  Ex.: pensando pisca mais; ocioso menos. Inclui piscada dupla ocasional.
const DUR = 0.12;

export function createBlinkLayer() {
  let next = 1.5, closing = 0, queue = 0, dur = DUR;
  const rand = (a, b) => a + Math.random() * (b - a);

  return {
    name: 'blink',
    update(rig, buf, ctx, dt) {
      const [min, max] = ctx.blinkRange || [2.4, 6.0];
      next -= dt;
      if (next <= 0 && closing <= 0) {
        dur = DUR * rand(0.8, 1.3);                    // varia a VELOCIDADE da piscada
        closing = dur; next = rand(min, max);
        if (Math.random() < 0.18) queue = 1;           // ~18%: pisca 2x
      }
      if (closing > 0) {
        closing -= dt;
        buf.setExpr('blink', Math.sin(Math.max(0, closing) / dur * Math.PI));
        if (closing <= 0 && queue > 0) { queue = 0; closing = dur; }
      }
    },
  };
}
