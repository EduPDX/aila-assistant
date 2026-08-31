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
import { createInteractionManager } from './interactions/interaction-manager.js';
import { StageComposer } from './stage-composer.js';
import { STATE_VISUALS, DEFAULT_STATE_VISUAL } from './state-visuals.js';
import { preloadAssets, getAsset, cloneAsset } from './scene-assets.js';
import { createThinkingPanel } from './procedural/thinking-panel.js';
import { createServerHall } from './procedural/server-hall.js';

// intent → âncora que a Aila aponta (Fase 3)
const POINT_TARGET = { analysis: 'panel_analysis', coding: 'panel_analysis', reading: 'panel_analysis', search: 'panel_memory', thinking: 'panel_memory' };

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
    this.lastInteraction = null;   // {type,target} p/ o body.report (Fase D)
    this.monitor = null;
    this.controller = null;      // AnimationController do avatar (p/ IK/pose) — avatar3d o injeta
    this._pointCooldown = 0;
    this.composer = new StageComposer(camera, controls);
    this.interactions = createInteractionManager({
      resolveWorld: (id, out) => this.resolveWorld(id, out),
      getController: () => this.controller,
    });
    this._built = false;
    this._fadeAlpha = 1;   // Fase 9: fade-in suave ao reativar
    if (this.enabled) this.scene.add(this.root);
  }

  build() {
    if (this._built || !this.enabled) return;
    this._built = true;

    // chão "INFINITO": grade grande + neblina escura que a faz sumir na distância
    // (a Aila e as telas ficam PERTO da câmera → intocadas pela neblina).
    const gh = new THREE.GridHelper(50, 100, HOLO.teal, HOLO.blue);
    gh.material.transparent = true; gh.material.opacity = 0.11; gh.material.depthWrite = false;
    gh.position.y = 0.001;
    this.root.add(gh);
    if (!this.scene.fog) this.scene.fog = new THREE.Fog(0x0a0e14, 7, 20);   // horizonte que desvanece
    const ringGeo = new THREE.RingGeometry(0.42, 0.46, 48);
    const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({
      color: HOLO.teal, transparent: true, opacity: 0.4, side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending, depthWrite: false }));
    ring.rotation.x = -Math.PI / 2; ring.position.y = 0.002;
    this.root.add(ring);
    this._ring = ring;
    this._grid = gh;
    this._ringSpeed = 0.15;

    // monitor holográfico principal (cognitivo)
    this.monitor = createMonitor();   // usa o tamanho padrão (grande) do módulo
    this.root.add(this.monitor.group);

    // segunda tela: STATUS do sistema (dados reais via setMetrics)
    this.status = createStatusPanel();
    this.root.add(this.status.group);

    // balão holográfico (Jarvis): resumo curto que a Aila fala
    this.message = createMessagePanel();
    this.root.add(this.message.group);

    // painel de Extended Thinking: mostra passos do raciocínio em tempo real
    this.thinking = createThinkingPanel();
    this.thinking.group.visible = false;
    this.root.add(this.thinking.group);

    // Infraestrutura cognitiva: racks reais, discretos e atrás da Aila.
    this.infrastructure = createServerHall();
    this.root.add(this.infrastructure.group);

    // Fase 8: tenta carregar assets GLB (async, não bloqueia).
    // Se existirem, substitui os elementos procedurais por meshes.
    this._loadAssets();
  }

  /** Fase 8: carrega GLBs opcionais e substitui procedurais. */
  async _loadAssets() {
    try {
      await preloadAssets();
      const floorRoot = getAsset('floor');
      if (floorRoot && this._grid) {
        const clone = cloneAsset(floorRoot);
        if (clone) {
          this.root.remove(this._grid);
          disposeObject(this._grid);
          this._grid = clone;
          this.root.add(clone);
        }
      }
      // monitor/status/message GLBs: futura extensão (por ora ficam procedurais
      // porque têm lógica interna — setMode, setMetrics, etc).
    } catch (e) {
      console.warn('[scene-assets] fallback procedural:', e.message);
    }
  }

  /** posiciona as telas relativo ao avatar + compõe a câmera diagonal. */
  compose(vrm) {
    if (!this.enabled || !this._built || !vrm) return;
    this.composer.compose(vrm, this.monitor.group, this._ring, this.status.group, this.message.group, this.infrastructure?.group);
  }

  /** alimenta a tela de STATUS com o snapshot real de /api/metrics (+ estado). */
  setMetrics(m) { this.status?.setMetrics(m); }

  /** Inventário seguro de modelos locais e APIs configuradas. */
  setInfrastructure(payload) { this.infrastructure?.setData(payload); }

  /** mostra o RESUMO curto da resposta da Aila no balão holográfico (Jarvis). */
  showMessage(text) { this.message?.show(text); }

  // ---- Extended Thinking ----
  /** Mostra o painel de thinking e adiciona um passo. */
  showThinking(stepText) {
    if (!this.thinking) return;
    this.thinking.show();
    if (stepText) this.thinking.addStep(stepText);
  }

  /** Adiciona um novo passo ao thinking (sem mostrar o painel se já estiver oculto). */
  addThinkingStep(stepText) {
    if (this.thinking) this.thinking.addStep(stepText);
  }

  /** Esconde o painel de thinking e limpa os passos. */
  hideThinking() {
    if (this.thinking) { this.thinking.hide(); this.thinking.clear(); }
  }

  /** Fase 2+3+6: o backend DIRIGE a cena via BehaviorSpec.
   *  `cui` pode ser:
   *  - string (intent legado: 'search', 'analysis'…)
   *  - objeto {enabled, type, intensity} (CognitiveUI do BehaviorSpec)
   *  - null/undefined → fallback p/ this.intent atual (mantém estado). */
  setState(cui, interaction) {
    let type, intensity, enabled;

    if (cui && typeof cui === 'object') {
      enabled = cui.enabled !== false;
      type = cui.type || 'conversation';
      intensity = cui.intensity ?? 0.6;
    } else {
      enabled = true;
      type = cui || 'conversation';
      intensity = 0.6;
    }

    if (!enabled) {
      this.intent = 'conversation';
      this.monitor?.setMode('conversation');
      return;
    }

    this.intent = type;
    this.monitor?.setMode(type);
    this.monitor?.setIntensity?.(intensity);

    // Fase 2: aplicar visuais por estado
    const sv = STATE_VISUALS[type] || DEFAULT_STATE_VISUAL;
    this.monitor?.applyStateVisuals?.(sv);

    // Interaction inline do BehaviorSpec (Fase 6) tem prioridade
    // sobre o POINT_TARGET legado.
    if (interaction && this._pointCooldown <= 0) {
      const anchor = this._resolveAnchor(interaction.target);
      if (anchor && this.interactions.interact({ type: interaction.type, target: anchor })) {
        this._pointCooldown = 14;
        // guarda p/ o body.report: é isto que vira "estou apontando para X"
        this.lastInteraction = { type: interaction.type, target: interaction.target };
      }
    } else {
      // fallback: POINT_TARGET legado (backward compat)
      const target = POINT_TARGET[this.intent];
      if (target && this._pointCooldown <= 0) {
        if (this.interactions.interact({ type: 'point', target })) {
          this._pointCooldown = 14;
          this.lastInteraction = { type: 'point', target: this.intent };
        }
      }
    }
  }

  /** resolve target semântico ('analysis', 'memory'…) p/ âncora 3D. */
  _resolveAnchor(target) {
    if (!target) return null;
    const MAP = { analysis: 'panel_analysis', memory: 'panel_memory', data: 'panel_analysis', search: 'panel_memory' };
    return MAP[target] || target;
  }

  /** injeta o AnimationController do avatar (p/ o InteractionManager usar o IK). */
  setController(c) { this.controller = c; }

  /** dispara uma interação manual: {type:'point'|'inspect'|..., target:'panel_analysis'} */
  interact(spec) { return this.interactions.interact(spec); }

  setPaused(p) { this.paused = !!p; }

  /** degrada sob pressão de VRAM (reusa o planejador de VRAM). */
  setVramState(state) {
    this.vramState = state || 'green';
    if (!this.root) return;
    // 🔴 vermelho: esconde a cena inteira (prioriza o avatar); 🟡 mantém, sem extras.
    this.root.visible = this.enabled && state !== 'red';
    // sob pressão Vermelha, disposing texturas/buffers auxiliares libera VRAM.
    if (state === 'red' && this.monitor) {
      this.monitor.setMode?.('conversation');   // reseta animações
    }
  }

  update(dt) {
    if (!this.enabled || !this._built || this.paused || this.root.visible === false) return;

    // Fase 9: fade-in suave ao reativar
    if (this._fadeAlpha < 1) {
      this._fadeAlpha = Math.min(1, this._fadeAlpha + dt * 2.5);
      this.root.traverse((o) => {
        if (o.material && 'opacity' in o.material) {
          o.material._savedOpacity = o.material._savedOpacity ?? o.material.opacity;
          o.material.opacity = o.material._savedOpacity * this._fadeAlpha;
        }
      });
      if (this._fadeAlpha >= 1) {
        this.root.traverse((o) => {
          if (o.material && o.material._savedOpacity !== undefined) {
            o.material.opacity = o.material._savedOpacity;
            delete o.material._savedOpacity;
          }
        });
      }
    }

    this.monitor?.update(dt);
    this.status?.update(dt);
    this.message?.update(dt);
    this.thinking?.update(dt);
    this.infrastructure?.update(dt);
    this.interactions.update(dt);
    if (this._pointCooldown > 0) this._pointCooldown -= dt;
    if (this._ring) this._ring.rotation.z += dt * this._ringSpeed;   // giro lento do anel
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
    if (on) {
      if (!this.scene.children.includes(this.root)) this.scene.add(this.root);
      this.build();
      this.root.visible = true;
      this._fadeAlpha = 0;   // Fase 9: inicia fade-in
    } else if (this.root) {
      this.root.visible = false;
      this.composer.reset();
    }
  }

  destroy() {
    this.composer.reset();
    if (this.root) { this.scene.remove(this.root); disposeObject(this.root); }
    this._built = false; this.monitor = null;
  }
}
