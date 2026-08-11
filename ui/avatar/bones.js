// ============================================================
//  BONES — mapa ÚNICO de nomes de ossos humanoides (VRM 1.0).
//
//  Verificado no rig REAL (Aila.vrm): 54 humanBones, nomenclatura padrão
//  VRM 1.0. Centraliza os nomes para IK, gestos e poses de mão NÃO espalharem
//  strings pelo código (regra: "centralize o mapeamento de bones").
//
//  IMPORTANTE: aqui só há NOMES (dados). A orientação real dos eixos X/Y/Z
//  de cada osso é verificada EMPIRICAMENTE nas fases que de fato rotacionam
//  esses ossos (Fase B/C) — não assumimos eixo nenhum a partir daqui.
// ============================================================

export const SIDES = ['left', 'right'];

// cadeia do braço por lado: ombro → braço → antebraço → mão
export const ARM = {
  left:  { shoulder: 'leftShoulder',  upperArm: 'leftUpperArm',  lowerArm: 'leftLowerArm',  hand: 'leftHand' },
  right: { shoulder: 'rightShoulder', upperArm: 'rightUpperArm', lowerArm: 'rightLowerArm', hand: 'rightHand' },
};

// 5 dedos × 3 segmentos. Polegar usa Metacarpal/Proximal/Distal;
// os demais usam Proximal/Intermediate/Distal (padrão VRM 1.0).
export const FINGERS = ['Thumb', 'Index', 'Middle', 'Ring', 'Little'];
const SEGMENTS = {
  Thumb: ['Metacarpal', 'Proximal', 'Distal'],
  _default: ['Proximal', 'Intermediate', 'Distal'],
};

/** nomes dos 3 ossos de UM dedo, na ordem raiz→ponta.
 *  Ex.: fingerBones('left', 'Index') → ['leftIndexProximal','leftIndexIntermediate','leftIndexDistal'] */
export function fingerBones(side, finger) {
  const segs = SEGMENTS[finger] || SEGMENTS._default;
  return segs.map((seg) => `${side}${finger}${seg}`);
}

/** todos os 15 ossos de dedo de um lado (Thumb..Little, raiz→ponta) */
export function handFingerBones(side) {
  return FINGERS.flatMap((f) => fingerBones(side, f));
}

// nomes do tronco/cabeça (referência única; as camadas atuais ainda usam
// literais — migração opcional e fora do escopo desta fase).
export const SPINE_CHAIN = ['hips', 'spine', 'chest', 'upperChest', 'neck', 'head'];
