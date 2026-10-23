/* The courtroom the trial plays out in: a walnut-panelled room lit by tall windows, a raised bench,
 * two counsel tables and a brass scale above the judge that tilts with the trial.
 * Everything is built from primitives and canvas textures, so there is nothing to download.
 * API (window.Court3D): open(), close(), shot(name), speak(who, on), exhibit(item, phase), syncExhibits(statusMap),
 * setBalance(b), gavel(times), reset().
 */
"use strict";

window.Court3D = (() => {
  const canvas = document.getElementById("court-canvas");
  if (!window.THREE || !canvas) return null;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  } catch {
    return null;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.25));
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.72;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.shadowMap.autoUpdate = false; // the room is static; refresh only when people or exhibits move

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0d0a08);
  scene.fog = new THREE.Fog(0x0d0a08, 12, 30);
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 60);
  const look = new THREE.Vector3(0, 1.6, -2);
  camera.position.set(0, 2.2, 15);

  /* ------------------------------------------------------------ textures drawn in code */
  function canvasTex(w, h, draw, repeat) {
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    draw(c.getContext("2d"), w, h);
    const t = new THREE.CanvasTexture(c);
    t.encoding = THREE.sRGBEncoding;
    t.anisotropy = 8;
    if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(...repeat); }
    return t;
  }
  const rnd = (() => { let s = 7; return () => ((s = (s * 16807) % 2147483647) / 2147483647); })();
  const planks = canvasTex(512, 512, (x, w, h) => {
    const rows = 8;
    for (let r = 0; r < rows; r++) {
      let off = rnd() * w;
      for (let k = 0; k < 3; k++) {
        const l = 70 + rnd() * 30;
        x.fillStyle = `hsl(${24 + rnd() * 6}, ${38 + rnd() * 10}%, ${20 + rnd() * 7}%)`;
        x.fillRect((off) % w, r * (h / rows), w, h / rows);
        off += w / 3;
        for (let g = 0; g < 14; g++) {
          x.strokeStyle = `rgba(0,0,0,${0.05 + rnd() * 0.08})`;
          x.beginPath();
          const y = r * (h / rows) + rnd() * (h / rows);
          x.moveTo(0, y); x.bezierCurveTo(w * 0.3, y + 3, w * 0.6, y - 3, w, y);
          x.stroke();
        }
        void l;
      }
      x.fillStyle = "rgba(0,0,0,.55)";
      x.fillRect(0, r * (h / rows), w, 2);
    }
  }, [5, 5]);
  const panelTex = canvasTex(512, 512, (x, w, h) => {
    x.fillStyle = "#3a2216"; x.fillRect(0, 0, w, h);
    for (let i = 0; i < 400; i++) {
      x.strokeStyle = `rgba(${20 + rnd() * 30},${10 + rnd() * 10},5,${0.08 + rnd() * 0.1})`;
      const y = rnd() * h; x.beginPath(); x.moveTo(0, y); x.lineTo(w, y + (rnd() - 0.5) * 20); x.stroke();
    }
    // raised panels
    for (const [px, py, pw, ph] of [[40, 40, 432, 200], [40, 280, 432, 192]]) {
      x.fillStyle = "rgba(0,0,0,.35)"; x.fillRect(px - 6, py - 6, pw + 12, ph + 12);
      x.fillStyle = "rgba(255,190,130,.06)"; x.fillRect(px, py, pw, ph);
      x.strokeStyle = "rgba(255,200,140,.12)"; x.lineWidth = 3; x.strokeRect(px + 4, py + 4, pw - 8, ph - 8);
    }
  }, [1, 1]);
  const sealTex = canvasTex(512, 512, (x, w) => {
    x.fillStyle = "#1d130c"; x.beginPath(); x.arc(w / 2, w / 2, 250, 0, 7); x.fill();
    x.strokeStyle = "#c79a4e"; x.lineWidth = 10; x.beginPath(); x.arc(w / 2, w / 2, 236, 0, 7); x.stroke();
    x.lineWidth = 3; x.beginPath(); x.arc(w / 2, w / 2, 200, 0, 7); x.stroke();
    x.fillStyle = "#c79a4e"; x.font = "600 34px 'EB Garamond', Georgia, serif"; x.textAlign = "center";
    const text = "FIAT JUSTITIA RUAT CAELUM ·  ";
    for (let i = 0; i < text.length; i++) {
      const a = (i / text.length) * Math.PI * 2 - Math.PI / 2;
      x.save(); x.translate(w / 2 + Math.cos(a) * 218, w / 2 + Math.sin(a) * 218); x.rotate(a + Math.PI / 2);
      x.fillText(text[i], 0, 12); x.restore();
    }
    x.font = "600 64px 'EB Garamond', Georgia, serif";
    x.fillText("SG", w / 2, w / 2 + 22);
  });

  /* ------------------------------------------------------------ materials */
  const M = {
    floor: new THREE.MeshStandardMaterial({ map: planks, roughness: 0.55, metalness: 0.05 }),
    wall: new THREE.MeshStandardMaterial({ map: panelTex, roughness: 0.75 }),
    walnut: new THREE.MeshStandardMaterial({ color: 0x3a1f10, roughness: 0.45, metalness: 0.05 }),
    walnutDark: new THREE.MeshStandardMaterial({ color: 0x2c180e, roughness: 0.6 }),
    plaster: new THREE.MeshStandardMaterial({ color: 0x4a3c31, roughness: 0.95 }),
    brass: new THREE.MeshStandardMaterial({ color: 0xd9a54a, metalness: 1, roughness: 0.28 }),
    leather: new THREE.MeshStandardMaterial({ color: 0x3f1712, roughness: 0.65 }),
    green: new THREE.MeshStandardMaterial({ color: 0x24402e, roughness: 0.8 }),
    robe: new THREE.MeshStandardMaterial({ color: 0x0f0f12, roughness: 0.85 }),
    skin: new THREE.MeshStandardMaterial({ color: 0xc69276, roughness: 0.7 }),
    paper: new THREE.MeshStandardMaterial({ color: 0xefe6d2, roughness: 0.9 }),
    window: new THREE.MeshBasicMaterial({ color: 0x9fb8e8 }),
  };

  // a soft environment so brass and wood catch light
  const env = new THREE.Scene();
  const addPanel = (c, p, s) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(...s), new THREE.MeshBasicMaterial({ color: c, side: THREE.DoubleSide })); m.position.set(...p); m.lookAt(0, 0, 0); env.add(m); };
  env.background = new THREE.Color(0x120c08);
  addPanel(0xffe0b0, [0, 8, 0], [10, 10]);
  addPanel(0x9fbfff, [-8, 2, 0], [4, 8]);
  addPanel(0xff9a50, [8, 2, 2], [4, 6]);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(env, 0.05).texture;
  scene.environment.userData = {};
  pmrem.dispose();

  const box = (w, h, d, mat, x, y, z, parent = scene) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; parent.add(m); return m;
  };
  const cyl = (rt, rb, h, mat, x, y, z, seg = 24, parent = scene) => {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), mat);
    m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; parent.add(m); return m;
  };

  /* ------------------------------------------------------------ the room */
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(22, 30), M.floor);
  floor.rotation.x = -Math.PI / 2; floor.position.z = 2; floor.receiveShadow = true; scene.add(floor);
  // carpet runner up the aisle
  const runner = new THREE.Mesh(new THREE.PlaneGeometry(1.8, 14), new THREE.MeshStandardMaterial({ color: 0x3a0e0e, roughness: 1 }));
  runner.rotation.x = -Math.PI / 2; runner.position.set(0, 0.005, 6); runner.receiveShadow = true; scene.add(runner);

  // back wall: panelling below, plaster above, seal in the middle
  const back = new THREE.Mesh(new THREE.PlaneGeometry(22, 4), M.wall);
  back.position.set(0, 2, -7); back.receiveShadow = true; scene.add(back);
  M.wall.map.repeat.set(5, 1);
  for (const m of [M.walnut, M.walnutDark, M.wall, M.plaster, M.floor]) m.envMapIntensity = 0.35; M.wall.map.wrapS = THREE.RepeatWrapping;
  box(22, 6, 0.2, M.plaster, 0, 7, -7.1);
  box(22, 0.25, 0.3, M.walnutDark, 0, 4.05, -6.9);
  const seal = new THREE.Mesh(new THREE.CircleGeometry(1.1, 64), new THREE.MeshStandardMaterial({ map: sealTex, roughness: 0.5, metalness: 0.3 }));
  seal.position.set(0, 5.6, -6.95); scene.add(seal);
  for (const x of [-4.2, 4.2]) { // pilasters either side of the seal
    box(0.7, 8, 0.4, M.walnutDark, x, 4, -6.8);
    box(0.95, 0.3, 0.55, M.walnut, x, 8, -6.75);
  }
  // side walls with tall windows (left lit, right dim)
  for (const side of [-1, 1]) {
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(30, 10), M.plaster);
    wall.rotation.y = side * -Math.PI / 2; wall.position.set(side * 11, 5, 2); wall.receiveShadow = true; scene.add(wall);
    const wain = new THREE.Mesh(new THREE.PlaneGeometry(30, 2.4), M.wall);
    wain.rotation.y = side * -Math.PI / 2; wain.position.set(side * 10.98, 1.2, 2); scene.add(wain);
    for (const z of [-4, 1, 6]) {
      const win = new THREE.Mesh(new THREE.PlaneGeometry(2, 4.6), side < 0 ? M.window : new THREE.MeshBasicMaterial({ color: 0x2a3550 }));
      win.rotation.y = side * -Math.PI / 2; win.position.set(side * 10.95, 5.2, z); scene.add(win);
      // mullions
      box(0.08, 4.6, 0.08, M.walnutDark, side * 10.9, 5.2, z);
      box(0.08, 0.08, 2, M.walnutDark, side * 10.9, 5.6, z);
    }
  }
  // gallery benches behind the bar
  for (let r = 0; r < 3; r++) for (const s of [-1, 1]) {
    const z = 4.4 + r * 1.5, x = s * 4.2;
    box(5.6, 0.12, 0.5, M.walnut, x, 0.48, z);
    box(5.6, 0.7, 0.08, M.walnut, x, 0.85, z + 0.27);
    for (const lx of [-2.6, 0, 2.6]) box(0.1, 0.45, 0.45, M.walnutDark, x + lx, 0.22, z);
  }
  // the bar: balustrade between the public and the well
  for (const s of [-1, 1]) {
    box(8.2, 0.1, 0.18, M.walnut, s * 5.2, 1.0, 3.2);
    box(8.2, 0.12, 0.2, M.walnutDark, s * 5.2, 0.06, 3.2);
    for (let i = 0; i < 18; i++) cyl(0.035, 0.045, 0.9, M.walnut, s * (1.4 + i * 0.44), 0.5, 3.2, 8);
  }

  /* ------------------------------------------------------------ the bench */
  box(9, 0.5, 3.2, M.walnutDark, 0, 0.25, -5.4); // dais
  const bench = new THREE.Group(); scene.add(bench);
  box(5.2, 1.7, 0.35, M.walnut, 0, 1.35, -4.0, bench); // front
  box(5.5, 0.12, 1.1, M.walnut, 0, 2.25, -4.35, bench); // top
  for (const x of [-2, 0, 2]) box(1.5, 1.2, 0.05, M.walnutDark, x, 1.35, -3.81, bench); // inset panels
  const plate = canvasTex(512, 96, (x, w, h) => {
    x.fillStyle = "#b8893d"; x.fillRect(0, 0, w, h);
    x.fillStyle = "#2a1a0c"; x.font = "600 46px 'EB Garamond', Georgia, serif"; x.textAlign = "center"; x.fillText("THE RULEBOOK", w / 2, h / 2 + 15);
  });
  const nameplate = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 0.22), new THREE.MeshStandardMaterial({ map: plate, metalness: 0.7, roughness: 0.35 }));
  nameplate.position.set(0, 2.42, -3.85); nameplate.rotation.x = -0.25; scene.add(nameplate);
  // judge's chair: tall leather back
  box(1.1, 2.2, 0.25, M.leather, 0, 2.1, -6.1);
  // witness stand to the right
  box(1.6, 1.1, 1.2, M.walnut, 4.1, 1.05, -3.6);
  box(1.8, 0.08, 1.4, M.walnut, 4.1, 1.62, -3.6);

  // brass scale above the bench (tilts with the trial)
  const scale = new THREE.Group(); scale.position.set(0, 3.7, -6.2); scene.add(scale);
  cyl(0.03, 0.03, 1.1, M.brass, 0, -0.1, 0, 12, scale);
  const beam = new THREE.Group(); beam.position.y = 0.45; scale.add(beam);
  const bar = cyl(0.02, 0.02, 1.6, M.brass, 0, 0, 0, 8, beam); bar.rotation.z = Math.PI / 2;
  const pans = [-1, 1].map((s) => {
    const g = new THREE.Group(); scale.add(g);
    const dish = new THREE.Mesh(new THREE.SphereGeometry(0.22, 24, 8, 0, Math.PI * 2, Math.PI * 0.6, Math.PI * 0.4), M.brass);
    dish.position.y = 0.12; g.add(dish);
    g.userData.s = s; return g;
  });

  /* ------------------------------------------------------------ counsel tables */
  const tables = {};
  for (const [side, s] of [["prosecution", -1], ["defense", 1]]) {
    const g = new THREE.Group(); g.position.set(s * 2.7, 0, 0.2); scene.add(g);
    box(2.6, 0.08, 1.1, M.walnut, 0, 0.95, 0, g);
    box(2.6, 0.82, 0.06, M.walnutDark, 0, 0.5, -0.5, g);
    for (const lx of [-1.2, 1.2]) box(0.08, 0.9, 1, M.walnutDark, lx, 0.47, 0, g);
    box(2.3, 0.01, 0.8, M.green, 0, 1.0, 0, g); // desk blotter
    // a stack of files, a lamp
    for (let i = 0; i < 4; i++) box(0.5, 0.04, 0.36, i % 2 ? M.paper : new THREE.MeshStandardMaterial({ color: 0xc9ad78, roughness: 0.9 }), s * 0.7, 1.03 + i * 0.04, 0.1, g).rotation.y = (rnd() - 0.5) * 0.3;
    cyl(0.1, 0.12, 0.04, M.brass, -s * 0.8, 1.02, -0.2, 16, g);
    cyl(0.015, 0.015, 0.45, M.brass, -s * 0.8, 1.25, -0.2, 8, g);
    const shade = cyl(0.16, 0.16, 0.12, M.green, -s * 0.8, 1.5, -0.12, 20, g); shade.rotation.x = 0.4;
    const lamp = new THREE.PointLight(0xffc888, 0.6, 3.5, 2); lamp.position.set(-s * 0.8, 1.42, -0.05); g.add(lamp);
    tables[side] = g;
  }
  // evidence table at the centre of the well
  const evTable = new THREE.Group(); evTable.position.set(0, 0, -2.3); scene.add(evTable);
  box(2.4, 0.07, 0.9, M.walnut, 0, 0.82, 0, evTable);
  for (const [lx, lz] of [[-1.1, -0.35], [1.1, -0.35], [-1.1, 0.35], [1.1, 0.35]]) box(0.07, 0.8, 0.07, M.walnutDark, lx, 0.4, lz, evTable);

  /* ------------------------------------------------------------ people */
  function person({ robe, accent, judge = false }) {
    const g = new THREE.Group();
    const body = new THREE.Group(); g.add(body);
    const robeMat = new THREE.MeshStandardMaterial({ color: robe, roughness: 0.8 });
    const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.36, 1.05, 20), robeMat);
    torso.position.y = 1.02; torso.castShadow = true; body.add(torso);
    const hips = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.34, 0.5, 20), robeMat);
    hips.position.y = 0.3; hips.castShadow = true; body.add(hips);
    const legs = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.22, 0.6, 16), new THREE.MeshStandardMaterial({ color: 0x15151a, roughness: 0.9 }));
    legs.position.y = -0.1; body.add(legs);
    const shoulders = new THREE.Mesh(new THREE.SphereGeometry(0.29, 20, 12), robeMat);
    shoulders.scale.set(1.2, 0.55, 0.85); shoulders.position.y = 1.52; shoulders.castShadow = true; body.add(shoulders);
    // collar: white for the judge, the side's colour for counsel
    const collar = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.32, 3), new THREE.MeshStandardMaterial({ color: accent, roughness: 0.6 }));
    collar.rotation.x = Math.PI; collar.position.set(0, 1.42, 0.24); body.add(collar);
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.08, 0.14, 12), M.skin); neck.position.y = 1.66; body.add(neck);
    const head = new THREE.Group(); head.position.y = 1.86; body.add(head);
    const skull = new THREE.Mesh(new THREE.SphereGeometry(0.17, 24, 18), M.skin); skull.scale.set(0.92, 1.1, 0.98); skull.castShadow = true; head.add(skull);
    const hair = new THREE.Mesh(new THREE.SphereGeometry(0.18, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.55), new THREE.MeshStandardMaterial({ color: judge ? 0xd8d4cc : 0x2a1d14, roughness: 0.9 }));
    hair.position.set(0, 0.03, -0.03); hair.scale.set(0.95, 1.05, 1.02); hair.rotation.x = -0.35; head.add(hair);
    // a simple face so you can tell which way everyone is looking
    const eyeMat = new THREE.MeshStandardMaterial({ color: 0x1a120c, roughness: 0.4 });
    for (const s of [-1, 1]) {
      const eye = new THREE.Mesh(new THREE.SphereGeometry(0.02, 10, 8), eyeMat); eye.position.set(s * 0.055, 0.02, 0.155); head.add(eye);
      const brow = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.012, 0.01), hair.material); brow.position.set(s * 0.055, 0.065, 0.158); brow.rotation.z = s * -0.12; head.add(brow);
    }
    const nose = new THREE.Mesh(new THREE.ConeGeometry(0.022, 0.06, 8), M.skin); nose.rotation.x = Math.PI / 2; nose.position.set(0, -0.02, 0.18); head.add(nose);
    const mouth = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.01, 0.01), new THREE.MeshStandardMaterial({ color: 0x7a3b30 })); mouth.position.set(0, -0.085, 0.152); head.add(mouth);
    if (judge) { // a powdered wig roll either side
      for (const s of [-1, 1]) { const roll = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.035, 8, 16), hair.material); roll.position.set(s * 0.17, -0.06, 0); roll.rotation.y = Math.PI / 2; head.add(roll); }
    }
    const arms = [-1, 1].map((s) => {
      const pivot = new THREE.Group(); pivot.position.set(s * 0.34, 1.5, 0); body.add(pivot);
      const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.1, 0.7, 12), robeMat);
      arm.position.y = -0.33; arm.castShadow = true; pivot.add(arm);
      const hand = new THREE.Mesh(new THREE.SphereGeometry(0.065, 12, 10), M.skin); hand.position.y = -0.7; pivot.add(hand);
      pivot.rotation.z = s * 0.12;
      return pivot;
    });
    g.userData = { body, head, arms, mouth, robeMat, hairMat: hair.material, talk: 0, phase: rnd() * 10 };
    return g;
  }
  const people = {
    court: person({ robe: 0x0c0c10, accent: 0xf2efe8, judge: true }),
    prosecution: person({ robe: 0x1d2433, accent: 0xd8644a }),
    defense: person({ robe: 0x24262b, accent: 0x2f9e98 }),
  };
  for (const p of Object.values(people)) { p.scale.setScalar(0.82); scene.add(p); }
  people.court.position.set(0, 1.0, -5.5); people.court.scale.setScalar(0.88);
  people.prosecution.position.set(-2.7, 0.33, 1.15); people.prosecution.rotation.y = Math.atan2(2.7, -5.3);
  people.defense.position.set(2.7, 0.33, 1.15); people.defense.rotation.y = Math.atan2(-2.7, -5.3);

  // the witness called to the stand (re-dressed for each person), and the bailiff who carries exhibits up
  const witness = person({ robe: 0x5a4636, accent: 0xe8e0d0 });
  witness.scale.setScalar(0.8); witness.visible = false; scene.add(witness);
  people.witness = witness;
  const bailiff = person({ robe: 0x1c2a44, accent: 0xd9a54a });
  bailiff.scale.setScalar(0.84); scene.add(bailiff);
  people.bailiff = bailiff;
  const POST = [-5.2, 0.33, -3.4];
  bailiff.position.set(...POST); bailiff.rotation.y = Math.PI / 2;
  const WIT_SPOT = [4.1, 0.82, -4.5];
  const WIT_IN = [[0.5, 0.33, 3.2], [0.8, 0.33, -1.2], [2.9, 0.33, -2.4], [2.9, 0.33, -3.6], [2.9, 0.82, -4.5], WIT_SPOT];
  const WIT_OUT = [[2.9, 0.82, -4.5], [2.9, 0.33, -3.6], [2.9, 0.33, -2.4], [0.8, 0.33, -1.2], [0.5, 0.33, 3.2], [0.5, 0.33, 10]];
  const ROBES = [0x5a4636, 0x3d4a3a, 0x6b2f2f, 0x2f3d5a, 0x6a5a3a, 0x4a3a5a, 0x7a6a58];
  const HAIRS = [0x2a1d14, 0x6b4a2a, 0xb08a50, 0x1a1a1a, 0x8a8a8a, 0x4a2a1a];
  const hash = (k) => [...k].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);

  /* walk a person along points [x, y, z], turning to face each leg of the route */
  function walk(p, pts, speed = 1.9) {
    return new Promise((resolve) => {
      window.gsap?.killTweensOf(p.position); window.gsap?.killTweensOf(p.rotation);
      if (!window.gsap || reduced) { const [x, y, z] = pts[pts.length - 1]; p.position.set(x, y, z); p.userData.walking = false; resolve(); return; }
      const tl = gsap.timeline({ onComplete: () => { p.userData.walking = false; resolve(); } });
      p.userData.walking = true;
      let fx = p.position.x, fz = p.position.z, ang = p.rotation.y;
      for (const [x, y, z] of pts) {
        const d = Math.hypot(x - fx, z - fz);
        if (d < 0.02) continue;
        let a = Math.atan2(x - fx, z - fz);
        while (a - ang > Math.PI) a -= Math.PI * 2;
        while (a - ang < -Math.PI) a += Math.PI * 2;
        tl.to(p.rotation, { y: a, duration: 0.25, ease: "power1.out" });
        tl.to(p.position, { x, y, z, duration: d / speed, ease: "none" }, "<0.1");
        fx = x; fz = z; ang = a;
      }
    });
  }
  const faceRoom = (p) => window.gsap && !reduced ? gsap.to(p.rotation, { y: Math.atan2(-WIT_SPOT[0], 6), duration: 0.4 }) : (p.rotation.y = Math.atan2(-WIT_SPOT[0], 6));

  // gavel on the bench
  const gavel = new THREE.Group(); gavel.position.set(0.9, 2.33, -4.35); scene.add(gavel);
  const block = cyl(0.14, 0.14, 0.05, M.walnutDark, 0, 0, 0, 24, gavel); void block;
  const gavelArm = new THREE.Group(); gavelArm.position.set(0.45, 0.06, 0); gavel.add(gavelArm);
  const handle = cyl(0.022, 0.026, 0.5, M.walnut, -0.22, 0.04, 0, 10, gavelArm); handle.rotation.z = Math.PI / 2;
  const headG = cyl(0.06, 0.06, 0.22, M.walnut, -0.45, 0.04, 0, 16, gavelArm); headG.rotation.x = Math.PI / 2;
  for (const z of [-0.08, 0.08]) { const band = cyl(0.064, 0.064, 0.02, M.brass, -0.45, 0.04, z, 16, gavelArm); band.rotation.x = Math.PI / 2; }

  /* ------------------------------------------------------------ light */
  scene.add(new THREE.HemisphereLight(0xffe2c0, 0x1a0e08, 0.1));
  const sun = new THREE.DirectionalLight(0xbcd2ff, 1.0);
  sun.position.set(-10, 9, 1); sun.target.position.set(0, 0, -1); scene.add(sun, sun.target);
  sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 30 });
  sun.shadow.bias = -0.0004; sun.shadow.radius = 4;
  const key = new THREE.SpotLight(0xffc98a, 2.6, 20, 0.45, 0.6, 1.5);
  key.position.set(0, 9, -1); key.target.position.set(0, 1.5, -4.5); scene.add(key, key.target);
  key.castShadow = false;
  const well = new THREE.SpotLight(0xffd9a8, 0.9, 22, 0.6, 0.8, 1.4);
  well.position.set(0, 9, 5); well.target.position.set(0, 0, 0); scene.add(well, well.target);
  const wash = new THREE.SpotLight(0xffb873, 1.2, 16, 0.7, 0.9, 1.2); // warm wash on the back wall and seal
  wash.position.set(0, 1, -1); wash.target.position.set(0, 6, -7); scene.add(wash, wash.target);
  const speakerLight = new THREE.SpotLight(0xffffff, 0, 10, 0.32, 0.6, 1.2);
  speakerLight.position.set(0, 7, 2); scene.add(speakerLight, speakerLight.target);

  // window light shafts: additive planes angled down from the left windows
  const shaftMat = new THREE.MeshBasicMaterial({ color: 0xa8c4ff, transparent: true, opacity: 0.022, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
  for (const z of [-4, 1, 6]) {
    const shaft = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 14), shaftMat);
    shaft.position.set(-5.5, 3.2, z); shaft.rotation.set(0, Math.PI / 2, -1.0); scene.add(shaft);
  }
  // dust in the light
  const DN = reduced ? 300 : 900, dpos = new Float32Array(DN * 3);
  for (let i = 0; i < DN; i++) { dpos[i * 3] = -9 + rnd() * 12; dpos[i * 3 + 1] = rnd() * 7; dpos[i * 3 + 2] = -6 + rnd() * 14; }
  const dustGeo = new THREE.BufferGeometry(); dustGeo.setAttribute("position", new THREE.BufferAttribute(dpos, 3));
  const dot = canvasTex(32, 32, (x) => { const g = x.createRadialGradient(16, 16, 0, 16, 16, 16); g.addColorStop(0, "rgba(255,240,220,1)"); g.addColorStop(1, "rgba(255,240,220,0)"); x.fillStyle = g; x.fillRect(0, 0, 32, 32); });
  const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({ size: 0.035, map: dot, transparent: true, opacity: 0.55, depthWrite: false, blending: THREE.AdditiveBlending }));
  scene.add(dust);

  /* ------------------------------------------------------------ post: gentle bloom on lamps and brass */
  let composer = null, bloom = null;
  if (THREE.EffectComposer && THREE.UnrealBloomPass) {
    composer = new THREE.EffectComposer(renderer);
    composer.addPass(new THREE.RenderPass(scene, camera));
    bloom = new THREE.UnrealBloomPass(new THREE.Vector2(256, 256), 0.28, 0.5, 0.92);
    composer.addPass(bloom);
  }

  /* ------------------------------------------------------------ exhibits: paper cards that fly to the bench */
  const cards = new Map();
  function cardTexture(item) {
    return canvasTex(512, 340, (x, w, h) => {
      x.fillStyle = "#f1e9d6"; x.fillRect(0, 0, w, h);
      x.fillStyle = item.owner === "prosecution" ? "#c4553b" : "#24857f"; x.fillRect(0, 0, w, 14);
      x.fillStyle = "#6b5a44"; x.font = "500 26px Inter, sans-serif"; x.fillText(`Exhibit ${item.id}`, 28, 58);
      x.fillStyle = "#1e160e"; x.font = "600 38px 'EB Garamond', Georgia, serif";
      const words = item.title.split(" "); let line = "", y = 112;
      for (const wd of words) { const t = line ? `${line} ${wd}` : wd; if (x.measureText(t).width > w - 56) { x.fillText(line, 28, y); line = wd; y += 44; } else line = t; }
      x.fillText(line, 28, y);
    });
  }
  function card(item) {
    if (cards.has(item.id)) return cards.get(item.id);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(0.75, 0.5), new THREE.MeshStandardMaterial({ map: cardTexture(item), roughness: 0.85, side: THREE.DoubleSide, transparent: true }));
    m.castShadow = true; m.userData.item = item; scene.add(m); cards.set(item.id, m);
    m.visible = false;
    return m;
  }
  function tableSlot(i) { // fan the accepted exhibits across the evidence table
    const col = i % 4, row = Math.floor(i / 4);
    return { x: -0.9 + col * 0.6, y: 0.87 + row * 0.006, z: -2.3 + (row % 2 ? 0.15 : -0.15), rz: (((i * 37) % 11) - 5) * 0.03 };
  }

  function release(m) { if (m.parent !== scene) scene.attach(m); }
  async function carry(m, item) {
    // the bailiff walks round the outside of the counsel tables, so he never crosses the lawyers' close-ups
    const run = ++st.carryRun, side = item.owner === "prosecution" ? -1 : 1, hand = bailiff.userData.arms[1].children[1];
    const toTable = side < 0 ? [[-4.4, 0.33, -0.8]] : [[-1.0, 0.33, -2.9], [4.3, 0.33, -2.7], [4.4, 0.33, -0.8]];
    const toBench = [[side * 4.3, 0.33, -2.7], [side * 0.9, 0.33, -2.9], [side * 0.9, 0.33, -3.25]];
    m.position.set(side * 3.7, 1.06, 0.1); m.rotation.set(-Math.PI / 2, 0, 0); m.scale.setScalar(0.6);
    await walk(bailiff, toTable, 2.6);
    if (run !== st.carryRun) return;
    hand.attach(m);
    gsap.to(m.position, { x: 0, y: -0.08, z: 0.14, duration: 0.3 });
    bailiff.userData.carrying = true;
    await walk(bailiff, toBench, 2.4);
    if (run !== st.carryRun) return;
    release(m); bailiff.userData.carrying = false;
    gsap.to(m.position, { x: 0, y: 2.55, z: -3.0, duration: 0.7, ease: "power2.out" });
    gsap.to(m.rotation, { x: -0.15, y: 0, z: 0, duration: 0.7 });
    gsap.to(m.scale, { x: 1, y: 1, z: 1, duration: 0.7 });
    await walk(bailiff, [[-2.6, 0.33, -3.0], POST], 2.4);
    if (run === st.carryRun) gsap.to(bailiff.rotation, { y: Math.PI / 2, duration: 0.4 });
  }
  function bailiffHome() {
    st.carryRun++;
    for (const m of cards.values()) release(m);
    bailiff.userData.carrying = false;
    walk(bailiff, [POST], 99).then(() => { bailiff.rotation.y = Math.PI / 2; });
  }

  /* ------------------------------------------------------------ state + loop */
  const st = { balance: 0.5, tilt: 0, open: false, talking: null, shake: 0, carryRun: 0, witnessKey: null };
  const cam = { px: camera.position.x, py: camera.position.y, pz: camera.position.z, lx: look.x, ly: look.y, lz: look.z };
  const SHOTS = {
    door: [0, 2.2, 15, 0, 1.6, -2],
    wide: [0, 4.3, 10.5, 0, 1.5, -2.5],
    court: [1.1, 3.0, 0.4, 0, 2.55, -5.4],
    prosecution: [-0.7, 2.25, -2.2, -2.7, 1.25, 1.15],
    defense: [0.7, 2.25, -2.2, 2.7, 1.25, 1.15],
    exhibit: [0, 2.6, -0.4, 0, 2.2, -3.5],
    verdict: [0, 2.8, 1.8, 0, 2.6, -5.4],
    witness: [2.3, 2.5, -1.4, 4.1, 1.75, -4.5],
  };
  function shot(name, dur = 1.6) {
    const s = SHOTS[name] ?? SHOTS.wide;
    if (!window.gsap || reduced) { [cam.px, cam.py, cam.pz, cam.lx, cam.ly, cam.lz] = s; return; }
    gsap.to(cam, { px: s[0], py: s[1], pz: s[2], lx: s[3], ly: s[4], lz: s[5], duration: dur, ease: "power3.inOut", overwrite: true });
  }

  function resize() {
    const w = canvas.clientWidth || innerWidth, h = canvas.clientHeight || innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.fov = w < 700 ? 58 : 40;
    camera.updateProjectionMatrix();
    composer?.setSize(w, h);
    bloom?.setSize(w / 2, h / 2);
  }
  addEventListener("resize", resize);

  const clock = new THREE.Clock();
  const v = new THREE.Vector3();
  let frame = 0;
  window.__court = { renderer, scene, get composer() { return composer; }, set composer(c) { composer = c; } };
  function loop() {
    if (!st.open) return;
    requestAnimationFrame(loop);
    const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;

    // scale
    st.tilt += ((st.balance - 0.5) * 0.7 - st.tilt) * Math.min(1, dt * 2);
    beam.rotation.z = st.tilt;
    for (const p of pans) { v.set(p.userData.s * 0.8, 0.45, 0).applyAxisAngle(new THREE.Vector3(0, 0, 1), st.tilt); p.position.set(v.x, v.y - 0.5, 0); }

    // people: breathing, and gestures while speaking
    for (const [who, p] of Object.entries(people)) {
      const u = p.userData, speaking = st.talking === who;
      u.talk += ((speaking ? 1 : 0) - u.talk) * Math.min(1, dt * 4);
      const ph = t + u.phase;
      u.body.scale.y = 1 + Math.sin(ph * 1.6) * 0.008;
      u.head.rotation.x = Math.sin(ph * 0.7) * 0.03 + u.talk * Math.sin(ph * 7) * 0.05;
      u.head.rotation.y = Math.sin(ph * 0.4) * 0.12 + u.talk * Math.sin(ph * 2.3) * 0.15;
      u.mouth.scale.y = 1 + u.talk * Math.abs(Math.sin(ph * 14)) * 3.5;
      if (who !== "court") {
        u.arms[1].rotation.x = -u.talk * (0.9 + Math.sin(ph * 3) * 0.35);
        u.arms[1].rotation.z = 0.12 + u.talk * 0.25;
        u.arms[0].rotation.x = -u.talk * (0.25 + Math.sin(ph * 2.2 + 1) * 0.2);
      } else {
        u.arms[0].rotation.x = -0.7 - u.talk * Math.sin(ph * 2) * 0.2; // judge's hands rest on the bench
        u.arms[1].rotation.x = -0.7;
      }
      if (u.walking) {
        const w = Math.sin(t * 9 + u.phase);
        u.body.position.y = Math.abs(w) * 0.035;
        u.arms[0].rotation.x = w * 0.45;
        if (!u.carrying) u.arms[1].rotation.x = -w * 0.45;
      } else u.body.position.y = 0;
      if (u.carrying) u.arms[1].rotation.x = -1.3;
      if (who === "witness") { // right hand up for the oath
        u.oath = (u.oath ?? 0) + ((st.oath ? 1 : 0) - (u.oath ?? 0)) * Math.min(1, dt * 5);
        if (u.oath > 0.01) { u.arms[1].rotation.x = -2.7 * u.oath; u.arms[1].rotation.z = 0.12 + 0.25 * u.oath; }
      }
    }
    if (st.talking && people[st.talking]) {
      people[st.talking].getWorldPosition(v);
      speakerLight.target.position.lerp(v.setY(1.4), Math.min(1, dt * 4));
      speakerLight.position.set(speakerLight.target.position.x * 0.6, 7, speakerLight.target.position.z + 3);
      speakerLight.intensity += (1.6 - speakerLight.intensity) * dt * 3;
    } else speakerLight.intensity += (0 - speakerLight.intensity) * dt * 3;

    // dust drift
    const d = dustGeo.attributes.position.array;
    for (let i = 0; i < DN; i++) { d[i * 3 + 1] += dt * 0.05; d[i * 3] += Math.sin(t * 0.2 + i) * dt * 0.02; if (d[i * 3 + 1] > 7) d[i * 3 + 1] = 0; }
    dustGeo.attributes.position.needsUpdate = true;

    // camera with a slow handheld drift and the gavel shake
    st.shake *= 0.9;
    const drift = reduced ? 0 : 1;
    camera.position.set(cam.px + Math.sin(t * 0.31) * 0.05 * drift + (Math.random() - 0.5) * st.shake, cam.py + Math.sin(t * 0.43) * 0.03 * drift + (Math.random() - 0.5) * st.shake, cam.pz);
    look.set(cam.lx, cam.ly, cam.lz);
    camera.lookAt(look);
    if ((frame++ % 6) === 0) renderer.shadowMap.needsUpdate = true;
    composer ? composer.render() : renderer.render(scene, camera);
  }

  return {
    open() {
      st.open = true;
      resize();
      [cam.px, cam.py, cam.pz, cam.lx, cam.ly, cam.lz] = SHOTS.door;
      clock.getDelta();
      loop();
      shot("wide", reduced ? 0 : 4.2);
    },
    close() { st.open = false; },
    shot,
    speak(who, on) { st.talking = on ? who : null; },
    oath(on) { st.oath = on; },
    setBalance(b) { st.balance = Math.max(0, Math.min(1, b)); },
    gavel(times = 1) {
      if (!window.gsap || reduced) return;
      const tl = gsap.timeline();
      for (let i = 0; i < times; i++) {
        tl.to(gavelArm.rotation, { z: 0.9, duration: 0.22, ease: "power2.out" })
          .to(gavelArm.rotation, { z: -0.05, duration: 0.1, ease: "power4.in", onComplete: () => { st.shake = 0.06; } })
          .to(gavelArm.rotation, { z: 0, duration: 0.15 });
      }
    },
    /* show one exhibit being handed up; phase: "offered" | "admitted" | "excluded" */
    exhibit(item, phase, animate) {
      if (!item) return;
      const m = card(item), from = tables[item.owner].position;
      m.visible = true;
      const g = window.gsap && animate && !reduced;
      if (phase === "offered") {
        m.material.color.set(0xffffff); m.material.opacity = 1;
        if (g && item.kind !== "testimony" && item.kind !== "expert") { carry(m, item); return; }
        if (!g) bailiffHome();
        if (g) {
          m.position.set(from.x, 1.1, from.z); m.rotation.set(-Math.PI / 2, 0, 0); m.scale.setScalar(0.6);
          gsap.timeline()
            .to(m.position, { x: from.x * 0.4, y: 2.6, z: -1.6, duration: 0.9, ease: "power2.out" })
            .to(m.rotation, { x: -0.15, y: 0, z: 0, duration: 0.9, ease: "power2.out" }, 0)
            .to(m.scale, { x: 1, y: 1, z: 1, duration: 0.9, ease: "power2.out" }, 0)
            .to(m.position, { x: 0, y: 2.55, z: -3.0, duration: 0.8, ease: "power2.inOut" });
        } else { m.position.set(0, 2.55, -3.0); m.rotation.set(-0.15, 0, 0); m.scale.setScalar(1); }
      }
    },
    /* lay every exhibit out to match the trial at this step (works backwards and forwards) */
    syncExhibits(status, current, animate) {
      let i = 0;
      for (const [id, m] of cards) {
        const s = status[id];
        if (id !== current) release(m);
        if (id === current && s === "offered") continue;
        if (s === "admitted") {
          const slot = tableSlot(i++);
          m.visible = true; m.material.opacity = 1; m.material.color.set(0xffffff);
          const to = { x: slot.x, y: slot.y, z: slot.z };
          if (animate && window.gsap && !reduced && id === current) {
            gsap.to(m.position, { ...to, duration: 1, ease: "power2.inOut", delay: 0.4 });
            gsap.to(m.rotation, { x: -Math.PI / 2, y: 0, z: slot.rz, duration: 1, ease: "power2.inOut", delay: 0.4 });
            gsap.to(m.scale, { x: 0.8, y: 0.8, z: 0.8, duration: 1, delay: 0.4 });
          } else { m.position.set(to.x, to.y, to.z); m.rotation.set(-Math.PI / 2, 0, slot.rz); m.scale.setScalar(0.8); }
        } else if (s === "excluded") {
          if (animate && window.gsap && !reduced && id === current) {
            m.material.color.set(0xff8a80);
            gsap.timeline()
              .to(m.position, { y: "+=0.2", duration: 0.3, delay: 0.5 })
              .to(m.position, { y: 0.02, x: m.position.x + (rnd() - 0.5) * 1.5, z: -1.4, duration: 1.1, ease: "power2.in" })
              .to(m.rotation, { x: -Math.PI / 2, z: rnd() * 3, duration: 1.1, ease: "power2.in" }, "<")
              .to(m.material, { opacity: 0, duration: 0.6, onComplete: () => { m.visible = false; } });
          } else m.visible = false;
        } else m.visible = false;
      }
    },
    /* call a witness to the stand (walks in from the gallery); resolves when they're in place */
    callWitness(key, animate) {
      if (st.witnessKey === key && witness.visible) return Promise.resolve();
      st.witnessKey = key;
      const h = hash(key);
      witness.userData.robeMat.color.set(ROBES[h % ROBES.length]);
      witness.userData.hairMat.color.set(HAIRS[(h >> 3) % HAIRS.length]);
      witness.visible = true;
      if (!animate || !window.gsap || reduced) { window.gsap?.killTweensOf(witness.position); witness.position.set(...WIT_SPOT); faceRoom(witness); return Promise.resolve(); }
      witness.position.set(0.5, 0.33, 10); witness.rotation.y = Math.PI;
      return walk(witness, WIT_IN, 2.4).then(() => { faceRoom(witness); });
    },
    dismissWitness(animate) {
      if (!st.witnessKey) return;
      st.witnessKey = null;
      if (!animate || !window.gsap || reduced) { window.gsap?.killTweensOf(witness.position); witness.visible = false; return; }
      walk(witness, WIT_OUT, 2.4).then(() => { if (!st.witnessKey) witness.visible = false; });
    },
    reset() { st.witnessKey = null; witness.visible = false; bailiffHome(); for (const m of cards.values()) { scene.remove(m); m.material.map.dispose(); m.material.dispose(); m.geometry.dispose(); } cards.clear(); st.balance = 0.5; st.talking = null; },
  };
})();
