/* Estúdio de holograma (vídeo do carro verde, e além): qualquer objeto vira PEÇAS que o João pega, gira, move,
   escala, esconde, desenha, edita por voz, exporta e manda imprimir.

   Objetos: catálogo (carro/SUV, moto, casa, drone, foguete, átomo, planeta), peças geradas pelo modelo para
   QUALQUER objeto, .glb do João (~/Jaime/hologramas/<nome>.glb) e desenhos feitos no ar.

   Mãos (webcam, via sentidos.js):
     indicador aponta → mira a peça (fica branca);  pinça rápida em cima → seleciona (fica âmbar);
     pinça segurando em cima de uma peça → arrasta a peça; girar o punho durante a pinça → gira a peça;
     mão aberta movendo → gira a peça selecionada (ou o objeto todo, sem seleção);
     pinça fora das peças → zoom;  duas mãos afastando → escala a peça (ou abre o objeto em peças);
     mão fechada → solta a seleção (sem seleção: remonta);  modo desenho: só o indicador esticado desenha.
   Olhar (opcional): parar o olhar ~0,9 s numa peça seleciona.
   Mouse: clique seleciona · arrastar gira (a peça ou o objeto) · Shift+arrastar move a peça · roda = zoom (ou escala
   a peça) · Delete esconde · Ctrl/⌘+Z desfaz · E abre/fecha · Esc solta/fecha.
   A tela conta ao servidor o que está aberto (peças e seleção) para a edição por voz, e manda as malhas quando
   o João pede o arquivo 3D. Nada daqui aprova ação nenhuma. */
