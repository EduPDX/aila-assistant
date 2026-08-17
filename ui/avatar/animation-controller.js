// ============================================================
//  ANIMATION CONTROLLER — orquestra as camadas e a máquina de estados.
//
//  Responsabilidade: manter o CONTEXTO (estado, emoção, ritmo, olhar, fala),
//  suavizar transições, rodar as camadas na ordem certa e commitar no Rig.
//  Ele NÃO sabe renderizar — só decide o contexto e compõe as camadas.
//  (No futuro, o Behavior Planner do backend alimenta este contexto.)
// ============================================================
import { Rig, damp } from './rig-core.js';
import { EMOTIONS, STATES, resolveEmotion } from './profiles.js';

import { createPostureLayer } from './layers/posture.js';
import { createBreathLayer } from './layers/breath.js';
import { createProceduralLayer } from './layers/procedural.js';
import { createEyeLayer } from './layers/eye.js';
import { createLookAtLayer } from './layers/lookat.js';
import { createEmotionLayer } from './layers/emotion.js';
import { createLipSyncLayer } from './layers/lipsync.js';
import { createGestureAnimLayer } from './layers/gesture-anim.js';
import { createGestureIKLayer } from './layers/gesture-ik.js';
import { createSpeechGestureLayer } from './layers/speech-gesture.js';
import { createBlinkLayer } from './layers/blink.js';
import { createHandPoseLayer } from './hand-poses.js';
import { createJointLimits } from './solvers/joint-limits.js';
import { createArmIK } from './solvers/ik.js';
import { createSelfCollision } from './solvers/self-collision.js';

const GESTURE_HOLD = 1.6;   // seg que um gesto de pose fica antes de voltar ao rest
                            //  (curto de propósito: gesto é PONTUAÇÃO; entre eles
                            //   a gesticulação ambiente da fala assume as mãos)
const ANIM_GESTURES = new Set(['nod', 'shake']);   // gestos ANIMADOS (cabeça)

export class AnimationController {
  constructor(vrm, scene, camera) {
    this.rig = new Rig(vrm, scene);
    // ordem de composição: base → offsets → olhar → face/fala → blink
    this.layers = [
      createPostureLayer(),
      createBreathLayer(),
      createProceduralLayer(),
      createEyeLayer(),
      createLookAtLayer(),   // lê ctx.gaze escrito pela EyeLayer
      createEmotionLayer(),
      createLipSyncLayer(),
      createGestureAnimLayer(),   // nod/shake (cabeça) — F5
      createGestureIKLayer(),     // gestos de braço por IK → alvo de mão (Fase C)
      createSpeechGestureLayer(), // gesticulação ocasional da fala por IK (Fase E)
      createHandPoseLayer(),      // dedos: poses de mão (Fase B)
      createBlinkLayer(),
    ];
    // solvers: clampam/corrigem a pose antes do commit final
    this.bufferSolver = createJointLimits();  // opera no PoseBuffer (antes de aplicar)
    this.collision = createSelfCollision();   // empurra a mão p/ fora do corpo (define alvo de IK)
    this.ikSolver = createArmIK();            // resolve o braço até o alvo (após aplicar)
    this.ctx = {
      t: 0,
      camera,
      status: 'IDLE',
      emotionKey: 'neutral',
      emotion: EMOTIONS.neutral,
      motion: { amp: 1, speed: 1, breath: 1 },  // suavizado
      gazeMode: 'soft',
      gaze: { yaw: 0, pitch: 0 },               // EyeLayer escreve, LookAt lê
      blinkRange: [2.4, 6.0],
      mouth: 0,                                 // alvo instantâneo da boca (lip-sync)
      speech: 0,                                // envelope 0..1 "está falando"
      gesture: 'rest',
      handPose: { left: 'relaxed', right: 'relaxed' },   // pose dos dedos por lado (Fase B)
      anim: null,                               // gesto ANIMADO ativo (nod/shake) — F5
      handTarget: null,                         // {side,x,y,z,weight} → braço via IK
      intensity: 1,                             // reservado (força de expressão)
    };
    this._gestureTimer = 0;
    this._behavior = null;                      // overlay do BehaviorSpec (F4)
    this._queue = [];                           // timeline de gestos (F5)
    this._clock = 0;                            // relógio da fala (p/ a timeline)
    this.layerW = new Map();                    // peso/fade por CAMADA (P5) — name -> {cur,target,k}
  }

