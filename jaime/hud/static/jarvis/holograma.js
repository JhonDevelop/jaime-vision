/* Holograma 3D verde controlado pela mão (vídeo do carro).
   - modelo montado por PEÇAS (cada uma com direção de explosão): carro/SUV, moto, casa, drone, foguete, átomo, planeta;
     ou um .glb do João (~/Jaime/hologramas/<nome>.glb, servido por /jarvis/holograma/<nome>.glb);
   - mãos pela webcam (MediaPipe Hand Landmarker, no navegador desta máquina):
       uma mão aberta movendo → gira;  pinça (polegar+indicador) subindo/descendo → zoom;
       duas mãos se afastando → as peças se abrem;  mão fechada → remonta;
   - sem câmera: arrastar gira, roda do mouse dá zoom, E abre/fecha as peças, Esc fecha. */
(function () {
  const VERDE = 0x3dffa0, VERDE2 = 0x1fd180;
  let cena, cam, ren, raiz, pecas = [], abrir = 0, abrirAlvo = 0, rotX = -.25, rotY = .6, rotXA = -.25, rotYA = .6, dist = 9, distA = 9;
  let vivo = false, loopId = 0, video = null, maos = null, ultimoVideo = -1, dica, hudEl;
  const box = document.getElementById('holo');

  function mat(op) { return new THREE.LineBasicMaterial({ color: VERDE, transparent: true, opacity: op ?? .85, blending: THREE.AdditiveBlending }); }
  function peca(geo, pos, dir, opts = {}) {
    const g = new THREE.Group();
    g.add(new THREE.LineSegments(new THREE.WireframeGeometry(geo), mat(opts.op ?? .22)));
    g.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), mat(.95)));
    const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: VERDE2, transparent: true, opacity: .05, blending: THREE.AdditiveBlending, depthWrite: false }));
    g.add(m);
    g.position.set(...pos); if (opts.rot) g.rotation.set(...opts.rot);
    g.userData = { base: new THREE.Vector3(...pos), dir: new THREE.Vector3(...dir) };
    raiz.add(g); pecas.push(g); return g;
  }
  const B = (x, y, z, sx = 2, sy = 2, sz = 2) => new THREE.BoxGeometry(x, y, z, sx, sy, sz);
  function cabine(larg, alt, comp, topoX, topoZ) {       // tronco de pirâmide: a cabine/teto do carro
    const g = B(comp, alt, larg, 4, 2, 3), p = g.attributes.position;
    for (let i = 0; i < p.count; i++) if (p.getY(i) > 0) { p.setX(i, p.getX(i) * topoX); p.setZ(i, p.getZ(i) * topoZ); }
    p.needsUpdate = true; return g;
  }
  function roda(x, z) {
    const g = new THREE.Group();
    const pneu = new THREE.TorusGeometry(.46, .17, 10, 28), aro = new THREE.CylinderGeometry(.3, .3, .22, 14, 1);
    peca(pneu, [x, .46, z], [Math.sign(x) * .6, -.3, Math.sign(z) * 1.6], { rot: [0, 0, 0] });
    peca(aro, [x, .46, z], [Math.sign(x) * .6, -.3, Math.sign(z) * 2.3], { rot: [Math.PI / 2, 0, 0] });
    return g;
  }
  const MODELOS = {
    carro() {        // SUV genérico elétrico, silhueta por perfil extrudado; abre em lataria, cabine, portas, bateria, motores e bancos
      const perfil = (pts, prof, bevel = .07) => { const sh = new THREE.Shape(); pts.forEach(([x, y], i) => i ? sh.lineTo(x, y) : sh.moveTo(x, y));
        const g = new THREE.ExtrudeGeometry(sh, { depth: prof, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 2, curveSegments: 10, steps: 3 });
        g.translate(0, 0, -prof / 2); return g; };
      const arco = (cx, r, a0, a1, n = 10) => Array.from({ length: n + 1 }, (_, i) => { const a = a0 + (a1 - a0) * i / n; return [cx + Math.cos(a) * r, .5 + Math.sin(a) * r]; });
      const lataria = [[2.42, .62], [2.42, 1.25], [2.28, 1.46], [1.55, 1.58], [-2.05, 1.58], [-2.34, 1.5], [-2.38, .62], [-1.98, .62],
        ...arco(-1.45, .56, Math.PI, 0).slice(1, -1), [-.9, .62], [.97, .62], ...arco(1.5, .56, Math.PI, 0).slice(1, -1), [2.06, .62]];
      peca(perfil(lataria, 1.84), [0, 0, 0], [0, -.35, 0]);
      peca(perfil([[1.48, 1.6], [.72, 2.36], [-1.72, 2.44], [-2.1, 1.6]], 1.62, .05), [0, 0, 0], [0, 1.9, 0]);          // cabine/teto
      for (const [x0, x1, s] of [[.02, 1.28, 1], [-1.3, 0, 1], [.02, 1.28, -1], [-1.3, 0, -1]])                          // portas
        peca(perfil([[x1, .7], [x1, 1.55], [x1 - .45, 2.2], [x0, 2.25], [x0, .7]], .06, .02), [0, 0, s * .98], [0, .2, s * 2.4]);
      peca(B(3.1, .16, 1.55, 8, 1, 4), [-.2, .5, 0], [0, -1.9, 0]);                                                       // bateria no assoalho
      peca(new THREE.CylinderGeometry(.25, .25, .55, 14, 2), [1.5, .5, 0], [2.6, -1.2, 0], { rot: [Math.PI / 2, 0, 0] });      // motor dianteiro
      peca(new THREE.CylinderGeometry(.25, .25, .55, 14, 2), [-1.45, .5, 0], [-2.6, -1.2, 0], { rot: [Math.PI / 2, 0, 0] });   // motor traseiro
      for (const [x, z] of [[.35, .42], [.35, -.42], [-.6, .42], [-.6, -.42], [-1.45, .42], [-1.45, -.42]]) {                // 7 lugares (6 bancos + banco)
        peca(B(.52, .12, .5, 2, 1, 2), [x, 1.02, z], [0, 1.2 + (1 - x) * .15, z * 1.6]);
        peca(B(.12, .62, .5, 1, 3, 2), [x - .25, 1.36, z], [0, 1.4 + (1 - x) * .15, z * 1.6]);
      }
      peca(new THREE.TorusGeometry(.19, .03, 6, 24), [.95, 1.5, .42], [1.3, 1.5, .7], { rot: [0, Math.PI / 2, .35] });       // volante
      peca(B(.9, .05, 1.5, 3, 1, 4), [1.15, 1.35, 0], [1.4, .9, 0]);                                                      // painel
      for (const z of [.62, -.62]) { peca(B(.06, .12, .42, 1, 1, 2), [2.46, 1.1, z], [3, .3, z * 1.2]); peca(B(.06, .1, .45, 1, 1, 2), [-2.42, 1.3, z], [-3, .3, z * 1.2]); }
      for (const [x, z] of [[1.5, 1], [1.5, -1], [-1.45, 1], [-1.45, -1]]) {                                              // rodas: pneu, aro, raios
        peca(new THREE.TorusGeometry(.42, .15, 10, 32), [x, .5, z * .93], [x * .4, -.4, z * 1.9]);
        const aro = new THREE.CylinderGeometry(.3, .3, .2, 18, 1); peca(aro, [x, .5, z * .93], [x * .4, -.4, z * 2.6], { rot: [Math.PI / 2, 0, 0] });
        peca(new THREE.CylinderGeometry(.33, .33, .04, 6, 1), [x, .5, z * 1.02], [x * .4, -.4, z * 3.1], { rot: [Math.PI / 2, 0, 0] });
      }
    },
    moto() {
      peca(B(1.6, .35, .35), [0, 1.1, 0], [0, .6, 0]); peca(B(.7, .25, .5), [-.5, 1.4, 0], [-.4, 1.2, 0]);
      peca(B(.5, .45, .4), [.2, .75, 0], [0, -1, 0]); peca(new THREE.CylinderGeometry(.03, .03, 1.1, 8), [1.05, 1.35, 0], [1, .9, 0], { rot: [0, 0, .5] });
      for (const x of [1.15, -1.1]) { peca(new THREE.TorusGeometry(.5, .1, 8, 28), [x, .55, 0], [x * 1.2, -.4, 0]); peca(new THREE.CylinderGeometry(.35, .35, .08, 16), [x, .55, 0], [x * 1.4, -.4, .8], { rot: [Math.PI / 2, 0, 0] }); }
    },
    casa() {
      peca(B(4, .2, 3, 6, 1, 5), [0, .1, 0], [0, -1.5, 0]); peca(B(4, 2, .1, 6, 4, 1), [0, 1.2, 1.5], [0, 0, 2]); peca(B(4, 2, .1, 6, 4, 1), [0, 1.2, -1.5], [0, 0, -2]);
      peca(B(.1, 2, 3, 1, 4, 5), [2, 1.2, 0], [2, 0, 0]); peca(B(.1, 2, 3, 1, 4, 5), [-2, 1.2, 0], [-2, 0, 0]);
      const t = new THREE.ConeGeometry(3, 1.5, 4, 3); peca(t, [0, 3, 0], [0, 2.5, 0], { rot: [0, Math.PI / 4, 0] });
      peca(B(.9, .1, 1.4, 2, 1, 2), [0, 1.2, 0], [0, .8, 0]); peca(B(1.4, 1.2, .9), [-.9, .8, .2], [-.8, 1, .6]);
    },
    drone() {
      peca(B(1, .3, 1, 3, 1, 3), [0, 0, 0], [0, 1, 0]); peca(new THREE.SphereGeometry(.2, 10, 8), [0, -.25, .4], [0, -1.2, .8]);
      for (const [x, z] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) { peca(B(1.1, .08, .12), [x * .55, 0, z * .55], [x, .3, z], { rot: [0, -x * z * Math.PI / 4, 0] });
        peca(new THREE.TorusGeometry(.45, .03, 6, 32), [x * 1.05, .12, z * 1.05], [x * 1.8, .8, z * 1.8], { rot: [Math.PI / 2, 0, 0] }); }
    },
    foguete() {
      peca(new THREE.CylinderGeometry(.6, .6, 3.2, 16, 6), [0, 1.6, 0], [0, 0, 0]); peca(new THREE.ConeGeometry(.6, 1.3, 16, 3), [0, 3.85, 0], [0, 2.5, 0]);
      for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2; peca(B(.08, .9, .8, 1, 2, 2), [Math.cos(a) * .7, .45, Math.sin(a) * .7], [Math.cos(a) * 2, -.5, Math.sin(a) * 2], { rot: [0, -a, 0] }); }
      peca(new THREE.CylinderGeometry(.35, .5, .5, 14), [0, -.25, 0], [0, -2, 0]);
    },
    atomo() {
      peca(new THREE.IcosahedronGeometry(.7, 1), [0, 0, 0], [0, 0, 0]);
      for (let i = 0; i < 3; i++) peca(new THREE.TorusGeometry(2.2, .02, 6, 64), [0, 0, 0], [0, (i - 1) * 1.5, 0], { rot: [i * 1.05, i * .7, 0] });
      for (let i = 0; i < 6; i++) peca(new THREE.SphereGeometry(.18, 8, 6), [Math.cos(i) * 2.2, Math.sin(i * 1.7) * 1.2, Math.sin(i) * 2.2], [Math.cos(i) * 2, Math.sin(i * 1.7), Math.sin(i) * 2]);
    },
    planeta() {
      peca(new THREE.SphereGeometry(2, 24, 16), [0, 0, 0], [0, 0, 0]); peca(new THREE.TorusGeometry(3, .03, 6, 80), [0, 0, 0], [0, 1.4, 0], { rot: [1.3, 0, 0] });
      peca(new THREE.SphereGeometry(.4, 10, 8), [3.6, .8, 0], [2.4, 1, 0]);
    },
  };
  function montar(d) {
    if (raiz) cena.remove(raiz);
    raiz = new THREE.Group(); pecas = []; cena.add(raiz);
    if (d.modelo === 'glb' && d.arquivo) return carregarGLB(d.arquivo);
    (MODELOS[d.modelo] || MODELOS.atomo)();
    const c = new THREE.Box3().setFromObject(raiz).getCenter(new THREE.Vector3()); raiz.position.sub(c);
  }
  async function carregarGLB(slug) {
    if (!THREE.GLTFLoader) await new Promise((ok, e) => { const s = document.createElement('script'); s.src = 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js'; s.onload = ok; s.onerror = e; document.head.appendChild(s); });
    new THREE.GLTFLoader().load(`/jarvis/holograma/${encodeURIComponent(slug)}.glb`, g => {
      const bb = new THREE.Box3().setFromObject(g.scene), tam = bb.getSize(new THREE.Vector3()).length() || 1, esc = 6 / tam, centro = bb.getCenter(new THREE.Vector3());
      g.scene.traverse(o => { if (o.isMesh) {
        const w = new THREE.Group(); o.updateWorldMatrix(true, false);
        const geo = o.geometry.clone().applyMatrix4(o.matrixWorld).translate(-centro.x, -centro.y, -centro.z).scale(esc, esc, esc);
        geo.computeBoundingBox(); const c = geo.boundingBox.getCenter(new THREE.Vector3());
        w.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 20), mat(.9)));
        w.userData = { base: new THREE.Vector3(), dir: c.clone().multiplyScalar(.9) }; raiz.add(w); pecas.push(w);
      } });
    });
  }
  function iniciar3D() {
    ren = new THREE.WebGLRenderer({ antialias: true, alpha: true }); ren.setPixelRatio(Math.min(2, devicePixelRatio)); ren.setSize(innerWidth, innerHeight);
    box.appendChild(ren.domElement);
    cena = new THREE.Scene(); cena.fog = new THREE.FogExp2(0x001a10, .035);
    cam = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, .1, 100);
    const grade = new THREE.GridHelper(30, 60, 0x0f6, 0x063); grade.position.y = -1.6; grade.material.transparent = true; grade.material.opacity = .25; cena.add(grade);
    for (let i = 1; i <= 3; i++) { const a = new THREE.Mesh(new THREE.RingGeometry(i * 1.6, i * 1.6 + .02, 64), new THREE.MeshBasicMaterial({ color: VERDE, transparent: true, opacity: .35 / i, side: THREE.DoubleSide })); a.rotation.x = -Math.PI / 2; a.position.y = -1.58; cena.add(a); }
    addEventListener('resize', () => { if (!ren) return; ren.setSize(innerWidth, innerHeight); cam.aspect = innerWidth / innerHeight; cam.updateProjectionMatrix(); });
    let arr = null;
    ren.domElement.addEventListener('pointerdown', e => arr = [e.clientX, e.clientY, rotYA, rotXA]);
    addEventListener('pointerup', () => arr = null);
    addEventListener('pointermove', e => { if (arr) { rotYA = arr[2] + (e.clientX - arr[0]) * .008; rotXA = Math.max(-1.3, Math.min(1.3, arr[3] + (e.clientY - arr[1]) * .006)); } });
    ren.domElement.addEventListener('wheel', e => { distA = Math.max(4, Math.min(20, distA + e.deltaY * .01)); });
    addEventListener('keydown', e => { if (!vivo) return; if (e.key.toLowerCase() === 'e') abrirAlvo = abrirAlvo > .5 ? 0 : 1; if (e.key === 'Escape') fechar(); });
  }
  function quadro() {
    if (!vivo) return;
    loopId = requestAnimationFrame(quadro);
    maosQuadro();
    abrir += (abrirAlvo - abrir) * .07; rotX += (rotXA - rotX) * .12; rotY += (rotYA - rotY) * .12; dist += (distA - dist) * .1;
    if (!maos || !maos.ativa) rotYA += .0025;
    for (const p of pecas) p.position.copy(p.userData.base).addScaledVector(p.userData.dir, abrir * 1.25);
    raiz.rotation.set(rotX, rotY, 0);
    cam.position.set(0, 1.2, dist); cam.lookAt(0, 0, 0);
    ren.render(cena, cam);
    hudEl.querySelector('.st').textContent = `PEÇAS ${pecas.length} · EXPLOSÃO ${Math.round(abrir * 100)}% · ZOOM ${(9 / dist).toFixed(2)}x · ${maos && maos.ativa ? 'MÃOS ATIVAS' : 'MOUSE'}`;
  }

  /* ── mãos ── */
  async function ligarMaos() {
    try {
      const loc = await fetch('/hud/jarvis/vendor/ok.json').then(r => r.ok).catch(() => false);   // `python -m jaime jarvis baixar`
      const base = loc ? '/hud/jarvis/vendor/' : 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/';
      const v = await import(base + 'vision_bundle.mjs');
      const fs = await v.FilesetResolver.forVisionTasks(base + 'wasm');
      const modelo = loc ? '/hud/jarvis/vendor/hand_landmarker.task' : 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';
      let lm;
      try { lm = await v.HandLandmarker.createFromOptions(fs, { baseOptions: { modelAssetPath: modelo, delegate: 'GPU' }, runningMode: 'VIDEO', numHands: 2 }); }
      catch (e) { lm = await v.HandLandmarker.createFromOptions(fs, { baseOptions: { modelAssetPath: modelo, delegate: 'CPU' }, runningMode: 'VIDEO', numHands: 2 }); }
      video = document.createElement('video'); video.autoplay = true; video.muted = true; video.playsInline = true; box.appendChild(video);
      video.srcObject = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } }); await video.play();
      maos = { lm, ativa: false, ref: null, pinca: null, dois: null }; window.HOLO_MAOS = true;
      dica.textContent = 'MÃO ABERTA GIRA · PINÇA SOBE/DESCE = ZOOM · DUAS MÃOS SE AFASTANDO ABREM · MÃO FECHADA REMONTA';
    } catch (e) { console.warn('mãos indisponíveis:', e && e.message); dica.textContent = 'SEM CÂMERA: ARRASTE PARA GIRAR · RODA = ZOOM · E ABRE/FECHA · ESC SAI'; }
  }
  const d2 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  function fechada(h) { const p = h[0]; return [8, 12, 16, 20].every(i => d2(h[i], p) < d2(h[i - 2], p) * 1.05); }
  function maosQuadro() {
    if (!maos || !video || video.readyState < 2 || video.currentTime === ultimoVideo) return;
    ultimoVideo = video.currentTime;
    const r = maos.lm.detectForVideo(video, performance.now());
    aplicarGesto(r.landmarks || []);
  }
  function aplicarGesto(hs) {                                   // separado da câmera: dá para testar com mãos sintéticas
    maos = maos || { ativa: false, ref: null, pinca: null, dois: null };
    maos.ativa = hs.length > 0;
    if (hs.length === 2) {
      const d = d2(hs[0][9], hs[1][9]);
      if (maos.dois == null) maos.dois = { d, a: abrirAlvo };
      abrirAlvo = Math.max(0, Math.min(1.6, maos.dois.a + (d - maos.dois.d) * 3.2)); maos.ref = null; return;
    }
    maos.dois = null;
    if (hs.length !== 1) { maos.ref = null; maos.pinca = null; return; }
    const h = hs[0], palma = h[9];
    if (fechada(h)) { abrirAlvo = 0; maos.ref = null; return; }
    if (d2(h[4], h[8]) < .045) {                              // pinça: zoom pela altura
      if (!maos.pinca) maos.pinca = { y: palma.y, dist: distA };
      distA = Math.max(4, Math.min(20, maos.pinca.dist + (palma.y - maos.pinca.y) * 22)); return;
    }
    maos.pinca = null;
    if (!maos.ref) maos.ref = { x: palma.x, y: palma.y, ry: rotYA, rx: rotXA };
    rotYA = maos.ref.ry - (palma.x - maos.ref.x) * 7;           // espelhado: mão para a direita gira para a direita
    rotXA = Math.max(-1.3, Math.min(1.3, maos.ref.rx + (palma.y - maos.ref.y) * 5));
  }

  function abrirHolo(d) {
    if (!ren) {
      box.innerHTML = '<div class="hud"><div>HOLOGRAMA · J.A.I.M.E</div><b class="tt"></b><div class="st"></div></div><div class="fechar">FECHAR ✕</div><div class="dica"></div>';
      hudEl = box.querySelector('.hud'); dica = box.querySelector('.dica'); box.querySelector('.fechar').onclick = fechar;
      iniciar3D(); ligarMaos();
    }
    hudEl.querySelector('.tt').textContent = String(d.titulo || d.modelo || '').toUpperCase();
    abrir = 0; abrirAlvo = 0; distA = 9; montar(d);
    box.classList.add('on'); vivo = true; cancelAnimationFrame(loopId); quadro();
  }
  function fechar() {
    vivo = false; box.classList.remove('on');
    if (video && video.srcObject) video.srcObject.getTracks().forEach(t => t.stop());
    if (video) video.remove(); video = null; maos = null;
    if (ren) { ren.dispose(); ren.domElement.remove(); ren = null; }
  }
  window.Holograma = { abrir: abrirHolo, fechar, _estado: () => ({ pecas: pecas.length, abrir: +abrir.toFixed(2), abrirAlvo: +abrirAlvo.toFixed(2), dist: +distA.toFixed(2), rotY: +rotYA.toFixed(2), rotX: +rotXA.toFixed(2), maos: !!(maos && maos.ativa) }), _explodir: v => abrirAlvo = v, _gesto: aplicarGesto };
})();
