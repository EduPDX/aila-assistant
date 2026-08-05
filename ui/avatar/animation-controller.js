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
import { createBlinkLayer } from './layers/blink.js';

const GESTURE_HOLD = 2.8;   // seg que um gesto fica antes de voltar ao rest

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
      createBlinkLayer(),
    ];
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
    };
    this._gestureTimer = 0;
  }

  // -------- API pública (a UI / WS chamam isto) -------- //
  setStatus(status) { if (STATES[status]) this.ctx.status = status; }
  setEmotion(name) { const k = resolveEmotion(name); this.ctx.emotionKey = k; this.ctx.emotion = EMOTIONS[k]; }
  setMouth(v) { this.ctx.mouth = Math.max(0, Math.min(1, v || 0)); }
  triggerGesture(name) {
    if (!name) return;
    this.ctx.gesture = name;
    this._gestureTimer = name === 'rest' || name === 'none' ? 0 : GESTURE_HOLD;
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

    // ritmo-alvo = estado × emoção (amplitude/velocidade/respiração), suavizado
    const st = STATES[ctx.status] || STATES.IDLE, em = ctx.emotion;
    ctx.motion.amp = damp(ctx.motion.amp, st.amp * em.amp, 2.5, dt);
    ctx.motion.speed = damp(ctx.motion.speed, em.speed, 2.5, dt);
    ctx.motion.breath = damp(ctx.motion.breath, em.breath, 2.5, dt);

    // olhar: estados de tarefa mandam (tela/usuário/baixo); senão, viés da emoção
    ctx.gazeMode = (st.gaze === 'screen' || st.gaze === 'user' || st.gaze === 'down')
      ? st.gaze : (em.gaze || st.gaze);
    ctx.blinkRange = st.blink;

    // envelope de fala (sobe rápido, desce suave)
    ctx.speech = damp(ctx.speech, ctx.mouth > 0.05 ? 1 : 0, 3, dt);

    // roda as camadas -> PoseBuffer, depois aplica no VRM
    this.rig.buffer.reset();
    for (const layer of this.layers) layer.update(this.rig, this.rig.buffer, ctx, dt);
    this.rig.commit(dt);
  }
}
