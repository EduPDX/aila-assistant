// ============================================================
//  PONTE COGNITIVA → AVATAR (P4). Traduz eventos do Event Bus (que chegam pelo
//  WebSocket) em REAÇÕES DE ALTO NÍVEL do avatar. Mostra só o estado cognitivo
//  (recuperando memória, aprendendo, atento) — NUNCA o chain-of-thought.
//
//  Reações são BREVES e têm cooldown por categoria p/ o avatar não "tiquetear"
//  (memory.recalled acontece todo turno; consolidação roda em background).
// ============================================================
import { avatarGesture, avatarStatus, avatarVramPressure } from './avatar.js';

const last = {};
function cool(key, ms) {
  const t = performance.now();
  if (t - (last[key] || 0) < ms) return false;
  last[key] = t;
  return true;
}

export function cognitiveAvatar(m) {
  switch (m.type) {
    case 'memory.recalled':                     // "ah, eu lembro disso" → aceno breve
      if (cool('recall', 10000)) avatarGesture('nod');
      break;
    case 'skill.ran':                           // executou uma skill → reação positiva
      if (cool('skill', 6000)) avatarGesture('nod');
      break;
    case 'memory.consolidated':                 // "dreaming": aprendendo em background
    case 'graph.updated':
      if (cool('learn', 12000)) avatarGesture('think');
      break;
    case 'permission.request':                  // esperando decisão → postura atenta
      avatarStatus('LISTENING');
      break;
    case 'system.vram':                         // pressão de VRAM (ex.: pré-voo da visão)
      avatarVramPressure(m.state);              // → avatar encolhe o pixelRatio na hora
      break;
  }
}
