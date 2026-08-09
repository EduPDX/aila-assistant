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
  const dCur = new THREE.Vector3(), dWant = new THREE.Vector3();
  const na = new THREE.Vector3(), nb = new THREE.Vector3();
  const qDelta = new THREE.Quaternion(), qWorld = new THREE.Quaternion(), qPar = new THREE.Quaternion();
  const qFk = new THREE.Quaternion();

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

  return {
    name: 'ik-arm',
    solve(rig, buf) {
      for (const [side, tgt] of buf.ik) {
        const upper = rig.bone(side + 'UpperArm');
        const lower = rig.bone(side + 'LowerArm');
        const hand = rig.bone(side + 'Hand');
        if (!upper || !lower || !hand) continue;

        S.setFromMatrixPosition(upper.matrixWorld);
        E.setFromMatrixPosition(lower.matrixWorld);
        H.setFromMatrixPosition(hand.matrixWorld);
        const L1 = S.distanceTo(E), L2 = E.distanceTo(H);
        if (L1 < 1e-4 || L2 < 1e-4) continue;

        // alvo com alcance limitado (evita esticão/hiperextensão)
        T.set(tgt.x, tgt.y, tgt.z);
        axis.copy(T).sub(S);
        let d = axis.length();
        const dMax = (L1 + L2) * 0.995, dMin = Math.abs(L1 - L2) * 1.02;
        d = Math.max(dMin, Math.min(dMax, d));
        axis.normalize();

        // posição analítica do cotovelo (lei dos cossenos)
        const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d);
        const h = Math.sqrt(Math.max(0, L1 * L1 - a * a));
        foot.copy(S).addScaledVector(axis, a);
        // pólo: cotovelo aponta p/ baixo e levemente p/ trás (natural)
        pole.set(0, -1, -0.35);
        proj.copy(pole).addScaledVector(axis, -pole.dot(axis));  // perpendicular ao eixo
        if (proj.lengthSq() < 1e-6) proj.set(side === 'left' ? 1 : -1, 0, 0);
        proj.normalize();
        elbow.copy(foot).addScaledVector(proj, h);

        const w = tgt.weight ?? 1;
        // 1) upperArm: direção atual (S->E) -> desejada (S->cotovelo)
        align(upper, dCur.copy(E).sub(S), dWant.copy(elbow).sub(S), w);
        // 2) lowerArm: recomputa E/H pós-rotação e aponta a mão p/ o alvo
        E.setFromMatrixPosition(lower.matrixWorld);
        H.setFromMatrixPosition(hand.matrixWorld);
        align(lower, dCur.copy(H).sub(E), dWant.copy(T).sub(E), w);
      }
    },
  };
}
