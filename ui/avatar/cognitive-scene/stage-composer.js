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

  /** posiciona as telas LADO A LADO + gira o avatar + enquadra a câmera a NÍVEL
   *  DOS OLHOS (nada de câmera de cima; nada de uma tela atrás da outra). */
  compose(vrm, monitorGroup, ring, statusGroup, messageGroup, infrastructureGroup) {
    if (!vrm) return;
    const box0 = new THREE.Box3().setFromObject(vrm.scene);
    if (box0.isEmpty()) return;
    const c = box0.getCenter(new THREE.Vector3());
    const feetY = box0.min.y, h = box0.max.y - feetY;
    const eyeY = feetY + h * 0.86;
    const s = Math.max(0.7, Math.min(1.4, h / 1.5));

    if (ring) ring.position.set(c.x, feetY + 0.002, c.z);

    // monitor PRINCIPAL (grande): totalmente à ESQUERDA da Aila (borda direita
    // livre dela → ela não fica "em cima" da tela). Mesmo plano das duas telas.
    if (monitorGroup) {
      monitorGroup.position.set(c.x - h * 1.30, eyeY - h * 0.025, c.z + h * 0.05);
      monitorGroup.rotation.set(0, 0.26, 0);
      monitorGroup.scale.setScalar(s);
    }
    // STATUS: à esquerda do monitor, MESMO plano/ângulo, com um pequeno ESPAÇO
    // (lado a lado, sem uma parecer em cima da outra na perspectiva).
    if (statusGroup) {
      statusGroup.position.set(c.x - h * 2.95, eyeY - h * 0.025, c.z + h * 0.05);
      statusGroup.rotation.set(0, 0.26, 0);
      statusGroup.scale.setScalar(s);
    }

    // balão de resumo (Jarvis): à DIREITA da Aila, na altura dos olhos — o lado
    // livre (os dois monitores ficam à esquerda). Antes ficava acima da cabeça,
    // apertado; aqui usa o espaço vazio e não tampa o rosto. Inclinação
    // espelhada à dos monitores, p/ encarar quem olha.
    if (messageGroup) {
      messageGroup.position.set(c.x + h * 1.02, eyeY + h * 0.02, c.z + h * 0.30);
      messageGroup.rotation.set(0, -0.26, 0);
      messageGroup.scale.setScalar(s * 0.92);
    }

    // Racks ao fundo: compõem o cenário sem entrar no cálculo da câmera e sem
    // competir visualmente com as telas de trabalho.
    if (infrastructureGroup) {
      infrastructureGroup.position.set(c.x - h * 0.45, feetY, c.z - h * 2.38);
      infrastructureGroup.rotation.set(0, 0, 0);
      infrastructureGroup.scale.setScalar(s * 0.88);
    }

    // vira o corpo p/ as telas (diagonal sutil; olhos seguem o usuário via lookAt).
    if (!this._applied) this._savedYaw = vrm.scene.rotation.y;
    this._vrm = vrm;
    vrm.scene.rotation.y = this._savedYaw - 0.22;

    // enquadra TUDO (Aila + as 2 telas) a NÍVEL DOS OLHOS, num leve 3/4.
    vrm.scene.updateWorldMatrix(true, true);
    monitorGroup?.updateWorldMatrix(true, true);
    statusGroup?.updateWorldMatrix(true, true);
    const box = new THREE.Box3().setFromObject(vrm.scene);
    if (monitorGroup) box.expandByObject(monitorGroup);
    if (statusGroup) box.expandByObject(statusGroup);
    if (messageGroup) {   // reserva espaço p/ o balão no quadro (mesmo oculto agora)
      const wasVis = messageGroup.visible; messageGroup.visible = true;
      messageGroup.updateWorldMatrix(true, true); box.expandByObject(messageGroup);
      messageGroup.visible = wasVis;
    }
    const bc = box.getCenter(new THREE.Vector3());
    const bs = box.getSize(new THREE.Vector3());
    const fov = this.camera.fov * Math.PI / 180;
    const aspect = this.camera.aspect || 1.6;
    const fitH = (bs.y * 0.5) / Math.tan(fov / 2);
    const fitW = (bs.x * 0.5) / Math.tan(fov / 2) / aspect;
    const dist = Math.max(fitH, fitW) * 1.12;
    this.controls.target.set(bc.x, bc.y, bc.z);                        // mira o centro
    this.camera.position.set(bc.x + bs.x * 0.04, bc.y + bs.y * 0.05, bc.z + dist);  // quase nível (leve 3/4)
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
