// CAMADA: Eye — para onde ela olha. Sacadas (micro-saltos), foco por estado e
//  olhar aleatório discreto. Produz o alvo dos OLHOS (VRM lookAt) e a "vontade"
//  de olhar (yaw/pitch) que a LookAtLayer distribui pelo corpo.
export function createEyeLayer() {
  const g = { yaw: 0, pitch: 0, tYaw: 0, tPitch: 0, saccade: 0 };
  const r = () => Math.random();

  function pickTarget(mode) {
    switch (mode) {
      case 'user':   return [(r() - 0.5) * 0.12, (r() - 0.5) * 0.08];   // encara o usuário, quase parado
      case 'lock':   return [(r() - 0.5) * 0.06, (r() - 0.5) * 0.05];   // travado
      case 'wander': return [(r() - 0.3) * 0.5, -0.14 - r() * 0.20];    // pensativo: vagueia p/ cima/lado
      case 'down':   return [(r() - 0.5) * 0.15, 0.24 + r() * 0.14];    // olhar baixo
      case 'screen': return [(r() - 0.4) * 0.22, 0.08 + r() * 0.10];    // "tela": levemente pra baixo/frente
      default:       return [(r() - 0.5) * 0.28, (r() - 0.5) * 0.16];   // soft
    }
  }

  return {
    name: 'eye',
    update(rig, buf, ctx, dt) {
      g.saccade -= dt;
      if (g.saccade <= 0) {
        g.saccade = 0.8 + r() * 3.4;                 // nova sacada
        [g.tYaw, g.tPitch] = pickTarget(ctx.gazeMode);
      }
      // sacadas são rápidas
      const k = Math.min(1, dt * 9);
      g.yaw += (g.tYaw - g.yaw) * k;
      g.pitch += (g.tPitch - g.pitch) * k;

      // alvo dos olhos: perto da câmera (engaja o espectador) + desvio do gaze
      const cam = ctx.camera;
      buf.setGaze(cam.position.x + g.yaw * 1.2, cam.position.y - g.pitch * 1.2, cam.position.z);

      // publica a intenção de olhar p/ a LookAtLayer distribuir no corpo
      ctx.gaze.yaw = g.yaw;
      ctx.gaze.pitch = g.pitch;
    },
  };
}
