// ============================================================
//  PROFILES — dados de comportamento (sem lógica). Adicionar emoção/estado/
//  gesto aqui NÃO exige mexer nas camadas. Este é o "conteúdo" do sistema.
// ============================================================

// -------- perfil por EMOÇÃO: face + postura + ritmo + viés de olhar --------
//  face: expressão VRM alvo · spine/head: postura base (graus)
//  amp/speed/breath: multiplicadores de amplitude/velocidade/respiração
//  gaze: viés do olhar · brow: intensidade (reservado p/ nuance)
export const EMOTIONS = {
  neutral:   { face: 'neutral',   amp: 1.00, speed: 1.00, breath: 1.00, spine: [0, 0, 0],  head: [0, 0, 0],  gaze: 'soft' },
  happy:     { face: 'happy',     amp: 1.35, speed: 1.25, breath: 1.15, spine: [-2, 0, 0], head: [-2, 0, 0], gaze: 'soft' },
  confident: { face: 'happy',     amp: 1.20, speed: 1.10, breath: 1.05, spine: [-3, 0, 0], head: [-3, 0, 0], gaze: 'soft' },
  relaxed:   { face: 'relaxed',   amp: 0.85, speed: 0.85, breath: 0.92, spine: [1, 0, 0],  head: [2, 0, 0],  gaze: 'soft' },
  focused:   { face: 'relaxed',   amp: 0.80, speed: 0.90, breath: 0.95, spine: [-1, 0, 0], head: [-1, 0, 0], gaze: 'lock' },
  thinking:  { face: 'relaxed',   amp: 0.80, speed: 0.80, breath: 0.90, spine: [2, 0, 0],  head: [6, -6, 0], gaze: 'wander' },
  confused:  { face: 'sad',       amp: 0.85, speed: 0.90, breath: 0.95, spine: [1, 0, 0],  head: [4, 5, 0],  gaze: 'wander' },
  sad:       { face: 'sad',       amp: 0.55, speed: 0.70, breath: 0.82, spine: [6, 0, 0],  head: [9, 0, 0],  gaze: 'down' },
  angry:     { face: 'angry',     amp: 1.20, speed: 1.30, breath: 1.20, spine: [-3, 0, 0], head: [-4, 0, 0], gaze: 'lock' },
  surprised: { face: 'surprised', amp: 1.30, speed: 1.40, breath: 1.10, spine: [-4, 0, 0], head: [-5, 0, 0], gaze: 'lock' },
};

// mapeia a emoção "crua" do backend p/ uma chave de EMOTIONS
export const EMOTION_ALIAS = {
  neutral: 'neutral', happy: 'happy', confident: 'confident', relaxed: 'relaxed',
  focused: 'focused', thinking: 'thinking', confused: 'confused', sad: 'sad',
  angry: 'angry', surprised: 'surprised',
};

// expressões faciais que interpolamos (as demais ficam em 0)
export const FACE_EXPRESSIONS = ['happy', 'angry', 'sad', 'relaxed', 'surprised', 'neutral'];

// -------- perfil por ESTADO (máquina de estados de comportamento) --------
//  gaze: p/ onde olha · blink:[min,max] seg entre piscadas · amp: energia do corpo
//  nod: acena levemente (escuta) · defaultEmotion: emoção se o backend não mandar
export const STATES = {
  IDLE:            { gaze: 'soft',   blink: [2.4, 6.0], amp: 1.00, defaultEmotion: 'neutral' },
  LISTENING:       { gaze: 'user',   blink: [2.5, 5.5], amp: 0.92, nod: true, defaultEmotion: 'relaxed' },
  THINKING:        { gaze: 'wander', blink: [1.2, 3.2], amp: 0.85, defaultEmotion: 'thinking' },
  SEARCHING:       { gaze: 'wander', blink: [1.5, 4.0], amp: 0.90, defaultEmotion: 'thinking' },
  READING_FILE:    { gaze: 'screen', blink: [2.0, 5.0], amp: 0.80, defaultEmotion: 'focused' },
  CODING:          { gaze: 'screen', blink: [2.2, 5.5], amp: 0.75, defaultEmotion: 'focused' },
  ANALYZING_IMAGE: { gaze: 'screen', blink: [1.5, 4.0], amp: 0.82, defaultEmotion: 'focused' },
  TOOL_RUNNING:    { gaze: 'wander', blink: [1.6, 4.2], amp: 0.85, defaultEmotion: 'focused' },
  SPEAKING:        { gaze: 'user',   blink: [1.6, 4.0], amp: 1.15, defaultEmotion: 'neutral' },
  ERROR:           { gaze: 'down',   blink: [1.0, 3.0], amp: 0.70, defaultEmotion: 'confused' },
};

// -------- ossos que o sistema controla (o resto fica com a pose do modelo) --------
export const CTRL_BONES = [
  'leftUpperArm', 'rightUpperArm', 'leftLowerArm', 'rightLowerArm',
  'leftHand', 'rightHand', 'head',
];

// -------- biblioteca de poses/gestos (graus). "rest" = braços ao lado. --------
export const POSES = {
  rest:        { leftUpperArm: [0, 0, -72], rightUpperArm: [0, 0, 72], leftLowerArm: [0, 4, -10], rightLowerArm: [0, -4, 10] },
  wave:        { rightUpperArm: [0, 0, 150], rightLowerArm: [0, -25, 20] },
  thumbs_up:   { rightUpperArm: [-25, 0, 80], rightLowerArm: [-95, 0, 10] },
  point:       { rightUpperArm: [-80, 0, 74], rightLowerArm: [0, 0, 5] },
  hand_explain:{ leftUpperArm: [-35, 0, -70], rightUpperArm: [-35, 0, 70], leftLowerArm: [-40, 10, -20], rightLowerArm: [-40, -10, 20] },
  shrug:       { leftUpperArm: [0, 0, -110], rightUpperArm: [0, 0, 110], leftLowerArm: [0, 40, -80], rightLowerArm: [0, -40, 80] },
  think:       { rightUpperArm: [-60, 0, 66], rightLowerArm: [-115, 0, 10], head: [10, -8, 0] },
  cheer:       { leftUpperArm: [0, 0, -165], rightUpperArm: [0, 0, 165] },
  raise_right: { rightUpperArm: [0, 0, 168] },
  raise_left:  { leftUpperArm: [0, 0, -168] },
};
export const GESTURE_ALIASES = { nice: 'thumbs_up', none: 'rest', nod: 'rest' };

export function resolveEmotion(name) {
  return EMOTIONS[EMOTION_ALIAS[name] || name] ? (EMOTION_ALIAS[name] || name) : 'neutral';
}
