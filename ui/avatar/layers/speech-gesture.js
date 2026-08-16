// CAMADA: Speech Gesture — gesticulação da fala, CONTROLADA (Fase E).
//
//  Substitui o antigo "fala → seno → braços" (removido na Fase A). Aqui a fala
//  gera GESTOS OCASIONAIS por IK, alternando REPOUSO ↔ pequeno gesto ↔ repouso
//  (uma pessoa falando passa MUITO tempo com os braços parados). A amplitude vem
//  de emoção × intensidade × ritmo × envelope de fala. Só age enquanto ela fala
//  E não há gesto explícito (aí o gesto manda). Usa alvo de mão + IK (não FK).
import * as THREE from 'three';

export function createSpeechGestureLayer() {
  const V = () => new THREE.Vector3();
  const RU = V(), LU = V(), NK = V(), HP = V(), right = V(), up = V(), fwd = V();
  const S = V(), E = V(), H = V(), off = V(), world = V();
  const w = { left: 0, right: 0 };           // peso de IK por lado (ramp)
  let phaseT = 0, active = false, side = 'right', seed = 0;

  const wp = (rig, n, o) => { const b = rig.bone(n); return b ? o.setFromMatrixPosition(b.matrixWorld) : null; };
  const rand = (a, b) => a + Math.random() * (b - a);

  return {
    name: 'speech-gesture',
    update(rig, buf, ctx, dt) {
      const speaking = ctx.speech > 0.08 && ctx.gesture === 'rest' && !ctx.handTarget;
      // expressividade (emoção × intensidade × ritmo), limitada
      const expr = Math.max(0.4, Math.min(1.4, (ctx.emotion?.amp ?? 1) * (ctx.intensity ?? 1) * (ctx.motion?.amp ?? 1)));

      // máquina de fases: REPOUSO (longo) ↔ GESTO (curto)
      phaseT -= dt;
      if (phaseT <= 0) {
        if (active) { active = false; phaseT = rand(2.0, 5.0); }          // repouso 2-5s
        else if (speaking) {                                              // começa um gesto curto
          active = true; phaseT = rand(0.8, 1.8); seed = Math.random() * 10;
          const r = Math.random(); side = r < 0.4 ? 'right' : r < 0.75 ? 'left' : 'both';
        } else { phaseT = 0.3; }
      }
      if (!speaking) active = false;                                       // parou de falar → repouso

      // frame do avatar (do rig)
      if (!wp(rig, 'rightUpperArm', RU) || !wp(rig, 'leftUpperArm', LU)
        || !wp(rig, 'neck', NK) || !wp(rig, 'hips', HP)) return;
      right.copy(RU).sub(LU).normalize();
      up.copy(NK).sub(HP).normalize();
      fwd.copy(up).cross(right).normalize();

      const size = 0.5 + 0.5 * (expr / 1.4);          // gesto maior qdo mais expressiva
      const osc = expr * Math.min(1, ctx.speech);     // vivacidade da oscilação
      const t = ctx.t;

      for (const s of ['left', 'right']) {
        const sActive = active && (side === s || side === 'both');
        w[s] += ((sActive ? 1 : 0) - w[s]) * Math.min(1, dt * 6);
        if (w[s] < 0.02) continue;
        const upper = rig.bone(s + 'UpperArm'), lower = rig.bone(s + 'LowerArm'), hand = rig.bone(s + 'Hand');
        if (!upper || !lower || !hand) continue;
        S.setFromMatrixPosition(upper.matrixWorld);
        E.setFromMatrixPosition(lower.matrixWorld);
        H.setFromMatrixPosition(hand.matrixWorld);
        const armLen = S.distanceTo(E) + E.distanceTo(H);
        const mir = s === 'left' ? -1 : 1;
        // alvo: antebraço à frente/cima (base) + oscilação sutil (osc)
        const ox = (0.16 * size + 0.05 * osc * Math.sin(t * 2.1 + seed)) * mir;
        const oy = (0.02 * size + 0.06 * osc * Math.sin(t * 1.7 + seed + 1));
        const oz = (0.42 * size + 0.07 * osc * Math.sin(t * 2.6 + seed + 2));
        off.set(0, 0, 0)
          .addScaledVector(right, ox * armLen)
          .addScaledVector(up, oy * armLen)
          .addScaledVector(fwd, oz * armLen);
        world.copy(S).add(off);
        buf.setHandTarget(s, world.x, world.y, world.z, w[s]);
        ctx.handPose[s] = 'relaxed';
      }
    },
  };
}