  /** faz uma CAMADA inteira aparecer/sumir suavemente (peso alvo 0..1) sem "pop".
   *  Base p/ clips (P6): a camada de clipe pode entrar/sair coexistindo com as
   *  demais (aditivas) em vez de brigar por sobrescrita. Existing layers ficam
   *  em peso 1 → comportamento idêntico. */
  fadeLayer(name, target, seconds = 0.4) {
    const e = this.layerW.get(name) || { cur: 1, target: 1, k: 6 };
    e.target = Math.max(0, Math.min(1, target));
    e.k = seconds > 0 ? 3.2 / seconds : 999;
    this.layerW.set(name, e);
  }
  _layerWeight(name, dt) {
    const e = this.layerW.get(name);
    if (!e) return 1;
    e.cur = damp(e.cur, e.target, e.k, dt);
    // assentou de volta em 1 → remove a entrada e volta ao caminho rápido
    if (e.target >= 0.999 && e.cur > 0.998) { this.layerW.delete(name); return 1; }
    return e.cur;
  }

  /** aplica um BehaviorSpec (do Behavior Planner): decide emoção/olhar/ritmo/
   *  gesto pelo SIGNIFICADO da resposta. Fica ativo pela duração da fala. */
  applyBehavior(spec) {
    if (!spec) return;
    if (spec.state) this.setStatus(spec.state);
    if (spec.emotion) this.setEmotion(spec.emotion);
    this.ctx.intensity = spec.intensity ?? 1;
    const m = spec.motion || {};
    this._behavior = {
      gaze: spec.gaze || null,
      amp: m.amplitude ?? 1, speed: m.speed ?? 1, breath: m.breath ?? 1,
      timer: (spec.est_speech_seconds || 2) + 1.2,   // renovado enquanto fala
    };
    // F5: timeline de gestos — cada um dispara no seu at_time (relativo à fala)
    this._queue = (spec.gestures || [])
      .map((g) => ({ type: g.type, at: g.at_time || 0 }))
      .sort((a, b) => a.at - b.at);
    this._clock = 0;
  }

  triggerGesture(name) {
    if (!name) return;
    if (ANIM_GESTURES.has(name)) {          // gesto animado (cabeça): nod/shake
      this.ctx.anim = { type: name, t: 0, dur: name === 'shake' ? 0.9 : 0.8 };
      return;
    }
    this.ctx.gesture = name;                // gesto de pose (braço): wave/point/…
    this._gestureTimer = name === 'rest' || name === 'none' ? 0 : GESTURE_HOLD;
  }

  /** move só a MÃO (mundo); o IK resolve o braço. null desliga. */
  setHandTarget(side, x, y, z, weight = 1) {
    this.ctx.handTarget = side ? { side, x, y, z, weight } : null;
  }
  clearHandTarget() { this.ctx.handTarget = null; }

  // -------- API pública (a UI / WS chamam isto) -------- //
  setStatus(status) { if (STATES[status]) this.ctx.status = status; }
  setEmotion(name) { const k = resolveEmotion(name); this.ctx.emotionKey = k; this.ctx.emotion = EMOTIONS[k]; }
  setMouth(v) { this.ctx.mouth = Math.max(0, Math.min(1, v || 0)); }
  /** pose dos dedos por lado. side='left'|'right'|'both'. Ex.: setHandPose('both','open') */
  setHandPose(side, name) {
    if (side === 'both' || !side) { this.ctx.handPose.left = name; this.ctx.handPose.right = name; }
    else this.ctx.handPose[side] = name;
  }

