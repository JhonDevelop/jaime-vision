/* Camada espacial do cockpit — objetos virtuais, mão rastreada, seleção e kill switch.
 *
 * Inerte com JAIME_SPATIAL=off: só se instala quando /espacial/estado diz que o serviço existe ou quando chega
 * o primeiro evento `espacial` pelo /hud/stream. Não mexe no canvas do cockpit: desenha num canvas próprio,
 * por cima, com pointer-events desligado (o mouse continua do cockpit).
 *
 * Medição: cada evento traz `wall_ms` (relógio do servidor na captura do frame). Ao desenhar, anotamos
 * Date.now() − wall_ms e mandamos em lote para /espacial/latencia — é o p95 captura→HUD do relatório. */
(function () {
  'use strict';
  const S = { on: false, cena: { objetos: [], selecionado: {} }, maos: [], estado: {}, flash: {}, lat: [], ultimo: 0 };
  let cv, ctx, chip, dpr = 1;

  function instalar() {
    if (cv) return;
    cv = document.createElement('canvas');
    cv.id = 'espacial';
    cv.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;z-index:14;pointer-events:none';
    document.body.appendChild(cv);
    ctx = cv.getContext('2d');
    chip = document.createElement('div');
    chip.className = 'chip btn';
    chip.title = 'rastreamento de mãos — clique ou tecle X para desligar';
    chip.style.cssText = 'position:fixed;right:16px;bottom:14px;z-index:21';
    chip.onclick = alternar;
    document.body.appendChild(chip);
    addEventListener('resize', medir); medir();
    addEventListener('keydown', e => {
      if (document.activeElement && document.activeElement.id === 'kbIn') return;
      if ((e.key === 'x' || e.key === 'X') && !e.metaKey && !e.ctrlKey && !e.altKey && S.estado.rodando) { e.preventDefault(); desligar(); }
    });
    setInterval(enviarLatencia, 5000);
    requestAnimationFrame(desenhar);
    S.on = true; atualizarChip();
  }

  function medir() { dpr = window.devicePixelRatio || 1; cv.width = innerWidth * dpr; cv.height = innerHeight * dpr; }

  async function desligar() {
    try { S.estado = await (await fetch('/espacial/desligar', { method: 'POST' })).json(); } catch (e) {}
    S.maos = []; atualizarChip();
  }
  async function alternar() {
    if (S.estado.rodando) return desligar();
    try { const r = await fetch('/espacial/ligar', { method: 'POST' }); if (r.ok) S.estado = await r.json(); } catch (e) {}
    atualizarChip();
  }
  function atualizarChip() {
    if (!chip) return;
    const e = S.estado || {};
    const m = e.metricas || {};
    const txt = e.rodando ? `✋ ${e.modo}${e.dry_run ? ' · dry-run' : ''}${m.fps ? ' · ' + m.fps + ' fps' : ''}`
      : e.suspenso ? `✋ suspenso: ${e.suspenso}` : e.erro ? `✋ erro: ${String(e.erro).slice(0, 48)}` : '✋ desligado';
    chip.innerHTML = `<u>X</u>${txt}`;
    chip.classList.toggle('on', !!e.rodando);
  }

  function evento(e) {
    if (!S.on) instalar();
    const k = e.evento;
    if (e.wall_ms) S.lat.push(Date.now() - e.wall_ms);
    if (S.lat.length > 600) S.lat.splice(0, S.lat.length - 600);
    switch (k) {
      case 'spatial.scene': S.cena = { objetos: e.objetos || [], selecionado: e.selecionado || {} }; break;
      case 'spatial.estado': Object.assign(S.estado, e); atualizarChip(); break;
      case 'spatial.cursor': S.maos = e.maos || []; S.ultimo = performance.now(); break;
      case 'spatial.select': S.cena.selecionado[e.actor] = e.object_id; pisca(e.object_id, '#38e1ff'); rac('seleção', rotulo(e.object_id)); break;
      case 'spatial.deselect': delete S.cena.selecionado[e.actor]; break;
      case 'gesture.drag': case 'gesture.scale': case 'gesture.grab': moverObj(e); if (k === 'gesture.grab') pisca(e.object_id, '#ffb347'); break;
      case 'gesture.click': pisca(e.object_id, '#49e6a0'); break;
      case 'gesture.cancel': case 'spatial.tracking_lost': moverObj(e); pisca(e.object_id, '#ff5c72'); if (k === 'spatial.tracking_lost') rac('mão perdida', (e.data && e.data.reason) || ''); break;
      case 'spatial.object': if (e.obj_novo) { S.cena.objetos = S.cena.objetos.filter(o => o.id !== e.obj_novo.id).concat([e.obj_novo]); } break;
      case 'spatial.removed': S.cena.objetos = S.cena.objetos.filter(o => o.id !== e.object_id); break;
      case 'voice.reference':
        (e.objetos || []).forEach(id => pisca(id, e.status === 'ok' ? '#49e6a0' : '#ffb347'));
        rac('isso =', e.status === 'ok' ? (e.objetos || []).map(rotulo).join(' + ') : (e.pergunta || e.status)); break;
      case 'action.preview': case 'action.receipt': case 'action.undo': case 'action.denied':
        rac(k.replace('action.', 'ação '), (e.resumo || e.motivo || '').slice(0, 90)); pisca(e.object_id, k === 'action.denied' ? '#ff5c72' : '#ffb347'); break;
    }
  }

  function rac(a, b) { // reaproveita o painel de raciocínio do cockpit, se existir
    try { if (typeof window.rac === 'function') window.rac(a, b); } catch (e) {}
  }
  function rotulo(id) { const o = S.cena.objetos.find(o => o.id === id); return o ? (o.label || o.id) : (id || ''); }
  function pisca(id, cor) { if (id) S.flash[id] = { cor, ate: performance.now() + 450 }; }
  function moverObj(e) {
    const o = S.cena.objetos.find(o => o.id === e.object_id);
    if (o && e.obj) { o.pos = e.obj.pos; o.scale = e.obj.scale; }
  }

  function desenhar(t) {
    requestAnimationFrame(desenhar);
    if (!ctx) return;
    const W = cv.width, H = cv.height;
    ctx.clearRect(0, 0, W, H);
    if (!S.estado.rodando && !S.cena.objetos.length) return;
    const sel = new Set(Object.values(S.cena.selecionado || {}));
    ctx.font = `${11 * dpr}px monospace`; ctx.textAlign = 'center';
    for (const o of S.cena.objetos) {
      const x = o.pos[0] * W, y = o.pos[1] * H, r = (o.radius || 0.06) * (o.scale || 1) * Math.min(W, H);
      const f = S.flash[o.id]; const quente = f && f.ate > t;
      const hover = S.maos.some(m => m.alvo === o.id);
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = o.kind === 'lixeira' ? 'rgba(255,92,114,.08)' : 'rgba(56,225,255,.07)'; ctx.fill();
      ctx.lineWidth = (sel.has(o.id) ? 2.5 : 1) * dpr;
      ctx.strokeStyle = quente ? f.cor : sel.has(o.id) ? '#38e1ff' : hover ? '#ffb347' : 'rgba(127,147,171,.55)';
      ctx.shadowColor = ctx.strokeStyle; ctx.shadowBlur = (quente || sel.has(o.id)) ? 18 * dpr : 0;
      ctx.stroke(); ctx.shadowBlur = 0;
      ctx.fillStyle = '#dfe9f5'; ctx.fillText(o.label || o.id, x, y + 4 * dpr);
      ctx.fillStyle = '#7f93ab'; ctx.fillText(o.kind, x, y + r + 13 * dpr);
    }
    const velho = performance.now() - S.ultimo > 400;   // sem cursor recente = mão fora do quadro
    if (velho) return;
    for (const m of S.maos) {
      ctx.strokeStyle = 'rgba(56,225,255,.35)'; ctx.lineWidth = 1 * dpr;
      const P = i => [m.lm[i][0] * W, m.lm[i][1] * H];
      for (const cadeia of [[0, 1, 2, 3, 4], [0, 5, 6, 7, 8], [5, 9, 13, 17], [9, 10, 11, 12], [13, 14, 15, 16], [0, 17, 18, 19, 20]]) {
        ctx.beginPath(); cadeia.forEach((i, j) => { const [x, y] = P(i); j ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke();
      }
      const x = m.x * W, y = m.y * H;
      const cor = m.estado === 'held' ? '#ffb347' : m.estado === 'candidate' ? '#7d5cff' : '#38e1ff';
      ctx.beginPath(); ctx.arc(x, y, (m.estado === 'held' ? 7 : 10) * dpr, 0, Math.PI * 2);
      ctx.strokeStyle = cor; ctx.lineWidth = 2 * dpr; ctx.shadowColor = cor; ctx.shadowBlur = 14 * dpr; ctx.stroke(); ctx.shadowBlur = 0;
    }
  }

  async function enviarLatencia() {
    if (!S.lat.length) return;
    const amostras = S.lat.splice(0, S.lat.length);
    try {
      await fetch('/espacial/latencia', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ amostras }) });
      const r = await fetch('/espacial/estado'); if (r.ok) { S.estado = await r.json(); atualizarChip(); }
    } catch (e) {}
  }

  window.JaimeEspacial = { evento, estado: S };
  (async () => {
    try {
      const r = await fetch('/espacial/estado'); if (!r.ok) return;
      const e = await r.json();
      if (!e.ativo) return;              // JAIME_SPATIAL=off: nada é instalado
      instalar(); S.estado = e; if (e.cena) S.cena = { objetos: e.cena.objetos || [], selecionado: e.cena.selecionado || {} };
      atualizarChip();
    } catch (e) {}
  })();
})();
