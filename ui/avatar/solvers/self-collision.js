// ============================================================
//  SOLVER: Auto-colisão — impede a mão/braço de atravessar o corpo.
//
//  Cápsulas/esferas simplificadas (SEM colisão por malha) montadas a partir
//  dos ossos, com raio proporcional à escala do modelo (largura de ombros).
//  PROATIVO (Fase D): roda ANTES do IK e constrange o ALVO DA MÃO — empurra o
//  alvo p/ fora dos colliders, o IK resolve UMA vez p/ o alvo já seguro. Evita
//  o ciclo IK↔colisão. Suavização (damp) + histerese p/ não "pipocar".
// ============================================================
import * as THREE from 'three';
import { damp } from '../rig-core.js';

export function createSelfCollision() {
  const V = () => new THREE.Vector3();
  const hips = V(), neck = V(), head = V(), lLeg = V(), lKnee = V(), rLeg = V(), rKnee = V();
  const lU = V(), rU = V(), center = V(), bodyRight = V();
  const cp = V(), d = V(), ab = V(), ap = V(), P = V();
  // pool de colliders reusado (type 0=esfera[a,r], 1=cápsula[a,b,r])
  const pool = []; for (let i = 0; i < 6; i++) pool.push({ type: 0, a: V(), b: V(), r: 0 });
  let nCol = 0, sw = 0;   // sw = largura de ombros (escala do corpo), setada por build()
  const state = { left: { on: false, t: V() }, right: { on: false, t: V() } };

  const wpos = (rig, name, out) => { const b = rig.bone(name); return b ? out.setFromMatrixPosition(b.matrixWorld) : null; };
  const addSphere = (c, r) => { const o = pool[nCol++]; o.type = 0; o.a.copy(c); o.r = r; };
  const addCapsule = (a, b, r) => { const o = pool[nCol++]; o.type = 1; o.a.copy(a); o.b.copy(b); o.r = r; };

  // empurra P p/ fora de uma esfera (C,r); devolve profundidade (>0 se empurrou)
  function pushSphere(p, C, r) {
    d.copy(p).sub(C); const len = d.length();
    if (len >= r) return 0;
    if (len < 1e-6) {
      d.copy(bodyRight); if (d.lengthSq() < 1e-8) d.set(1, 0, 0);
      p.copy(C).addScaledVector(d.normalize(), r);
      return r;
    }
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

  // monta os colliders do frame a partir dos ossos (raios ∝ escala do corpo).
  // Separado do solve() p/ o Debug Mode poder visualizá-los mesmo sem gesto.
  function build(rig) {
    if (!wpos(rig, 'hips', hips) || !wpos(rig, 'leftUpperArm', lU) || !wpos(rig, 'rightUpperArm', rU)) return false;
    sw = lU.distanceTo(rU);                  // largura de ombros → escala do corpo
    if (sw < 1e-4) return false;
    center.copy(lU).add(rU).multiplyScalar(0.5);
    bodyRight.copy(rU).sub(lU).normalize();
    wpos(rig, 'neck', neck); wpos(rig, 'head', head);
    const legs = wpos(rig, 'leftUpperLeg', lLeg) && wpos(rig, 'leftLowerLeg', lKnee)
              && wpos(rig, 'rightUpperLeg', rLeg) && wpos(rig, 'rightLowerLeg', rKnee);
    nCol = 0;
    addCapsule(hips, neck, sw * 0.36);       // tronco
    addSphere(hips, sw * 0.40);              // pelve
    addSphere(head, sw * 0.38);              // cabeça
    if (legs) { addCapsule(lLeg, lKnee, sw * 0.26); addCapsule(rLeg, rKnee, sw * 0.26); }
    return true;
  }

  return {
    name: 'self-collision',
    // DEBUG (P0): reconstrói e devolve os colliders p/ visualização (read-only).
    colliders(rig) { return build(rig) ? pool.slice(0, nCol) : []; },
    solve(rig, buf, ctx, dt) {
      if (!build(rig)) return;

      // PROATIVO: constrange o ALVO DA MÃO (empurra p/ fora do corpo) ANTES do
      // IK, preservando orientação/peso. Só age nos alvos que existem (buf.ik).
      // Damp + histerese p/ estabilidade (converge, sem loop IK↔colisão).
      for (const [side, tgt] of buf.ik) {
        P.set(tgt.x, tgt.y, tgt.z);
        // Não deixa a mão atravessar o plano central do tronco. Uma margem
        // pequena mantém gestos próximos ao rosto possíveis sem inverter lado.
        const mir = side === 'left' ? -1 : 1;
        const lateral = d.copy(P).sub(center).dot(bodyRight) * mir;
        const minLateral = sw * 0.08;
        const planePush = lateral < minLateral ? minLateral - lateral : 0;
        if (planePush) P.addScaledVector(bodyRight, planePush * mir);
        const pushed = planePush + resolve(P);        // empurra o alvo p/ fora dos colliders
        const st = state[side];
        if (pushed > 0.0005) {
          if (!st.on) { st.on = true; st.t.set(tgt.x, tgt.y, tgt.z); }   // parte do alvo (sem pulo)
          st.t.set(damp(st.t.x, P.x, 16, dt), damp(st.t.y, P.y, 16, dt), damp(st.t.z, P.z, 16, dt));
          buf.setHandTarget(side, st.t.x, st.t.y, st.t.z, tgt.weight, tgt.orient);
        } else if (st.on) {                            // relaxa: volta suave ao alvo original
          st.t.set(damp(st.t.x, tgt.x, 12, dt), damp(st.t.y, tgt.y, 12, dt), damp(st.t.z, tgt.z, 12, dt));
          if (st.t.distanceTo(P) < sw * 0.03) st.on = false;
          else buf.setHandTarget(side, st.t.x, st.t.y, st.t.z, tgt.weight, tgt.orient);
        }
      }
    },
  };
}