  // -------- loop -------- //
  update(dt) {
    const ctx = this.ctx;
    ctx.t += dt;

    // gesto volta ao rest sozinho
    if (this._gestureTimer > 0) {
      this._gestureTimer -= dt;
      if (this._gestureTimer <= 0) ctx.gesture = 'rest';
    }

    // timeline de gestos (F5): dispara cada gesto no seu at_time (relativo à fala).
    // O relógio só COMEÇA a correr quando a fala inicia de fato (boca/envelope) —
    // assim nenhum gesto dispara no vão entre o plano e o áudio do TTS (fim da
    // "tremida antes de falar"); at_time=0 vira "ao começar a falar".
    if (this._queue.length && (this._clock > 0 || ctx.speech > 0.06)) {
      this._clock += dt;
      while (this._queue.length && this._queue[0].at <= this._clock) {
        this.triggerGesture(this._queue.shift().type);
      }
    }

    const st = STATES[ctx.status] || STATES.IDLE, em = ctx.emotion;

    // overlay do Behavior Planner: ativo pela duração da fala (renovado enquanto
    // a boca se mexe); ao expirar, volta ao ritmo derivado de estado × emoção.
    const b = this._behavior;
    if (b) {
      if (ctx.mouth > 0.05) b.timer = Math.max(b.timer, 0.8);
      b.timer -= dt;
      if (b.timer <= 0) this._behavior = null;
    }
    const bb = this._behavior;

    // ritmo-alvo (amplitude/velocidade/respiração), suavizado
    ctx.motion.amp = damp(ctx.motion.amp, bb ? bb.amp : st.amp * em.amp, 2.5, dt);
    ctx.motion.speed = damp(ctx.motion.speed, bb ? bb.speed : em.speed, 2.5, dt);
    ctx.motion.breath = damp(ctx.motion.breath, bb ? bb.breath : em.breath, 2.5, dt);

    // olhar: overlay do planner > estados de tarefa (tela/usuário/baixo) > emoção
    ctx.gazeMode = (bb && bb.gaze) ? bb.gaze
      : (st.gaze === 'screen' || st.gaze === 'user' || st.gaze === 'down') ? st.gaze
      : (em.gaze || st.gaze);
    ctx.blinkRange = st.blink;

    // envelope de fala (sobe rápido, desce suave)
    ctx.speech = damp(ctx.speech, ctx.mouth > 0.05 ? 1 : 0, 3, dt);

    // 1) camadas escrevem no PoseBuffer
    const buf = this.rig.buffer;
    buf.reset();
    // cada camada contribui com o seu PESO (P5). Sem fades ativos → peso 1 p/
    // todas (idêntico ao anterior); o buffer escala rot/expr/handTarget por _w.
    const fading = this.layerW.size > 0;
    for (const layer of this.layers) {
      buf._w = fading ? this._layerWeight(layer.name, dt) : 1;
      layer.update(this.rig, buf, ctx, dt);
    }
    buf._w = 1;
    if (ctx.handTarget) {                        // gesto por IK (alvo de mão)
      const t = ctx.handTarget;
      buf.setHandTarget(t.side, t.x, t.y, t.z, t.weight);
    }
    // 2) limites anatômicos (clampa o buffer FK) e aplica no esqueleto
    this.bufferSolver.solve(this.rig, buf);
    this.rig.applyBones();
    // solvers de posição (colisão→IK + updateMatrices, o passo mais caro) SÓ
    // quando há alvo de mão (buf.ik). Parada ao lado (sem gesto) = pula tudo.
    if (buf.ik.size) {
      this.rig.updateMatrices();                     // corpo posado → colliders válidos
      // 3) colisão PROATIVA: constrange o alvo p/ fora do corpo (antes do IK)
      this.collision.solve(this.rig, buf, ctx, dt);
      // 4) IK resolve o braço UMA vez p/ o alvo já seguro (cotovelo + orientação)
      this.ikSolver.solve(this.rig, buf);
    }
    // 6) blendshapes + olhar + física secundária
    this.rig.finalize(dt);
  }
}
