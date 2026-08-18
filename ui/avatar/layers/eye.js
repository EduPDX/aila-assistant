// CAMADA: Eye — para onde ela olha. Sacadas (micro-saltos), foco por estado e
//  olhar aleatório discreto. Produz o alvo dos OLHOS (VRM lookAt) e a "vontade"
//  de olhar (yaw/pitch) que a LookAtLayer distribui pelo corpo.
//  Fase 4: se ctx.gazeWorld estiver setado, olha ESSE ponto do mundo (converte a
//  direção p/ o frame local do avatar → yaw/pitch); senão, o comportamento normal.
import * as THREE from 'three';

const _clamp = (v, a, b) => (v < a ? a : v > b ? b : v);

export function createEyeLayer() {
  const g = { yaw: 0, pitch: 0, tYaw: 0, tPitch: 0, saccade: 0 };
  const r = () => Math.random();
  const _head = new THREE.Vector3(), _dir = new THREE.Vector3(), _q = new THREE.Quaternion();

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
      // Fase 4: olhar dirigido a um ponto do MUNDO (ex.: o painel que ela aponta)
      if (ctx.gazeWorld) {
        const hp = rig.boneWorld('head', _head);
        const gw = ctx.gazeWorld;
        if (hp) {
          _dir.set(gw.x - hp.x, gw.y - hp.y, gw.z - hp.z).normalize();
          rig.vrm.scene.getWorldQuaternion(_q).invert();   // → frame local do avatar
          _dir.applyQuaternion(_q);
          g.tYaw = _clamp(Math.atan2(_dir.x, _dir.z), -0.9, 0.9);
          g.tPitch = _clamp(-Math.asin(_clamp(_dir.y, -1, 1)), -0.5, 0.5);
        }
        const k = Math.min(1, dt * 7);
        g.yaw += (g.tYaw - g.yaw) * k;
        g.pitch += (g.tPitch - g.pitch) * k;
        buf.setGaze(gw.x, gw.y, gw.z);                 // olhos exatamente no alvo real
        ctx.gaze.yaw = g.yaw; ctx.gaze.pitch = g.pitch;
        return;
      }

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
