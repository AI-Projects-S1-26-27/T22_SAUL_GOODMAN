/* WebGL backdrop: a brass scale of justice in drifting gold dust.
 * The beam tilts with the live trial (window.Scene.setBalance), so the 3D scene is not
 * decoration: it is the trial's balance, drawn big. Degrades to nothing if WebGL or three.js
 * is unavailable; the page never depends on it.
 */
"use strict";

window.Scene = (() => {
  const noop = { setBalance() {}, pulse() {}, setMode() {}, pause() {}, resume() {} };
  const canvas = document.getElementById("scene");
  if (!window.THREE || !canvas) return noop;
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  } catch {
    return noop;
  }
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x0f0d0b, 0.05);
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
  camera.position.set(0, 1.2, 11);

  // ---- light: warm key, cool rim, coloured side fills for the two lawyers
  scene.add(new THREE.AmbientLight(0x30364a, 0.9));
  const key = new THREE.DirectionalLight(0xffe2b0, 2.2);
  key.position.set(3, 6, 6);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x8fb4ff, 1.4);
  rim.position.set(-4, 3, -5);
  scene.add(rim);
  const fillP = new THREE.PointLight(0xff7a59, 0, 12);
  fillP.position.set(-4, 0, 3);
  const fillD = new THREE.PointLight(0x3fd0c9, 0, 12);
  fillD.position.set(4, 0, 3);
  scene.add(fillP, fillD);

  // ---- soft studio environment so the brass has something to reflect
  const envScene = new THREE.Scene();
  envScene.background = new THREE.Color(0x0a0e1a);
  const panel = (color, x, y, z, w, h) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }));
    m.position.set(x, y, z);
    m.lookAt(0, 0, 0);
    envScene.add(m);
  };
  panel(0xfff0d0, 0, 6, 2, 8, 3);
  panel(0xffb070, 6, 1, 3, 3, 6);
  panel(0x6f9cff, -6, 1, -2, 3, 6);
  panel(0x332a20, 0, -5, 0, 12, 12);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(envScene, 0.04).texture;

  // ---- the scale
  const brass = new THREE.MeshStandardMaterial({ color: 0xe0a848, metalness: 1, roughness: 0.25, envMapIntensity: 1.1 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x2c180e, metalness: 0.1, roughness: 0.5 });
  const rig = new THREE.Group();
  scene.add(rig);

  const base = new THREE.Mesh(new THREE.CylinderGeometry(1.25, 1.5, 0.28, 64), dark);
  base.position.y = -2.6;
  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(0.75, 1.05, 0.22, 64), brass);
  plinth.position.y = -2.36;
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.1, 4.4, 24), brass);
  pole.position.y = -0.15;
  const finial = new THREE.Mesh(new THREE.SphereGeometry(0.2, 32, 16), brass);
  finial.position.y = 2.3;
  rig.add(base, plinth, pole, finial);

  const beam = new THREE.Group();
  beam.position.y = 1.95;
  const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.055, 4.6, 16), brass);
  bar.rotation.z = Math.PI / 2;
  const hub = new THREE.Mesh(new THREE.TorusGeometry(0.22, 0.05, 16, 48), brass);
  beam.add(bar, hub);
  rig.add(beam);

  const HALF = 2.2, DROP = 2.1;
  function makePan(color) {
    const g = new THREE.Group();
    const dish = new THREE.Mesh(new THREE.SphereGeometry(0.85, 48, 16, 0, Math.PI * 2, Math.PI * 0.62, Math.PI * 0.38), brass);
    dish.material = brass.clone();
    dish.material.side = THREE.DoubleSide;
    dish.position.y = 0.55;
    const glow = new THREE.PointLight(color, 0, 4);
    glow.position.y = 0.3;
    g.add(dish, glow);
    const lineMat = new THREE.LineBasicMaterial({ color: 0xc9a25a, transparent: true, opacity: 0.7 });
    const pts = [];
    for (let i = 0; i < 3; i++) {
      const a = (i / 3) * Math.PI * 2;
      pts.push(new THREE.Vector3(0, DROP, 0), new THREE.Vector3(Math.cos(a) * 0.78, 0.2, Math.sin(a) * 0.78));
    }
    g.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), lineMat));
    g.userData.glow = glow;
    rig.add(g);
    return g;
  }
  const panP = makePan(0xff7a59), panD = makePan(0x3fd0c9);

  // ---- gold dust
  const N = reduced ? 500 : 1800;
  const pos = new Float32Array(N * 3), seed = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    pos[i * 3] = (Math.random() - 0.5) * 26;
    pos[i * 3 + 1] = (Math.random() - 0.5) * 14;
    pos[i * 3 + 2] = (Math.random() - 0.5) * 16 - 2;
    seed[i] = Math.random() * 100;
  }
  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const sprite = (() => {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const x = c.getContext("2d");
    const g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(255,230,170,1)");
    g.addColorStop(0.3, "rgba(255,200,120,.45)");
    g.addColorStop(1, "rgba(255,200,120,0)");
    x.fillStyle = g;
    x.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(c);
  })();
  const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({
    size: 0.09, map: sprite, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0.8,
  }));
  scene.add(dust);

  // ---- big soft halo behind the scale
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: sprite, color: 0xffc070, transparent: true, opacity: 0.16, depthWrite: false, blending: THREE.AdditiveBlending }));
  halo.scale.set(12, 12, 1);
  halo.position.set(0, 0.6, -3);
  rig.add(halo);

  // ---- state
  const st = { balance: 0.5, tilt: 0, mx: 0, my: 0, scroll: 0, mode: "hero", pulseP: 0, pulseD: 0 };
  addEventListener("pointermove", (e) => {
    st.mx = e.clientX / innerWidth - 0.5;
    st.my = e.clientY / innerHeight - 0.5;
  }, { passive: true });
  addEventListener("scroll", () => { st.scroll = scrollY / innerHeight; }, { passive: true });

  function resize() {
    const w = innerWidth, h = innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  addEventListener("resize", resize);
  resize();

  const tmp = new THREE.Vector3();
  const clock = new THREE.Clock();
  let running = true, paused = false;
  const wake = () => { const was = running; running = !document.hidden && !paused; if (running && !was) { clock.getDelta(); loop(); } };
  document.addEventListener("visibilitychange", wake);

  function loop() {
    if (!running) return;
    requestAnimationFrame(loop);
    const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;
    const wide = innerWidth > 900;

    // beam: spring toward the trial's balance (left pan = Accuser goes down when they lead)
    const target = (st.balance - 0.5) * 0.9 + (reduced ? 0 : Math.sin(t * 0.7) * 0.015);
    st.tilt += (target - st.tilt) * Math.min(1, dt * 2.4);
    beam.rotation.z = st.tilt;
    for (const [pan, sign] of [[panP, -1], [panD, 1]]) {
      tmp.set(sign * HALF, 0, 0).applyAxisAngle(new THREE.Vector3(0, 0, 1), st.tilt);
      pan.position.set(tmp.x, beam.position.y + tmp.y - DROP, 0);
    }
    st.pulseP *= 0.94;
    st.pulseD *= 0.94;
    panP.userData.glow.intensity = st.pulseP * 6;
    panD.userData.glow.intensity = st.pulseD * 6;
    fillP.intensity = 0.4 + st.pulseP * 3 + Math.max(0, st.balance - 0.5) * 3;
    fillD.intensity = 0.4 + st.pulseD * 3 + Math.max(0, 0.5 - st.balance) * 3;

    // framing: hero puts the scale right of the headline; deeper sections push it back and centre
    const s = Math.min(st.scroll, 3);
    const heroX = wide ? 4.3 : 0;
    const x = st.mode === "trial" ? 0 : heroX * Math.max(0, 1 - s * 0.6);
    rig.position.x += (x - rig.position.x) * dt * 2.5;
    rig.position.z += ((st.mode === "trial" ? -1.5 : -s * 1.2) - rig.position.z) * dt * 2;
    rig.rotation.y = reduced ? 0 : Math.sin(t * 0.18) * 0.25 + st.mx * 0.35;
    camera.position.x += (st.mx * 1.2 - camera.position.x) * dt * 2;
    camera.position.y += (1.2 - st.my * 0.8 - camera.position.y) * dt * 2;
    camera.lookAt(0, 0.2, 0);

    // dust drifts upward like courtroom air in a sunbeam
    const p = dustGeo.attributes.position.array;
    for (let i = 0; i < N; i++) {
      p[i * 3 + 1] += dt * (0.08 + (seed[i] % 1) * 0.12);
      p[i * 3] += Math.sin(t * 0.3 + seed[i]) * dt * 0.05;
      if (p[i * 3 + 1] > 7) p[i * 3 + 1] = -7;
    }
    dustGeo.attributes.position.needsUpdate = true;
    halo.material.opacity = 0.13 + Math.sin(t * 0.8) * 0.03;
    renderer.render(scene, camera);
  }
  loop();

  return {
    setBalance(b) { st.balance = Math.max(0, Math.min(1, b)); },
    pulse(side) { if (side === "prosecution") st.pulseP = 1; else if (side === "defense") st.pulseD = 1; },
    setMode(m) { st.mode = m; },
    pause() { paused = true; running = false; },
    resume() { paused = false; wake(); },
  };
})();
