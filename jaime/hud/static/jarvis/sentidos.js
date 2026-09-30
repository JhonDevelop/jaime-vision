/* Sentidos da tela Jarvis: UMA câmera para as mãos (MediaPipe Hand Landmarker) e o olhar (Face Landmarker + íris).
   Tudo roda no navegador desta máquina; nada de imagem sai daqui.

   Quem usa assina:  const sair = Sentidos.assinar(q => …)   q = { maos: [21 pontos]…, olhar: {x, y} | null, t }
   - holograma.js: mãos manipulam peças; o olhar mira a peça (parar o olhar ~0,9 s seleciona);
   - cursor da tela ("liga o controle por mão"): o indicador move o cursor; pinça rápida clica em controles marcados
     com data-mao; mão aberta parada 1,2 s fecha o que estiver aberto (holograma, cartões).
   Gesto NUNCA aprova nada: o cursor só clica em controles da própria tela; nada do Vigia tem data-mao.
   O olhar pela webcam é aproximado (íris + cabeça, calibrado olhando o centro 1 s) — serve para peças grandes. */
(function () {
  const est = { maos: false, olhar: false, tela: false, erro: '' };
  let video = null, vision = null, base = '', local = false, lmMao = null, lmRosto = null, rodando = false, ultimo = -1, n = 0;
  const assinantes = new Set();
  let olharSuave = null, calib = null, amostras = [], ultimoOlhar = null;
  const GANHO = { x: 3.2, y: 4.2 };
  const d2 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

  async function carregar() {
    if (vision) return vision;
    local = await fetch('/hud/jarvis/vendor/ok.json').then(r => r.ok).catch(() => false);
    base = local ? '/hud/jarvis/vendor/' : 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/';
    const v = await import(base + 'vision_bundle.mjs');
    vision = { v, fs: await v.FilesetResolver.forVisionTasks(base + 'wasm') };
    return vision;
  }
  async function criar(Classe, modelo, extra) {
    const op = d => ({ baseOptions: { modelAssetPath: modelo, delegate: d }, runningMode: 'VIDEO', ...extra });
    try { return await Classe.createFromOptions(vision.fs, op('GPU')); } catch (e) { return await Classe.createFromOptions(vision.fs, op('CPU')); }
  }
  async function modelo(nome, google) {
    const ok = local && await fetch('/hud/jarvis/vendor/' + nome, { method: 'HEAD' }).then(r => r.ok).catch(() => false);
    return ok ? '/hud/jarvis/vendor/' + nome : google;
  }
  async function camera() {
    if (video) return video;
    video = document.createElement('video'); video.autoplay = true; video.muted = true; video.playsInline = true; video.id = 'sentidosVideo';
    document.body.appendChild(video);
    video.srcObject = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    await video.play(); return video;
  }

  async function ligar(o) {
    Object.assign(est, o || {});
    atualizarCursor();
    try {
      await carregar(); await camera();
      if ((est.maos || est.tela) && !lmMao) lmMao = await criar(vision.v.HandLandmarker,
        await modelo('hand_landmarker.task', 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'), { numHands: 2 });
      if (est.olhar && !lmRosto) { lmRosto = await criar(vision.v.FaceLandmarker,
        await modelo('face_landmarker.task', 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'), { numFaces: 1 });
        calibrar(); }
      est.erro = '';
      if (!rodando) { rodando = true; requestAnimationFrame(quadro); }
    } catch (e) { est.erro = (e && e.message) || 'câmera indisponível'; console.warn('sentidos:', est.erro); }
    atualizarCursor(); return est;
  }
  function desligar(o) {
    Object.assign(est, o || { maos: false, olhar: false, tela: false });
    if (!est.maos && !est.olhar && !est.tela) {
      rodando = false;
      if (video && video.srcObject) video.srcObject.getTracks().forEach(t => t.stop());
      if (video) video.remove(); video = null;
    }
    atualizarCursor();
  }
  function calibrar() { calib = null; amostras = []; }

  /* ── olhar: íris dentro do olho + um pouco da cabeça; o centro é medido nos primeiros ~30 quadros ── */
  function olharDe(f) {
    if (!f || f.length < 478) return null;
    const h1 = (f[468].x - f[33].x) / ((f[133].x - f[33].x) || 1e-3), h2 = (f[473].x - f[362].x) / ((f[263].x - f[362].x) || 1e-3);
    const v1 = (f[468].y - f[159].y) / ((f[145].y - f[159].y) || 1e-3), v2 = (f[473].y - f[386].y) / ((f[374].y - f[386].y) || 1e-3);
    const olhos = d2(f[33], f[263]) || 1e-3, meio = { x: (f[33].x + f[263].x) / 2, y: (f[33].y + f[263].y) / 2 };
    const yaw = (f[1].x - meio.x) / olhos, pitch = (f[1].y - meio.y) / olhos;
    return { gx: (h1 + h2) / 2 + yaw * .9, gy: (v1 + v2) / 2 + pitch * .6 };
  }
  function olharNaTela(g) {
    if (!g) return null;
    if (!calib) {
      amostras.push(g);
      if (amostras.length >= 30) calib = { gx: amostras.reduce((s, a) => s + a.gx, 0) / amostras.length, gy: amostras.reduce((s, a) => s + a.gy, 0) / amostras.length };
      return null;
    }
    const alvo = { x: Math.max(0, Math.min(1, .5 - (g.gx - calib.gx) * GANHO.x)), y: Math.max(0, Math.min(1, .5 + (g.gy - calib.gy) * GANHO.y)) };
    olharSuave = olharSuave ? { x: olharSuave.x + (alvo.x - olharSuave.x) * .18, y: olharSuave.y + (alvo.y - olharSuave.y) * .18 } : alvo;
    return olharSuave;
  }

  function quadro() {
    if (!rodando) return;
    requestAnimationFrame(quadro);
    if (!video || video.readyState < 2 || video.currentTime === ultimo) return;
    ultimo = video.currentTime; n++;
    const t = performance.now();
    let maos = [];
    try { if (lmMao) maos = lmMao.detectForVideo(video, t).landmarks || []; } catch (e) { }
    if (lmRosto && est.olhar && n % 2 === 0) {
      try { const r = lmRosto.detectForVideo(video, t); ultimoOlhar = olharNaTela(olharDe((r.faceLandmarks || [])[0])); } catch (e) { }
    }
    publicar({ maos, olhar: est.olhar ? ultimoOlhar : null, t });
  }
  function publicar(q) {
    q.t = q.t || performance.now();
    desenharOlhar(q.olhar);
    cursorTela(q);
    for (const f of assinantes) { try { f(q); } catch (e) { console.warn(e); } }
  }

  /* ── cursor da tela toda ── */
  let cur = null, alvoOlho = null, pinca = null, palma = null;
  function atualizarCursor() {
    if (!cur) { cur = document.createElement('div'); cur.id = 'cursorMao'; document.body.appendChild(cur);
      alvoOlho = document.createElement('div'); alvoOlho.id = 'cursorOlhar'; document.body.appendChild(alvoOlho); }
    cur.style.display = est.tela ? 'block' : 'none';
    alvoOlho.style.display = est.olhar ? 'block' : 'none';
  }
  function desenharOlhar(o) { if (alvoOlho && o) { alvoOlho.style.left = o.x * innerWidth + 'px'; alvoOlho.style.top = o.y * innerHeight + 'px'; } }
  function aberta(h) { const p = h[0]; return [8, 12, 16, 20].every(i => d2(h[i], p) > d2(h[i - 2], p) * 1.15); }
  function cursorTela(q) {
    if (!est.tela || !cur) return;
    if (window.Holograma && Holograma.aberto && Holograma.aberto()) { cur.classList.add('oculto'); return; }   // lá dentro a mão é do holograma
    cur.classList.remove('oculto');
    const h = (q.maos || [])[0];
    if (!h) { pinca = null; palma = null; return; }
    const x = (1 - h[8].x) * innerWidth, y = h[8].y * innerHeight;             // espelhado: mão direita → direita
    cur.style.left = x + 'px'; cur.style.top = y + 'px';
    const fechando = d2(h[4], h[8]) < .045;
    cur.classList.toggle('pinca', fechando);
    if (fechando && !pinca) pinca = { t: q.t, x, y, p: h[9] };
    if (!fechando && pinca) {           // clique onde a pinça fechou; a palma (não a ponta do dedo) mede se a mão andou
      if (q.t - pinca.t < 450 && d2(h[9], pinca.p) < .04) clicar(pinca.x, pinca.y);
      pinca = null;
    }
    if (aberta(h) && !fechando) {
      const c = h[9];
      if (!palma || d2(c, palma.c) > .04) palma = { c, t: q.t };
      else if (q.t - palma.t > 1200) { palma = { c, t: q.t + 1e9 }; fecharTudo(); }
    } else palma = null;
  }
  function clicar(x, y) {
    const el = document.elementFromPoint(x, y), alvo = el && el.closest('[data-mao]');
    cur.classList.add('clique'); setTimeout(() => cur.classList.remove('clique'), 250);
    if (alvo) alvo.click();
  }
  function fecharTudo() { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })); }

  window.Sentidos = {
    ligar, desligar, calibrar, estado: () => ({ ...est, calibrado: !!calib }),
    assinar(f) { assinantes.add(f); return () => assinantes.delete(f); },
    _publicar: publicar, _olharDe: olharDe, _olharNaTela: olharNaTela,
  };
})();
