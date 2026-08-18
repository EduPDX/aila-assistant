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

  /** posiciona o monitor + gira o avatar + enquadra a câmera para o "palco". */
  compose(vrm, monitorGroup, ring) {
    if (!vrm) return;
    const box = new THREE.Box3().setFromObject(vrm.scene);
    if (box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3());
    const c = box.getCenter(new THREE.Vector3());
    const feetY = box.min.y, topY = box.max.y, h = topY - feetY;
    const eyeY = feetY + h * 0.86;          // ~altura dos olhos

    // anel do palco sob os pés
    if (ring) ring.position.set(c.x, feetY + 0.002, c.z);

    // monitor: à FRENTE-ESQUERDA da Aila, na altura do peito/olhos, virado p/
    // o espaço entre ela e a câmera (a Aila trabalha "de lado" nele).
    if (monitorGroup) {
      monitorGroup.position.set(c.x - h * 0.62, eyeY - h * 0.02, c.z + h * 0.40);
      monitorGroup.rotation.set(0, 0.5, 0);
      const s = Math.max(0.7, Math.min(1.4, h / 1.5));   // escala com a altura do modelo
      monitorGroup.scale.setScalar(s);
    }

    // vira o CORPO ~10° para o monitor (diagonal sutil). A cabeça/olhos seguem
    // encarando o usuário pelo lookAt existente (na Fase 1 a virada é pequena
    // de propósito, p/ não precisar ainda da compensação de cabeça do gaze).
    if (!this._applied) this._savedYaw = vrm.scene.rotation.y;
    this._vrm = vrm;
    vrm.scene.rotation.y = this._savedYaw - 0.22;   // ~13° (Fase 1 sutil; virada forte c/ compensação de cabeça vem no gaze/Fase 4)

    // câmera: um pouco à direita e mais afastada → cabe Aila + monitor no quadro,
    // vendo o rosto (3/4) e a interação. Respeita o zoom/órbita depois.
    const fov = this.camera.fov * Math.PI / 180;
    const fitH = (h * 0.62) / Math.tan(fov / 2);
    const dist = Math.max(fitH, 1.2) * 1.15;
    const target = new THREE.Vector3(c.x - h * 0.16, eyeY - h * 0.10, c.z + h * 0.15);
    this.controls.target.copy(target);
    this.camera.position.set(c.x + h * 0.28, eyeY - h * 0.02, c.z + dist);
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
