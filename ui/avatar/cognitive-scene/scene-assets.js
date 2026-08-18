// ============================================================
//  SCENE ASSETS — carregamento OPCIONAL de meshes GLB para a
//  Cognitive Scene. Se existirem arquivos em ui/models/cognitive/,
//  são carregados e substituem os elementos procedurais. Caso
//  contrário, tudo fica 100% procedural (fallback gracioso).
//
//  Assets suportados (todos opcionais):
//    monitor.glb   → substitui o monitor holográfico
//    status.glb    → substitui o painel de status
//    message.glb   → substitui o balão de mensagem
//    floor.glb     → substitui o grid procedural
// ============================================================
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { disposeObject } from './procedural/primitives.js';

const ASSET_DIR = '/static/models/cognitive/';
const loader = new GLTFLoader();
const _cache = new Map();

/** Tenta carregar um GLB. Retorna o scene do GLTF ou null se não existir. */
async function loadGLB(name) {
  if (_cache.has(name)) return _cache.get(name);
  try {
    const gltf = await new Promise((res, rej) => {
      loader.load(ASSET_DIR + name + '.glb', res, undefined, rej);
    });
    const root = gltf.scene || gltf.scenes?.[0];
    if (root) { root.traverse((o) => { o.frustumCulled = false; }); _cache.set(name, root); }
    return root || null;
  } catch {
    _cache.set(name, null);
    return null;
  }
}

/** Pré-carrega todos os assets conhecidos (chamado no boot, non-blocking).
 *  OPT-IN: só tenta carregar GLB se `localStorage 'aila.scene.assets'==='on'`.
 *  Por padrão (sem GLBs), NÃO faz requisição nenhuma → zero 404 no console,
 *  tudo procedural. Ligue a flag depois de colocar arquivos em models/cognitive/. */
export async function preloadAssets() {
  try { if (localStorage.getItem('aila.scene.assets') !== 'on') return false; } catch { return false; }
  const names = ['monitor', 'status', 'message', 'floor'];
  const results = await Promise.allSettled(names.map(loadGLB));
  const loaded = results.filter((r) => r.status === 'fulfilled' && r.value).length;
  if (loaded) console.log(`[scene-assets] ${loaded}/${names.length} GLB(s) carregados`);
  return loaded > 0;
}

/** Retorna um asset por nome (já carregado ou null). Síncrono: só funciona
 *  depois de preloadAssets(). */
export function getAsset(name) { return _cache.get(name) || null; }

/** clone profundo de um asset (para reuso entre rebuilds). */
export function cloneAsset(root) {
  if (!root) return null;
  return root.clone(true);
}
