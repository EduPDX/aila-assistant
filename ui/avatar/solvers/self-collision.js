// ============================================================
//  SOLVER: Auto-colisão — impede a mão/braço de atravessar o corpo.
//
//  Cápsulas/esferas simplificadas (SEM colisão por malha) montadas a partir
//  dos ossos, com raio proporcional à escala do modelo (largura de ombros).
//  Roda após applyBones()+updateMatrices(): amostra mão e antebraço, empurra
//  o ALVO DA MÃO p/ fora dos colliders e deixa o IK (F2) resolver o braço.
//  Suavização (damp) + histerese p/ não "pipocar" ao entrar/sair da colisão.
// ============================================================
import * as THREE from 'three';
import { damp } from '../rig-core.js';

export function createSelfCollision() {
  const V = () => new THREE.Vector3();
  const hips = V(), neck = V(), head = V(), lLeg = V(), lKnee = V(), rLeg = V(), rKnee = V();
  const lU = V(), rU = V();
  const cp = V(), d = V(), ab = V(), ap = V(), hand = V(), elbow = V(), mid = V(), want = V(), P = V();
  // pool de colliders reusado (type 0=esfera[a,r], 1=cápsula[a,b,r])
  const pool = []; for (let i = 0; i < 6; i++) pool.push({ type: 0, a: V(), b: V(), r: 0 });
  let nCol = 0;
  const state = { left: { on: false, t: V() }, right: { on: false, t: V() } };

  const wpos = (rig, name, out) => { const b = rig.bone(name); return b ? out.setFromMatrixPosition(b.matrixWorld) : null; };
  const addSphere = (c, r) => { const o = pool[nCol++]; o.type = 0; o.a.copy(c); o.r = r; };
  const addCapsule = (a, b, r) => { const o = pool[nCol++]; o.type = 1; o.a.copy(a); o.b.copy(b); o.r = r; };

  // empurra P p/ fora de uma esfera (C,r); devolve profundidade (>0 se empurrou)
  function pushSphere(p, C, r) {
    d.copy(p).sub(C); const len = d.length();
    if (len >= r || len < 1e-6) return 0;
    p.copy(C).addScaledVector(d, r / len);
    return r - len;
  }
  function pushCapsule(p, A, B, r) {
    ab.copy(B).sub(A); const L2 = ab.lengthSq();
    const t = L2 < 1e-8 ? 0 : Math.max(0, Math.min(1, ap.copy(p).sub(A).dot(ab) / L2));
    cp.copy(A).addScaledVector(ab, t);
    return pushSphere(p, cp, r);
  }
  function resolve(p) {   // empurra p p/ fora de todos os colliders (2 passes p/ estabilizar)
    let pushed = 0;
    for (let pass = 0; pass < 2; pass++)
      for (let i = 0; i < nCol; i++) {
        const c = pool[i];
        pushed += c.type === 0 ? pushSphere(p, c.a, c.r) : pushCapsule(p, c.a, c.b, c.r);
      }
    return pushed;
  }

  return {
    name: 'self-collision',
    solve(rig, buf, ctx, dt) {
      if (!wpos(rig, 'hips', hips) || !wpos(rig, 'leftUpperArm', lU) || !wpos(rig, 'rightUpperArm', rU)) return;
      const sw = lU.distanceTo(rU);           // largura de ombros → escala do corpo
      if (sw < 1e-4) return;
      wpos(rig, 'neck', neck); wpos(rig, 'head', head);
      const legs = wpos(rig, 'leftUpperLeg', lLeg) && wpos(rig, 'leftLowerLeg', lKnee)
                && wpos(rig, 'rightUpperLeg', rLeg) && wpos(rig, 'rightLowerLeg', rKnee);

      // monta os colliders do frame (raios proporcionais à escala; justos p/
      // só pegar penetração real e não "inchar" a gesticulação)
      nCol = 0;
      addCapsule(hips, neck, sw * 0.36);      // tronco
      addSphere(hips, sw * 0.40);             // pelve
      addSphere(head, sw * 0.38);             // cabeça
      if (legs) { addCapsule(lLeg, lKnee, sw * 0.26); addCapsule(rLeg, rKnee, sw * 0.26); }

      for (const side of ['left', 'right']) {
        if (!wpos(rig, side + 'Hand', hand) || !wpos(rig, side + 'LowerArm', elbow)) continue;
        mid.copy(hand).add(elbow).multiplyScalar(0.5);
        P.copy(hand); const handPush = resolve(P); want.copy(P);           // mão p/ fora
        P.copy(mid); const midPush = resolve(P);
        if (midPush > 0) { ap.copy(P).sub(mid); want.addScaledVector(ap, 0.5); }  // antebraço: metade

        const st = state[side];
        if (handPush + midPush > 0.0005) {
          if (!st.on) { st.on = true; st.t.copy(hand); }                  // parte da posição atual (sem pulo)
          st.t.set(damp(st.t.x, want.x, 14, dt), damp(st.t.y, want.y, 14, dt), damp(st.t.z, want.z, 14, dt));
          buf.setHandTarget(side, st.t.x, st.t.y, st.t.z, 1);
        } else if (st.on) {                                               // solta suave
          st.t.set(damp(st.t.x, hand.x, 10, dt), damp(st.t.y, hand.y, 10, dt), damp(st.t.z, hand.z, 10, dt));
          if (st.t.distanceTo(hand) < sw * 0.05) st.on = false;
          else buf.setHandTarget(side, st.t.x, st.t.y, st.t.z, 1);
        }
      }
    },
  };
}
