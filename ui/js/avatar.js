// Ponte com o avatar 3D (iframe). Comanda via postMessage.
import { byId } from './dom.js';

export function toAvatar(msg) {
  const f = byId('avatar3d');
  if (f && f.contentWindow) f.contentWindow.postMessage(msg, location.origin);
}
export const avatarEmotion = (emotion, state, gesture) =>
  toAvatar({ type: 'aila:emotion', value: emotion, state, gesture });
export const avatarStatus = (status) => toAvatar({ type: 'aila:status', value: status });
export const avatarBehavior = (spec) => toAvatar({ type: 'aila:behavior', spec });
export const avatarGesture = (name) => toAvatar({ type: 'aila:gesture', value: name });
// série de movimentos (demonstração): o iframe toca um a um, com pausa
export const avatarGestureSequence = (names) => toAvatar({ type: 'aila:gesture_seq', values: names });
export const avatarMouth = (v) => toAvatar({ type: 'aila:mouth', value: v });
export const avatarReload = () => toAvatar({ type: 'aila:reloadVRM' });
// P8: pausa/retoma o render do avatar conforme ele está (ou não) na tela
export const avatarShow = (on) => toAvatar({ type: on ? 'aila:show' : 'aila:hide' });
// VRAM Fase 2: encaminha o estado (green/yellow/red) p/ o avatar degradar o pixelRatio
export const avatarVramPressure = (state) => toAvatar({ type: 'aila:vram-pressure', state });
// Cognitive Scene: métricas REAIS (GPU/CPU/VRAM/modelo/tokens) → tela de STATUS
export const avatarMetrics = (payload) => toAvatar({ type: 'aila:metrics', payload });
// Cognitive Scene: RESUMO curto que a Aila fala → balão holográfico (Jarvis)
export const avatarSay = (text) => toAvatar({ type: 'aila:say', text });


// Ponte de VOLTA (Cognitive Core, Fase D): o avatar relata o estado do corpo e
// o app manda ao backend. É isto que permite a Aila dizer "estou com a mão
// levantada" em vez de "o avatar está com a mão levantada".
addEventListener('message', (e) => {
  const frame = byId('avatar3d');
  if (e.origin !== location.origin || !frame || e.source !== frame.contentWindow) return;
  const m = e && e.data;
  if (!m || m.type !== 'body.report') return;
  import('./ws.js').then(({ wsSend }) => wsSend({ type: 'body.report', body: m.body }))
    .catch(() => {});
});
