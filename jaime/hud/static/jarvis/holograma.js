/* Estúdio de holograma: qualquer objeto vira PEÇAS que o João pega, move, gira, escala, separa, isola, pinta,
   desenha, edita por voz, exporta e manda imprimir.

   Objetos: catálogo (carro/SUV, moto, casa, drone, foguete, átomo, planeta), peças geradas pelo modelo para
   QUALQUER objeto, .glb do João (~/Jaime/hologramas/<nome>.glb), desenhos no ar e capturas da câmera.

   Mãos INDIVIDUAIS e com PROFUNDIDADE (webcam, via sentidos.js):
     - as duas mãos aparecem espelhadas como holograma na cena (direita ciano, esquerda âmbar), com os braços
       quando "mostra meus braços"; um anel no chão e um fio mostram a que profundidade a mão está;
     - profundidade = tamanho aparente da mão: aproximar a mão da câmera = entrar na cena. A mão "encosta" numa
       peça quando o ponto da pinça chega à caixa dela — ela acende. Pinça ENCOSTADA = pegar a peça;
       pinça no VAZIO = mexer na cena (direita gira, esquerda aproxima/afasta);
     - peça pega: segue a mão em 3D; girar o punho gira a peça; as DUAS mãos na mesma peça escalam e giram;
     - pinça rápida numa peça = seleciona; punho fechado = solta tudo;
     - modo desenho: só o indicador esticado desenha, na profundidade do dedo (desenho 3D de verdade).
   Olhar (opcional): parar o olhar ~0,9 s numa peça seleciona.
   Câmera no holograma: a imagem da webcam vira projeção holográfica atrás da peça, alinhada com a mão; "captura"
   congela a imagem como uma peça de referência (para projetar algo para o braço, o pulso, um objeto real).
   Mouse: clique seleciona · arrastar gira · Shift+arrastar move · roda zoom/escala · Delete esconde · Ctrl/⌘+Z · E · Esc.
   Nada daqui aprova ação nenhuma. */
