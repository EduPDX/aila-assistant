// Salão holográfico: cada rack representa uma ferramenta cognitiva da Aila.
// Procedural, sem assets externos; LEDs usam InstancedMesh e o loop não aloca.
import * as THREE from 'three';
import { HOLO, fillMat, glowMat, textPlane, disposeObject } from './primitives.js';

const STATUS_COLOR = { active: 0x64ffd8, ready: HOLO.blue, offline: 0x46536b };
const MAX_RACKS = 10;
const PORT_COLORS = [
  new THREE.Color(0x36ff9a), // tráfego normal
  new THREE.Color(0x49bfff), // atividade de rede/modelo
  new THREE.Color(0xff4d5e), // alerta breve
  new THREE.Color(0x061018), // pulso apagado
];

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
  const scale = Math.max(0.82, Math.min(1.34, Number(data.scale) || 1));
  // Mantém proporção por capacidade, mas dentro de dimensões de um rack 19".
  const w = 0.82 * (0.92 + scale * 0.08), h = 1.76 * scale, d = 0.64;
  const color = STATUS_COLOR[data.status] ?? HOLO.blue;

  const cabinetMat = new THREE.MeshBasicMaterial({
    color: 0x071421, transparent: true, opacity: data.status === 'offline' ? 0.22 : 0.48,
    depthWrite: true, side: THREE.DoubleSide,
  });
  const shell = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), cabinetMat);
  root.add(shell);
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(shell.geometry), new THREE.LineBasicMaterial({
    color, transparent: true, opacity: data.status === 'active' ? 0.42 : data.status === 'offline' ? 0.09 : 0.2,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }));
  root.add(edges);

  // Base, teto e trilhos dão leitura de rack de verdade, não apenas uma caixa.
  const slabGeo = new THREE.BoxGeometry(w * 1.08, h * 0.035, d * 1.08);
  const slabMat = fillMat(color, data.status === 'offline' ? 0.05 : 0.14);
  const base = new THREE.Mesh(slabGeo, slabMat);
  base.position.y = -h * 0.482; root.add(base);
  const top = new THREE.Mesh(slabGeo, slabMat);
  top.position.y = h * 0.482; root.add(top);
  const railGeo = new THREE.BoxGeometry(w * 0.045, h * 0.91, d * 0.035);
  for (const x of [-w * 0.44, w * 0.44]) {
    const rail = new THREE.Mesh(railGeo, fillMat(color, 0.22));
    rail.position.set(x, 0, d * 0.525); root.add(rail);
  }

  // Porta frontal rebaixada + marcações das unidades do rack.
  const door = new THREE.Mesh(
    new THREE.PlaneGeometry(w * 0.86, h * 0.82),
    new THREE.MeshBasicMaterial({ color: 0x091c2c, transparent: true, opacity: 0.72, depthWrite: true }),
  );
  door.position.set(0, -h * 0.025, d * 0.532); root.add(door);
  const pts = [];
  const units = 18;
  for (let i = 0; i <= units; i++) {
    const y = -h * 0.41 + i * h * 0.82 / units;
    pts.push(-w * 0.40, y, d * 0.538, w * 0.40, y, d * 0.538);
  }
  const slotGeo = new THREE.BufferGeometry();
  slotGeo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  root.add(new THREE.LineSegments(slotGeo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.3, depthWrite: false })));

  // LEDs: duas colunas de atividade, um draw call por rack.
  const ledGeo = new THREE.BoxGeometry(w * 0.025, h * 0.007, d * 0.018);
  const ledMat = glowMat(color, data.status === 'offline' ? 0.12 : 0.8);
  const leds = new THREE.InstancedMesh(ledGeo, ledMat, 12);
  const matrix = new THREE.Matrix4();
  for (let i = 0; i < 12; i++) {
    matrix.makeTranslation((i % 2 ? 1 : -1) * w * 0.34, -h * 0.34 + Math.floor(i / 2) * h * 0.115, d * 0.548);
    leds.setMatrixAt(i, matrix);
  }
  root.add(leds);

  // Servidores 1U/2U, gavetas, puxadores e grelhas de ventilação.
  const moduleGeo = new THREE.BoxGeometry(w * 0.67, h * 0.052, d * 0.035);
  const modules = new THREE.InstancedMesh(moduleGeo, new THREE.MeshBasicMaterial({
    color: data.status === 'active' ? 0x174f59 : 0x10283d, transparent: true, opacity: 0.92,
  }), 10);
  const handleGeo = new THREE.BoxGeometry(w * 0.07, h * 0.012, d * 0.018);
  const handles = new THREE.InstancedMesh(handleGeo, glowMat(color, 0.46), 20);
  const mm = new THREE.Matrix4();
  for (let i = 0; i < 10; i++) {
    const y = -h * 0.35 + i * h * 0.071;
    mm.makeTranslation(0, y, d * 0.548); modules.setMatrixAt(i, mm);
    mm.makeTranslation(-w * 0.27, y, d * 0.57); handles.setMatrixAt(i * 2, mm);
    mm.makeTranslation(w * 0.27, y, d * 0.57); handles.setMatrixAt(i * 2 + 1, mm);
  }
  root.add(modules, handles);

  // Malha perfurada nos módulos: 60 furos em um único draw call. É o detalhe
  // que faz a frente lembrar uma grade de ventilação de servidor real.
  const holeGeo = new THREE.BoxGeometry(w * 0.010, h * 0.006, d * 0.010);
  const holes = new THREE.InstancedMesh(holeGeo, new THREE.MeshBasicMaterial({
    color: 0x02070c, transparent: true, opacity: 0.95,
  }), 60);
  let hi = 0;
  for (let row = 0; row < 10; row++) for (let col = 0; col < 6; col++) {
    const y = -h * 0.35 + row * h * 0.071;
    const x = -w * 0.15 + col * w * 0.035;
    mm.makeTranslation(x, y, d * 0.568); holes.setMatrixAt(hi++, mm);
  }
  root.add(holes);

  // Quatro baias hot-swap com recorte, trava e LED próprio.
  const driveGeo = new THREE.BoxGeometry(w * 0.105, h * 0.105, d * 0.025);
  const drives = new THREE.InstancedMesh(driveGeo, new THREE.MeshBasicMaterial({
    color: 0x0b2130, transparent: true, opacity: 0.96,
  }), 4);
  const latchGeo = new THREE.BoxGeometry(w * 0.055, h * 0.009, d * 0.018);
  const latches = new THREE.InstancedMesh(latchGeo, glowMat(color, 0.38), 4);
  for (let i = 0; i < 4; i++) {
    const x = (i % 2 ? 1 : -1) * w * 0.075;
    const y = h * 0.13 + Math.floor(i / 2) * h * 0.115;
    mm.makeTranslation(x, y, d * 0.565); drives.setMatrixAt(i, mm);
    mm.makeTranslation(x, y - h * 0.035, d * 0.58); latches.setMatrixAt(i, mm);
  }
  root.add(drives, latches);

  // Painel de rede/controle: portas RJ45, USB e botão de energia.
  const portGeo = new THREE.BoxGeometry(w * 0.045, h * 0.025, d * 0.018);
  const ports = new THREE.InstancedMesh(portGeo, new THREE.MeshBasicMaterial({ color: 0x02080d }), 6);
  const portLedGeo = new THREE.BoxGeometry(w * 0.012, h * 0.007, d * 0.016);
  const portLedMat = glowMat(0xffffff, data.status === 'offline' ? 0.22 : 0.95);
  const portLights = new THREE.InstancedMesh(portLedGeo, portLedMat, 6);
  for (let i = 0; i < 6; i++) {
    const x = -w * 0.16 + i * w * 0.063;
    mm.makeTranslation(x, h * 0.285, d * 0.57);
    ports.setMatrixAt(i, mm);
    mm.makeTranslation(x + w * 0.014, h * 0.293, d * 0.584);
    portLights.setMatrixAt(i, mm);
    portLights.setColorAt(i, data.status === 'offline' ? PORT_COLORS[3] : PORT_COLORS[i % 2]);
  }
  portLights.instanceColor.needsUpdate = true;
  root.add(ports, portLights);
  const power = new THREE.Mesh(new THREE.TorusGeometry(w * 0.019, w * 0.006, 6, 14), glowMat(color, 0.9));
  power.position.set(w * 0.30, h * 0.285, d * 0.575); root.add(power);

  // Numeração das unidades e identificação do cluster na própria porta.
  const unitLabel = textPlane('18U  12U  06U  01U', {
    width: w * 0.12, px: 256, size: 18, align: 'right', color: '#6387a0',
  });
  unitLabel.mesh.rotation.z = Math.PI / 2;
  unitLabel.mesh.position.set(-w * 0.415, 0, d * 0.575); root.add(unitLabel.mesh);
  const clusterId = textPlane(`NODE ${String(index + 1).padStart(2, '0')}`, {
    width: w * 0.25, px: 256, size: 22, align: 'center', color: '#85b9c8',
  });
  clusterId.mesh.position.set(0, -h * 0.405, d * 0.575); root.add(clusterId.mesh);

  // Ventilação superior e controlador/visor de status.
  const fanGeo = new THREE.TorusGeometry(w * 0.072, w * 0.014, 6, 18);
  for (const x of [-w * 0.22, 0, w * 0.22]) {
    const fan = new THREE.Mesh(fanGeo, glowMat(color, 0.28));
    fan.position.set(x, h * 0.355, d * 0.55); root.add(fan);
  }
  const display = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.30, h * 0.035), glowMat(color, 0.34));
  display.position.set(0, h * 0.415, d * 0.552); root.add(display);

  // Laterais ventiladas: ao orbitar a câmera o rack continua parecendo um
  // equipamento completo, em vez de perder todos os detalhes fora da frente.
  const sideVentGeo = new THREE.BoxGeometry(w * 0.018, h * 0.018, d * 0.42);
  const sideVents = new THREE.InstancedMesh(sideVentGeo, new THREE.MeshBasicMaterial({
    color: 0x173b50, transparent: true, opacity: 0.78,
  }), 12);
  for (let side = 0; side < 2; side++) for (let row = 0; row < 6; row++) {
    const x = (side ? 1 : -1) * w * 0.508;
    const y = -h * 0.27 + row * h * 0.105;
    mm.makeTranslation(x, y, 0); sideVents.setMatrixAt(side * 6 + row, mm);
  }
  root.add(sideVents);

  // Parafusos nas quatro quinas da porta.
  const screwGeo = new THREE.CircleGeometry(w * 0.009, 8);
  for (const x of [-w * 0.405, w * 0.405]) for (const y of [-h * 0.405, h * 0.405]) {
    const screw = new THREE.Mesh(screwGeo, glowMat(color, 0.7));
    screw.position.set(x, y, d * 0.555); root.add(screw);
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
  root.traverse((obj) => {
    obj.renderOrder = -20;
    if (obj.isMesh && obj.material) obj.material.side = THREE.DoubleSide;
    // Elementos luminosos e linhas técnicas não participam da profundidade da
    // carcaça translúcida. Assim continuam legíveis de cima, de baixo e de lado.
    if (obj.material && (obj.material.blending === THREE.AdditiveBlending || obj.isLine)) {
      obj.material.depthTest = false;
      obj.material.depthWrite = false;
      obj.renderOrder = -10;
    }
  });
  // A carcaça é desenhada primeiro; porta, módulos e indicadores ficam acima
  // dela e não somem por ordenação de transparência em ângulos oblíquos.
  shell.renderOrder = -30;
  edges.renderOrder = -29;

  root.userData = {
    index, status: data.status, leds, portLights, lastPortTick: -1,
    baseOpacity: ledMat.opacity, phase: index * 0.71, rackHeight: h, rackWidth: w,
  };
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
    const gap = 0.12;
    const total = racks.reduce((sum, rack) => sum + rack.userData.rackWidth, 0) + gap * (racks.length - 1);
    let cursor = -total / 2;
    racks.forEach((rack, i) => {
      cursor += rack.userData.rackWidth / 2;
      // Cada gabinete encosta no mesmo piso independentemente de sua escala.
      rack.position.set(cursor, rack.userData.rackHeight / 2, 0);
      rack.rotation.set(0, 0, 0);
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

      // LEDs das portas piscam em ritmos diferentes. A sequência é
      // determinística e atualiza apenas quatro vezes por segundo (0 GC/frame).
      const tick = Math.floor(elapsed * 4);
      if (tick !== u.lastPortTick) {
        u.lastPortTick = tick;
        for (let i = 0; i < 6; i++) {
          let ci = 0;
          if (u.status === 'offline' || (tick + i + u.index) % 5 === 0) ci = 3;
          else if ((tick + i * 3 + u.index * 5) % 31 === 0) ci = 2;
          else if ((tick + i + u.index) % 3 === 0) ci = 1;
          u.portLights.setColorAt(i, PORT_COLORS[ci]);
        }
        u.portLights.instanceColor.needsUpdate = true;
      }
    }
  }

  return { group, setData, update, dispose: clear };
}
