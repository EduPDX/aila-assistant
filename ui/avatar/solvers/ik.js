// ============================================================
//  SOLVER: IK de braço (2 ossos, analítico).
//
//  Roda DEPOIS do applyBones() (pose FK aplicada + matrizes atualizadas).
//  Em vez de girar upperArm/lowerArm à mão, move-se só o ALVO da mão e o IK
//  resolve o cotovelo. Base p/ a F3 (colisão empurra o alvo p/ fora do corpo).
//
//  Método: posição analítica do cotovelo (lei dos cossenos) + alinhamento de
//  direção por quaternion (agnóstico ao eixo do osso → vale p/ qualquer VRM).
// ============================================================
import * as THREE from 'three';

export function createArmIK() {
  // temporários reusados (zero-GC)
  const S = new THREE.Vector3(), E = new THREE.Vector3(), H = new THREE.Vector3();
  const T = new THREE.Vector3(), axis = new THREE.Vector3(), foot = new THREE.Vector3();
  const pole = new THREE.Vector3(), proj = new THREE.Vector3(), elbow = new THREE.Vector3();
  const bodyRight = new THREE.Vector3(), bodyUp = new THREE.Vector3(), bodyFwd = new THREE.Vector3();
  const lShoulder = new THREE.Vector3(), rShoulder = new THREE.Vector3();
  const hips = new THREE.Vector3(), neck = new THREE.Vector3();
  const poleState = { left: new THREE.Vector3(), right: new THREE.Vector3() };
  const poleReady = { left: false, right: false };
  const dCur = new THREE.Vector3(), dWant = new THREE.Vector3();
  const na = new THREE.Vector3(), nb = new THREE.Vector3();
  const qDelta = new THREE.Quaternion(), qWorld = new THREE.Quaternion(), qPar = new THREE.Quaternion();
  const qFk = new THREE.Quaternion();
  // orientação do punho (roll): temporários
  const refA = new THREE.Vector3(), refW = new THREE.Vector3(), dirW = new THREE.Vector3();
  const rp = new THREE.Vector3(), dp = new THREE.Vector3(), axisW = new THREE.Vector3(), cw = new THREE.Vector3();
  const kn = new THREE.Vector3(), fg = new THREE.Vector3();

  // gira o osso p/ que a direção `from` (mundo) aponte p/ `to` (mundo)
  function align(node, from, to, weight) {
    if (from.lengthSq() < 1e-8 || to.lengthSq() < 1e-8) return;
    na.copy(from).normalize(); nb.copy(to).normalize();
    qDelta.setFromUnitVectors(na, nb);
    node.getWorldQuaternion(qWorld);
    qWorld.premultiply(qDelta);                 // nova orientação de mundo
    node.parent.getWorldQuaternion(qPar);
    qWorld.premultiply(qPar.invert());          // -> local (relativo ao pai)
    if (weight >= 0.999) node.quaternion.copy(qWorld);
    else { qFk.copy(node.quaternion); node.quaternion.slerpQuaternions(qFk, qWorld, weight); }
    node.updateWorldMatrix(false, true);        // propaga p/ os filhos (cotovelo/mão)
  }

  // vetor de referência da MÃO (mundo): 'thumb' = direção do polegar;
  // 'palm' = normal da palma (linha dos nós × direção dos dedos). Derivado do rig.
  function handRefVec(rig, side, refType, handW, out) {
    if (refType === 'thumb') {
      const m = rig.bone(side + 'ThumbMetacarpal'), d = rig.bone(side + 'ThumbDistal');
      if (m && d) {
        out.setFromMatrixPosition(d.matrixWorld);
        refA.setFromMatrixPosition(m.matrixWorld);
        return out.sub(refA);
      }
    }
    const ip = rig.bone(side + 'IndexProximal'), lp = rig.bone(side + 'LittleProximal'), mp = rig.bone(side + 'MiddleProximal');
    if (ip && lp && mp) {
      kn.setFromMatrixPosition(ip.matrixWorld);
      refA.setFromMatrixPosition(lp.matrixWorld);
      kn.sub(refA);                                      // linha dos nós (index - little)
      fg.setFromMatrixPosition(mp.matrixWorld).sub(handW);
      return out.crossVectors(kn, fg);                   // normal da palma
    }
    return out.set(0, 0, 0);
  }

  // rola a MÃO em torno do antebraço p/ alinhar sua referência (ref) à direção
  // desejada (dir, mundo). Não muda a POSIÇÃO da mão — só o "twist" do punho.
  function rollWrist(rig, side, hand, elbowW, handW, orient) {
    axisW.copy(handW).sub(elbowW);
    if (axisW.lengthSq() < 1e-8) return;
    axisW.normalize();
    handRefVec(rig, side, orient.ref, handW, refW);
    dirW.set(orient.dir[0], orient.dir[1], orient.dir[2]);
    rp.copy(refW).addScaledVector(axisW, -refW.dot(axisW));   // ref ⟂ eixo
    dp.copy(dirW).addScaledVector(axisW, -dirW.dot(axisW));   // dir ⟂ eixo
    if (rp.lengthSq() < 1e-8 || dp.lengthSq() < 1e-8) return;
    rp.normalize(); dp.normalize();
    cw.crossVectors(rp, dp);
    // A solução de roll possui duas respostas equivalentes perto de 180°.
    // Limitar a correção evita que a palma dê uma volta completa entre frames.
    const raw = Math.atan2(cw.dot(axisW), rp.dot(dp));
    const maxRoll = THREE.MathUtils.degToRad(110);
    const angle = THREE.MathUtils.clamp(raw, -maxRoll, maxRoll) * (orient.weight ?? 1);
    qDelta.setFromAxisAngle(axisW, angle);
    hand.getWorldQuaternion(qWorld);
    qWorld.premultiply(qDelta);
    hand.parent.getWorldQuaternion(qPar);
    qWorld.premultiply(qPar.invert());
    hand.quaternion.copy(qWorld);
    hand.updateWorldMatrix(false, true);
  }

  return {
    name: 'ik-arm',
    solve(rig, buf, ctx = null, dt = 1 / 60) {
      // Frame corporal medido no próprio VRM: direita, cima e frente.
      const l = rig.bone('leftUpperArm'), r = rig.bone('rightUpperArm');
      const hp = rig.bone('hips'), nk = rig.bone('neck');
      if (l && r && hp && nk) {
        lShoulder.setFromMatrixPosition(l.matrixWorld);
        rShoulder.setFromMatrixPosition(r.matrixWorld);
        hips.setFromMatrixPosition(hp.matrixWorld);
        neck.setFromMatrixPosition(nk.matrixWorld);
        bodyRight.copy(rShoulder).sub(lShoulder).normalize();
        bodyUp.copy(neck).sub(hips).normalize();
        bodyFwd.copy(bodyUp).cross(bodyRight).normalize();
      } else {
        bodyRight.set(1, 0, 0); bodyUp.set(0, 1, 0); bodyFwd.set(0, 0, 1);
      }

      for (const [side, tgt] of buf.ik) {
        const shoulder = rig.bone(side + 'Shoulder');
        const upper = rig.bone(side + 'UpperArm');
        const lower = rig.bone(side + 'LowerArm');
        const hand = rig.bone(side + 'Hand');
        if (!upper || !lower || !hand) continue;

        // Clavícula acompanha discretamente a direção da mão. Isso amplia o
        // alcance alto sem deformar o upperArm nem criar um ombro rígido.
        if (shoulder) {
          shoulder.getWorldPosition(S);
          upper.getWorldPosition(E);
          T.set(tgt.x, tgt.y, tgt.z);
          const assist = Math.min(0.18, (tgt.weight ?? 1) * 0.18);
          align(shoulder, dCur.copy(E).sub(S), dWant.copy(T).sub(S), assist);
        }

        S.setFromMatrixPosition(upper.matrixWorld);
        E.setFromMatrixPosition(lower.matrixWorld);
        H.setFromMatrixPosition(hand.matrixWorld);
        const L1 = S.distanceTo(E), L2 = E.distanceTo(H);
        if (L1 < 1e-4 || L2 < 1e-4) continue;

        // alvo com alcance limitado (evita esticão/hiperextensão)
        T.set(tgt.x, tgt.y, tgt.z);
        axis.copy(T).sub(S);
        let d = axis.length();
        const armLen = L1 + L2;
        const dMax = armLen * 0.97;
        const dMin = Math.max(Math.abs(L1 - L2) * 1.02, armLen * 0.16);
        d = Math.max(dMin, Math.min(dMax, d));
        axis.normalize();

        // posição analítica do cotovelo (lei dos cossenos)
        const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d);
        const h = Math.sqrt(Math.max(0, L1 * L1 - a * a));
        foot.copy(S).addScaledVector(axis, a);
        // Pólo ESPELHADO no frame corporal: cotovelo abre para fora, desce um
        // pouco e recua. O vetor anterior era igual nos dois lados e podia
        // escolher o lado errado do plano, especialmente em VRM 1 estreitos.
        const mir = side === 'left' ? -1 : 1;
        pole.set(0, 0, 0)
          .addScaledVector(bodyRight, mir * 0.82)
          .addScaledVector(bodyUp, -0.34)
          .addScaledVector(bodyFwd, -0.24);
        proj.copy(pole).addScaledVector(axis, -pole.dot(axis));  // perpendicular ao eixo
        if (proj.lengthSq() < 1e-6) proj.set(side === 'left' ? 1 : -1, 0, 0);
        proj.normalize();
        // Continuidade temporal impede o pole de trocar de hemisfério quando o
        // braço passa perto de uma singularidade (esticado quase por completo).
        const ps = poleState[side];
        if (!poleReady[side]) { ps.copy(proj); poleReady[side] = true; }
        if (ps.dot(proj) < 0) proj.negate();
        ps.lerp(proj, Math.min(1, Math.max(0.05, dt * 12))).normalize();
        elbow.copy(foot).addScaledVector(ps, h);

        const w = tgt.weight ?? 1;
        // 1) upperArm: direção atual (S->E) -> desejada (S->cotovelo)
        align(upper, dCur.copy(E).sub(S), dWant.copy(elbow).sub(S), w);
        // 2) lowerArm: recomputa E/H pós-rotação e aponta a mão p/ o alvo
        E.setFromMatrixPosition(lower.matrixWorld);
        H.setFromMatrixPosition(hand.matrixWorld);
        align(lower, dCur.copy(H).sub(E), dWant.copy(T).sub(E), w);
        // 3) orientação do punho (opcional): rola a mão em torno do antebraço
        if (tgt.orient) {
          E.setFromMatrixPosition(lower.matrixWorld);
          H.setFromMatrixPosition(hand.matrixWorld);
          rollWrist(rig, side, hand, E, H, tgt.orient);
        }
      }
    },
  };
}
