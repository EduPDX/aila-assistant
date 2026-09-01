// Política de estabilidade para SpringBone. O three-vrm continua sendo o único
// solver; esta classe só saneia dados inválidos, subdivide frames longos e
// reinicializa o histórico Verlet depois de pausas/trocas de contexto.
export class SecondaryMotionController {
  constructor(vrm) {
    this.manager = vrm?.springBoneManager || null;
    this.quality = 'green';
    this.paused = false;
    this.pendingReset = false;
    this.stats = { joints: this.manager?.joints?.size || 0, corrected: 0, resets: 0, lastSteps: 0 };
    this._sanitize();
  }

  _sanitize() {
    if (!this.manager?.joints) return;
    for (const joint of this.manager.joints) {
      const s = joint.settings;
      if (!s) continue;
      if (!Number.isFinite(s.dragForce)) { s.dragForce = 0.4; this.stats.corrected++; }
      else if (s.dragForce < 0 || s.dragForce > 1) {
        s.dragForce = Math.max(0, Math.min(1, s.dragForce)); this.stats.corrected++;
      }
      if (!Number.isFinite(s.stiffness) || s.stiffness < 0) { s.stiffness = 1; this.stats.corrected++; }
      if (!Number.isFinite(s.gravityPower) || s.gravityPower < 0) { s.gravityPower = 0; this.stats.corrected++; }
      if (!Number.isFinite(s.hitRadius) || s.hitRadius < 0) { s.hitRadius = 0; this.stats.corrected++; }
    }
  }

  setQuality(state = 'green') { this.quality = ['green', 'yellow', 'red'].includes(state) ? state : 'green'; }

  setPaused(value) {
    const next = Boolean(value);
    if (this.paused && !next) this.pendingReset = true;
    this.paused = next;
  }

  reset() {
    if (!this.manager) return;
    try { this.manager.reset(); this.stats.resets++; } catch (_) { /* modelo sem estado inicial válido */ }
    this.pendingReset = false;
  }

  advance(vrm, dt) {
    if (!vrm || this.paused) return;
    if (!this.manager) { vrm.update(dt); return; }
    if (this.pendingReset || !Number.isFinite(dt) || dt > 0.12) this.reset();
    const safeDt = Math.max(0, Math.min(Number.isFinite(dt) ? dt : 0, 0.05));
    const maxSteps = this.quality === 'red' ? 1 : this.quality === 'yellow' ? 2 : 3;
    const targetStep = this.quality === 'red' ? 1 / 30 : 1 / 60;
    const steps = Math.max(1, Math.min(maxSteps, Math.ceil(safeDt / targetStep)));
    const step = safeDt / steps;
    this.stats.lastSteps = steps;
    for (let i = 0; i < steps; i++) vrm.update(step);
  }

  snapshot() { return { quality: this.quality, paused: this.paused, ...this.stats }; }
}

