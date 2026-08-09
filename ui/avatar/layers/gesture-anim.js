// CAMADA: Gestos ANIMADOS da cabeça (nod = sim, shake = não).
//  Diferente dos gestos de POSE (braço), estes são animações curtas: a cabeça
//  balança e volta. Somam offsets no head/neck; expiram sozinhos.
export function createGestureAnimLayer() {
  return {
    name: 'gesture-anim',
    update(rig, buf, ctx, dt) {
      const a = ctx.anim;
      if (!a) return;
      a.t += dt;
      const p = a.t / a.dur;              // 0..1
      if (p >= 1) { ctx.anim = null; return; }
      const env = Math.sin(p * Math.PI); // envelope (fade-in/out)
      if (a.type === 'nod') {             // 2 acenos p/ baixo (positivo = queixo desce)
        buf.addRot('head', Math.max(0, Math.sin(p * Math.PI * 4)) * 0.20 * env, 0, 0);
        buf.addRot('neck', Math.max(0, Math.sin(p * Math.PI * 4)) * 0.06 * env, 0, 0);
      } else if (a.type === 'shake') {    // 2 balanços laterais (não)
        buf.addRot('head', 0, Math.sin(p * Math.PI * 4) * 0.24 * env, 0);
        buf.addRot('neck', 0, Math.sin(p * Math.PI * 4) * 0.07 * env, 0);
      }
    },
  };
}
