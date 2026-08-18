// ============================================================
//  INTERACTION TYPES — mapa extensível: tipo de interação → (pose de dedo,
//  alcance do braço, tempo de permanência). O InteractionManager usa isto p/
//  traduzir {type,target} em alvo de mão (IK) + pose. Novos tipos = 1 linha.
// ============================================================
export const INTERACTIONS = {
  point:   { pose: 'point', reach: 0.44, hold: 3.2 },   // aponta o indicador
  inspect: { pose: 'open',  reach: 0.40, hold: 3.8 },   // mão aberta "examinando"
  select:  { pose: 'point', reach: 0.44, hold: 2.2 },
  touch:   { pose: 'point', reach: 0.46, hold: 2.0 },
};
export const DEFAULT_INTERACTION = { pose: 'point', reach: 0.44, hold: 2.8 };
