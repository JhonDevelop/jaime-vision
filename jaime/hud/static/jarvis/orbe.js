/* Orbe do J.A.I.M.E — dois estilos dos vídeos:
   'fios'       : ~16 laços de luz ciano, cada um num plano inclinado que gira, ondulando (vídeo do bom dia);
   'particulas' : nuvem de pontos numa esfera que se deforma com a voz (vídeo da esfera de partículas).
   A voz manda na energia: Orbe.nivel(0..1) a cada evento de áudio; Orbe.falando(true/false). */
(function () {
  const cv = document.getElementById('orbe'), cx = cv.getContext('2d');
  let W = 0, H = 0, DPR = 1, t = 0, nivel = 0, alvo = 0, falando = false, estilo = 'fios', energia = 0.3;
  function tam() { DPR = Math.min(2, window.devicePixelRatio || 1); W = innerWidth; H = innerHeight; cv.width = W * DPR; cv.height = H * DPR; cx.setTransform(DPR, 0, 0, DPR, 0, 0); }
  addEventListener('resize', tam); tam();
  const rnd = (a, b) => a + Math.random() * (b - a);
  const LACOS = Array.from({ length: 17 }, (_, i) => ({
    rx: rnd(-1.2, 1.2), ry: rnd(0, Math.PI * 2), rz: rnd(0, Math.PI * 2),
    vx: rnd(-.0022, .0022), vy: rnd(.0015, .004) * (i % 2 ? 1 : -1), vz: rnd(-.002, .002),
    esc: rnd(.86, 1.06), k1: 2 + (i % 4), k2: 3 + ((i * 7) % 5), f1: rnd(0, 6.28), f2: rnd(0, 6.28),
    a1: rnd(.025, .06), a2: rnd(.012, .035), w: rnd(.6, 1.4), alfa: rnd(.28, .7), larg: rnd(.7, 1.6),
  }));
  const FAISCAS = Array.from({ length: 26 }, () => ({ laco: (Math.random() * 17) | 0, th: rnd(0, 6.28), v: rnd(.006, .018) }));
  const N_PART = 4200, PART = [];
  for (let i = 0; i < N_PART; i++) {            // esfera de Fibonacci: pontos bem espalhados
    const y = 1 - (i / (N_PART - 1)) * 2, r = Math.sqrt(1 - y * y), th = i * 2.399963;
    PART.push([Math.cos(th) * r, y, Math.sin(th) * r, rnd(.4, 1)]);
  }
  function rot(p, ax, ay, az) {
    let [x, y, z] = p, c, s;
    c = Math.cos(ax); s = Math.sin(ax); [y, z] = [y * c - z * s, y * s + z * c];
    c = Math.cos(ay); s = Math.sin(ay); [x, z] = [x * c + z * s, -x * s + z * c];
    c = Math.cos(az); s = Math.sin(az); [x, y] = [x * c - y * s, x * s + y * c];
    return [x, y, z];
  }
  const centro = () => [W * 0.5, H * 0.48];
  function ruido(x, y, z, tt) {
    return Math.sin(x * 3.1 + tt * 1.3) * Math.sin(y * 2.7 - tt) * .5 + Math.sin(z * 4.2 + tt * .7) * .3 + Math.sin((x + y + z) * 5 + tt * 2.1) * .2;
  }
  function pontoDoLaco(L, th, R, amp) {
    const r = R * L.esc * (1 + (L.a1 * Math.sin(L.k1 * th + L.f1 + t * L.w) + L.a2 * Math.sin(L.k2 * th + L.f2 - t * L.w * 1.3)) * amp);
    return rot([Math.cos(th) * r, Math.sin(th) * r, 0], L.rx, L.ry, L.rz);
  }
  function desenharFios(R) {
    const [ox, oy] = centro(), amp = 1 + energia * 3.2;
    const g = cx.createRadialGradient(ox, oy, R * .1, ox, oy, R * 1.35);
    g.addColorStop(0, `rgba(40,120,255,${.10 + energia * .12})`); g.addColorStop(.6, 'rgba(20,70,200,.06)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    cx.fillStyle = g; cx.beginPath(); cx.arc(ox, oy, R * 1.4, 0, 6.283); cx.fill();
    cx.globalCompositeOperation = 'lighter';
    cx.shadowColor = 'rgba(90,190,255,.9)'; cx.shadowBlur = 10 + energia * 14;
    for (const L of LACOS) {
      L.rx += L.vx * (1 + energia * 2); L.ry += L.vy * (1 + energia * 2.5); L.rz += L.vz;
      cx.beginPath();
      for (let i = 0; i <= 120; i++) {
        const p = pontoDoLaco(L, i / 120 * 6.2832, R, amp), f = 1 + p[2] / (R * 6);
        const x = ox + p[0] * f, y = oy + p[1] * f;
        i ? cx.lineTo(x, y) : cx.moveTo(x, y);
      }
      cx.strokeStyle = `rgba(${110 + energia * 60 | 0},${195 + energia * 40 | 0},255,${L.alfa * (.55 + energia * .5)})`;
      cx.lineWidth = L.larg * (1 + energia * .6); cx.stroke();
    }
    cx.shadowBlur = 16;
    for (const F of FAISCAS) {
      F.th += F.v * (1 + energia * 3);
      const p = pontoDoLaco(LACOS[F.laco], F.th, R, amp);
      cx.fillStyle = 'rgba(200,240,255,.95)'; cx.beginPath(); cx.arc(ox + p[0], oy + p[1], 1.4 + energia * 1.2, 0, 6.283); cx.fill();
    }
    cx.shadowBlur = 0; cx.globalCompositeOperation = 'source-over';
  }
  let ang = 0;
  function desenharParticulas(R) {
    const [ox, oy] = centro();
    ang += .0025 + energia * .01;
    cx.globalCompositeOperation = 'lighter';
    for (const p of PART) {
      const d = 1 + .16 * ruido(p[0], p[1], p[2], t * .9) * (1 + energia * 2.5) + energia * .08 * Math.sin(t * 6 + p[1] * 8);
      const q = rot([p[0] * d, p[1] * d, p[2] * d], .35, ang, 0);
      const f = 1 / (1.9 - q[2] * .5), prof = (q[2] + 1) / 2;
      const a = Math.min(1, (.3 + prof * .85) * p[3]);
      cx.fillStyle = `rgba(${150 + prof * 90 | 0},${200 + prof * 50 | 0},255,${a})`;
      cx.fillRect(ox + q[0] * R * f * 1.1, oy + q[1] * R * f * 1.1, 1.5 + prof * 1.3, 1.5 + prof * 1.3);
    }
    cx.globalCompositeOperation = 'source-over';
  }
  function quadro() {
    t += 1 / 60;
    nivel += (alvo - nivel) * .18; alvo *= .93;
    const base = falando ? .38 + .12 * Math.sin(t * 5.3) : .16 + .05 * Math.sin(t * 1.2);
    energia += (Math.min(1, Math.max(base, nivel * 1.4)) - energia) * .08;
    cx.clearRect(0, 0, W, H);
    const R = Math.min(W, H) * (estilo === 'fios' ? .245 : .3);
    estilo === 'fios' ? desenharFios(R) : desenharParticulas(R);
    requestAnimationFrame(quadro);
  }
  requestAnimationFrame(quadro);
  window.Orbe = {
    nivel(v) { alvo = Math.max(alvo, +v || 0); },
    falando(b) { falando = !!b; },
    estilo(s) { estilo = s === 'particulas' ? 'particulas' : 'fios'; try { localStorage.setItem('orbe', estilo); } catch (e) {} },
    get estiloAtual() { return estilo; },
  };
  try { const s = localStorage.getItem('orbe'); if (s) window.Orbe.estilo(s); } catch (e) {}
})();
