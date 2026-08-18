// ============================================================
//  STATE VISUALS — parâmetros visuais por INTENT para o monitor.
//  Cada intent define: cor dominante, opacidade base, velocidade de
//  animação e quais zonas ficam em destaque. Render-agnóstico:
//  só retorna valores que o monitor aplica.
// ============================================================

// Coginas Three.js: HOLO cores
import { HOLO } from './procedural/primitives.js';

export const STATE_VISUALS = {
  search: {
    accent: HOLO.teal,
    glow: 0.85,
    scanSpeed: 0.5,
    zoneWeights: { memory: 1.0, analysis: 0.3, stream: 0.6, bars: 0.4 },
    verb: 'SEARCHING',
  },
  analysis: {
    accent: HOLO.blue,
    glow: 0.9,
    scanSpeed: 0.35,
    zoneWeights: { memory: 0.5, analysis: 1.0, stream: 0.4, bars: 0.7 },
    verb: 'ANALYZING',
  },
  thinking: {
    accent: HOLO.teal,
    glow: 0.6,
    scanSpeed: 0.2,
    zoneWeights: { memory: 0.9, analysis: 0.5, stream: 0.2, bars: 0.3 },
    verb: 'THINKING',
  },
  coding: {
    accent: HOLO.blue,
    glow: 0.8,
    scanSpeed: 0.6,
    zoneWeights: { memory: 0.3, analysis: 0.8, stream: 0.9, bars: 0.5 },
    verb: 'COMPILING',
  },
  reading: {
    accent: HOLO.teal,
    glow: 0.7,
    scanSpeed: 0.25,
    zoneWeights: { memory: 0.7, analysis: 0.6, stream: 0.8, bars: 0.3 },
    verb: 'READING',
  },
  tool_execution: {
    accent: HOLO.blue,
    glow: 0.65,
    scanSpeed: 0.45,
    zoneWeights: { memory: 0.4, analysis: 0.5, stream: 0.7, bars: 0.8 },
    verb: 'EXECUTING',
  },
  error: {
    accent: 0xff4444,
    glow: 0.4,
    scanSpeed: 0.15,
    zoneWeights: { memory: 0.2, analysis: 0.3, stream: 0.5, bars: 0.2 },
    verb: 'ERROR',
  },
  greeting: {
    accent: HOLO.teal,
    glow: 0.5,
    scanSpeed: 0.3,
    zoneWeights: { memory: 0.3, analysis: 0.3, stream: 0.2, bars: 0.3 },
    verb: 'READY',
  },
  farewell: {
    accent: HOLO.teal,
    glow: 0.3,
    scanSpeed: 0.2,
    zoneWeights: { memory: 0.2, analysis: 0.2, stream: 0.1, bars: 0.2 },
    verb: 'READY',
  },
  conversation: {
    accent: HOLO.teal,
    glow: 0.6,
    scanSpeed: 0.3,
    zoneWeights: { memory: 0.4, analysis: 0.4, stream: 0.3, bars: 0.4 },
    verb: 'READY',
  },
  explanation: {
    accent: HOLO.teal,
    glow: 0.7,
    scanSpeed: 0.35,
    zoneWeights: { memory: 0.6, analysis: 0.7, stream: 0.4, bars: 0.5 },
    verb: 'EXPLAINING',
  },
};

export const DEFAULT_STATE_VISUAL = STATE_VISUALS.conversation;