(function () {
  const VERDE = 0x3dffa0, VERDE2 = 0x1fd180, SEL = 0xffc24a, MIRA = 0xe8fff4;
  const COR_MAO = { direita: 0x3be8ff, esquerda: 0xffb347 };
  const V3 = THREE.Vector3;
  let cena, cam, ren, raiz, pecas = [], abrir = 0, abrirAlvo = 0, rotX = -.25, rotY = .6, rotXA = -.25, rotYA = .6, dist = 9, distA = 9;
  let vivo = false, loopId = 0, dica, hudEl, maosEl, titulo = '', modo = 'ver', sel = null, mira = null, pilha = [], sairSentidos = null;
  let tracos = [], ultimoMouse = 0, olharEm = null, relatarT = 0, raioModelo = 3, foco = null, capturas = 0;
  const focoAtual = new V3(), mouseTraco = { traco: null, linha: null };
  let camPlano = null, camLigada = false, ultimoQ = null, maosAtivas = false;
  const estMao = { direita: novoEstado(), esquerda: novoEstado() }, visual = {};
  const box = document.getElementById('holo');
  const ray = new THREE.Raycaster(), p2 = new THREE.Vector2();
  function novoEstado() { return { s0: null, amostras: [], visto: -1e9, pinca: false, pincaT: 0, alvo: null, cenaRef: null, moveu: false,
                                   P0: new V3(), ultimoP: new V3(), rol: 0, apontaT: -1e9, dono: { traco: null, linha: null }, duas: null, toque: null }; }

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
    g.userData = { base: new V3(...pos), dir: new V3(...dir), nome: opts.nome || `peça ${pecas.length + 1}`, malha,
      caixa: malha.geometry.boundingBox.clone(), base0: new V3(...pos), q0: g.quaternion.clone(), s0: g.scale.clone(), cor: null };
    malha.userData.peca = g;
    raiz.add(g); pecas.push(g); return g;
  }
  function corBase(g) { return g.userData.cor ? new THREE.Color(g.userData.cor).getHex() : VERDE; }
  function colorir(g, cor, forte) {
    g.children.forEach((c, i) => { if (!c.material || !c.material.color) return;
      c.material.color.setHex(i === 2 && cor === VERDE ? VERDE2 : cor);
      if (i === 2 && !g.userData.foto) c.material.opacity = forte ? .16 : (g.userData.cor ? .12 : .05); });
  }
  function pintar() { for (const g of pecas) colorir(g, g === sel ? SEL : g === mira ? MIRA : corBase(g), g === sel || g === mira); }

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
    if (p.forma === 'tubo') return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(p.pontos.map(q => new V3(...q))), Math.max(8, p.pontos.length * 2), Math.max(.01, a), 6);
    return p.forma === 'caixa' ? new THREE.BoxGeometry(a, b, c, seg(a), seg(b), seg(c))
      : p.forma === 'cilindro' ? new THREE.CylinderGeometry(a, a, b, 18, 2)
      : p.forma === 'esfera' ? new THREE.SphereGeometry(a, 16, 12)
      : p.forma === 'toro' ? new THREE.TorusGeometry(a, Math.max(.02, b), 8, 32)
      : new THREE.ConeGeometry(a, b, 16, 2);
  }
  function montarGerado(lista) { return lista.map(p => peca(geometria(p), p.forma === 'tubo' ? [0, 0, 0] : p.pos.map(Number), (p.explode || [0, 1, 0]).map(Number), { rot: p.forma === 'tubo' ? null : p.rot.map(Number), nome: p.nome })); }
  function medirModelo() {
    const b = new THREE.Box3().setFromObject(raiz);
    raioModelo = b.isEmpty() ? 2.5 : Math.max(1.2, b.getSize(new V3()).length() / 2);
  }
  function montar(d) {
    if (raiz) cena.remove(raiz);
    raiz = new THREE.Group(); pecas = []; sel = null; mira = null; pilha = []; tracos = []; foco = null; cena.add(raiz);
    if (d.modelo === 'desenho' || d.modelo === 'vazio') { raioModelo = 2.5; return; }
    if (d.modelo === 'glb' && d.arquivo) return carregarGLB(d.arquivo);
    if (d.modelo === 'gerado' && Array.isArray(d.pecas)) montarGerado(d.pecas);
    else (MODELOS[d.modelo] || MODELOS.atomo)();
    const c = new THREE.Box3().setFromObject(raiz).getCenter(new V3()); raiz.position.sub(c);
    medirModelo();
  }
  async function carregarGLB(slug) {
    if (!THREE.GLTFLoader) await new Promise((ok, e) => { const s = document.createElement('script'); s.src = 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js'; s.onload = ok; s.onerror = e; document.head.appendChild(s); });
    new THREE.GLTFLoader().load(`/jarvis/holograma/${encodeURIComponent(slug)}.glb`, g => {
      const bb = new THREE.Box3().setFromObject(g.scene), tam = bb.getSize(new V3()).length() || 1, esc = 6 / tam, centro = bb.getCenter(new V3());
      g.scene.traverse(o => { if (o.isMesh) {
        o.updateWorldMatrix(true, false);
        const geo = o.geometry.clone().applyMatrix4(o.matrixWorld).translate(-centro.x, -centro.y, -centro.z).scale(esc, esc, esc);
        geo.computeBoundingBox(); const c = geo.boundingBox.getCenter(new V3());
        const w = new THREE.Group(); w.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 20), mat(.9))); w.add(new THREE.Object3D());
        const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: VERDE2, transparent: true, opacity: .05, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
        w.add(m); registrar(w, m, [0, 0, 0], c.clone().multiplyScalar(.9).toArray(), { nome: o.name || `peça ${pecas.length + 1}` });
      } });
      medirModelo(); relatar();
    });
  }

  /* ── transformações (em torno do centro da peça, ou de uma face: "pivo") ── */
  function pivoLocal(g, pivo) {
    const cx = g.userData.caixa, c = cx.getCenter(new V3());
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
  function centroLocal(g) { return g.userData.caixa.clone().applyMatrix4(new THREE.Matrix4().compose(g.userData.base, g.quaternion, g.scale)).getCenter(new V3()); }
  function caixaMundo(g) { return new THREE.Box3().setFromObject(g.userData.malha); }

  /* ── desfazer ── */
  function guardar() {
    pilha.push({ n: pecas.length, t: tracos.length, a: abrirAlvo, e: pecas.map(g => ({ b: g.userData.base.clone(), q: g.quaternion.clone(), s: g.scale.clone(), v: g.visible, c: g.userData.cor })) });
    if (pilha.length > 80) pilha.shift();
  }
  function desfazer() {
    const s = pilha.pop(); if (!s) return false;
    while (pecas.length > s.n) { const g = pecas.pop(); raiz.remove(g); if (g === sel) sel = null; }
    s.e.forEach((e, i) => { const g = pecas[i]; g.userData.base.copy(e.b); g.quaternion.copy(e.q); g.scale.copy(e.s); g.visible = e.v; g.userData.cor = e.c; });
    abrirAlvo = s.a;
    if (tracos.length !== s.t) { tracos.length = s.t; enviarTracos(); }
    pintar(); relatar(); return true;
  }

  /* ── operações da voz (validadas no servidor; as comuns chegam sem passar pelo modelo) ── */
  function alvos(a) { return a === 'selecionada' ? (sel ? [sel] : []) : a === 'todas' ? pecas.slice() : (a || []).map(i => pecas[i]).filter(Boolean); }
  function focar(lista) {
    lista = (lista || []).filter(Boolean);
    if (!lista.length) { foco = null; distA = 9; return; }
    foco = lista;
    const b = new THREE.Box3(); lista.forEach(g => b.union(caixaMundo(g)));
    distA = Math.max(2.2, Math.min(24, b.getSize(new V3()).length() * 1.7));
  }
  function resetarPeca(g) { g.userData.base.copy(g.userData.base0); g.quaternion.copy(g.userData.q0); g.scale.copy(g.userData.s0); g.visible = true; g.userData.cor = null; g.userData.removida = false; }
  function editar(ops) {
    guardar();
    let ultimoAlvo = null;
    for (const o of ops || []) {
      const v = o.valor;
      if (o.op === 'explodir') abrirAlvo = v;
      else if (o.op === 'mostrar_tudo') { pecas.forEach(g => { if (!g.userData.removida) g.visible = true; }); foco = null; distA = 9; }
      else if (o.op === 'resetar' && !o.alvo) {
        while (pecas.length && pecas[pecas.length - 1].userData.adicionada) raiz.remove(pecas.pop());
        pecas.forEach(resetarPeca); abrirAlvo = 0; foco = null; distA = 9;
      }
      else if (o.op === 'adicionar') { const g = montarGerado([o.peca])[0]; g.position.copy(g.userData.base); g.userData.adicionada = true; ultimoAlvo = g; }
      else if (o.op === 'isolar') {
        const alv = new Set(alvos(o.alvo));
        if (alv.size) { pecas.forEach(g => { g.visible = alv.has(g); }); focar([...alv]); ultimoAlvo = [...alv][0]; }
      }
      else if (o.op === 'focar') focar(alvos(o.alvo));
      else for (const g of alvos(o.alvo)) {
        ultimoAlvo = g;
        if (o.op === 'mover') g.userData.base.add(new V3(...v));
        else if (o.op === 'girar') girar(g, new THREE.Quaternion().setFromEuler(new THREE.Euler(...v)), o.pivo);
        else if (o.op === 'escalar') escalar(g, new V3(...v));
        else if (o.op === 'esconder') g.visible = false;
        else if (o.op === 'remover') { g.visible = false; g.userData.removida = true; }
        else if (o.op === 'mostrar') { g.visible = true; g.userData.removida = false; }
        else if (o.op === 'cor') g.userData.cor = v === '#3dffa0' ? null : v;
        else if (o.op === 'resetar') resetarPeca(g);
        else if (o.op === 'separar') {
          let d = g.userData.dir.clone();
          if (d.lengthSq() < 1e-6) d = centroLocal(g);
          if (d.lengthSq() < 1e-6) d.set(0, 1, 0);
          g.userData.base.addScaledVector(d.normalize(), (v || 1.6) * raioModelo * .45);
          g.visible = true;
        }
        else if (o.op === 'duplicar') {
          const ud = g.userData; g.userData = {};             // userData tem a malha (referência circular): fora do clone
          const c = g.clone(true); g.userData = ud; c.userData = {};
          c.children.forEach(k => { if (k.material) k.material = k.material.clone(); k.userData = {}; });
          const m = c.children[2]; registrar(c, m, g.userData.base.clone().add(new V3(...(v || [.5, 0, 0]))).toArray(), g.userData.dir.toArray(), { nome: g.userData.nome + ' (cópia)' });
          c.quaternion.copy(g.quaternion); c.scale.copy(g.scale); c.userData.adicionada = true; c.userData.cor = g.userData.cor;
        }
      }
    }
    if (ultimoAlvo && ops.some(o => ['separar', 'isolar', 'cor', 'escalar', 'girar', 'mover', 'adicionar', 'duplicar'].includes(o.op))) sel = ultimoAlvo;
    pintar(); relatar();
  }

  /* ── o servidor sabe o que está aberto (para a voz) ── */
  function relatar() {
    clearTimeout(relatarT);
    relatarT = setTimeout(() => {
      const r2 = x => Math.round(x * 100) / 100;
      const lista = pecas.map(g => { const b = g.userData.caixa.clone().applyMatrix4(new THREE.Matrix4().compose(g.userData.base, g.quaternion, g.scale));
        return { nome: g.userData.nome, centro: b.getCenter(new V3()).toArray().map(r2), tam: b.getSize(new V3()).toArray().map(r2), visivel: g.visible }; });
      post('/jarvis/holograma/cena', { titulo, pecas: lista, selecionada: sel ? pecas.indexOf(sel) : null });
    }, 350);
  }
  function post(url, corpo) { return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) }).catch(() => {}); }
  function malhas() {
    const r4 = x => Math.round(x * 1e4) / 1e4, desloc = new THREE.Matrix4().makeTranslation(raiz.position.x, raiz.position.y, raiz.position.z);
    return pecas.filter(g => g.visible).map(g => {
      const geo = g.userData.malha.geometry, pos = geo.attributes.position, m = new THREE.Matrix4().compose(g.userData.base, g.quaternion, g.scale).premultiply(desloc);
      const v = [], p = new V3();
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

  /* ── desenho (mouse: plano de frente para a câmera; mão: na profundidade do dedo) ── */
  function pontoNoPlano(x, y) {
    p2.set(x * 2 - 1, -(y * 2 - 1)); ray.setFromCamera(p2, cam);
    const n = cam.getWorldDirection(new V3()), plano = new THREE.Plane().setFromNormalAndCoplanarPoint(n, raiz.getWorldPosition(new V3()));
    const q = ray.ray.intersectPlane(plano, new V3());
    return q ? raiz.worldToLocal(q) : null;
  }
  function tracarLocal(dono, q, cor) {
    if (!q) return;
    if (!dono.traco) { dono.traco = [q]; dono.linha = new THREE.Line(new THREE.BufferGeometry().setFromPoints([q, q]), new THREE.LineBasicMaterial({ color: cor || VERDE })); raiz.add(dono.linha); return; }
    if (q.distanceTo(dono.traco[dono.traco.length - 1]) < .025) return;
    dono.traco.push(q); dono.linha.geometry.dispose(); dono.linha.geometry = new THREE.BufferGeometry().setFromPoints(dono.traco);
  }
  function fecharTracoDe(dono) {
    if (!dono.traco) return;
    raiz.remove(dono.linha); dono.linha = null;
    if (dono.traco.length >= 3) {
      guardar();
      const pts = dono.traco.map(v => v.toArray().map(x => Math.round(x * 1000) / 1000));
      peca(geometria({ forma: 'tubo', tam: [.04, 0, 0], pontos: pts }), [0, 0, 0], [0, 0, 0], { nome: `traço ${tracos.length + 1}` });
      tracos.push(pts); enviarTracos(); relatar();
    }
    dono.traco = null;
  }
  const tracar = (x, y) => tracarLocal(mouseTraco, pontoNoPlano(x, y));
  const fecharTraco = () => fecharTracoDe(mouseTraco);
  function enviarTracos() { post('/jarvis/holograma/tracos', { tracos }); }

  /* ── câmera no holograma: a webcam como projeção holográfica, alinhada com as mãos ── */
  function planoCamera(ligar) {
    if (!ligar) { if (camPlano) { cena.remove(camPlano); camPlano = null; } camLigada = false; return; }
    const v = window.Sentidos && Sentidos.video();
    if (!v || !v.videoWidth) { if (window.Sentidos) Sentidos.ligar({ maos: true }).then(() => setTimeout(() => planoCamera(true), 600)); return; }
    if (camPlano) return;
    const tex = new THREE.VideoTexture(v); tex.minFilter = THREE.LinearFilter;
    const m = new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: { tex: { value: tex }, t: { value: 0 }, px: { value: new THREE.Vector2(1 / v.videoWidth, 1 / v.videoHeight) } },
      vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: `uniform sampler2D tex; uniform float t; uniform vec2 px; varying vec2 vUv;
        float l(vec2 u){ return dot(texture2D(tex, u).rgb, vec3(.299, .587, .114)); }
        void main(){
          vec2 u = vec2(1.0 - vUv.x, vUv.y);
          float gx = l(u + vec2(px.x, 0.)) - l(u - vec2(px.x, 0.)), gy = l(u + vec2(0., px.y)) - l(u - vec2(0., px.y));
          float borda = clamp(length(vec2(gx, gy)) * 5.0, 0.0, 1.0), lum = l(u);
          float linhas = .78 + .22 * sin(vUv.y * 900.0 + t * 6.0);
          vec3 c = vec3(.24, 1.0, .63) * (lum * .45 + borda * 1.2) * linhas;
          gl_FragColor = vec4(c, clamp(lum * .35 + borda, 0.0, 1.0) * .8);
        }` });
    camPlano = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), m); camPlano.renderOrder = -1; cena.add(camPlano); camLigada = true;
  }
  function posicionarPlano(t) {
    if (!camPlano) return;
    const D = dist + raioModelo * 1.6, h = 2 * D * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2));
    camPlano.position.copy(cam.position).addScaledVector(cam.getWorldDirection(new V3()), D);
    camPlano.quaternion.copy(cam.quaternion); camPlano.scale.set(h * cam.aspect, h, 1);
    camPlano.material.uniforms.t.value = t / 1000;
  }
  function capturar() {
    const v = window.Sentidos && Sentidos.video();
    if (!v || !v.videoWidth) return false;
    const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight;
    const x = c.getContext('2d'); x.translate(c.width, 0); x.scale(-1, 1); x.drawImage(v, 0, 0);
    const tex = new THREE.CanvasTexture(c), h = raioModelo * .62, w = h * c.width / c.height, geo = new THREE.PlaneGeometry(w, h, 4, 4);
    const g = new THREE.Group();
    g.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo), mat(.9))); g.add(new THREE.Object3D());
    const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: tex, color: VERDE, transparent: true, opacity: .7, side: THREE.DoubleSide, depthWrite: false }));
    g.add(m); guardar();
    raiz.updateMatrixWorld(true);
    const frente = raiz.worldToLocal(cam.position.clone().addScaledVector(cam.getWorldDirection(new V3()), Math.max(2.5, dist - raioModelo * .4)).add(new V3(raioModelo * .9, raioModelo * .35, 0)));
    registrar(g, m, frente.toArray(), [0, 0, 1], { nome: `referência ${++capturas}` });
    g.quaternion.copy(raiz.quaternion).invert().multiply(cam.quaternion); g.userData.q0 = g.quaternion.clone();
    g.userData.foto = true; g.userData.adicionada = true;
    sel = g; pintar(); relatar(); return true;
  }

  /* ── mãos em 3D: holograma de cada mão + profundidade pelo tamanho aparente ── */
  const OSSOS = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]];
  const FECHA = .30, ABRE = .45;
  const d2 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const escalaMao = h => (d2(h[0], h[5]) + d2(h[0], h[17]) + d2(h[5], h[17])) / 3 || 1e-3;
  const fechada = h => { const p = h[0]; return [8, 12, 16, 20].every(i => d2(h[i], p) < d2(h[i - 2], p) * 1.05); };
  const apontando = h => { const p = h[0]; return d2(h[8], p) > d2(h[6], p) * 1.12 && d2(h[12], p) < d2(h[10], p) * 1.08 && d2(h[4], h[8]) / escalaMao(h) > .5; };
  const rolagem = h => Math.atan2(h[9].y - h[0].y, h[9].x - h[0].x);
  function larguraEm(T) { return 2 * T * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)) * cam.aspect; }
  function ponto3D(p, T, out) { p2.set((1 - p.x) * 2 - 1, -(p.y * 2 - 1)); ray.setFromCamera(p2, cam); return ray.ray.at(T, out || new V3()); }
  function profundidade(e, s) {
    const R = raioModelo, D = cam.position.distanceTo(focoAtual);
    return Math.max(D - R * 3, Math.min(D + R * 2, D - R * 1.1 + (s / e.s0 - 1) * R * 5.5));
  }
  function visualMao(lado) {
    if (visual[lado]) return visual[lado];
    const cor = COR_MAO[lado], g = new THREE.Group();
    const ml = (op, dt = false) => new THREE.LineBasicMaterial({ color: cor, transparent: true, opacity: op, blending: THREE.AdditiveBlending, depthTest: dt });
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(OSSOS.length * 6), 3));
    const linhas = new THREE.LineSegments(geo, ml(.95));
    const juntas = [...Array(21)].map((_, i) => { const m = new THREE.Mesh(new THREE.SphereGeometry([4, 8, 12, 16, 20].includes(i) ? .055 : .035, 8, 6),
      new THREE.MeshBasicMaterial({ color: cor, transparent: true, opacity: .9, blending: THREE.AdditiveBlending, depthTest: false })); g.add(m); return m; });
    const anelPinca = new THREE.Mesh(new THREE.RingGeometry(.09, .13, 28), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, side: THREE.DoubleSide, depthTest: false }));
    const sombra = new THREE.Mesh(new THREE.RingGeometry(.12, .17, 28), new THREE.MeshBasicMaterial({ color: cor, transparent: true, opacity: .55, side: THREE.DoubleSide }));
    sombra.rotation.x = -Math.PI / 2;
    const fio = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new V3(), new V3(0, -1, 0)]), new THREE.LineDashedMaterial({ color: cor, dashSize: .09, gapSize: .07, transparent: true, opacity: .45 }));
    const braco = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new V3(), new V3(), new V3()]), ml(.6));
    braco.visible = false;
    g.add(linhas, anelPinca, sombra, fio, braco); cena.add(g);
    return (visual[lado] = { g, linhas, juntas, anelPinca, sombra, fio, braco });
  }
  function desenharMao(lado, pts, P, e, bracoPts) {
    const vis = visualMao(lado); vis.g.visible = true;
    const pos = vis.linhas.geometry.attributes.position;
    OSSOS.forEach(([a, b], i) => { pos.setXYZ(i * 2, pts[a].x, pts[a].y, pts[a].z); pos.setXYZ(i * 2 + 1, pts[b].x, pts[b].y, pts[b].z); });
    pos.needsUpdate = true;
    const acesa = !!(e.toque || e.alvo), forte = acesa ? 1.35 : 1;
    pts.forEach((p, i) => { vis.juntas[i].position.copy(p); vis.juntas[i].scale.setScalar(forte); vis.juntas[i].material.color.setHex(acesa ? 0xffffff : COR_MAO[lado]); });
    vis.linhas.material.opacity = acesa ? 1 : .8;
    vis.anelPinca.position.copy(P); vis.anelPinca.quaternion.copy(cam.quaternion);
    vis.anelPinca.material.opacity = e.pinca ? .95 : 0; vis.anelPinca.material.color.setHex(e.alvo ? 0xffffff : COR_MAO[lado]);
    vis.sombra.position.set(P.x, -1.57, P.z);
    vis.fio.geometry.setFromPoints([P, new V3(P.x, -1.57, P.z)]); vis.fio.computeLineDistances();
    if (bracoPts) { vis.braco.visible = true; vis.braco.geometry.setFromPoints(bracoPts); } else vis.braco.visible = false;
  }
  function esconderMao(lado) { if (visual[lado]) visual[lado].g.visible = false; }
  function tocada(P) {
    // precisão: o raio da câmera até o ponto da pinça cruza as superfícies REAIS das peças; vale a superfície mais
    // perto da profundidade da mão (peça pequena ganha o desempate: a porta vence a lataria que está atrás dela)
    const dP = P.distanceTo(cam.position);
    ray.set(cam.position, P.clone().sub(cam.position).normalize());
    const hits = ray.intersectObjects(pecas.filter(g => g.visible).map(g => g.userData.malha), false);
    let melhor = null, bd = raioModelo * .16;
    for (const h of hits) {
      const g = h.object.userData.peca, diag = caixaMundo(g).getSize(new V3()).length();
      const nota = Math.abs(h.distance - dP) + .04 * diag;
      if (Math.abs(h.distance - dP) < raioModelo * .16 && nota < bd) { bd = nota; melhor = g; }
    }
    if (melhor) return melhor;
    let menor = null, vol = Infinity;                        // mão DENTRO de uma peça oca: a menor caixa que a contém
    for (const g of pecas) { if (!g.visible) continue; const b = caixaMundo(g);
      if (b.containsPoint(P)) { const t = b.getSize(new V3()), v = t.x * t.y * t.z; if (v < vol) { vol = v; menor = g; } } }
    return menor;
  }
  function umaMao(lado, h, s, t, bracoN) {
    const e = estMao[lado];
    if (t - e.visto > 1500) e.amostras = [];
    e.visto = t;
    if (e.amostras.length < 15 && !e.pinca) { e.amostras.push(s); if (e.amostras.length === 15) { const o = [...e.amostras].sort((a, b) => a - b); e.s0 = o[7]; } }
    if (!e.s0) e.s0 = s;
    const T = profundidade(e, s), W = larguraEm(T);
    const z0 = h[0].z || 0, pts = h.map(p => ponto3D(p, T + (z0 - (p.z || 0)) * W));
    const P = pts[4].clone().add(pts[8]).multiplyScalar(.5);
    let bracoPts = null;
    if (bracoN) { const [o, c] = bracoN; bracoPts = [ponto3D(o, T + raioModelo * .9), ponto3D(c, T + raioModelo * .45), pts[0]]; }
    const r = d2(h[4], h[8]) / escalaMao(h);
    if (fechada(h)) {                                        // punho: solta tudo
      if (e.alvo || e.pinca) { if (e.alvo) relatar(); e.alvo = null; e.cenaRef = null; e.pinca = false; e.duas = null; }
      fecharTracoDe(e.dono); e.toque = null; desenharMao(lado, pts, P, e, bracoPts); return;
    }
    if (modo === 'desenho') {
      if (apontando(h)) e.apontaT = t;
      if (t - e.apontaT < 300 && r > ABRE) { tracarLocal(e.dono, raiz.worldToLocal(pts[8].clone()), COR_MAO[lado]); desenharMao(lado, pts, pts[8], e, bracoPts); return; }
      fecharTracoDe(e.dono);
    }
    e.toque = e.pinca ? e.toque : tocada(r > ABRE ? pts[8] : P);      // mão aberta: a ponta do indicador; fechando: a pinça
    const pincando = e.pinca ? r < ABRE : r < FECHA;
    if (pincando && !e.pinca) {
      e.pinca = true; e.pincaT = t; e.moveu = false; e.P0.copy(P); e.ultimoP.copy(P); e.rol = rolagem(h); e.alvo = e.toque;
      e.cenaRef = e.alvo ? null : { rx: rotXA, ry: rotYA, d: distA, x: 1 - h[8].x, y: h[8].y };
      if (e.alvo) guardar();
    } else if (pincando && e.pinca) {
      if (P.distanceTo(e.P0) > raioModelo * .04) e.moveu = true;
      const outro = estMao[lado === 'direita' ? 'esquerda' : 'direita'];
      if (e.alvo && outro.pinca && outro.alvo === e.alvo) {
        if (lado === 'esquerda') duasMaos(e.alvo, outro, e);
      } else if (e.alvo) {
        e.duas = null;
        if (e.moveu) {
          const a = raiz.worldToLocal(e.ultimoP.clone()), b = raiz.worldToLocal(P.clone());
          e.alvo.userData.base.add(b.sub(a));
          const rr = rolagem(h), dr = rr - e.rol; e.rol = rr;
          if (Math.abs(dr) > .01 && Math.abs(dr) < 1) girar(e.alvo, new THREE.Quaternion().setFromAxisAngle(eixoLocal(cam.getWorldDirection(new V3())), dr));
        }
      } else if (e.cenaRef) {
        const x = 1 - h[8].x, y = h[8].y;
        if (lado === 'direita') { rotYA = e.cenaRef.ry + (x - e.cenaRef.x) * 6; rotXA = Math.max(-1.3, Math.min(1.3, e.cenaRef.rx + (y - e.cenaRef.y) * 4)); }
        else distA = Math.max(2.2, Math.min(24, e.cenaRef.d + (y - e.cenaRef.y) * 20));
      }
      e.ultimoP.copy(P);
    } else if (!pincando && e.pinca) {
      e.pinca = false; e.duas = null;
      if (e.alvo) { if (!e.moveu && t - e.pincaT < 450) { pilha.pop(); selecionar(e.alvo); } else relatar(); }
      e.alvo = null; e.cenaRef = null;
    }
    desenharMao(lado, pts, P, e, bracoPts);
  }
  function duasMaos(g, d, e) {                             // as duas mãos na mesma peça: distância escala, ângulo gira
    const v = e.ultimoP.clone().sub(d.ultimoP);
    if (!e.duas) { e.duas = { v0: v.clone(), s: g.scale.clone(), q: g.quaternion.clone() }; return; }
    const k = Math.max(.2, Math.min(6, v.length() / Math.max(1e-3, e.duas.v0.length())));
    const qm = new THREE.Quaternion().setFromUnitVectors(e.duas.v0.clone().normalize(), v.clone().normalize());
    const rq = raiz.getWorldQuaternion(new THREE.Quaternion()), ql = rq.clone().invert().multiply(qm).multiply(rq);
    emTorno(g, null, () => { g.quaternion.copy(e.duas.q).premultiply(ql); g.scale.copy(e.duas.s).multiplyScalar(k); });
    e.moveu = true;
  }
  function aplicarMaos(q) {
    const hs = q.maos || [], ls = q.lados || [], ss = q.escalas || [];
    maosAtivas = hs.length > 0;
    const vistos = new Set();
    hs.forEach((h, i) => { const lado = ls[i] || (i ? 'esquerda' : 'direita'); if (vistos.has(lado)) return; vistos.add(lado);
      umaMao(lado, h, ss[i] || escalaMao(h), q.t, q.bracos && q.bracos[lado]); });
    for (const lado of ['direita', 'esquerda']) if (!vistos.has(lado)) {
      const e = estMao[lado];
      if (e.pinca && q.t - e.visto > 400) { if (e.alvo) relatar(); e.pinca = false; e.alvo = null; e.cenaRef = null; e.duas = null; }
      if (q.t - e.visto > 300) { fecharTracoDe(e.dono); esconderMao(lado); }
    }
    const toques = ['direita', 'esquerda'].map(l => estMao[l].alvo || estMao[l].toque).filter(Boolean);
    mirar(toques[0] || null);
    if (!hs.length && q.olhar && performance.now() - ultimoMouse > 1500) olharNaPeca(q.olhar, q.t);
    if (maosEl) maosEl.textContent = ['direita', 'esquerda'].map(l => { const e = estMao[l];
      if (!vistos.has(l)) return `${l === 'direita' ? 'D' : 'E'}: —`;
      return `${l === 'direita' ? 'D' : 'E'}: ${e.alvo ? 'PEGANDO ' + e.alvo.userData.nome.toUpperCase() : e.cenaRef ? (l === 'direita' ? 'GIRANDO A CENA' : 'ZOOM') : e.toque ? 'ENCOSTOU EM ' + e.toque.userData.nome.toUpperCase() : e.dono.traco ? 'DESENHANDO' : 'LIVRE'}`; }).join('   ·   ');
  }
  function olharNaPeca(o, t) {
    const g = pecaEm(o.x, o.y);
    mirar(g);
    if (!g) { olharEm = null; return; }
    if (!olharEm || olharEm.g !== g) { olharEm = { g, t, feito: false }; return; }
    if (!olharEm.feito && t - olharEm.t > 900) { olharEm.feito = true; if (sel !== g) selecionar(g); }
  }
  function aplicarGesto(hs, t, olhar, lados) {                // compatível com testes: listas cruas de pontos
    aplicarMaos({ maos: hs, lados: lados || hs.map((_, i) => i ? 'esquerda' : 'direita'), escalas: hs.map(escalaMao), t: t ?? performance.now(), olhar });
  }

  /* ── cena 3D e mouse ── */
  function iniciar3D() {
    ren = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true }); ren.setPixelRatio(Math.min(2, devicePixelRatio)); ren.setSize(innerWidth, innerHeight);
    box.appendChild(ren.domElement);
    cena = new THREE.Scene(); cena.fog = new THREE.FogExp2(0x001a10, .03);
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
      if (!arr) { if (!maosAtivas) mirar(pecaEm(x, y)); return; }
      if (arr.desenho) return tracar(x, y);
      const dx = e.clientX - arr.ult[0], dy = e.clientY - arr.ult[1]; arr.ult = [e.clientX, e.clientY];
      const g = (arr.alvo && arr.alvo === sel) ? sel : arr.mover ? (arr.alvo || sel) : null;
      if (g) {
        if (!arr.guardado) { guardar(); arr.guardado = true; }
        if (arr.mover) { const k = dist / innerHeight * .8; g.userData.base.add(eixoLocal(new V3(1, 0, 0)).multiplyScalar(dx * k)).add(eixoLocal(new V3(0, 1, 0)).multiplyScalar(-dy * k)); }
        else { girar(g, new THREE.Quaternion().setFromAxisAngle(eixoLocal(new V3(0, 1, 0)), dx * .01));
               girar(g, new THREE.Quaternion().setFromAxisAngle(eixoLocal(new V3(1, 0, 0)), dy * .01)); }
        return;
      }
      rotYA = arr.ry + (e.clientX - arr.x0) * .008; rotXA = Math.max(-1.3, Math.min(1.3, arr.rx + (e.clientY - arr.y0) * .006));
    });
    el.addEventListener('wheel', e => { if (sel) { guardar(); escalar(sel, new V3(1, 1, 1).multiplyScalar(e.deltaY < 0 ? 1.06 : 1 / 1.06)); relatar(); } else distA = Math.max(2.2, Math.min(24, distA + e.deltaY * .01)); });
    addEventListener('keydown', e => {
      if (!vivo || document.activeElement && document.activeElement.tagName === 'INPUT') return;
      const k = e.key.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && k === 'z') { e.preventDefault(); desfazer(); }
      else if (k === 'e') { guardar(); abrirAlvo = abrirAlvo > .5 ? 0 : 1; }
      else if ((k === 'delete' || k === 'backspace') && sel) { guardar(); sel.visible = false; sel = null; pintar(); relatar(); }
      else if (k === 'escape') { if (sel) selecionar(null); else if (foco) { editar([{ op: 'mostrar_tudo' }]); } else fechar(); }
    });
  }
  function quadro() {
    if (!vivo) return;
    loopId = requestAnimationFrame(quadro);
    const agora = performance.now();
    abrir += (abrirAlvo - abrir) * .07; rotX += (rotXA - rotX) * .12; rotY += (rotYA - rotY) * .12; dist += (distA - dist) * .1;
    if (!maosAtivas && !sel && !foco && modo === 'ver' && agora - ultimoMouse > 4000) rotYA += .0025;
    for (const p of pecas) p.position.copy(p.userData.base).addScaledVector(p.userData.dir, abrir * 1.25);
    raiz.rotation.set(rotX, rotY, 0); raiz.updateMatrixWorld(true);
    let alvoVista = new V3();
    if (foco && foco.length) { const b = new THREE.Box3(); foco.forEach(g => b.union(caixaMundo(g))); if (!b.isEmpty()) alvoVista = b.getCenter(new V3()); }
    focoAtual.lerp(alvoVista, .1);
    cam.position.set(focoAtual.x, focoAtual.y + 1.2 * Math.min(1, dist / 9), focoAtual.z + dist); cam.lookAt(focoAtual);
    cam.updateMatrixWorld(true);
    posicionarPlano(agora);
    ren.render(cena, cam);
    const s = sel ? `SELECIONADA: ${sel.userData.nome.toUpperCase()}` : mira ? `MIRA: ${mira.userData.nome.toUpperCase()}` : `PEÇAS ${pecas.filter(p => p.visible).length}`;
    hudEl.querySelector('.st').textContent = `${modo === 'desenho' ? `DESENHO · TRAÇOS ${tracos.length} · ` : ''}${s} · EXPLOSÃO ${Math.round(abrir * 100)}% · ZOOM ${(9 / dist).toFixed(2)}x${foco ? ' · FOCO' : ''}${camLigada ? ' · CÂMERA' : ''}`;
  }

  function ouvirSentidos(bracos) {
    if (!window.Sentidos) { dica.textContent = 'SEM CÂMERA: ARRASTE GIRA · CLIQUE SELECIONA · SHIFT+ARRASTE MOVE · RODA ZOOM/ESCALA · CTRL+Z DESFAZ'; return; }
    Sentidos.ligar({ maos: true, ...(bracos ? { bracos: true } : {}) }).then(s => {
      dica.textContent = s.erro ? 'SEM CÂMERA: ARRASTE GIRA · CLIQUE SELECIONA · SHIFT+ARRASTE MOVE · RODA ZOOM/ESCALA · CTRL+Z DESFAZ'
        : modo === 'desenho' ? 'INDICADOR ESTICADO DESENHA NA PROFUNDIDADE DO DEDO · PUNHO PARA · "DÁ VOLUME AO DESENHO"'
        : 'CHEGUE A MÃO PERTO DA CÂMERA PARA ENTRAR NA CENA · ENCOSTOU (ACENDE) + PINÇA = PEGA · PINÇA NO VAZIO: DIREITA GIRA, ESQUERDA ZOOM · DUAS MÃOS NA PEÇA ESCALAM · PUNHO SOLTA';
    });
    if (sairSentidos) sairSentidos();
    sairSentidos = Sentidos.assinar(q => { if (!vivo) return; ultimoQ = q; if (Sentidos.estado().computador) return; aplicarMaos(q); });
  }

  /* ── abrir / fechar ── */
  const BOTOES = [['DESFAZER', () => desfazer()], ['SOLTAR', () => selecionar(null)], ['MOSTRAR TUDO', () => editar([{ op: 'mostrar_tudo' }])],
    ['ABRIR PEÇAS', () => { guardar(); abrirAlvo = abrirAlvo > .5 ? 0 : 1; }],
    ['SEPARAR', () => sel && editar([{ op: 'separar', alvo: [pecas.indexOf(sel)], valor: 1.6 }])],
    ['SÓ ESSA', () => sel && editar([{ op: 'isolar', alvo: [pecas.indexOf(sel)] }])],
    ['ESCONDER', () => { if (sel) { guardar(); sel.visible = false; sel = null; pintar(); relatar(); } }],
    ['CÂMERA', () => camera(!camLigada, true)], ['CAPTURAR', () => capturar()],
    ['STL', () => falarJarvis('exporta em stl')], ['BLENDER', () => falarJarvis('abre no blender')], ['IMPRIMIR', () => falarJarvis('manda para impressão')],
    ['OLHAR', () => window.Sentidos && Sentidos.ligar({ olhar: !Sentidos.estado().olhar })]];
  function falarJarvis(t) { post('/hud/falar', { texto: t }); }
  function preparar() {
    if (ren) return;
    box.innerHTML = '<div class="hud"><div>HOLOGRAMA · J.A.I.M.E</div><b class="tt"></b><div class="st"></div><div class="maos"></div></div><div class="fechar" data-mao>FECHAR ✕</div>' +
      '<div class="ferramentas">' + BOTOES.map(([r], i) => `<span data-mao data-i="${i}">${r}</span>`).join('') + '</div><div class="dica"></div>';
    hudEl = box.querySelector('.hud'); maosEl = box.querySelector('.maos'); dica = box.querySelector('.dica'); box.querySelector('.fechar').onclick = fechar;
    box.querySelectorAll('.ferramentas span').forEach(s => s.onclick = () => BOTOES[+s.dataset.i][1]());
    iniciar3D();
  }
  function abrirHolo(d) {
    preparar();
    modo = d.modelo === 'desenho' ? 'desenho' : 'ver';
    titulo = String(d.titulo || d.modelo || '');
    hudEl.querySelector('.tt').textContent = titulo.toUpperCase();
    abrir = 0; abrirAlvo = 0; distA = 9; if (modo === 'desenho') { rotXA = 0; rotYA = 0; }
    for (const l of ['direita', 'esquerda']) Object.assign(estMao[l], novoEstado(), { s0: estMao[l].s0 });
    montar(d);
    box.classList.add('on'); box.classList.toggle('desenho', modo === 'desenho'); vivo = true;
    cancelAnimationFrame(loopId); quadro(); ouvirSentidos(); relatar();
  }
  function camera(ligar, bracos) {
    if (!vivo) abrirHolo({ modelo: 'vazio', titulo: 'VOCÊ NO HOLOGRAMA' });
    if (window.Sentidos && bracos) Sentidos.ligar({ maos: true, bracos: !!ligar });
    planoCamera(!!ligar);
  }
  function fechar() {
    if (!vivo && !ren) return;
    vivo = false; box.classList.remove('on');
    if (sairSentidos) { sairSentidos(); sairSentidos = null; }
    if (window.Sentidos) { const s = Sentidos.estado(); Sentidos.desligar({ maos: !!s.computador, bracos: false }); }
    planoCamera(false);
    for (const k of Object.keys(visual)) { cena.remove(visual[k].g); delete visual[k]; }
    if (ren) { ren.dispose(); ren.domElement.remove(); ren = null; }
    post('/jarvis/holograma/fechado', {});
  }
  window.Holograma = {
    abrir: abrirHolo, fechar, aberto: () => vivo, editar, desfazer, exportar, camera, capturar,
    desenho: d => abrirHolo({ ...d, modelo: 'desenho', titulo: d.titulo || 'DESENHO' }),
    _estado: () => ({ pecas: pecas.length, visiveis: pecas.filter(p => p.visible).length, abrir: +abrir.toFixed(2), abrirAlvo: +abrirAlvo.toFixed(2), dist: +distA.toFixed(2),
      rotY: +rotYA.toFixed(2), rotX: +rotXA.toFixed(2), maos: maosAtivas, sel: sel ? sel.userData.nome : null, mira: mira ? mira.userData.nome : null,
      tracos: tracos.length, pilha: pilha.length, modo, nomes: pecas.map(p => p.userData.nome), foco: foco ? foco.map(g => g.userData.nome) : null, camera: camLigada,
      raio: +raioModelo.toFixed(2),
      maosEstado: Object.fromEntries(['direita', 'esquerda'].map(l => [l, { s0: estMao[l].s0, pinca: estMao[l].pinca, alvo: estMao[l].alvo && estMao[l].alvo.userData.nome, toque: estMao[l].toque && estMao[l].toque.userData.nome, cena: !!estMao[l].cenaRef }])) }),
    _peca: i => { const g = pecas[i]; return g && { base: g.userData.base.toArray(), q: g.quaternion.toArray(), s: g.scale.toArray(), v: g.visible, cor: g.userData.cor }; },
    _explodir: v => abrirAlvo = v, _gesto: aplicarGesto, _maos: aplicarMaos, _selecionar: i => selecionar(pecas[i] || null), _malhas: malhas,
    _pecaEm: (x, y) => { const g = pecaEm(x, y); return g && g.userData.nome; },
    _centroTela: nome => { const g = pecas.find(p => p.userData.nome === nome); if (!g) return null; raiz.updateMatrixWorld(true);
      const c = caixaMundo(g).getCenter(new V3()), dd = c.distanceTo(cam.position), n = c.clone().project(cam); return { x: (n.x + 1) / 2, y: (1 - n.y) / 2, dist: dd }; },
    _tela: nome => { const g = pecas.find(p => p.userData.nome === nome); if (!g) return null; raiz.updateMatrixWorld(true);
      const c = g.userData.caixa.getCenter(new V3()).applyMatrix4(g.matrixWorld).project(cam); return { x: (c.x + 1) / 2, y: (1 - c.y) / 2 }; },
  };
})();
