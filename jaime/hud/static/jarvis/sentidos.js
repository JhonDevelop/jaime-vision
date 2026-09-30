/* Sentidos da tela Jarvis: UMA câmera para as mãos (MediaPipe Hand Landmarker), os braços (Pose Landmarker, opcional)
   e o olhar (Face Landmarker + íris, opcional). Tudo roda no navegador desta máquina; nenhuma imagem sai daqui.

   Quem usa assina:  const sair = Sentidos.assinar(q => …)
     q = { maos: [[21 pontos {x,y,z}] …], lados: ['direita'|'esquerda' …], escalas: [tamanho da mão na imagem …],
           bracos: {direita: [ombro, cotovelo, punho], esquerda: […]} | null, olhar: {x, y} | null, t, video }
   - cada mão é INDIVIDUAL: lado vem do rastreador (imagem crua → a lateralidade do MediaPipe inverte) e, se ele se
     confundir, pela posição; cada mão tem o seu filtro One Euro (tira o tremor sem atrasar o movimento rápido);
   - "escala" = tamanho aparente da mão; mão mais perto da câmera = maior. O holograma usa isso como PROFUNDIDADE;
   - controle do computador ("liga o controle do computador"): os pontos crus vão por WebSocket ao servidor, que
     mexe o mouse de verdade (controle_maos.py). A aba precisa estar visível em algum monitor; escondida, o Safari
     para de processar — por isso existe o rastreador nativo (maos_nativo.py);
   - o olhar pela webcam é aproximado (íris + cabeça, calibrado olhando o centro 1 s). */
