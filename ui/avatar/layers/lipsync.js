// CAMADA: Lip-sync — SÓ A BOCA (viseme 'aa') + um aceno leve de cabeça na fala.
//
//  FASE A: a gesticulação de BRAÇOS que vivia aqui foi REMOVIDA (era o
//  "fala → seno → braços" que brigava com postura/gesto/IK/colisão). A
//  expressividade da fala volta na Fase E, como um controlador dedicado
//  (speech-gesture) que usa alvos de mão + IK e alterna repouso ↔ gesto.
//  Aqui a boca e o micro-aceno da cabeça continuam intactos.
export function createLipSyncLayer() {
  let mouthNow = 0;
  return {
    name: 'lipsync',
    update(rig, buf, ctx, dt) {
      // boca (viseme 'aa') a partir do envelope de áudio
      mouthNow += (ctx.mouth - mouthNow) * Math.min(1, dt * 20);
      if (mouthNow > 0.001) buf.setExpr('aa', mouthNow);

      // aceno leve da cabeça enquanto fala — NÃO mexe nos braços
      const g = Math.min(1, ctx.speech);
      if (g <= 0.05) return;
      const tt = ctx.t;
      buf.addRot('head', Math.sin(tt * 4.2) * 0.018 * g, Math.sin(tt * 2.6 + 1) * 0.028 * g, 0);
    },
  };
}
