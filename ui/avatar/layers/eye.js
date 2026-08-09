// CAMADA: Eye — para onde ela olha. Sacadas (micro-saltos), foco por estado e
//  olhar aleatório discreto. Produz o alvo dos OLHOS (VRM lookAt) e a "vontade"
//  de olhar (yaw/pitch) que a LookAtLayer distribui pelo corpo.
export function createEyeLayer() {
  const g = { yaw: 0, pitch: 0, tYaw: 0, tPitch: 0, saccade: 0 };
  const r = () => Math.random();

  // escreve o alvo direto em g (sem alocar array por sacada)
  function pickTarget(mode) {
    switch (mode) {
      case 'user':   g.tYaw = (r() - 0.5) * 0.12; g.tPitch = (r() - 0.5) * 0.08; break;   // encara o usuário
      case 'lock':   g.tYaw = (r() - 0.5) * 0.06; g.tPitch = (r() - 0.5) * 0.05; break;   // travado
      case 'wander': g.tYaw = (r() - 0.3) * 0.5;  g.tPitch = -0.14 - r() * 0.20;  break;  // pensativo
      case 'down':   g.tYaw = (r() - 0.5) * 0.15; g.tPitch = 0.24 + r() * 0.14;   break;  // olhar baixo
      case 'screen': g.tYaw = (r() - 0.4) * 0.22; g.tPitch = 0.08 + r() * 0.10;   break;  // "tela"
      default:       g.tYaw = (r() - 0.5) * 0.28; g.tPitch = (r() - 0.5) * 0.16;  break;  // soft
    }
  }

  return {
    name: 'eye',
    update(rig, buf, ctx, dt) {
      g.saccade -= dt;
      if (g.saccade <= 0) {
        g.saccade = 0.8 + r() * 3.4;                 // nova sacada
        pickTarget(ctx.gazeMode);
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
