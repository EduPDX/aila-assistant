// Salão holográfico: cada rack representa uma ferramenta cognitiva da Aila.
// Procedural, sem assets externos; LEDs usam InstancedMesh e o loop não aloca.
import * as THREE from 'three';
import { HOLO, fillMat, glowMat, textPlane, disposeObject } from './primitives.js';

const STATUS_COLOR = { active: 0x64ffd8, ready: HOLO.blue, offline: 0x46536b };
const MAX_RACKS = 10;

function rackLabel(raw) {
  const s = String(raw || 'MODELO');
  const low = s.toLowerCase();
  if (low.includes('nemotron')) return `NEMOTRON ${low.match(/\d+(?:\.\d+)?b/)?.[0]?.toUpperCase() || ''}`.trim();
  if (low.includes('gemini')) return 'GEMINI FLASH';
  if (low.includes('nomic-embed')) return 'NOMIC EMBED';
  if (low.includes('qwen') && low.includes('coder')) return `QWEN CODER ${low.match(/\d+(?:\.\d+)?b/)?.[0]?.toUpperCase() || ''}`.trim();
  if (low.includes('qwen')) return `QWEN ${low.match(/\d+(?:\.\d+)?b/)?.[0]?.toUpperCase() || ''}`.trim();
  if (low.includes('llava')) return `LLAVA ${low.match(/\d+(?:\.\d+)?b/)?.[0]?.toUpperCase() || ''}`.trim();
  return s.length > 24 ? `${s.slice(0, 21)}…` : s;
}

function createRack(data, index) {
  const root = new THREE.Group();
  root.name = `model-rack:${data.id}`;
  const scale = Math.max(0.72, Math.min(1.48, Number(data.scale) || 1));
  const w = 0.52 * scale, h = 1.72 * scale, d = 0.28 * scale;
  const color = STATUS_COLOR[data.status] ?? HOLO.blue;

  const shell = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), fillMat(color, data.status === 'offline' ? 0.035 : 0.075));
  root.add(shell);
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(shell.geometry), new THREE.LineBasicMaterial({
    color, transparent: true, opacity: data.status === 'active' ? 0.42 : data.status === 'offline' ? 0.09 : 0.2,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }));
  root.add(edges);

  // Slots frontais em uma única geometria de linhas.
  const pts = [];
  for (let i = 0; i < 10; i++) {
    const y = -h * 0.36 + i * h * 0.075;
    pts.push(-w * 0.38, y, d * 0.51, w * 0.38, y, d * 0.51);
  }
  const slotGeo = new THREE.BufferGeometry();
  slotGeo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  root.add(new THREE.LineSegments(slotGeo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.3, depthWrite: false })));

  // LEDs: 12 instâncias, um draw call por rack.
  const ledGeo = new THREE.PlaneGeometry(0.025 * scale, 0.009 * scale);
  const ledMat = glowMat(color, data.status === 'offline' ? 0.12 : 0.8);
  const leds = new THREE.InstancedMesh(ledGeo, ledMat, 12);
  const matrix = new THREE.Matrix4();
  for (let i = 0; i < 12; i++) {
    matrix.makeTranslation((i % 2 ? 1 : -1) * w * 0.3, -h * 0.34 + Math.floor(i / 2) * h * 0.12, d * 0.515);
    leds.setMatrixAt(i, matrix);
  }
  root.add(leds);

  const title = textPlane(rackLabel(data.label), { width: w * 1.45, px: 512, size: 38, align: 'center' });
  title.mesh.position.set(0, h * 0.58, d * 0.53);
  root.add(title.mesh);
  const metaText = `${data.location === 'local' ? 'LOCAL' : 'CLOUD'} // ${(data.status || 'offline').toUpperCase()}`;
  const meta = textPlane(metaText, { width: w, px: 384, size: 24, align: 'center', color: data.status === 'offline' ? '#738198' : '#9fd0c6' });
  meta.mesh.position.set(0, h * 0.49, d * 0.53);
  root.add(meta.mesh);

  // Transparências da cena principal também não escrevem profundidade. Uma
  // ordem negativa garante que o salão seja realmente o pano de fundo.
  root.traverse((obj) => { obj.renderOrder = -20; });

  root.userData = { index, status: data.status, leds, baseOpacity: ledMat.opacity, phase: index * 0.71 };
  return root;
}

export function createServerHall() {
  const group = new THREE.Group();
  group.name = 'cognitive-infrastructure';
  let racks = [];
  let elapsed = 0;

  function clear() {
    for (const rack of racks) { group.remove(rack); disposeObject(rack); }
    racks = [];
  }

  function setData(payload = {}) {
    clear();
    const data = Array.isArray(payload.racks) ? payload.racks.slice(0, MAX_RACKS) : [];
    if (!data.length) { group.visible = false; return; }
    group.visible = true;
    const gap = 0.72;
    const total = (data.length - 1) * gap;
    racks = data.map((item, i) => {
      const rack = createRack(item, i);
      rack.position.set(i * gap - total / 2, 0.86, -Math.abs(i - (data.length - 1) / 2) * 0.08);
      rack.rotation.y = (i - (data.length - 1) / 2) * -0.045;
      group.add(rack);
      return rack;
    });
  }

  function update(dt) {
    elapsed += dt;
    for (const rack of racks) {
      const u = rack.userData;
      if (u.status === 'active') u.leds.material.opacity = 0.68 + Math.sin(elapsed * 4 + u.phase) * 0.24;
      else u.leds.material.opacity = u.baseOpacity;
    }
  }

  return { group, setData, update, dispose: clear };
}
