// CAMADA: LookAt distribuído — a cabeça NUNCA gira sozinha. A vontade de olhar
//  (yaw/pitch, vinda da EyeLayer) é repartida pela cadeia:
//    hips → spine → chest → upperChest → neck → head
//  Isso deixa o movimento muito mais humano (o corpo acompanha o olhar).
const CHAIN = [
  ['hips', 0.05], ['spine', 0.10], ['chest', 0.13],
  ['upperChest', 0.14], ['neck', 0.26], ['head', 0.32],
];

export function createLookAtLayer() {
  return {
    name: 'lookat',
    update(rig, buf, ctx, dt) {
      const yaw = ctx.gaze.yaw, pitch = ctx.gaze.pitch;
      if (!yaw && !pitch) return;
      for (const [bone, w] of CHAIN) {
        // pitch -> rotação em X (olhar p/ cima/baixo); yaw -> rotação em Y
        buf.addRot(bone, pitch * w, yaw * w, 0);
      }
    },
  };
}
