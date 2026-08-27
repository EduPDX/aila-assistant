// ============================================================
//  SOLVER: JointLimits — limites anatômicos por junta.
//
//  Roda DEPOIS de todas as camadas e ANTES do commit. Clampa a rotação
//  final (normalizada, padronizada pelo VRM) de cada osso pra evitar:
//    - hiperextensão de cotovelo;
//    - braço atravessando o tronco;
//    - rotações impossíveis de pescoço/cabeça.
//
//  Valores GENEROSOS: contêm todas as poses/gestos atuais e só cortam o
//  patológico. São em radianos, no frame normalizado do VRM (T-pose padrão),
//  por isso valem p/ qualquer modelo.
// ============================================================
const D = Math.PI / 180;
const R = (a, b) => [a * D, b * D];   // graus -> [min,max] rad

// { bone: { x:[min,max], y:[...], z:[...] } }  (eixos ausentes = livres)
const LIMITS = {
  // ombro/braço: z mantém o braço "pra baixo/frente"; impede cruzar o tronco
  rightUpperArm: { x: R(-110, 45), y: R(-70, 70), z: R(38, 205) },
  leftUpperArm:  { x: R(-110, 45), y: R(-70, 70), z: R(-205, -38) },
  // cotovelo: x negativo dobra; o teto perto de 0 impede hiperextensão
  rightLowerArm: { x: R(-135, 18), y: R(-90, 90), z: R(-40, 40) },
  leftLowerArm:  { x: R(-135, 18), y: R(-90, 90), z: R(-40, 40) },
  // mãos: leve
  rightHand: { x: R(-45, 45), y: R(-45, 45), z: R(-45, 45) },
  leftHand:  { x: R(-45, 45), y: R(-45, 45), z: R(-45, 45) },
  // cabeça/pescoço: amplitude humana
  head: { x: R(-42, 42), y: R(-62, 62), z: R(-32, 32) },
  neck: { x: R(-24, 24), y: R(-30, 30), z: R(-18, 18) },
  // tronco: pequeno
  spine:      { x: R(-16, 16), y: R(-16, 16), z: R(-14, 14) },
  chest:      { x: R(-14, 14), y: R(-14, 14), z: R(-12, 12) },
  upperChest: { x: R(-12, 12), y: R(-12, 12), z: R(-10, 10) },
  hips:       { x: R(-10, 10), y: R(-14, 14), z: R(-12, 12) },
};

const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);

export function createJointLimits() {
  return {
    name: 'joint-limits',
    solve(rig, buf) {
      // Modelos montados "ao contrário" giram o braço no sentido oposto
      // (rig.armZSign = -1). Os limites de Z dos BRAÇOS precisam espelhar junto,
      // senão eles cortam a pose de descanso e a avatar fica de braços levantados.
      const sz = rig && rig.armZSign === -1 ? -1 : 1;
      for (const [bone, lim] of Object.entries(LIMITS)) {
        const v = buf.rot.get(bone);
        if (!v) continue;
        if (lim.x) v[0] = clamp(v[0], lim.x[0], lim.x[1]);
        if (lim.y) v[1] = clamp(v[1], lim.y[0], lim.y[1]);
        if (lim.z) {
          const flip = sz === -1 && (bone.endsWith('UpperArm') || bone.endsWith('LowerArm'));
          const lo = flip ? -lim.z[1] : lim.z[0];
          const hi = flip ? -lim.z[0] : lim.z[1];
          v[2] = clamp(v[2], lo, hi);
        }
      }
    },
  };
}
