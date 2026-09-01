// Estado operacional do avatar, sem dependência de Three.js. O guard evita que
// um carregamento antigo substitua o modelo mais recente; o monitor mantém
// métricas agregadas sem alocar objetos no loop de render.
export class AvatarLoadGuard {
  constructor() { this.generation = 0; this.current = null; }
  begin(url) { this.current = { id: ++this.generation, url }; return this.current; }
  isCurrent(ticket) { return Boolean(ticket) && ticket.id === this.generation; }
  invalidate() { this.current = null; this.generation++; }
}

export class AvatarRuntimeHealth {
  constructor() {
    this.frames = 0; this.avgFrameMs = 0; this.maxFrameMs = 0; this.slowFrames = 0;
    this.loads = 0; this.staleLoads = 0; this.loadFailures = 0; this.contextLosses = 0;
    this.model = ''; this.version = ''; this.springJoints = 0; this.lastPhysicsSteps = 0;
  }
  frame(dt, physics = null) {
    const ms = Math.max(0, dt * 1000);
    this.frames++;
    this.avgFrameMs += (ms - this.avgFrameMs) * 0.03;
    if (ms > this.maxFrameMs) this.maxFrameMs = ms;
    if (ms > 34) this.slowFrames++;
    this.lastPhysicsSteps = physics?.stats?.lastSteps || 0;
  }
  loaded(profile) {
    this.loads++; this.model = profile?.name || ''; this.version = profile?.version || '';
    this.springJoints = profile?.capabilities?.springBoneJoints || 0;
  }
  snapshot() {
    return {
      fps: this.avgFrameMs > 0 ? Math.round(10000 / this.avgFrameMs) / 10 : 0,
      avgFrameMs: Math.round(this.avgFrameMs * 100) / 100,
      maxFrameMs: Math.round(this.maxFrameMs * 100) / 100,
      frames: this.frames, slowFrames: this.slowFrames, loads: this.loads,
      staleLoads: this.staleLoads, loadFailures: this.loadFailures, contextLosses: this.contextLosses,
      model: this.model, version: this.version, springJoints: this.springJoints,
      lastPhysicsSteps: this.lastPhysicsSteps,
    };
  }
}

