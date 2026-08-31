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
  const w = 0.72 * scale, h = 1.76 * scale, d = 0.42 * scale;
  const color = STATUS_COLOR[data.status] ?? HOLO.blue;

  const shell = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), fillMat(color, data.status === 'offline' ? 0.035 : 0.075));
  root.add(shell);
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(shell.geometry), new THREE.LineBasicMaterial({
    color, transparent: true, opacity: data.status === 'active' ? 0.42 : data.status === 'offline' ? 0.09 : 0.2,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }));
  root.add(edges);

  // Base, teto e trilhos dão leitura de rack de verdade, não apenas uma caixa.
  const slabGeo = new THREE.BoxGeometry(w * 1.08, h * 0.035, d * 1.12);
  const slabMat = fillMat(color, data.status === 'offline' ? 0.05 : 0.14);
  const base = new THREE.Mesh(slabGeo, slabMat);
  base.position.y = -h * 0.482; root.add(base);
  const top = new THREE.Mesh(slabGeo, slabMat);
  top.position.y = h * 0.482; root.add(top);
  const railGeo = new THREE.BoxGeometry(w * 0.035, h * 0.88, d * 0.025);
  for (const x of [-w * 0.44, w * 0.44]) {
    const rail = new THREE.Mesh(railGeo, fillMat(color, 0.22));
    rail.position.set(x, 0, d * 0.515); root.add(rail);
  }

  // Slots frontais em uma única geometria de linhas.
  const pts = [];
  for (let i = 0; i < 14; i++) {
    const y = -h * 0.39 + i * h * 0.058;
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

  // Módulos centrais e ventiladores: detalhes baratos, todos no painel frontal.
  const bayGeo = new THREE.PlaneGeometry(w * 0.54, h * 0.035);
  const bayMat = fillMat(color, 0.16);
  for (let i = 0; i < 7; i++) {
    const bay = new THREE.Mesh(bayGeo, bayMat);
    bay.position.set(0, -h * 0.34 + i * h * 0.105, d * 0.522); root.add(bay);
  }
  const fanGeo = new THREE.RingGeometry(w * 0.055, w * 0.09, 18);
  for (const x of [-w * 0.16, w * 0.16]) {
    const fan = new THREE.Mesh(fanGeo, glowMat(color, 0.28));
    fan.position.set(x, h * 0.34, d * 0.525); root.add(fan);
  }

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

  root.userData = { index, status: data.status, leds, baseOpacity: ledMat.opacity, phase: index * 0.71, rackHeight: h, rackWidth: w };
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
    racks = data.map((item, i) => createRack(item, i));
    const gap = 0.16;
    const total = racks.reduce((sum, rack) => sum + rack.userData.rackWidth, 0) + gap * (racks.length - 1);
    let cursor = -total / 2;
    racks.forEach((rack, i) => {
      cursor += rack.userData.rackWidth / 2;
      // Cada gabinete encosta no mesmo piso independentemente de sua escala.
      rack.position.set(cursor, rack.userData.rackHeight / 2, -Math.abs(i - (data.length - 1) / 2) * 0.10);
      rack.rotation.y = (i - (data.length - 1) / 2) * -0.045;
      group.add(rack);
      cursor += rack.userData.rackWidth / 2 + gap;
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
