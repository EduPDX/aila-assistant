// ============================================================
//  SCENE LOADER — carrega uma scene-definition.json e a aplica
//  à Cognitive Scene. Permite customização declarativa (temas,
//  layouts) sem modificar código. Fallback: hardcoded defaults.
// ============================================================

const DEFAULT_DEF = {
  monitor: { width: 2.9, height: 1.66 },
  statusPanel: { width: 1.0, height: 1.2 },
  composer: {
    monitorOffset: { x: -1.18, y: -0.04, z: 0.05 },
    monitorRotation: { x: 0, y: 0.26, z: 0 },
    statusOffset: { x: -2.55, y: -0.04, z: 0.05 },
    messageOffset: { x: 0.05, y: 0.32, z: 0.55 },
    avatarYaw: -0.22,
    cameraFitPadding: 1.12,
    cameraYOffset: 0.05,
    cameraXOffset: 0.04,
  },
  fog: { color: '#0a0e14', near: 7, far: 20 },
  grid: { size: 50, divisions: 100, opacity: 0.11 },
  ring: { innerRadius: 0.42, outerRadius: 0.46, segments: 48, rotationSpeed: 0.15 },
};

let _current = structuredClone(DEFAULT_DEF);

/** Retorna a definição ativa (cópia). */
export function getSceneDef() { return structuredClone(_current); }

/** Carrega uma scene-definition.json (fetch ou embed). Retorna a definição mesclada. */
export async function loadSceneDef(url) {
  if (!url) return _current;
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(r.status);
    const ext = await r.json();
    _current = mergeDeep(DEFAULT_DEF, ext);
  } catch (e) {
    console.warn('[scene-loader] fallback p/ defaults:', e.message);
    _current = structuredClone(DEFAULT_DEF);
  }
  return _current;
}

/** Aplica a definição à SceneManager (chamado após build). */
export function applySceneDef(sceneManager, def) {
  if (!def) def = _current;
  const c = def.composer || {};

  // grid
  if (sceneManager._grid && def.grid) {
    sceneManager._grid.material.opacity = def.grid.opacity ?? 0.11;
  }

  // anel
  if (sceneManager._ring && def.ring) {
    sceneManager._ringSpeed = def.ring.rotationSpeed ?? 0.15;
  }
}

/** Merge profundo (2 níveis). Não clona objetos aninhados além de 2. */
function mergeDeep(base, ext) {
  const out = { ...base };
  for (const k of Object.keys(ext)) {
    if (ext[k] && typeof ext[k] === 'object' && !Array.isArray(ext[k]) && base[k] && typeof base[k] === 'object') {
      out[k] = { ...base[k], ...ext[k] };
    } else {
      out[k] = ext[k];
    }
  }
  return out;
}
