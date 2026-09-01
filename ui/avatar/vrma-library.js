// Biblioteca VRMA independente do renderer. Cacheia a animação-fonte uma vez e
// o clip retargeteado por instância de VRM, evitando reutilizar tracks ligados
// aos ossos do avatar anterior.
export class VRMALibrary {
  constructor({ definitions, loader, retarget, root = '/static/models/gestures/' }) {
    this.definitions = definitions;
    this.loader = loader;
    this.retarget = retarget;
    this.root = root;
    this.sources = new Map();       // nome -> {status,promise,value}
    this.clips = new WeakMap();     // vrm -> Map(nome, AnimationClip)
    this.vrm = null;
    this.controller = null;
    this.generation = 0;
    this.stats = { loads: 0, retargets: 0, stale: 0, failures: 0 };
  }

  setTarget(vrm, controller) {
    this.vrm = vrm; this.controller = controller; this.generation++;
  }

  clearTarget() { this.vrm = null; this.controller = null; this.generation++; }

  supports(name) { return Boolean(this.definitions[name]) && this.sources.get(name)?.status !== 'fail'; }

  preload(names = Object.keys(this.definitions)) {
    return Promise.allSettled(names.filter((name) => this.definitions[name]).map((name) => this._source(name)));
  }

  play(name, motionId = 0) {
    if (!this.supports(name) || !this.vrm || !this.controller) return false;
    const vrm = this.vrm, controller = this.controller, generation = this.generation;
    this._source(name).then((source) => {
      const validTarget = generation === this.generation && vrm === this.vrm && controller === this.controller;
      const validMotion = !motionId || controller.motionScheduler.has(motionId);
      if (!validTarget || !validMotion) { this.stats.stale++; return; }
      const clip = this._retarget(name, source, vrm);
      controller.playClip(clip, { motionId, fade: name.startsWith('talk') ? 0.42 : 0.28 });
    }).catch(() => {
      this.stats.failures++;
      const valid = generation === this.generation && controller === this.controller;
      if (valid && motionId && controller.motionScheduler.has(motionId)) {
        controller.playFallbackGesture(name, motionId);
      }
    });
    return true;
  }

  _source(name) {
    const cached = this.sources.get(name);
    if (cached?.status === 'ready') return Promise.resolve(cached.value);
    if (cached?.status === 'loading') return cached.promise;
    if (cached?.status === 'fail') return Promise.reject(new Error('VRMA indisponível'));
    const file = this.definitions[name];
    this.stats.loads++;
    const entry = { status: 'loading', promise: null, value: null };
    entry.promise = new Promise((resolve, reject) => {
      this.loader.load(this.root + file, (gltf) => {
        const source = gltf.userData.vrmAnimations?.[0];
        if (!source) { entry.status = 'fail'; reject(new Error('VRMA sem animação')); return; }
        entry.status = 'ready'; entry.value = source; resolve(source);
      }, undefined, (error) => { entry.status = 'fail'; reject(error); });
    });
    this.sources.set(name, entry);
    return entry.promise;
  }

  _retarget(name, source, vrm) {
    let byName = this.clips.get(vrm);
    if (!byName) { byName = new Map(); this.clips.set(vrm, byName); }
    let clip = byName.get(name);
    if (clip) return clip;
    clip = this.retarget(source, vrm);
    // Gesto permanece no palco: posições de root/hips de clips externos não
    // podem deslocar o avatar para baixo ou para fora da câmera.
    clip.tracks = clip.tracks.filter((track) => !track.name.endsWith('.position'));
    byName.set(name, clip); this.stats.retargets++;
    return clip;
  }

  snapshot() {
    const sourceStates = {};
    for (const [name, entry] of this.sources) sourceStates[name] = entry.status;
    return { generation: this.generation, target: Boolean(this.vrm), sources: sourceStates, ...this.stats };
  }
}
