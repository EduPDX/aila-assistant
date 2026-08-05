// CAMADA: Respiração — nunca fica 100% parada. Peito/ombros/coluna sobem e
//  descem num ciclo contínuo que acelera ao falar.
export function createBreathLayer() {
  let phase = 0;
  return {
    name: 'breath',
    update(rig, buf, ctx, dt) {
      const m = ctx.motion;
      // ~0.25 Hz em repouso; acelera ao falar
      const hz = 0.25 * m.breath * (1 + ctx.speech * 0.35);
      phase += dt * hz * Math.PI * 2;
      const breath = Math.sin(phase);          // -1..1
      const inhale = (breath + 1) / 2;         // 0..1
      const a = m.amp;
      buf.addRot('spine', breath * 0.010 * a, 0, 0);
      buf.addRot('chest', -inhale * 0.020 * a, 0, 0);
      buf.addRot('upperChest', -inhale * 0.012 * a, 0, 0);
      buf.addRot('leftShoulder', 0, 0, -inhale * 0.030 * a);
      buf.addRot('rightShoulder', 0, 0, inhale * 0.030 * a);
    },
  };
}
