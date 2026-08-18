// ============================================================
//  STAGE COMPOSER — a "composição" da cena: coloca o monitor relativo ao
//  avatar, gira o corpo da Aila em DIAGONAL (sutil na Fase 1 — a virada forte
//  com compensação de cabeça vem com o gaze, Fase 4) e enquadra a câmera para
//  o usuário ver rosto + corpo + mãos + monitor (nunca de costas).
//
//  Guarda o estado original da câmera/controls e do root do avatar → reset()
//  restaura 100% (revertível). Números são de calibração.
// ============================================================
import * as THREE from 'three';

export class StageComposer {
  constructor(camera, controls) {
    this.camera = camera; this.controls = controls;
    this._applied = false;
    this._savedYaw = 0; this._vrm = null;
  }

  /** posiciona as telas + gira o avatar + enquadra a câmera para o "palco". */
  compose(vrm, monitorGroup, ring, statusGroup) {
    if (!vrm) return;
    const box = new THREE.Box3().setFromObject(vrm.scene);
    if (box.isEmpty()) return;
    const c = box.getCenter(new THREE.Vector3());
    const feetY = box.min.y, topY = box.max.y, h = topY - feetY;
    const eyeY = feetY + h * 0.86;          // ~altura dos olhos
    const s = Math.max(0.7, Math.min(1.4, h / 1.5));   // escala com a altura do modelo

    // anel do palco sob os pés
    if (ring) ring.position.set(c.x, feetY + 0.002, c.z);

    // monitor PRINCIPAL (cognitivo): à frente-esquerda, virado p/ o espaço entre
    // a Aila e a câmera (ela trabalha "de lado" nele).
    if (monitorGroup) {
      monitorGroup.position.set(c.x - h * 0.60, eyeY - h * 0.02, c.z + h * 0.42);
      monitorGroup.rotation.set(0, 0.5, 0);
      monitorGroup.scale.setScalar(s);
    }
    // segunda tela (STATUS): mais à esquerda, virada MAIS p/ a câmera → forma uma
    // "estação de trabalho" de duas telas em torno da Aila.
    if (statusGroup) {
      statusGroup.position.set(c.x - h * 1.28, eyeY - h * 0.03, c.z + h * 0.14);
      statusGroup.rotation.set(0, 0.82, 0);
      statusGroup.scale.setScalar(s * 0.95);
    }

    // vira o CORPO ~13° para as telas (diagonal sutil; a virada forte com
    // compensação de cabeça vem no gaze/Fase 4). Olhos seguem o usuário via lookAt.
    if (!this._applied) this._savedYaw = vrm.scene.rotation.y;
    this._vrm = vrm;
    vrm.scene.rotation.y = this._savedYaw - 0.22;

    // câmera: à direita e afastada o bastante p/ caber as DUAS telas + a Aila,
    // ainda vendo o rosto (3/4). Respeita o zoom/órbita depois.
    const fov = this.camera.fov * Math.PI / 180;
    const fitH = (h * 0.9) / Math.tan(fov / 2);
    const dist = Math.max(fitH, 1.5) * 1.12;
    this.controls.target.set(c.x - h * 0.40, eyeY - h * 0.10, c.z + h * 0.12);
    this.camera.position.set(c.x + h * 0.30, eyeY - h * 0.02, c.z + dist);
    this.controls.minDistance = dist * 0.3;
    this.controls.maxDistance = dist * 3.5;
    this.controls.update();

    this._applied = true;
  }

  /** desfaz a composição (volta o root do avatar; a câmera é reenquadrada pelo
   *  frameVRM do host). */
  reset() {
    if (this._applied && this._vrm) this._vrm.scene.rotation.y = this._savedYaw;
    this._applied = false;
  }
}
