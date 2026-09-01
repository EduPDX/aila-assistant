// ============================================================
//  INTERACTION MANAGER — traduz {type, target} em GESTO real usando os sistemas
//  EXISTENTES: resolve a posição de mundo da âncora (scene) → aponta o braço na
//  direção dela via o IK do controller (setHandTarget) + pose de dedo
//  (setHandPose). NÃO cria IK novo: só fornece alvos. Solta sozinho após o hold.
//
//  Importante: as telas ficam a ~1-2 m (fora do alcance do braço). Então NÃO
//  mandamos a mão até a tela — mandamos p/ um ponto ALCANÇÁVEL na DIREÇÃO do
//  alvo (ombro + dir*reach), o que lê como "apontando para". (Gaze vem na F4.)
// ============================================================
import * as THREE from 'three';
import { INTERACTIONS, DEFAULT_INTERACTION } from './interaction-types.js';

export function createInteractionManager({ resolveWorld, getController }) {
  const _t = new THREE.Vector3(), _s = new THREE.Vector3(), _d = new THREE.Vector3();
  let active = null;   // { side, hold, attentionId }

  function interact({ type = 'point', target } = {}) {
    const c = getController();
    if (!c || !c.rig || !target) return false;
    const pos = resolveWorld(target, _t);
    if (!pos) return false;
    const cfg = INTERACTIONS[type] || DEFAULT_INTERACTION;
    // lado: alvo à esquerda do avatar → mão esquerda (as telas ficam à esquerda)
    const rootX = c.rig.vrm?.scene?.position?.x ?? 0;
    const side = pos.x <= rootX ? 'left' : 'right';
    const shoulder = c.rig.boneWorld(side + 'UpperArm', _s);
    if (!shoulder) return false;
    _d.copy(pos).sub(shoulder);
    const dist = _d.length() || 1;
    _d.multiplyScalar(cfg.reach / dist);              // direção do alvo, alcance do braço
    c.setHandTarget(side, shoulder.x + _d.x, shoulder.y + _d.y, shoulder.z + _d.z, 1);
    c.setHandPose(side, cfg.pose);
    const attention = c.setGazeWorld?.(pos.x, pos.y, pos.z, { source: 'interaction', hold: cfg.hold });
    active = { side, hold: cfg.hold, attentionId: attention?.id || 0 };
    return true;
  }

  function update(dt) {
    if (!active) return;
    active.hold -= dt;
    if (active.hold <= 0) stop();
  }

  function stop() {
    const c = getController();
    if (c && active) {
      c.clearHandTarget?.(); c.setHandPose?.(active.side, 'relaxed');
      c.clearGazeWorld?.(active.attentionId, 'interaction');
    }
    active = null;
  }

  return { interact, update, stop, isActive: () => !!active };
}
