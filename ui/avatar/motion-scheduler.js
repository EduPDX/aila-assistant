// Scheduler determinístico de movimentos do avatar.
// Decide QUEM pode controlar cada região corporal; não conhece Three.js/VRM.
const ARM_R = ['rightArm', 'rightHand'];
const ARM_L = ['leftArm', 'leftHand'];
const BOTH = [...ARM_L, ...ARM_R];
const ALL = [...BOTH, 'head', 'shoulders', 'torso', 'pose'];
const POSE_R = [...ARM_R, 'pose'];
const POSE_L = [...ARM_L, 'pose'];
const POSE_BOTH = [...BOTH, 'pose'];

const DEFINITIONS = {
  nod:          { owners: ['head'], duration: 0.9 },
  shake:        { owners: ['head'], duration: 1.0 },
  wave:         { owners: [...POSE_R, 'torso'], duration: 1.7 },
  point:        { owners: POSE_R, duration: 1.7 },
  thumbs_up:    { owners: POSE_R, duration: 1.7 },
  think:        { owners: [...POSE_R, 'head'], duration: 1.8 },
  raise_right:  { owners: POSE_R, duration: 1.7 },
  raise_left:   { owners: POSE_L, duration: 1.7 },
  raise_both:   { owners: POSE_BOTH, duration: 1.9 },
  hand_explain: { owners: POSE_BOTH, duration: 1.8 },
  shrug:        { owners: [...POSE_BOTH, 'shoulders'], duration: 1.7 },
  cheer:        { owners: [...POSE_BOTH, 'shoulders', 'torso'], duration: 2.0 },
};

const SOURCE_PRIORITY = {
  speech: 20,
  behavior: 45,
  sequence: 65,
  user: 85,
  debug: 100,
};

export class MotionScheduler {
  constructor() {
    this.active = new Map();       // região -> movimento
    this.lastAccepted = new Map(); // assinatura -> instante
    this.serial = 0;
  }

  request(name, now, { source = 'user', priority = null, force = false } = {}) {
    if (name === 'rest' || name === 'none') {
      // O repouso automático de uma sequência só pode liberar a pose que a
      // própria sequência possui. Nunca cancela um gesto mais novo do usuário.
      if (source !== 'user' && source !== 'debug') {
        const cur = this.active.get('pose');
        if (!cur || cur.source !== source) return { accepted: false, reason: 'stale_rest' };
        this.release(cur.id);
        return { accepted: true, id: cur.id, name: 'rest', owners: cur.owners };
      }
      this.cancelAll();
      return { accepted: true, id: 0, name: 'rest', owners: ALL };
    }
    const def = DEFINITIONS[name] || { owners: ALL, duration: 1.7 };
    const p = priority ?? SOURCE_PRIORITY[source] ?? SOURCE_PRIORITY.behavior;
    const signature = `${source}:${name}`;
    const last = this.lastAccepted.get(signature) ?? -Infinity;
    // Mesmo evento costuma chegar pela ponte mais de uma vez em poucos ms.
    if (!force && now - last < Math.min(1.25, def.duration * 0.8)) {
      return { accepted: false, reason: 'duplicate' };
    }

    const conflicts = new Set();
    for (const owner of def.owners) {
      const cur = this.active.get(owner);
      if (!cur) continue;
      if (!force && cur.priority >= p && cur.expiresAt > now) {
        return { accepted: false, reason: 'owned', blockedBy: cur.name };
      }
      conflicts.add(cur.id);
    }
    for (const id of conflicts) this.release(id);

    const motion = {
      id: ++this.serial,
      name,
      source,
      priority: p,
      owners: def.owners,
      expiresAt: now + def.duration,
      duration: def.duration,
    };
    for (const owner of motion.owners) this.active.set(owner, motion);
    this.lastAccepted.set(signature, now);
    return { accepted: true, ...motion };
  }

  release(id) {
    if (!id) return;
    for (const [owner, motion] of this.active) {
      if (motion.id === id) this.active.delete(owner);
    }
  }

  tick(now) {
    const expired = new Set();
    for (const motion of this.active.values()) if (motion.expiresAt <= now) expired.add(motion.id);
    for (const id of expired) this.release(id);
  }

  owns(owner) { return this.active.get(owner) || null; }
  has(id) {
    if (!id) return false;
    for (const motion of this.active.values()) if (motion.id === id) return true;
    return false;
  }
  snapshot() {
    const unique = new Map();
    for (const motion of this.active.values()) unique.set(motion.id, motion);
    return Array.from(unique.values()).map((m) => ({ ...m, owners: [...m.owners] }));
  }
  cancelAll() { this.active.clear(); }
}

export const MOTION_DEFINITIONS = DEFINITIONS;
