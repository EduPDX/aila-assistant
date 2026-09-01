// Coordena a atenção visual sem conhecer Three.js ou o VRM. Mantém um único
// alvo, resolve prioridades e suaviza entrada/saída para olhos, cabeça e tronco
// receberem a mesma intenção sem saltos.
const PRIORITY = Object.freeze({ state: 20, behavior: 45, scene: 65, interaction: 80, user: 90, debug: 100 });

const damp = (cur, target, k, dt) => cur + (target - cur) * (1 - Math.exp(-k * dt));

export class AttentionController {
  constructor() {
    this.current = { x: 0, y: 0, z: 0, weight: 0, source: '' };
    this.target = { x: 0, y: 0, z: 0 };
    this.active = null;
    this._nextId = 1;
  }

  focus(x, y, z, now = 0, { source = 'interaction', hold = 0 } = {}) {
    const priority = PRIORITY[source] ?? PRIORITY.behavior;
    if (this.active && this.active.priority > priority) {
      return { accepted: false, reason: 'priority', id: this.active.id };
    }
    const id = this._nextId++;
    this.target.x = Number(x) || 0; this.target.y = Number(y) || 0; this.target.z = Number(z) || 0;
    if (this.current.weight <= 0.001) {
      this.current.x = this.target.x; this.current.y = this.target.y; this.current.z = this.target.z;
    }
    this.current.source = source;
    this.active = { id, source, priority, expires: hold > 0 ? now + hold : 0 };
    return { accepted: true, id };
  }

  release(id = 0, source = '') {
    if (!this.active) return false;
    if (id && this.active.id !== id) return false;
    if (source && this.active.source !== source) return false;
    this.active = null;
    return true;
  }

  update(now, dt) {
    if (this.active?.expires && now >= this.active.expires) this.active = null;
    const weight = this.active ? 1 : 0;
    this.current.weight = damp(this.current.weight, weight, this.active ? 9 : 5, dt);
    if (this.active) {
      this.current.x = damp(this.current.x, this.target.x, 8, dt);
      this.current.y = damp(this.current.y, this.target.y, 8, dt);
      this.current.z = damp(this.current.z, this.target.z, 8, dt);
    }
    return this.current.weight > 0.002 ? this.current : null;
  }

  snapshot() {
    return { active: this.active ? { ...this.active } : null, current: { ...this.current }, target: { ...this.target } };
  }
}