(function () {
  const VERDE = 0x3dffa0, VERDE2 = 0x1fd180, SEL = 0xffc24a, MIRA = 0xe8fff4;
  let cena, cam, ren, raiz, pecas = [], abrir = 0, abrirAlvo = 0, rotX = -.25, rotY = .6, rotXA = -.25, rotYA = .6, dist = 9, distA = 9;
  let vivo = false, loopId = 0, dica, hudEl, titulo = '', modo = 'ver', sel = null, mira = null, pilha = [], sairSentidos = null;
  let maos = { ativa: false }, tracos = [], traco = null, linhaViva = null, ultimoMouse = 0, olharEm = null, relatarT = 0;
  const box = document.getElementById('holo');
  const ray = new THREE.Raycaster(), p2 = new THREE.Vector2();

  /* ── peças ── */
  function mat(op) { return new THREE.LineBasicMaterial({ color: VERDE, transparent: true, opacity: op ?? .85, blending: THREE.AdditiveBlending }); }
  function peca(geo, pos, dir, opts = {}) {
    const g = new THREE.Group();
    g.add(new THREE.LineSegments(new THREE.WireframeGeometry(geo), mat(opts.op ?? .22)));
    g.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), mat(.95)));
    const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: VERDE2, transparent: true, opacity: .05, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    g.add(m);
    return registrar(g, m, pos, dir, opts);
  }
  function registrar(g, malha, pos, dir, opts = {}) {
    g.position.set(...pos); if (opts.rot) g.rotation.set(...opts.rot);
    malha.geometry.computeBoundingBox();
    g.userData = { base: new THREE.Vector3(...pos), dir: new THREE.Vector3(...dir), nome: opts.nome || `peça ${pecas.length + 1}`, malha,
      caixa: malha.geometry.boundingBox.clone(), base0: new THREE.Vector3(...pos), q0: g.quaternion.clone(), s0: g.scale.clone() };
    malha.userData.peca = g;
    raiz.add(g); pecas.push(g); return g;
  }
  function colorir(g, cor, forte) {
    g.children.forEach((c, i) => { if (!c.material) return; c.material.color.setHex(i === 2 ? (cor === VERDE ? VERDE2 : cor) : cor);
      if (i === 2) c.material.opacity = forte ? .16 : .05; });
  }
  function pintar() { for (const g of pecas) colorir(g, g === sel ? SEL : g === mira ? MIRA : VERDE, g === sel || g === mira); }

  const B = (x, y, z, sx = 2, sy = 2, sz = 2) => new THREE.BoxGeometry(x, y, z, sx, sy, sz);
  const LADO = z => z > 0 ? 'esquerd' : 'direit';
  const MODELOS = {
    carro() {        // SUV elétrico, silhueta por perfil extrudado; peças com nome para mão e voz
      const perfil = (pts, prof, bevel = .07) => { const sh = new THREE.Shape(); pts.forEach(([x, y], i) => i ? sh.lineTo(x, y) : sh.moveTo(x, y));
        const g = new THREE.ExtrudeGeometry(sh, { depth: prof, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 2, curveSegments: 10, steps: 3 });
        g.translate(0, 0, -prof / 2); return g; };
      const arco = (cx, r, a0, a1, n = 10) => Array.from({ length: n + 1 }, (_, i) => { const a = a0 + (a1 - a0) * i / n; return [cx + Math.cos(a) * r, .5 + Math.sin(a) * r]; });
      const lataria = [[2.42, .62], [2.42, 1.25], [2.28, 1.46], [1.55, 1.58], [-2.05, 1.58], [-2.34, 1.5], [-2.38, .62], [-1.98, .62],
        ...arco(-1.45, .56, Math.PI, 0).slice(1, -1), [-.9, .62], [.97, .62], ...arco(1.5, .56, Math.PI, 0).slice(1, -1), [2.06, .62]];
      peca(perfil(lataria, 1.84), [0, 0, 0], [0, -.35, 0], { nome: 'lataria' });
      peca(perfil([[1.48, 1.6], [.72, 2.36], [-1.72, 2.44], [-2.1, 1.6]], 1.62, .05), [0, 0, 0], [0, 1.9, 0], { nome: 'cabine e teto' });
      for (const [x0, x1, s, qual] of [[.02, 1.28, 1, 'dianteira'], [-1.3, 0, 1, 'traseira'], [.02, 1.28, -1, 'dianteira'], [-1.3, 0, -1, 'traseira']])
        peca(perfil([[x1, .7], [x1, 1.55], [x1 - .45, 2.2], [x0, 2.25], [x0, .7]], .06, .02), [0, 0, s * .98], [0, .2, s * 2.4], { nome: `porta ${qual} ${LADO(s)}a` });
      peca(B(3.1, .16, 1.55, 8, 1, 4), [-.2, .5, 0], [0, -1.9, 0], { nome: 'bateria' });
      peca(new THREE.CylinderGeometry(.25, .25, .55, 14, 2), [1.5, .5, 0], [2.6, -1.2, 0], { rot: [Math.PI / 2, 0, 0], nome: 'motor dianteiro' });
      peca(new THREE.CylinderGeometry(.25, .25, .55, 14, 2), [-1.45, .5, 0], [-2.6, -1.2, 0], { rot: [Math.PI / 2, 0, 0], nome: 'motor traseiro' });
      [[.35, .42], [.35, -.42], [-.6, .42], [-.6, -.42], [-1.45, .42], [-1.45, -.42]].forEach(([x, z], i) => {
        peca(B(.52, .12, .5, 2, 1, 2), [x, 1.02, z], [0, 1.2 + (1 - x) * .15, z * 1.6], { nome: `assento ${i + 1}` });
        peca(B(.12, .62, .5, 1, 3, 2), [x - .25, 1.36, z], [0, 1.4 + (1 - x) * .15, z * 1.6], { nome: `encosto ${i + 1}` });
      });
      peca(new THREE.TorusGeometry(.19, .03, 6, 24), [.95, 1.5, .42], [1.3, 1.5, .7], { rot: [0, Math.PI / 2, .35], nome: 'volante' });
      peca(B(.9, .05, 1.5, 3, 1, 4), [1.15, 1.35, 0], [1.4, .9, 0], { nome: 'painel' });
      for (const z of [.62, -.62]) { peca(B(.06, .12, .42, 1, 1, 2), [2.46, 1.1, z], [3, .3, z * 1.2], { nome: `farol ${LADO(z)}o` });
        peca(B(.06, .1, .45, 1, 1, 2), [-2.42, 1.3, z], [-3, .3, z * 1.2], { nome: `lanterna ${LADO(z)}a` }); }
      for (const [x, z] of [[1.5, 1], [1.5, -1], [-1.45, 1], [-1.45, -1]]) {
        const onde = `${x > 0 ? 'dianteir' : 'traseir'}`, l = LADO(z);
        peca(new THREE.TorusGeometry(.42, .15, 10, 32), [x, .5, z * .93], [x * .4, -.4, z * 1.9], { nome: `pneu ${onde}o ${l}o` });
        peca(new THREE.CylinderGeometry(.3, .3, .2, 18, 1), [x, .5, z * .93], [x * .4, -.4, z * 2.6], { rot: [Math.PI / 2, 0, 0], nome: `roda ${onde}a ${l}a` });
        peca(new THREE.CylinderGeometry(.33, .33, .04, 6, 1), [x, .5, z * 1.02], [x * .4, -.4, z * 3.1], { rot: [Math.PI / 2, 0, 0], nome: `calota ${onde}a ${l}a` });
      }
    },
    moto() {
      peca(B(1.6, .35, .35), [0, 1.1, 0], [0, .6, 0], { nome: 'quadro' }); peca(B(.7, .25, .5), [-.5, 1.4, 0], [-.4, 1.2, 0], { nome: 'banco' });
      peca(B(.5, .45, .4), [.2, .75, 0], [0, -1, 0], { nome: 'motor' }); peca(new THREE.CylinderGeometry(.03, .03, 1.1, 8), [1.05, 1.35, 0], [1, .9, 0], { rot: [0, 0, .5], nome: 'guidão' });
      for (const x of [1.15, -1.1]) { const q = x > 0 ? 'dianteira' : 'traseira';
        peca(new THREE.TorusGeometry(.5, .1, 8, 28), [x, .55, 0], [x * 1.2, -.4, 0], { nome: `pneu ${q === 'dianteira' ? 'dianteiro' : 'traseiro'}` });
        peca(new THREE.CylinderGeometry(.35, .35, .08, 16), [x, .55, 0], [x * 1.4, -.4, .8], { rot: [Math.PI / 2, 0, 0], nome: `roda ${q}` }); }
    },
    casa() {
      peca(B(4, .2, 3, 6, 1, 5), [0, .1, 0], [0, -1.5, 0], { nome: 'piso' });
      peca(B(4, 2, .1, 6, 4, 1), [0, 1.2, 1.5], [0, 0, 2], { nome: 'parede da frente' }); peca(B(4, 2, .1, 6, 4, 1), [0, 1.2, -1.5], [0, 0, -2], { nome: 'parede do fundo' });
      peca(B(.1, 2, 3, 1, 4, 5), [2, 1.2, 0], [2, 0, 0], { nome: 'parede direita' }); peca(B(.1, 2, 3, 1, 4, 5), [-2, 1.2, 0], [-2, 0, 0], { nome: 'parede esquerda' });
      peca(new THREE.ConeGeometry(3, 1.5, 4, 3), [0, 3, 0], [0, 2.5, 0], { rot: [0, Math.PI / 4, 0], nome: 'telhado' });
      peca(B(.9, .1, 1.4, 2, 1, 2), [0, 1.2, 0], [0, .8, 0], { nome: 'mesa' }); peca(B(1.4, 1.2, .9), [-.9, .8, .2], [-.8, 1, .6], { nome: 'armário' });
    },
    drone() {
      peca(B(1, .3, 1, 3, 1, 3), [0, 0, 0], [0, 1, 0], { nome: 'corpo' }); peca(new THREE.SphereGeometry(.2, 10, 8), [0, -.25, .4], [0, -1.2, .8], { nome: 'câmera' });
      [[1, 1], [1, -1], [-1, 1], [-1, -1]].forEach(([x, z], i) => { peca(B(1.1, .08, .12), [x * .55, 0, z * .55], [x, .3, z], { rot: [0, -x * z * Math.PI / 4, 0], nome: `braço ${i + 1}` });
        peca(new THREE.TorusGeometry(.45, .03, 6, 32), [x * 1.05, .12, z * 1.05], [x * 1.8, .8, z * 1.8], { rot: [Math.PI / 2, 0, 0], nome: `hélice ${i + 1}` }); });
    },
    foguete() {
      peca(new THREE.CylinderGeometry(.6, .6, 3.2, 16, 6), [0, 1.6, 0], [0, 0, 0], { nome: 'fuselagem' }); peca(new THREE.ConeGeometry(.6, 1.3, 16, 3), [0, 3.85, 0], [0, 2.5, 0], { nome: 'ogiva' });
      for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2; peca(B(.08, .9, .8, 1, 2, 2), [Math.cos(a) * .7, .45, Math.sin(a) * .7], [Math.cos(a) * 2, -.5, Math.sin(a) * 2], { rot: [0, -a, 0], nome: `aleta ${i + 1}` }); }
      peca(new THREE.CylinderGeometry(.35, .5, .5, 14), [0, -.25, 0], [0, -2, 0], { nome: 'motor' });
    },
    atomo() {
      peca(new THREE.IcosahedronGeometry(.7, 1), [0, 0, 0], [0, 0, 0], { nome: 'núcleo' });
      for (let i = 0; i < 3; i++) peca(new THREE.TorusGeometry(2.2, .02, 6, 64), [0, 0, 0], [0, (i - 1) * 1.5, 0], { rot: [i * 1.05, i * .7, 0], nome: `órbita ${i + 1}` });
      for (let i = 0; i < 6; i++) peca(new THREE.SphereGeometry(.18, 8, 6), [Math.cos(i) * 2.2, Math.sin(i * 1.7) * 1.2, Math.sin(i) * 2.2], [Math.cos(i) * 2, Math.sin(i * 1.7), Math.sin(i) * 2], { nome: `elétron ${i + 1}` });
    },
    planeta() {
      peca(new THREE.SphereGeometry(2, 24, 16), [0, 0, 0], [0, 0, 0], { nome: 'planeta' }); peca(new THREE.TorusGeometry(3, .03, 6, 80), [0, 0, 0], [0, 1.4, 0], { rot: [1.3, 0, 0], nome: 'anel' });
      peca(new THREE.SphereGeometry(.4, 10, 8), [3.6, .8, 0], [2.4, 1, 0], { nome: 'lua' });
    },
  };
  function geometria(p) {
    const [a, b, c] = p.tam.map(Number), seg = v => Math.max(1, Math.min(8, Math.round(v * 3)));
    if (p.forma === 'tubo') return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(p.pontos.map(q => new THREE.Vector3(...q))), Math.max(8, p.pontos.length * 2), Math.max(.01, a), 6);
    return p.forma === 'caixa' ? new THREE.BoxGeometry(a, b, c, seg(a), seg(b), seg(c))
      : p.forma === 'cilindro' ? new THREE.CylinderGeometry(a, a, b, 18, 2)
      : p.forma === 'esfera' ? new THREE.SphereGeometry(a, 16, 12)
      : p.forma === 'toro' ? new THREE.TorusGeometry(a, Math.max(.02, b), 8, 32)
      : new THREE.ConeGeometry(a, b, 16, 2);
  }
  function montarGerado(lista) { return lista.map(p => peca(geometria(p), p.forma === 'tubo' ? [0, 0, 0] : p.pos.map(Number), (p.explode || [0, 1, 0]).map(Number), { rot: p.forma === 'tubo' ? null : p.rot.map(Number), nome: p.nome })); }
  function montar(d) {
    if (raiz) cena.remove(raiz);
    raiz = new THREE.Group(); pecas = []; sel = null; mira = null; pilha = []; tracos = []; cena.add(raiz);
    if (d.modelo === 'desenho') return;
    if (d.modelo === 'glb' && d.arquivo) return carregarGLB(d.arquivo);
    if (d.modelo === 'gerado' && Array.isArray(d.pecas)) montarGerado(d.pecas);
    else (MODELOS[d.modelo] || MODELOS.atomo)();
    const c = new THREE.Box3().setFromObject(raiz).getCenter(new THREE.Vector3()); raiz.position.sub(c);
  }
  async function carregarGLB(slug) {
    if (!THREE.GLTFLoader) await new Promise((ok, e) => { const s = document.createElement('script'); s.src = 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js'; s.onload = ok; s.onerror = e; document.head.appendChild(s); });
    new THREE.GLTFLoader().load(`/jarvis/holograma/${encodeURIComponent(slug)}.glb`, g => {
      const bb = new THREE.Box3().setFromObject(g.scene), tam = bb.getSize(new THREE.Vector3()).length() || 1, esc = 6 / tam, centro = bb.getCenter(new THREE.Vector3());
      g.scene.traverse(o => { if (o.isMesh) {
        o.updateWorldMatrix(true, false);
        const geo = o.geometry.clone().applyMatrix4(o.matrixWorld).translate(-centro.x, -centro.y, -centro.z).scale(esc, esc, esc);
        geo.computeBoundingBox(); const c = geo.boundingBox.getCenter(new THREE.Vector3());
        const w = new THREE.Group(); w.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 20), mat(.9))); w.add(new THREE.Object3D());
        const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: VERDE2, transparent: true, opacity: .05, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
        w.add(m); registrar(w, m, [0, 0, 0], c.clone().multiplyScalar(.9).toArray(), { nome: o.name || `peça ${pecas.length + 1}` });
      } });
      relatar();
    });
  }

  /* ── transformações (em torno do centro da peça, ou de uma face: "pivo") ── */
  function pivoLocal(g, pivo) {
    const cx = g.userData.caixa, c = cx.getCenter(new THREE.Vector3());
    const face = { frente: ['x', 'max'], tras: ['x', 'min'], cima: ['y', 'max'], baixo: ['y', 'min'], esquerda: ['z', 'max'], direita: ['z', 'min'] }[pivo];
    if (face) c[face[0]] = cx[face[1]][face[0]];
    return c;
  }
  function emTorno(g, pivo, mudar) {
    const c = pivoLocal(g, pivo), antes = c.clone().multiply(g.scale).applyQuaternion(g.quaternion);
    mudar();
    const depois = c.clone().multiply(g.scale).applyQuaternion(g.quaternion);
    g.userData.base.add(antes.sub(depois));
  }
  const girar = (g, q, pivo) => emTorno(g, pivo, () => g.quaternion.premultiply(q));
  const escalar = (g, v) => emTorno(g, null, () => { g.scale.multiply(v); g.scale.clampScalar(.03, 30); });
  function eixoLocal(vMundo) { return vMundo.clone().applyQuaternion(raiz.quaternion.clone().invert()).normalize(); }

  /* ── desfazer ── */
  function guardar() {
    pilha.push({ n: pecas.length, t: tracos.length, a: abrirAlvo, e: pecas.map(g => ({ b: g.userData.base.clone(), q: g.quaternion.clone(), s: g.scale.clone(), v: g.visible })) });
    if (pilha.length > 60) pilha.shift();
  }
  function desfazer() {
    const s = pilha.pop(); if (!s) return false;
    while (pecas.length > s.n) { const g = pecas.pop(); raiz.remove(g); if (g === sel) sel = null; }
    s.e.forEach((e, i) => { const g = pecas[i]; g.userData.base.copy(e.b); g.quaternion.copy(e.q); g.scale.copy(e.s); g.visible = e.v; });
    abrirAlvo = s.a;
    if (tracos.length !== s.t) { tracos.length = s.t; enviarTracos(); }
    pintar(); relatar(); return true;
  }

  /* ── operações da voz (validadas no servidor) ── */
  function alvos(a) { return a === 'selecionada' ? (sel ? [sel] : []) : a === 'todas' ? pecas.slice() : (a || []).map(i => pecas[i]).filter(Boolean); }
  function editar(ops) {
    guardar();
    for (const o of ops || []) {
      const v = o.valor;
      if (o.op === 'explodir') abrirAlvo = v;
      else if (o.op === 'resetar') { while (pecas.length && pecas[pecas.length - 1].userData.adicionada) raiz.remove(pecas.pop());
        pecas.forEach(g => { g.userData.base.copy(g.userData.base0); g.quaternion.copy(g.userData.q0); g.scale.copy(g.userData.s0); g.visible = true; }); abrirAlvo = 0; }
      else if (o.op === 'adicionar') { const g = montarGerado([o.peca])[0]; g.position.copy(g.userData.base); g.userData.adicionada = true; }
      else for (const g of alvos(o.alvo)) {
        if (o.op === 'mover') g.userData.base.add(new THREE.Vector3(...v));
        else if (o.op === 'girar') girar(g, new THREE.Quaternion().setFromEuler(new THREE.Euler(...v)), o.pivo);
        else if (o.op === 'escalar') escalar(g, new THREE.Vector3(...v));
        else if (o.op === 'esconder' || o.op === 'remover') g.visible = false;
        else if (o.op === 'mostrar') g.visible = true;
        else if (o.op === 'duplicar') {
          const ud = g.userData; g.userData = {};             // userData tem a malha (referência circular): fora do clone
          const c = g.clone(true); g.userData = ud; c.userData = {};
          c.children.forEach(k => { if (k.material) k.material = k.material.clone(); k.userData = {}; });
          const m = c.children[2]; registrar(c, m, g.userData.base.clone().add(new THREE.Vector3(...(v || [.5, 0, 0]))).toArray(), g.userData.dir.toArray(), { nome: g.userData.nome + ' (cópia)' });
          c.quaternion.copy(g.quaternion); c.scale.copy(g.scale); c.userData.adicionada = true;
        }
      }
    }
    pintar(); relatar();
  }

  /* ── o servidor sabe o que está aberto (para a voz) ── */
  function relatar() {
    clearTimeout(relatarT);
    relatarT = setTimeout(() => {
      const r2 = x => Math.round(x * 100) / 100;
      const lista = pecas.map(g => { const b = g.userData.caixa.clone().applyMatrix4(new THREE.Matrix4().compose(g.userData.base, g.quaternion, g.scale));
        return { nome: g.userData.nome, centro: b.getCenter(new THREE.Vector3()).toArray().map(r2), tam: b.getSize(new THREE.Vector3()).toArray().map(r2), visivel: g.visible }; });
      post('/jarvis/holograma/cena', { titulo, pecas: lista, selecionada: sel ? pecas.indexOf(sel) : null });
    }, 350);
  }
  function post(url, corpo) { return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) }).catch(() => {}); }
  function malhas() {
    const r4 = x => Math.round(x * 1e4) / 1e4, desloc = new THREE.Matrix4().makeTranslation(raiz.position.x, raiz.position.y, raiz.position.z);
    return pecas.filter(g => g.visible).map(g => {
      const geo = g.userData.malha.geometry, pos = geo.attributes.position, m = new THREE.Matrix4().compose(g.userData.base, g.quaternion, g.scale).premultiply(desloc);
      const v = [], p = new THREE.Vector3();
      for (let i = 0; i < pos.count; i++) { p.fromBufferAttribute(pos, i).applyMatrix4(m); v.push(r4(p.x), r4(p.y), r4(p.z)); }
      const f = geo.index ? Array.from(geo.index.array) : Array.from({ length: pos.count - pos.count % 3 }, (_, i) => i);
      return { nome: g.userData.nome, v, f };
    });
  }
  function exportar() { return post('/jarvis/holograma/malhas', { titulo, pecas: malhas() }); }

  /* ── mira e seleção ── */
  function pecaEm(x, y) {                               // x, y em 0..1 da tela
    p2.set(x * 2 - 1, -(y * 2 - 1)); ray.setFromCamera(p2, cam);
    const hit = ray.intersectObjects(pecas.filter(g => g.visible).map(g => g.userData.malha), false)[0];
    return hit ? hit.object.userData.peca : null;
  }
  function mirar(g) { if (g !== mira) { mira = g; pintar(); } }
  function selecionar(g) { sel = (g && g === sel) ? null : g; pintar(); relatar(); }

  /* ── desenho no ar (plano de frente para a câmera, passando pelo centro) ── */
  function pontoNoPlano(x, y) {
    p2.set(x * 2 - 1, -(y * 2 - 1)); ray.setFromCamera(p2, cam);
    const n = cam.getWorldDirection(new THREE.Vector3()), plano = new THREE.Plane().setFromNormalAndCoplanarPoint(n, raiz.getWorldPosition(new THREE.Vector3()));
    const q = ray.ray.intersectPlane(plano, new THREE.Vector3());
    return q ? raiz.worldToLocal(q) : null;
  }
  function tracar(x, y) {
    const q = pontoNoPlano(x, y); if (!q) return;
    if (!traco) { traco = [q]; linhaViva = new THREE.Line(new THREE.BufferGeometry().setFromPoints([q, q]), mat(1)); raiz.add(linhaViva); return; }
    if (q.distanceTo(traco[traco.length - 1]) < .03) return;
    traco.push(q); linhaViva.geometry.dispose(); linhaViva.geometry = new THREE.BufferGeometry().setFromPoints(traco);
  }
  function fecharTraco() {
    if (!traco) return;
    raiz.remove(linhaViva); linhaViva = null;
    if (traco.length >= 2) {
      guardar();
      const pts = traco.map(v => v.toArray().map(x => Math.round(x * 1000) / 1000));
      peca(geometria({ forma: 'tubo', tam: [.04, 0, 0], pontos: pts }), [0, 0, 0], [0, 0, 0], { nome: `traço ${tracos.length + 1}` });
      tracos.push(pts); enviarTracos(); relatar();
    }
    traco = null;
  }
  function enviarTracos() { post('/jarvis/holograma/tracos', { tracos }); }

  /* ── cena 3D e mouse ── */
  function iniciar3D() {
    ren = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true }); ren.setPixelRatio(Math.min(2, devicePixelRatio)); ren.setSize(innerWidth, innerHeight);
    box.appendChild(ren.domElement);
    cena = new THREE.Scene(); cena.fog = new THREE.FogExp2(0x001a10, .035);
    cam = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, .1, 100);
    const grade = new THREE.GridHelper(30, 60, 0x0f6, 0x063); grade.position.y = -1.6; grade.material.transparent = true; grade.material.opacity = .25; cena.add(grade);
    for (let i = 1; i <= 3; i++) { const a = new THREE.Mesh(new THREE.RingGeometry(i * 1.6, i * 1.6 + .02, 64), new THREE.MeshBasicMaterial({ color: VERDE, transparent: true, opacity: .35 / i, side: THREE.DoubleSide })); a.rotation.x = -Math.PI / 2; a.position.y = -1.58; cena.add(a); }
    addEventListener('resize', () => { if (!ren) return; ren.setSize(innerWidth, innerHeight); cam.aspect = innerWidth / innerHeight; cam.updateProjectionMatrix(); });
    const el = ren.domElement; let arr = null;
    const norm = e => [e.clientX / innerWidth, e.clientY / innerHeight];
    el.addEventListener('pointerdown', e => {
      const [x, y] = norm(e); ultimoMouse = performance.now();
      if (modo === 'desenho' && !e.shiftKey && !e.altKey) { arr = { desenho: true }; tracar(x, y); return; }
      const alvo = pecaEm(x, y);
      arr = { x0: e.clientX, y0: e.clientY, t: performance.now(), ry: rotYA, rx: rotXA, alvo, mover: e.shiftKey, guardado: false, ult: [e.clientX, e.clientY] };
    });
    addEventListener('pointerup', e => {
      if (!arr) return;
      if (arr.desenho) fecharTraco();
      else if (Math.hypot(e.clientX - arr.x0, e.clientY - arr.y0) < 5 && performance.now() - arr.t < 400) selecionar(arr.alvo);
      else if (arr.guardado) relatar();
      arr = null;
    });
    addEventListener('pointermove', e => {
      if (!vivo) return;
      const [x, y] = norm(e); ultimoMouse = performance.now();
      if (!arr) { mirar(pecaEm(x, y)); return; }
      if (arr.desenho) return tracar(x, y);
      const dx = e.clientX - arr.ult[0], dy = e.clientY - arr.ult[1]; arr.ult = [e.clientX, e.clientY];
      const g = (arr.alvo && arr.alvo === sel) ? sel : arr.mover ? (arr.alvo || sel) : null;
      if (g) {
        if (!arr.guardado) { guardar(); arr.guardado = true; }
        if (arr.mover) { const k = dist / innerHeight * .8; g.userData.base.add(eixoLocal(new THREE.Vector3(1, 0, 0)).multiplyScalar(dx * k)).add(eixoLocal(new THREE.Vector3(0, 1, 0)).multiplyScalar(-dy * k)); }
        else { girar(g, new THREE.Quaternion().setFromAxisAngle(eixoLocal(new THREE.Vector3(0, 1, 0)), dx * .01));
               girar(g, new THREE.Quaternion().setFromAxisAngle(eixoLocal(new THREE.Vector3(1, 0, 0)), dy * .01)); }
        return;
      }
      rotYA = arr.ry + (e.clientX - arr.x0) * .008; rotXA = Math.max(-1.3, Math.min(1.3, arr.rx + (e.clientY - arr.y0) * .006));
    });
    el.addEventListener('wheel', e => { if (sel) { guardar(); escalar(sel, new THREE.Vector3(1, 1, 1).multiplyScalar(e.deltaY < 0 ? 1.06 : 1 / 1.06)); relatar(); } else distA = Math.max(3, Math.min(24, distA + e.deltaY * .01)); });
    addEventListener('keydown', e => {
      if (!vivo || document.activeElement && document.activeElement.tagName === 'INPUT') return;
      const k = e.key.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && k === 'z') { e.preventDefault(); desfazer(); }
      else if (k === 'e') { guardar(); abrirAlvo = abrirAlvo > .5 ? 0 : 1; }
      else if ((k === 'delete' || k === 'backspace') && sel) { guardar(); sel.visible = false; sel = null; pintar(); relatar(); }
      else if (k === 'escape') { if (sel) selecionar(null); else fechar(); }
    });
  }
  function quadro() {
    if (!vivo) return;
    loopId = requestAnimationFrame(quadro);
    abrir += (abrirAlvo - abrir) * .07; rotX += (rotXA - rotX) * .12; rotY += (rotYA - rotY) * .12; dist += (distA - dist) * .1;
    if (!maos.ativa && !sel && modo === 'ver' && performance.now() - ultimoMouse > 4000) rotYA += .0025;
    for (const p of pecas) p.position.copy(p.userData.base).addScaledVector(p.userData.dir, abrir * 1.25);
    raiz.rotation.set(rotX, rotY, 0);
    cam.position.set(0, 1.2, dist); cam.lookAt(0, 0, 0);
    ren.render(cena, cam);
    const s = sel ? `SELECIONADA: ${sel.userData.nome.toUpperCase()}` : mira ? `MIRA: ${mira.userData.nome.toUpperCase()}` : `PEÇAS ${pecas.filter(p => p.visible).length}`;
    hudEl.querySelector('.st').textContent = `${modo === 'desenho' ? `DESENHO · TRAÇOS ${tracos.length} · ` : ''}${s} · EXPLOSÃO ${Math.round(abrir * 100)}% · ZOOM ${(9 / dist).toFixed(2)}x · ${maos.ativa ? 'MÃOS' : 'MOUSE'}`;
  }

  /* ── mãos e olhar (sentidos.js) ── */
  const d2 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const fechada = h => { const p = h[0]; return [8, 12, 16, 20].every(i => d2(h[i], p) < d2(h[i - 2], p) * 1.05); };
  const apontando = h => { const p = h[0]; return d2(h[8], p) > d2(h[6], p) * 1.15 && [12, 16, 20].every(i => d2(h[i], p) < d2(h[i - 2], p) * 1.05); };
  const pinca = h => d2(h[4], h[8]) < .045;
  const rolagem = h => Math.atan2(h[9].y - h[0].y, h[9].x - h[0].x);
  function aplicarGesto(hs, t, olhar) {
    t = t ?? performance.now();
    maos.ativa = hs.length > 0;
    if (hs.length === 2) {
      const d = d2(hs[0][9], hs[1][9]);
      if (!maos.dois) { maos.dois = { d, a: abrirAlvo, s: sel ? sel.scale.clone() : null }; guardar(); }
      if (sel && maos.dois.s) { const k = Math.max(.2, Math.min(5, d / Math.max(.02, maos.dois.d))); emTorno(sel, null, () => sel.scale.copy(maos.dois.s).multiplyScalar(k)); }
      else abrirAlvo = Math.max(0, Math.min(1.6, maos.dois.a + (d - maos.dois.d) * 3.2));
      maos.ref = null; maos.pinca = null; return;
    }
    if (maos.dois) { maos.dois = null; relatar(); }
    if (hs.length !== 1) {
      if (modo === 'desenho') fecharTraco();
      maos.ref = null; maos.pinca = null;
      if (olhar && performance.now() - ultimoMouse > 1500) olharNaPeca(olhar, t);
      return;
    }
    const h = hs[0], palma = h[9], x = 1 - h[8].x, y = h[8].y;           // espelhado
    if (modo === 'desenho' && apontando(h)) { tracar(x, y); return; }
    if (modo === 'desenho') fecharTraco();
    if (pinca(h)) {
      if (!maos.pinca) {
        maos.pinca = { t, x: palma.x, y: palma.y, alvo: pecaEm(x, y), rol: rolagem(h), dist: distA, moveu: false };
        if (maos.pinca.alvo) guardar();
      }
      const P = maos.pinca;
      if (P.alvo) {
        const k = dist * .9, dx = -(palma.x - P.x) * k, dy = -(palma.y - P.y) * k;
        if (Math.hypot(palma.x - P.x, palma.y - P.y) > .02) P.moveu = true;
        if (P.moveu) {
          P.alvo.userData.base.add(eixoLocal(new THREE.Vector3(1, 0, 0)).multiplyScalar(dx)).add(eixoLocal(new THREE.Vector3(0, 1, 0)).multiplyScalar(dy));
          P.x = palma.x; P.y = palma.y;
          const r = rolagem(h), dr = r - P.rol; P.rol = r;
          if (Math.abs(dr) > .01 && Math.abs(dr) < 1) girar(P.alvo, new THREE.Quaternion().setFromAxisAngle(eixoLocal(new THREE.Vector3(0, 0, 1)), -dr));
        }
      } else distA = Math.max(3, Math.min(24, P.dist + (palma.y - P.y) * 22));
      maos.ref = null; return;
    }
    if (maos.pinca) {                                        // soltou a pinça
      const P = maos.pinca; maos.pinca = null;
      if (!P.moveu && t - P.t < 450) selecionar(P.alvo);
      else if (P.alvo) { if (!P.moveu) pilha.pop(); relatar(); }
      return;
    }
    mirar(pecaEm(x, y));
    if (fechada(h)) { if (sel) selecionar(null); else abrirAlvo = 0; maos.ref = null; return; }
    if (!maos.ref) { maos.ref = { x: palma.x, y: palma.y, ry: rotYA, rx: rotXA }; if (sel) guardar(); return; }
    if (sel) {
      const dx = palma.x - maos.ref.x, dy = palma.y - maos.ref.y; maos.ref.x = palma.x; maos.ref.y = palma.y;
      girar(sel, new THREE.Quaternion().setFromAxisAngle(eixoLocal(new THREE.Vector3(0, 1, 0)), -dx * 7));
      girar(sel, new THREE.Quaternion().setFromAxisAngle(eixoLocal(new THREE.Vector3(1, 0, 0)), dy * 5));
      return;
    }
    rotYA = maos.ref.ry - (palma.x - maos.ref.x) * 7;
    rotXA = Math.max(-1.3, Math.min(1.3, maos.ref.rx + (palma.y - maos.ref.y) * 5));
  }
  function olharNaPeca(o, t) {
    const g = pecaEm(o.x, o.y);
    mirar(g);
    if (!g) { olharEm = null; return; }
    if (!olharEm || olharEm.g !== g) { olharEm = { g, t, feito: false }; return; }
    if (!olharEm.feito && t - olharEm.t > 900) { olharEm.feito = true; if (sel !== g) selecionar(g); }
  }
  function ouvirSentidos() {
    if (!window.Sentidos) { dica.textContent = 'SEM CÂMERA: ARRASTE GIRA · CLIQUE SELECIONA · SHIFT+ARRASTE MOVE · RODA ZOOM/ESCALA · CTRL+Z DESFAZ'; return; }
    Sentidos.ligar({ maos: true }).then(s => {
      dica.textContent = s.erro ? 'SEM CÂMERA: ARRASTE GIRA · CLIQUE SELECIONA · SHIFT+ARRASTE MOVE · RODA ZOOM/ESCALA · CTRL+Z DESFAZ'
        : modo === 'desenho' ? 'INDICADOR ESTICADO DESENHA · MÃO ABERTA GIRA · MÃO FECHADA PARA · "DÁ VOLUME AO DESENHO"'
        : 'APONTE = MIRA · PINÇA RÁPIDA = SELECIONA · PINÇA SEGURANDO = ARRASTA/GIRA O PUNHO · MÃO ABERTA GIRA · DUAS MÃOS ESCALAM/ABREM · PUNHO SOLTA';
    });
    if (sairSentidos) sairSentidos();
    sairSentidos = Sentidos.assinar(q => { if (vivo) aplicarGesto(q.maos || [], q.t, q.olhar); });
  }

  /* ── abrir / fechar ── */
  const BOTOES = [['DESFAZER', () => desfazer()], ['SOLTAR', () => selecionar(null)], ['ABRIR PEÇAS', () => { guardar(); abrirAlvo = abrirAlvo > .5 ? 0 : 1; }],
    ['ESCONDER', () => { if (sel) { guardar(); sel.visible = false; sel = null; pintar(); relatar(); } }],
    ['STL', () => falarJarvis('exporta em stl')], ['BLENDER', () => falarJarvis('abre no blender')], ['IMPRIMIR', () => falarJarvis('manda para impressão')],
    ['OLHAR', () => window.Sentidos && Sentidos.ligar({ olhar: !Sentidos.estado().olhar })]];
  function falarJarvis(t) { post('/hud/falar', { texto: t }); }
  function preparar() {
    if (ren) return;
    box.innerHTML = '<div class="hud"><div>HOLOGRAMA · J.A.I.M.E</div><b class="tt"></b><div class="st"></div></div><div class="fechar" data-mao>FECHAR ✕</div>' +
      '<div class="ferramentas">' + BOTOES.map(([r], i) => `<span data-mao data-i="${i}">${r}</span>`).join('') + '</div><div class="dica"></div>';
    hudEl = box.querySelector('.hud'); dica = box.querySelector('.dica'); box.querySelector('.fechar').onclick = fechar;
    box.querySelectorAll('.ferramentas span').forEach(s => s.onclick = () => BOTOES[+s.dataset.i][1]());
    iniciar3D();
  }
  function abrirHolo(d) {
    preparar();
    modo = d.modelo === 'desenho' ? 'desenho' : 'ver';
    titulo = String(d.titulo || d.modelo || '');
    hudEl.querySelector('.tt').textContent = titulo.toUpperCase();
    abrir = 0; abrirAlvo = 0; distA = 9; if (modo === 'desenho') { rotXA = 0; rotYA = 0; }
    montar(d);
    box.classList.add('on'); box.classList.toggle('desenho', modo === 'desenho'); vivo = true;
    cancelAnimationFrame(loopId); quadro(); ouvirSentidos(); relatar();
  }
  function fechar() {
    if (!vivo && !ren) return;
    vivo = false; box.classList.remove('on');
    if (sairSentidos) { sairSentidos(); sairSentidos = null; }
    if (window.Sentidos) { const s = Sentidos.estado(); Sentidos.desligar({ maos: false }); if (s.tela || s.olhar) Sentidos.ligar({}); }
    if (ren) { ren.dispose(); ren.domElement.remove(); ren = null; }
    post('/jarvis/holograma/fechado', {});
  }
  window.Holograma = {
    abrir: abrirHolo, fechar, aberto: () => vivo, editar, desfazer, exportar,
    desenho: d => abrirHolo({ ...d, modelo: 'desenho', titulo: d.titulo || 'DESENHO' }),
    _estado: () => ({ pecas: pecas.length, visiveis: pecas.filter(p => p.visible).length, abrir: +abrir.toFixed(2), abrirAlvo: +abrirAlvo.toFixed(2), dist: +distA.toFixed(2),
      rotY: +rotYA.toFixed(2), rotX: +rotXA.toFixed(2), maos: !!maos.ativa, sel: sel ? sel.userData.nome : null, mira: mira ? mira.userData.nome : null,
      tracos: tracos.length, pilha: pilha.length, modo, nomes: pecas.map(p => p.userData.nome) }),
    _peca: i => { const g = pecas[i]; return g && { base: g.userData.base.toArray(), q: g.quaternion.toArray(), s: g.scale.toArray(), v: g.visible }; },
    _explodir: v => abrirAlvo = v, _gesto: aplicarGesto, _pecaEm: (x, y) => { const g = pecaEm(x, y); return g && g.userData.nome; }, _selecionar: i => selecionar(pecas[i] || null), _malhas: malhas,
    _tela: nome => { const g = pecas.find(p => p.userData.nome === nome); if (!g) return null; raiz.updateMatrixWorld(true);
      const c = g.userData.caixa.getCenter(new THREE.Vector3()).applyMatrix4(g.matrixWorld).project(cam); return { x: (c.x + 1) / 2, y: (1 - c.y) / 2 }; },
  };
})();