(function () {
  const est = { maos: false, olhar: false, computador: false, bracos: false, erro: '' };
  let video = null, vision = null, base = '', local = false, lmMao = null, lmRosto = null, lmPose = null, rodando = false, ultimo = -1, n = 0;
  const assinantes = new Set();
  let olharSuave = null, calib = null, amostras = [], ultimoOlhar = null, ultimosBracos = null, ws = null, wsVazioT = 0;
  const GANHO = { x: 3.2, y: 4.2 };
  const d2 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const GOOGLE = 'https://storage.googleapis.com/mediapipe-models/';

  /* ── One Euro por eixo (Casiez 2012): parado filtra forte, rápido filtra pouco ── */
  function OneEuro(minCut = 1.5, beta = 1.0, dCut = 1.0) {
    let x = null, dx = 0, t0 = null;
    const alfa = (c, dt) => 1 / (1 + 1 / (2 * Math.PI * c * dt));
    return (v, t) => {
      if (x === null || t0 === null || t <= t0) { x = v; t0 = t; dx = 0; return v; }
      const dt = (t - t0) / 1000; t0 = t;
      const ndx = (v - x) / dt; dx = dx + alfa(dCut, dt) * (ndx - dx);
      const c = minCut + beta * Math.abs(dx);
      x = x + alfa(c, dt) * (v - x); return x;
    };
  }
  const filtros = {};                                   // lado → 21×3 filtros
  function filtrar(lado, pts, t) {
    let f = filtros[lado];
    if (!f || (f.ult && d2(f.ult, pts[0]) > .25)) f = filtros[lado] = { e: pts.map(() => [OneEuro(), OneEuro(), OneEuro(1.0, .5)]) };
    f.ult = pts[0];
    return pts.map((p, i) => ({ x: f.e[i][0](p.x, t), y: f.e[i][1](p.y, t), z: f.e[i][2](p.z || 0, t) }));
  }
  const escala = h => (d2(h[0], h[5]) + d2(h[0], h[17]) + d2(h[5], h[17])) / 3;

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
    video.srcObject = await navigator.mediaDevices.getUserMedia({ video: { width: 960, height: 540 } });
    await video.play(); return video;
  }

  async function ligar(o) {
    Object.assign(est, o || {});
    if (est.computador) est.maos = true;
    painel();
    try {
      await carregar(); await camera();
      if (est.maos && !lmMao) lmMao = await criar(vision.v.HandLandmarker, await modelo('hand_landmarker.task',
        GOOGLE + 'hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'), { numHands: 2, minHandDetectionConfidence: .6, minTrackingConfidence: .6 });
      if (est.bracos && !lmPose) lmPose = await criar(vision.v.PoseLandmarker, await modelo('pose_landmarker_lite.task',
        GOOGLE + 'pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task'), { numPoses: 1 });
      if (est.olhar && !lmRosto) { lmRosto = await criar(vision.v.FaceLandmarker, await modelo('face_landmarker.task',
        GOOGLE + 'face_landmarker/face_landmarker/float16/1/face_landmarker.task'), { numFaces: 1 }); calibrar(); }
      est.erro = '';
      if (est.computador) abrirWS();
      if (!rodando) { rodando = true; agendar(); }
    } catch (e) { est.erro = (e && e.message) || 'câmera indisponível'; console.warn('sentidos:', est.erro); }
    painel(); return est;
  }
  function desligar(o) {
    Object.assign(est, o || { maos: false, olhar: false, computador: false, bracos: false });
    if (!est.computador && ws) { try { ws.close(); } catch (e) { } ws = null; }
    if (!est.bracos) ultimosBracos = null;
    if (!est.maos && !est.olhar && !est.computador && !est.bracos) {
      rodando = false;
      if (video && video.srcObject) video.srcObject.getTracks().forEach(t => t.stop());
      if (video) video.remove(); video = null;
    }
    painel();
  }
  function calibrar() { calib = null; amostras = []; }

  /* ── WebSocket do controle do computador ── */
  function abrirWS() {
    if (ws && ws.readyState <= 1) return;
    ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/jarvis/maos/ws');
    ws.onclose = () => { ws = null; if (est.computador) setTimeout(abrirWS, 1500); };
  }
  function enviar(maos, lados, t) {
    if (!est.computador || !ws || ws.readyState !== 1) return;
    if (!maos.length) { if (t - wsVazioT < 200) return; wsVazioT = t; }
    ws.send(JSON.stringify({ t, maos: maos.map((h, i) => ({ lado: lados[i], p: h.map(p => [+p.x.toFixed(4), +p.y.toFixed(4)]) })) }));
  }

  /* ── olhar ── */
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

  /* ── lateralidade: cada mão é uma ── */
  function lados(r) {
    const hs = r.landmarks || [], cats = r.handednesses || r.handedness || [];
    const out = hs.map((h, i) => { const c = (cats[i] || [])[0]; const nome = c && (c.categoryName || c.displayName || c.label);
      return nome === 'Left' ? 'direita' : nome === 'Right' ? 'esquerda' : null; });       // imagem crua: o rótulo vem invertido
    if (hs.length === 2 && (out[0] === out[1] || !out[0] || !out[1])) {
      const direitaPrimeiro = hs[0][0].x < hs[1][0].x;                                   // na imagem crua, a direita fica à esquerda
      return direitaPrimeiro ? ['direita', 'esquerda'] : ['esquerda', 'direita'];
    }
    return out.map(l => l || 'direita');
  }
  function bracosDe(r) {
    const p = (r.landmarks || [])[0]; if (!p) return null;
    const ok = i => p[i] && (p[i].visibility == null || p[i].visibility > .45);
    return { direita: [12, 14, 16].every(ok) ? [p[12], p[14], p[16]] : null, esquerda: [11, 13, 15].every(ok) ? [p[11], p[13], p[15]] : null };
  }

  function agendar() { if (!rodando) return; if (document.hidden) setTimeout(quadro, 33); else requestAnimationFrame(quadro); }
  function quadro() {
    if (!rodando) return;
    agendar();
    if (!video || video.readyState < 2 || video.currentTime === ultimo) return;
    ultimo = video.currentTime; n++;
    const t = performance.now();
    let maos = [], ls = [];
    try {
      if (lmMao) { const r = lmMao.detectForVideo(video, t); ls = lados(r); maos = r.landmarks || []; }
    } catch (e) { }
    enviar(maos, ls, t);                                           // cru: o servidor filtra o cursor do jeito dele
    const filtradas = maos.map((h, i) => filtrar(ls[i], h, t));
    if (lmPose && est.bracos && n % 2 === 0) { try { ultimosBracos = bracosDe(lmPose.detectForVideo(video, t)); } catch (e) { } }
    if (lmRosto && est.olhar && n % 2 === 1) {
      try { const r = lmRosto.detectForVideo(video, t); ultimoOlhar = olharNaTela(olharDe((r.faceLandmarks || [])[0])); } catch (e) { }
    }
    publicar({ maos: filtradas, lados: ls, escalas: filtradas.map(escala), bracos: est.bracos ? ultimosBracos : null,
               olhar: est.olhar ? ultimoOlhar : null, t, video });
  }
  function publicar(q) {
    q.t = q.t || performance.now();
    q.lados = q.lados || (q.maos || []).map((_, i) => i ? 'esquerda' : 'direita');
    q.escalas = q.escalas || (q.maos || []).map(escala);
    desenharOlhar(q.olhar);
    for (const f of assinantes) { try { f(q); } catch (e) { console.warn(e); } }
  }

  /* ── painel do controle do computador (estado vem do servidor: evento maos_so) ── */
  let chip = null, mapa = null, alvoOlho = null;
  function painel() {
    if (!chip) {
      chip = document.createElement('div'); chip.id = 'maosSO';
      chip.innerHTML = '<div class="tt">✋ COMPUTADOR</div><div class="mapa"><i></i></div><div class="tx"></div>'; document.body.appendChild(chip);
      mapa = chip.querySelector('.mapa i');
      alvoOlho = document.createElement('div'); alvoOlho.id = 'cursorOlhar'; document.body.appendChild(alvoOlho);
    }
    chip.style.display = est.computador ? 'block' : 'none';
    alvoOlho.style.display = est.olhar ? 'block' : 'none';
    if (est.erro && est.computador) chip.querySelector('.tx').textContent = 'câmera: ' + est.erro;
  }
  function estadoSO(e) {                                           // chamado pelo jarvis.js a cada evento maos_so
    if (!chip) painel();
    if (e.cursor && mapa) { mapa.style.left = e.cursor[0] * 100 + '%'; mapa.style.top = e.cursor[1] * 100 + '%'; mapa.classList.toggle('arrasta', !!e.arrastando); }
    if (e.ensaio != null) chip.classList.toggle('ensaio', !!e.ensaio);
    if (e.acao) { chip.classList.add('pisca'); setTimeout(() => chip.classList.remove('pisca'), 220); }
    if (e.texto) chip.querySelector('.tx').textContent = e.texto;
    if (e.ligado === false) { est.computador = false; if (ws) { try { ws.close(); } catch (x) { } ws = null; } painel(); }
    if (e.etapa != null) chip.classList.toggle('calibrando', e.etapa > 0);
  }
  function desenharOlhar(o) { if (alvoOlho && o) { alvoOlho.style.left = o.x * innerWidth + 'px'; alvoOlho.style.top = o.y * innerHeight + 'px'; } }

  window.Sentidos = {
    ligar, desligar, calibrar, estadoSO, estado: () => ({ ...est, calibrado: !!calib }), video: () => video,
    assinar(f) { assinantes.add(f); return () => assinantes.delete(f); },
    _publicar: publicar, _olharDe: olharDe, _olharNaTela: olharNaTela, _lados: lados, _escala: escala,
  };
})();
