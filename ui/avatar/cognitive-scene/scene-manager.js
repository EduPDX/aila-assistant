// ============================================================
//  SCENE MANAGER — a "Cognitive Scene": ambiente visual da Aila.
//  IRMÃO do AnimationController, vive na MESMA scene/camera/loop (sem 2º
//  renderer — lição do bug do grafo). Não toca no VRM. Fase 1: chão +
//  monitor holográfico + composição diagonal. setState(intent) é stub aqui
//  (a Fase 2 liga o conteúdo por estado).
//
//  Flag: localStorage 'aila.scene' — 'off' desliga tudo (avatar volta ao
//  comportamento atual, 100% revertível). Default: ligado.
// ============================================================
import * as THREE from 'three';
import { HOLO, lineMat, disposeObject } from './procedural/primitives.js';
import { createMonitor } from './procedural/monitor.js';
import { createStatusPanel } from './procedural/status-panel.js';
import { createMessagePanel } from './procedural/message-panel.js';
import { StageComposer } from './stage-composer.js';

export function sceneEnabled() { return localStorage.getItem('aila.scene') !== 'off'; }

export class SceneManager {
  constructor(scene, camera, controls) {
    this.scene = scene; this.camera = camera; this.controls = controls;
    this.root = new THREE.Group();
    this.root.name = 'cognitive-scene';
    this.enabled = sceneEnabled();
    this.paused = false;
    this.vramState = 'green';
    this.intent = 'conversation';
    this.monitor = null;
    this.composer = new StageComposer(camera, controls);
    this._built = false;
    if (this.enabled) this.scene.add(this.root);
  }

  build() {
    if (this._built || !this.enabled) return;
    this._built = true;

    // chão: grade sutil no plano XZ + anel sob a Aila (o "palco")
    const gh = new THREE.GridHelper(6, 24, HOLO.teal, HOLO.blue);
    gh.material.transparent = true; gh.material.opacity = 0.12; gh.material.depthWrite = false;
    gh.position.y = 0.001;
    this.root.add(gh);
    const ringGeo = new THREE.RingGeometry(0.42, 0.46, 48);
    const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({
      color: HOLO.teal, transparent: true, opacity: 0.4, side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending, depthWrite: false }));
    ring.rotation.x = -Math.PI / 2; ring.position.y = 0.002;
    this.root.add(ring);
    this._ring = ring;

    // monitor holográfico principal (cognitivo)
    this.monitor = createMonitor();   // usa o tamanho padrão (grande) do módulo
    this.root.add(this.monitor.group);

    // segunda tela: STATUS do sistema (dados reais via setMetrics)
    this.status = createStatusPanel();
    this.root.add(this.status.group);

    // balão holográfico (Jarvis): resumo curto que a Aila fala
    this.message = createMessagePanel();
    this.root.add(this.message.group);
  }

  /** posiciona as telas relativo ao avatar + compõe a câmera diagonal. */
  compose(vrm) {
    if (!this.enabled || !this._built || !vrm) return;
    this.composer.compose(vrm, this.monitor.group, this._ring, this.status.group, this.message.group);
  }

  /** alimenta a tela de STATUS com o snapshot real de /api/metrics (+ estado). */
  setMetrics(m) { this.status?.setMetrics(m); }

  /** mostra o RESUMO curto da resposta da Aila no balão holográfico (Jarvis). */
  showMessage(text) { this.message?.show(text); }

  /** Fase 2 (stub): troca o conteúdo por estado. Guardado desde já. */
  setState(intent) { this.intent = intent || 'conversation'; }

  setPaused(p) { this.paused = !!p; }

  /** degrada sob pressão de VRAM (reusa o planejador de VRAM). */
  setVramState(state) {
    this.vramState = state || 'green';
    if (!this.root) return;
    // 🔴 vermelho: esconde a cena inteira (prioriza o avatar); 🟡 mantém, sem extras.
    this.root.visible = this.enabled && state !== 'red';
  }

  update(dt) {
    if (!this.enabled || !this._built || this.paused || this.root.visible === false) return;
    this.monitor?.update(dt);
    this.status?.update(dt);
    this.message?.update(dt);
    if (this._ring) this._ring.rotation.z += dt * 0.15;   // giro lento do anel
  }

  /** posição de MUNDO de uma âncora nomeada (p/ InteractionTarget/IK — Fase 3). */
  resolveWorld(id, out = new THREE.Vector3()) {
    const obj = this.monitor?.anchors.get(id);
    if (!obj) return null;
    obj.getWorldPosition(out);
    return out;
  }

  setEnabled(on) {
    this.enabled = !!on;
    if (on) { if (!this.scene.children.includes(this.root)) this.scene.add(this.root); this.build(); this.root.visible = true; }
    else if (this.root) { this.root.visible = false; this.composer.reset(); }
  }

  destroy() {
    this.composer.reset();
    if (this.root) { this.scene.remove(this.root); disposeObject(this.root); }
    this._built = false; this.monitor = null;
  }
}
