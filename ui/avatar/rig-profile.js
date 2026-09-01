// Perfil estrutural calculado uma vez para cada VRM carregado.
// Mantém diferenças de modelo fora das camadas de comportamento.
const REQUIRED = [
  'hips', 'spine', 'head',
  'leftUpperArm', 'leftLowerArm', 'leftHand',
  'rightUpperArm', 'rightLowerArm', 'rightHand',
];

const EXPRESSION_CANDIDATES = Object.freeze({
  neutral: ['neutral'], happy: ['happy', 'joy', 'fun'], angry: ['angry'],
  sad: ['sad', 'sorrow'], relaxed: ['relaxed', 'fun'], surprised: ['surprised'],
  aa: ['aa', 'a', 'mouth_a'], ih: ['ih', 'i', 'mouth_i'],
  ou: ['ou', 'u', 'mouth_u'], ee: ['ee', 'e', 'mouth_e'], oh: ['oh', 'o', 'mouth_o'],
  blink: ['blink'], blinkLeft: ['blinkLeft', 'blink_l'], blinkRight: ['blinkRight', 'blink_r'],
});

export function createExpressionMap(expressions = []) {
  const actual = new Map(expressions.map((name) => [String(name).toLowerCase(), name]));
  const mapped = {};
  for (const [semantic, candidates] of Object.entries(EXPRESSION_CANDIDATES)) {
    const found = candidates.map((name) => actual.get(name.toLowerCase())).find(Boolean);
    if (found) mapped[semantic] = found;
  }
  return Object.freeze(mapped);
}

function worldDistance(a, b) {
  if (!a || !b) return 0;
  const ae = a.matrixWorld.elements, be = b.matrixWorld.elements;
  const x = ae[12] - be[12], y = ae[13] - be[13], z = ae[14] - be[14];
  return Math.sqrt(x * x + y * y + z * z);
}

/** Cria um retrato somente-leitura das capacidades e proporções do modelo. */
export function createRigProfile(vrm) {
  const humanoid = vrm?.humanoid;
  const bone = (name) => humanoid?.getNormalizedBoneNode(name) || null;
  vrm?.scene?.updateMatrixWorld(true);

  const present = {};
  for (const name of REQUIRED) present[name] = Boolean(bone(name));
  const lUpper = bone('leftUpperArm'), lLower = bone('leftLowerArm'), lHand = bone('leftHand');
  const rUpper = bone('rightUpperArm'), rLower = bone('rightLowerArm'), rHand = bone('rightHand');
  const head = bone('head'), hips = bone('hips');
  const expressions = vrm?.expressionManager?.expressions?.map((e) => e.expressionName) || [];
  const expressionMap = createExpressionMap(expressions);

  return Object.freeze({
    version: vrm?.meta?.metaVersion === '1' ? '1' : '0',
    name: vrm?.meta?.name || vrm?.meta?.title || 'VRM',
    humanoidComplete: REQUIRED.every((name) => present[name]),
    bones: Object.freeze(present),
    proportions: Object.freeze({
      height: worldDistance(hips, head),
      leftArm: worldDistance(lUpper, lLower) + worldDistance(lLower, lHand),
      rightArm: worldDistance(rUpper, rLower) + worldDistance(rLower, rHand),
      shoulderWidth: worldDistance(lUpper, rUpper),
    }),
    capabilities: Object.freeze({
      lookAt: Boolean(vrm?.lookAt),
      expressions: Object.freeze(expressions),
      expressionMap,
      springBone: Boolean(vrm?.springBoneManager),
      nodeConstraints: Boolean(vrm?.nodeConstraintManager),
    }),
  });
}
