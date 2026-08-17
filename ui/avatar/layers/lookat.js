// CAMADA: LookAt distribuído — a cabeça NUNCA gira sozinha. A vontade de olhar
//  (yaw/pitch, vinda da EyeLayer) é repartida pela cadeia:
//    hips → spine → chest → upperChest → neck → head
//  P2: os OLHOS chegam primeiro (rápidos, via VRM lookAt na EyeLayer) e o CORPO
//  ACOMPANHA com atraso (damp mais lento) — acaba o "olhar robótico" em que a
//  cabeça salta junto com os olhos. Glance pequeno ≈ só olhos; desvio grande →
//  a parte alta da cadeia engaja mais. Clamp p/ limites naturais.
import { damp } from '../rig-core.js';

const CHAIN = [
  ['hips', 0.05], ['spine', 0.10], ['chest', 0.13],
  ['upperChest', 0.14], ['neck', 0.26], ['head', 0.32],
];
// limites naturais do desvio distribuído (rad) — a cabeça não "quebra" o pescoço
const MAX_YAW = 0.55, MAX_PITCH = 0.42;
// taxa de acompanhamento do CORPO (os olhos, na EyeLayer, seguem a ~9.7/s → ~2x
// mais rápidos). Assim os olhos lideram e a cabeça vem atrás.
const BODY_K = 4.5;

export function createLookAtLayer() {
  let sYaw = 0, sPitch = 0;      // olhar suavizado do corpo (atrás dos olhos)
  const clampAbs = (v, m) => (v < -m ? -m : v > m ? m : v);

  return {
    name: 'lookat',
    update(rig, buf, ctx, dt) {
      // corpo persegue a intenção de olhar com ATRASO (independente de FPS)
      sYaw = damp(sYaw, ctx.gaze.yaw, BODY_K, dt);
      sPitch = damp(sPitch, ctx.gaze.pitch, BODY_K, dt);
      const yaw = clampAbs(sYaw, MAX_YAW), pitch = clampAbs(sPitch, MAX_PITCH);
      if (Math.abs(yaw) < 1e-4 && Math.abs(pitch) < 1e-4) return;

      // engajamento progressivo: quanto maior o desvio, mais o corpo acompanha
      // (glance discreto move pouco a cabeça; virar de fato leva o tronco junto)
      const mag = Math.min(1, Math.hypot(yaw / MAX_YAW, pitch / MAX_PITCH));
      const engage = 0.62 + 0.38 * mag;
      for (const [bone, w] of CHAIN) {
        buf.addRot(bone, pitch * w * engage, yaw * w * engage, 0);
      }
    },
  };
}
