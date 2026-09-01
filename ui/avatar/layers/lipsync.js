// CAMADA: Lip-sync — SÓ A BOCA (viseme 'aa') + um aceno leve de cabeça na fala.
//
//  FASE A: a gesticulação de BRAÇOS que vivia aqui foi REMOVIDA (era o
//  "fala → seno → braços" que brigava com postura/gesto/IK/colisão). A
//  expressividade da fala volta na Fase E, como um controlador dedicado
//  (speech-gesture) que usa alvos de mão + IK e alterna repouso ↔ gesto.
//  Aqui a boca e o micro-aceno da cabeça continuam intactos.
const VISEMES = ['aa', 'ih', 'ou', 'ee', 'oh'];

export function createLipSyncLayer() {
  let mouthNow = 0;
  const cur = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
  return {
    name: 'lipsync',
    update(rig, buf, ctx, dt) {
      // boca (viseme 'aa') a partir do envelope de áudio. O viseme CEDE um pouco
      // à boca emocional (não a apaga): quanto mais forte a face (sorriso etc.),
      // um pouco menos de abertura de 'aa' → os dois se misturam (P3).
      mouthNow += (ctx.mouth - mouthNow) * Math.min(1, dt * 20);
      const face = Math.min(1, ctx.faceWeight || 0);
      const available = rig.profile?.capabilities?.expressionMap || {};
      const supplied = ctx.visemes || {};
      const hasSpectral = supplied.aa > 0.001 || supplied.ih > 0.001 || supplied.ou > 0.001
        || supplied.ee > 0.001 || supplied.oh > 0.001;
      const k = Math.min(1, dt * 18);
      for (const name of VISEMES) {
        const raw = hasSpectral ? supplied[name] || 0 : (name === 'aa' ? mouthNow : 0);
        cur[name] += (raw * (1 - 0.4 * face) - cur[name]) * k;
        // Escrever também o zero fecha a boca no ExpressionManager, cujos
        // pesos persistem entre frames. O código anterior podia congelar 'aa'.
        if (available[name]) buf.setExpr(name, cur[name] < 0.001 ? 0 : cur[name]);
      }

      // aceno leve da cabeça enquanto fala — NÃO mexe nos braços
      const g = Math.min(1, ctx.speech);
      if (g <= 0.05) return;
      const tt = ctx.t;
      buf.addRot('head', Math.sin(tt * 4.2) * 0.018 * g, Math.sin(tt * 2.6 + 1) * 0.028 * g, 0);
    },
  };
}
