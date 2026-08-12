// ============================================================
//  GESTURES — gestos como INTENÇÃO (não rotações FK cravadas).
//
//  Cada gesto descreve ONDE a mão vai (alvo) + a pose dos DEDOS + uma dica
//  opcional de cabeça. O IK resolve upperArm/lowerArm/cotovelo; joint-limits
//  e colisão contêm. Assim o braço é CONSEQUÊNCIA do destino da mão, não uma
//  soma de ângulos arbitrários (Objetivo 2).
//
//  target = offset da MÃO relativo ao OMBRO daquele braço, no FRAME DO AVATAR
//  (x = lado da mão / +direita, y = cima, z = frente), em unidades de
//  COMPRIMENTO DO BRAÇO (upperArm+lowerArm). O resolvedor (layers/gesture-ik.js)
//  deriva esse frame do rig e converte para mundo → escala/orientação-agnóstico.
//
//  Fase C (regra 7): só gestos do braço DIREITO por enquanto. Os de dois braços
//  (hand_explain) e o espelho p/ o esquerdo entram depois que o direito validar.
// ============================================================

export const GESTURES = {
  // apontar à frente: braço estendido p/ frente, indicador esticado
  point:     { side: 'right', target: [0.28, -0.04, 0.82], hand: 'point' },
  // joinha: mão à frente do peito, polegar p/ cima
  thumbs_up: { side: 'right', target: [0.22, 0.10, 0.52], hand: 'thumbs_up' },
  // aceno: mão levantada à altura do ombro/cabeça, palma aberta
  wave:      { side: 'right', target: [0.42, 0.52, 0.34], hand: 'open' },
  // pensar: mão perto do queixo, dedos semi-dobrados + leve inclinação de cabeça
  think:     { side: 'right', target: [0.10, 0.28, 0.34], hand: 'thinking', head: [10, -8, 0] },
};
