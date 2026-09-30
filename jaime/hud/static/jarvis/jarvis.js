/* Tela Jarvis: escuta o /hud/stream e desenha as cenas dos vídeos.
   - briefing: card BRIEFING MATINAL no orbe → cada segmento vira um card no centro quando a VOZ começa aquela frase
     (evento `voz` com o texto) → o card anterior encolhe e encaixa na fileira embaixo do orbe;
   - monitor: câmera dentro do orbe, reconhecimento do rosto (face-api, nesta máquina), ícones holográficos com dados;
   - holograma: camada 3D verde controlada pela mão (holograma.js, carregado sob demanda);
   - painéis laterais: dados reais de /hud/sistemas (fila, filhos, estudo, orçamento, vontades, vigia). */
(function () {
  const $ = id => document.getElementById(id);
  const palco = $('palco');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = s => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
  const agora = () => performance.now();
  const post = (url, body) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json()).catch(() => ({}));

  /* ───────────── estado da voz ───────────── */
  let falando = false, estadoVoz = 'espera', ultimaVoz = -1e9, ultimaFalaEvento = -1e9;
  function rotulo() {
    const r = falando ? 'FALANDO' : estadoVoz === 'pensando' ? 'PENSANDO' : estadoVoz === 'ouvindo' ? 'OUVINDO' :
      estadoVoz === 'mudo' ? 'MUDO' : estadoVoz === 'erro' ? 'SEM MICROFONE' : 'EM ESPERA';
    $('rotEstado').textContent = r;
  }
  setInterval(() => { const d = new Date(); $('relogio').textContent = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }); }, 1000);

  /* onda de voz do painel */
  const onda = $('onda'), oc = onda.getContext('2d'), amostras = new Array(90).fill(0);
  let nivelAtual = 0;
  setInterval(() => {
    amostras.push(Math.max(nivelAtual, falando ? .12 + Math.random() * .2 : .02)); amostras.shift(); nivelAtual *= .7;
    const w = onda.width = onda.clientWidth * 2, h = onda.height = onda.clientHeight * 2;
    oc.clearRect(0, 0, w, h); oc.strokeStyle = '#6fdcff'; oc.shadowColor = '#39b6ff'; oc.shadowBlur = 8; oc.lineWidth = 2; oc.beginPath();
    amostras.forEach((v, i) => { const x = i / (amostras.length - 1) * w, y = h / 2 + Math.sin(i * .9) * v * h * .45; i ? oc.lineTo(x, y) : oc.moveTo(x, y); });
    oc.stroke();
  }, 60);

  /* ───────────── cards ───────────── */
  let principal = null; const doca = [];
  const LARG = { status: 21, clima: 19, agenda: 20, emails: 25, noticia: 23, saude: 21, foco: 22, bm: 27, html: 34 };
  const ICO = { status: '◎', clima: '☀', agenda: '▦', emails: '✉', noticia: '◧', saude: '♥', foco: '◆', bm: '◉', html: '▤' };
  function htmlCard(c) {
    const cab = (chips = '') => `<div class="cab"><div class="ico">${ICO[c.tipo] || '▣'}</div><div><div class="rot">${esc(c.rotulo)}</div><div class="tit">${esc(c.titulo)}</div></div>${chips}</div>`;
    switch (c.tipo) {
      case 'status':
        return `<div class="rot">${esc(c.rotulo)}</div><div class="tit">${esc(c.titulo)}</div><div class="sub">${esc(c.texto || '')}</div>` +
          (c.chips ? `<div class="chips">${c.chips.map(x => `<span class="chip">${esc(x)}</span>`).join('')}</div>` : '');
      case 'clima':
        return cab() + `<div class="clima-l"><div class="sol">☀</div><div><div class="t">${esc(c.temp)}°</div><div class="c">${esc(c.condicao)}</div></div></div>
          <div class="clima-g"><div><small>MÍNIMA</small>${esc(c.min)}°</div><div><small>MÁXIMA</small>${esc(c.max)}°</div><div><small>CHUVA</small>${esc(c.chuva)}</div></div>
          <div class="rodape"><span>OPEN-METEO</span><span>ATUALIZADO AGORA</span></div>`;
      case 'agenda':
        return cab('<div class="chips"><span class="chip">0 COMPROMISSOS</span></div>'.replace('0', (c.itens || []).length)) +
          (c.itens && c.itens.length ? `<div class="corpo">${c.itens.map(i => `<div class="item-mail"><div class="de">${esc(i.hora || '')}</div><div class="ac">${esc(i.titulo)}</div></div>`).join('')}</div>`
            : `<div class="vazio"><div class="cal">▦</div><b>${esc(c.vazio || 'Nenhum compromisso')}</b><small>${esc(c.sub || '')}</small></div>`) +
          `<div class="rodape"><span>GOOGLE AGENDA</span><span>HOJE</span></div>`;
      case 'emails':
        return cab(`<div class="chips"><span class="chip">${c.total} RECEBIDOS</span><span class="chip">${c.agir} PARA AGIR</span></div>`) +
          `<div class="linha-acao"><span class="ico" style="flex:0 0 18px;height:18px">✉</span><b>${c.agir}</b> mensagens precisam de ação</div>` +
          `<div class="corpo">${(c.itens || []).map(i => `<div class="item-mail"><div class="de">${esc(i.de)}</div><div class="ac">${esc(i.acao)}</div></div>`).join('')}</div>` +
          `<div class="rodape"><span>TRIAGEM DE RECEBIDOS</span><span>CONSULTE ITENS VERIFICADOS</span></div>`;
      case 'noticia':
        return cab() + (c.imagem ? `<div class="foto" style="background-image:url('${esc(c.imagem)}')"></div>` : '') +
          `<div class="manchete">${esc(c.manchete)}${c.fonte ? ' — ' + esc(c.fonte) : ''}</div><div class="rodape"><span>RADAR DE NOTÍCIAS</span><span>ABRIR MATÉRIA ↗</span></div>`;
      case 'saude':
        return cab(`<div class="chips"><span class="chip">${c.total} OBSERVAÇÕES</span></div>`) +
          `<div class="corpo">${(c.itens || []).map(i => `<div class="item-mail"><div class="ac">${esc(i)}</div></div>`).join('') || '<div class="vazio"><b>Sem observações</b></div>'}</div>`;
      case 'foco':
        return `<div class="cab"><div class="ico">◆</div><div><div class="rot">${esc(c.rotulo)}</div><div class="tit">${esc(c.titulo)}</div></div></div>`;
      case 'bm':
        return `<div class="rot">${esc(c.titulo)}</div><div class="grande" id="bmGrande"></div><div class="sub">${esc(c.texto)}</div>
          <div class="etapas">${c.etapas.map(e => `<span data-e="${esc(e)}">${esc(e)}</span>`).join('')}</div><div class="prog"><i id="bmProg"></i></div>`;
      case 'html':                               /* painel que o Jaime compôs na hora (evento `mostrar`) */
        return cab() + `<div class="corpo livre">${c.html || ''}</div>`;
    }
    return cab() + `<div class="corpo">${esc(c.texto || '')}</div>`;
  }
  function criar(c, classe) {
    const el = document.createElement('div');
    el.className = `card ${classe} ${c.tipo === 'bm' ? 'bm' : ''} ${['status', 'foco'].includes(c.tipo) ? 'status' : ''} ${c.alerta ? 'alerta' : ''} entrando`;
    el.innerHTML = htmlCard(c); el._c = c;
    if (c.link) el.onclick = () => window.open(c.link, '_blank', 'noopener');
    palco.appendChild(el); return el;
  }
  function posicionar() {
    const W = innerWidth, H = innerHeight;
    if (principal) {
      const c = principal._c, w = (LARG[c.tipo] || 26) * W / 100;
      const noOrbe = ['status', 'bm', 'foco'].includes(c.tipo);
      Object.assign(principal.style, { width: w + 'px', left: W / 2 + 'px', top: (noOrbe ? H * .48 : doca.length ? H * .37 : H * .45) + 'px', transform: 'translate(-50%,-50%)' });
    }
    const n = doca.length; if (!n) return;
    const gap = W * .007, largura = innerWidth > 900 ? W * .6 : W * .94, w = Math.min(W * .118, (largura - gap * (n - 1)) / n), total = n * w + (n - 1) * gap;
    doca.forEach((el, i) => Object.assign(el.style, { width: w + 'px', left: (W - total) / 2 + i * (w + gap) + w / 2 + 'px', top: H * (principal ? .775 : .7) + 'px', transform: 'translate(-50%,-50%)' }));
  }
  addEventListener('resize', posicionar);
  function mostrarPrincipal(c) {
    if (principal) {
      const p = principal._c;
      if (['status', 'bm', 'foco'].includes(p.tipo)) { const v = principal; v.classList.add('saindo'); setTimeout(() => v.remove(), 700); }
      else { principal.className = principal.className.replace('principal', 'doca'); doca.push(principal); }
    }
    principal = criar(c, 'principal'); posicionar(); ultimoCard = agora();
    requestAnimationFrame(() => requestAnimationFrame(() => principal && principal.classList.remove('entrando')));
    return principal;
  }
  function limparPalco() { palco.innerHTML = ''; principal = null; doca.length = 0; }
  // cartões não ficam para sempre: 75 s depois do último, sem fala e sem fila, a tela volta ao orbe limpo
  let ultimoCard = 0;
  setInterval(() => {
    if (!palco.children.length || agora() - ultimoCard < 75000 || (typeof fila !== 'undefined' && fila.length) || falando) return;
    [...palco.children].forEach(el => el.classList.add('saindo'));
    setTimeout(limparPalco, 700); ultimoCard = agora();
  }, 5000);
  function arrumarFinal() {                    // no fim: tudo enfileirado sob o orbe, sem card no centro
    if (principal && !['status', 'bm', 'foco'].includes(principal._c.tipo)) { principal.className = principal.className.replace('principal', 'doca'); doca.push(principal); }
    else if (principal) principal.remove();
    principal = null; posicionar();
  }

  /* efeito de digitação do card BRIEFING MATINAL */
  let digTimer = null;
  function digitar(txt) {
    const el = $('bmGrande'); if (!el) return; clearInterval(digTimer); let i = 0; el.textContent = '';
    digTimer = setInterval(() => { el.textContent = txt.slice(0, ++i); if (i >= txt.length) clearInterval(digTimer); }, 34);
  }

  /* ───────────── briefing sincronizado com a voz ───────────── */
  let fila = [], etapasOk = 0, totalEtapas = 5, ultimoMostrado = 0, fimPendente = false;
  function tentarMostrar(textoVoz) {
    if (!fila.length) return;
    const t = norm(textoVoz).slice(0, 36);
    let idx = -1;
    if (t) idx = fila.findIndex(s => norm(s.fala).includes(t));
    if (idx < 0) return;
    const [s] = fila.splice(0, idx + 1).slice(-1);           // o que ficou para trás é pulado (a voz já passou dele)
    exibir(s);
  }
  function exibir(s) {
    ultimoMostrado = agora();
    if (s.card && Object.keys(s.card).length) mostrarPrincipal(s.card);
    if (!fila.length && fimPendente) setTimeout(arrumarFinal, Math.max(3500, s.fala.length * 60));
  }
  setInterval(() => {                        // sem voz (canal de texto, TTS mudo): mostra pelo tempo estimado da fala
    if (!fila.length) return;
    const semVoz = agora() - ultimaVoz > 5000;
    const anterior = fila._anterior || '';
    if (semVoz && agora() - ultimoMostrado > Math.max(2500, anterior.length * 62)) { const s = fila.shift(); fila._anterior = s.fala; exibir(s); }
  }, 400);
  function briefing(e) {
    if (e.fase === 'inicio') {
      totalEtapas = (e.etapas || []).length || 5; etapasOk = 0;
      mostrarPrincipal({ tipo: 'bm', titulo: e.titulo || 'BRIEFING MATINAL', texto: e.texto || '', etapas: e.etapas || [] });
      digitar('Coletando sinais do dia...');
    } else if (e.fase === 'etapa') {
      const el = palco.querySelector(`.bm [data-e="${CSS.escape(e.etapa)}"]`); if (el) el.classList.add('ok');
      etapasOk++; const p = $('bmProg'); if (p) p.style.width = Math.min(100, etapasOk / totalEtapas * 100) + '%';
      if (e.etapa === 'E-MAILS') digitar('Filtrando e-mails importantes...');
    } else if (e.fase === 'radar') {
      digitar(e.texto || 'Atualizando o radar de notícias...');
    } else if (e.fase === 'segmento') {
      if (e.id === 'desvios') {                       // começo do briefing: o 1º card fica DENTRO do orbe
        limparPalco(); fila = []; fimPendente = false; ultimoMostrado = agora();
        mostrarPrincipal(e.card); return;
      }
      fila.push({ id: e.id, fala: e.fala, card: e.card });
      if (agora() - ultimaVoz < 1500 && ultimaTextoVoz) tentarMostrar(ultimaTextoVoz);
    } else if (e.fase === 'inicio_noticias') {
      limparPalco(); fila = []; fimPendente = false; ultimoMostrado = agora();
    } else if (e.fase === 'fim') {
      fimPendente = true; if (!fila.length) setTimeout(arrumarFinal, 4000);
    }
  }

  /* ───────────── monitor, rosto ───────────── */
  let stream = null, faceapi = null;
  let FACEAPI = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.15/dist/face-api.js';
  let MODELOS = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.15/model/';
  const local = fetch('/hud/jarvis/vendor/ok.json').then(r => r.ok).catch(() => false);   // bibliotecas guardadas nesta máquina?
  local.then(ok => { if (ok) { FACEAPI = '/hud/jarvis/vendor/face-api.js'; MODELOS = '/hud/jarvis/vendor/modelos/'; } window.JARVIS_VENDOR_LOCAL = ok; });
  function carregarScript(src) { return new Promise((ok, erro) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = erro; document.head.appendChild(s); }); }
  async function prepararFaceApi() {
    if (faceapi) return faceapi;
    await local;
    await carregarScript(FACEAPI); faceapi = window.faceapi;
    await Promise.all([faceapi.nets.tinyFaceDetector.loadFromUri(MODELOS), faceapi.nets.faceLandmark68Net.loadFromUri(MODELOS), faceapi.nets.faceRecognitionNet.loadFromUri(MODELOS)]);
    return faceapi;
  }
  async function abrirCamera() {
    if (stream) return stream;
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
    $('rostoVideo').srcObject = stream; await $('rostoVideo').play().catch(() => {}); return stream;
  }
  function fecharCamera() { if (stream) stream.getTracks().forEach(t => t.stop()); stream = null; $('rostoBox').classList.remove('on', 'ok'); $('rostoRot').classList.remove('on'); }
  async function descritores(n, prazoMs) {
    const fa = await prepararFaceApi(), v = $('rostoVideo'), out = [], fim = agora() + prazoMs;
    while (out.length < n && agora() < fim) {
      const r = await fa.detectSingleFace(v, new fa.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: .5 })).withFaceLandmarks().withFaceDescriptor();
      if (r) out.push(Array.from(r.descriptor));
      await new Promise(ok => setTimeout(ok, 250));
    }
    return out;
  }
  async function reconhecer() {
    $('rostoBox').classList.add('on'); $('rostoRot').textContent = 'RECONHECIMENTO FACIAL · ANALISANDO'; $('rostoRot').classList.add('on');
    try { await abrirCamera(); } catch (e) { $('rostoRot').textContent = 'CÂMERA INDISPONÍVEL'; return post('/jarvis/rosto/verificar', { status: 'sem_camera' }); }
    let d = [];
    try { d = await descritores(1, 7000); } catch (e) { d = []; }
    if (!d.length) return post('/jarvis/rosto/verificar', { status: 'sem_rosto' });
    return post('/jarvis/rosto/verificar', { descritor: d[0] });
  }
  async function identificar() {
    limparPalco(); await reconhecer(); setTimeout(fecharCamera, 5000);
  }
  async function cadastrar(n, nome) {
    $('rostoBox').classList.add('on'); $('rostoRot').textContent = nome ? 'APRENDENDO O ROSTO DE ' + String(nome).toUpperCase() : 'APRENDENDO O SEU ROSTO'; $('rostoRot').classList.add('on');
    try { await abrirCamera(); const d = await descritores(n || 5, 12000); if (d.length) await post('/jarvis/rosto/cadastrar', { descritores: d }); }
    catch (e) { $('rostoRot').textContent = 'CÂMERA INDISPONÍVEL'; }
    setTimeout(fecharCamera, 2500);
  }
  const ICONES = {
    passos: '<svg viewBox="0 0 64 64" fill="currentColor"><path d="M20 6c6 0 9 8 8 17-1 8-4 12-9 12s-7-6-7-13S14 6 20 6zm-7 33h13c1 6-1 13-7 13s-7-7-6-13zM44 16c6 0 8 8 7 16-1 7-3 11-8 11s-7-5-7-12 2-15 8-15zm-7 31h13c1 6-1 12-7 12s-7-6-6-12z"/></svg>',
    chama: '<svg viewBox="0 0 64 64" fill="currentColor"><path d="M32 4s18 14 18 32a18 18 0 0 1-36 0c0-9 5-15 9-19 0 6 3 10 7 11-2-10 2-18 2-24zm0 30s-8 6-8 13a8 8 0 0 0 16 0c0-7-8-13-8-13z"/></svg>',
    bateria: '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="4"><rect x="8" y="18" width="44" height="28" rx="5"/><path d="M52 27h5v10h-5"/><path d="M28 22l-6 12h10l-6 12" stroke-width="4"/></svg>',
  };
  function monitor(e) {
    if (e.fase === 'reconhecimento') { limparPalco(); reconhecer(); }
    else if (e.fase === 'identidade') {
      const ok = e.status === 'confirmado';
      $('rostoRot').textContent = ok ? 'IDENTIDADE CONFIRMADA' : e.status === 'desconhecido' ? 'ROSTO NÃO RECONHECIDO' : e.status === 'sem_cadastro' ? 'ROSTO SEM CADASTRO' : 'SEM RECONHECIMENTO';
      if (ok) $('rostoBox').classList.add('ok');
    } else if (e.fase === 'ativado') { $('rostoRot').textContent = 'MONITOR ATIVO'; }
    else if (e.fase === 'item') {
      document.body.classList.add('monitor-lado');
      const box = $('holo-icone'), cor = e.cor === 'verde' ? 'var(--verde)' : 'var(--laranja)';
      box.classList.remove('on');
      setTimeout(() => {
        box.style.color = cor;
        box.innerHTML = `<div class="plat b"></div><div class="plat"></div>${ICONES[e.icone] || ICONES.chama}` +
          (e.callouts || []).map((c, i) => `<div class="call" style="top:${14 + i * 22}%;color:${cor}"><span style="color:var(--texto-3)">${esc(c[0])}</span><b>${esc(c[1])}</b></div>`).join('');
        box.classList.add('on');
      }, 250);
    } else if (e.fase === 'fim') {
      setTimeout(() => { document.body.classList.remove('monitor-lado'); $('holo-icone').classList.remove('on'); fecharCamera(); }, 6000);
    }
  }

  /* ───────────── holograma ───────────── */
  async function holograma(e) {
    if (e.acao === 'fechar') { window.Holograma && Holograma.fechar(); return; }
    if (e.acao === 'exportado') { mostrarPrincipal({ tipo: 'status', rotulo: 'ARQUIVO 3D', titulo: Object.values(e.arquivos || {}).map(p => String(p).split('/').pop()).join(' · '), texto: 'Jaime/hologramas/exportados' }); return; }
    if (['editar', 'desfazer', 'exportar', 'capturar'].includes(e.acao) && !(window.Holograma && Holograma.aberto())) return;
    if (e.acao === 'editar') return Holograma.editar(e.ops);
    if (e.acao === 'desfazer') return Holograma.desfazer();
    if (e.acao === 'exportar') return Holograma.exportar();
    if (e.acao === 'capturar') return Holograma.capturar();
    if (!window.THREE) await carregarScript('/hud/vendor/three.min.js');
    if (!window.Holograma) await carregarScript('/hud/jarvis/holograma.js');
    if (e.acao === 'desenho') return Holograma.desenho(e);
    if (e.acao === 'camera') return Holograma.camera(!!e.ligar, !!e.bracos);
    if (e.acao === 'abrir') Holograma.abrir(e);
  }

  /* ───────────── sentinela (sistemas críticos) ───────────── */
  function sentinela(lista, mostrar) {
    if (!Array.isArray(lista)) return;
    $('sentN').textContent = lista.length ? `${lista.filter(a => a.ok).length}/${lista.length} NO AR` : '—';
    $('sentinela').innerHTML = lista.map(a => `<div class="linha"><span>${esc(a.nome)}</span><b style="color:${a.ok === false ? 'var(--vermelho)' : a.ok ? 'var(--verde)' : 'var(--texto-3)'}">${a.ok === false ? 'FORA' : a.ok ? (a.ms ?? '—') + ' ms' : '…'}</b></div>`).join('')
      || '<div class="linha"><span>nada vigiado</span></div>';
    if (mostrar) mostrarPrincipal({ tipo: 'status', rotulo: 'SENTINELA · SISTEMAS CRÍTICOS', titulo: lista.some(a => a.ok === false) ? 'Há sistema fora do ar' : 'Tudo no ar',
      texto: lista.map(a => `${a.nome}: ${a.ok === false ? 'fora' : a.ok ? (a.ms ?? '?') + ' ms · ' + (a.disponibilidade ?? '—') + '%' : 'checando'}`).join(' · '), alerta: lista.some(a => a.ok === false) });
  }
  setInterval(() => post('/jarvis/tela/viva', {}), 10000); setTimeout(() => post('/jarvis/tela/viva', {}), 500);   // "estou aberta"

  /* ───────────── painéis laterais (dados reais) ───────────── */
  function anel(id, v, txt) {
    const r = 15.5, c = 2 * Math.PI * r;
    $(id).innerHTML = `<svg viewBox="0 0 36 36"><circle cx="18" cy="18" r="${r}" fill="none" stroke="rgba(100,160,255,.18)" stroke-width="3"/>
      <circle cx="18" cy="18" r="${r}" fill="none" stroke="#6fdcff" stroke-width="3" stroke-dasharray="${c * Math.min(1, v)} ${c}" stroke-linecap="round"/></svg><span>${esc(txt)}</span>`;
  }
  async function sistemas() {
    try {
      const s = await (await fetch('/hud/sistemas')).json();
      const f = s.fila || {}, eq = s.equipe || [], est = s.estudo || {}, orc = s.orcamento || {}, von = (s.vontades || {}).niveis || {};
      anel('anelFila', (f.itens || []).length / 5, (f.itens || []).length); anel('anelEquipe', eq.length / 6, eq.length); anel('anelEstudo', (est.abertos || 0) / 5, est.abertos || 0);
      $('orcRot').textContent = orc.ativo ? 'COM TETO' : 'SEM TETO'; $('orcGasto').textContent = 'US$ ' + (orc.total || 0).toFixed(2);
      $('orcBar').style.width = orc.teto ? Math.min(100, (orc.total || 0) / orc.teto * 100) + '%' : '8%';
      $('humor').textContent = (s.humor || {}).rotulo || '—';
      $('vontades').innerHTML = Object.entries(von).slice(0, 6).map(([k, v]) => `<div class="linha"><span>${esc(k)}</span><b>${Math.round(v * 100)}%</b></div><div class="barra"><i style="width:${v * 100}%"></i></div>`).join('');
      $('vontEsc').textContent = (((s.vontades || {}).escolha || {}).atividade || '—').toUpperCase();
      $('equipe').innerHTML = eq.slice(0, 5).map(e => `<div class="linha"><span>${esc(e.nome)}</span><b>${esc(e.estado)}</b></div>`).join('') || '<div class="linha"><span>nenhum filho</span></div>';
      $('equipeN').textContent = eq.length; const v = s.vigia || {};
      $('vigiaLote').textContent = (v.lote || []).length; $('vigiaEst').textContent = v.armado ? 'ARMADO' : 'VIGIANDO';
      $('proximos').innerHTML = esc(s.proximos || '—').split('\n').slice(0, 4).join('<br>');
      $('acesso').textContent = (s.cerebro || {}).trancado ? 'TRANCADO' : 'LIBERADO';
      const o = s.ouvido || {}; $('vozEst').textContent = o.erro ? 'ERRO' : (o.modo || '—').toUpperCase();
      if (o.latencia_mediana_ms) $('lat').textContent = o.latencia_mediana_ms + ' ms';
      if (s.hermes) $('hermesEst').textContent = s.hermes;
      if (s.sentinela) sentinela(s.sentinela, false);
    } catch (e) {}
  }
  sistemas(); setInterval(sistemas, 10000);

  /* ───────────── barramento ───────────── */
  let ultimaTextoVoz = '';
  function evento(e) {
    switch (e.tipo) {
      case 'voz':
        if (e.estado) estadoVoz = e.estado; if (e.falando != null) { falando = !!e.falando; Orbe.falando(falando); }
        if (e.nivel != null) { Orbe.nivel(e.nivel); nivelAtual = Math.max(nivelAtual, e.nivel); }
        if (e.falando && e.texto) { ultimaVoz = agora(); ultimaTextoVoz = e.texto; tentarMostrar(e.texto); $('legenda').textContent = e.texto; }
        rotulo(); break;
      case 'escuta': if (e.nivel != null) { nivelAtual = Math.max(nivelAtual, e.nivel); if (!falando) Orbe.nivel(e.nivel * .5); } break;
      case 'fala': $('ultimaFala').textContent = (e.texto || '').slice(-220); ultimaFalaEvento = agora(); break;
      case 'raciocinio': case 'cortex': estadoVoz = 'pensando'; rotulo(); break;
      case 'fala_fim': if (estadoVoz === 'pensando') estadoVoz = 'ouvindo'; rotulo(); break;
      case 'modelo': if (e.modelo) $('modelo').textContent = String(e.modelo).replace('claude-', ''); break;
      case 'acesso': case 'estado': if (e.liberado != null) $('acesso').textContent = e.liberado ? 'LIBERADO' : 'TRANCADO'; break;
      case 'briefing': briefing(e); break;
      case 'monitor': monitor(e); break;
      case 'rosto':
        if (e.acao === 'cadastrar') cadastrar(e.amostras, e.nome);
        else if (e.acao === 'identificar') identificar();
        else if (e.acao === 'cadastrado') $('rostoRot').textContent = e.nome ? 'ROSTO DE ' + String(e.nome).toUpperCase() + ' APRENDIDO' : 'ROSTO APRENDIDO';
        else if (e.acao === 'resultado' && e.nome && e.status === 'conhecido') { $('rostoRot').textContent = 'IDENTIFICADO · ' + String(e.nome).toUpperCase(); $('rostoBox').classList.add('ok'); }
        else if (e.acao === 'resultado' && e.status === 'confirmado') { $('rostoRot').textContent = 'IDENTIDADE CONFIRMADA'; $('rostoBox').classList.add('ok'); }
        break;
      case 'holograma':
        if (e.acao === 'montando') { mostrarPrincipal({ tipo: 'status', rotulo: 'HOLOGRAMA · GERANDO', titulo: `Montando ${e.titulo || ''}`, texto: 'Descrevendo as peças e as proporções…' }); break; }
        if (e.acao === 'abrir' && principal && principal._c.rotulo === 'HOLOGRAMA · GERANDO') { principal.remove(); principal = null; }
        holograma(e); break;
      case 'sentinela':
        if (e.estado) sentinela(e.estado, !!e.mostrar);
        if (e.tipo === 'caiu' || e.tipo === 'voltou') mostrarPrincipal({ tipo: 'status', rotulo: 'SENTINELA · ALERTA', titulo: e.texto, alerta: e.tipo === 'caiu' });
        break;
      case 'orbe': Orbe.estilo(e.estilo); break;
      case 'cartao': if (e.card) mostrarPrincipal(e.card); break;
      case 'mostrar':                            /* painel composto na hora: aparece AQUI também, não só no cockpit */
        if (e.html) mostrarPrincipal({ tipo: 'html', rotulo: 'PAINEL', titulo: e.titulo || 'J.A.I.M.E',
                                        html: String(e.html).replace(/<\/?script[^>]*>/gi, '') });
        break;
      case 'fechar': limparPalco(); break;       /* quem abriu fecha */
      case 'sentidos':
        if (!window.Sentidos) break;
        if (e.computador === false) Sentidos.desligar({ computador: false, maos: !!(window.Holograma && Holograma.aberto()) });
        if (e.olhar === false) Sentidos.desligar({ olhar: false });
        if (e.computador === true) Sentidos.ligar({ computador: true, maos: true });
        if (e.olhar === true) { Sentidos.ligar({ olhar: true }); Sentidos.calibrar(); }
        $('btMao').classList.toggle('ativo', !!Sentidos.estado().computador);
        break;
      case 'maos_so': if (window.Sentidos) Sentidos.estadoSO(e); break;
    }
  }
  // O servidor reenvia os últimos 60 eventos a CADA conexão; o EventSource reconecta sozinho (sono do Mac, rede,
  // reinício). Sem este corte, cada reconexão reencenava o briefing inteiro — as notícias "em sequência para sempre".
  let visto = 0;
  function sse() {
    const es = new EventSource('/hud/stream');
    let corte = visto || (Date.now() / 1000 - 5);
    es.onmessage = ev => { let e; try { e = JSON.parse(ev.data); } catch (x) { return; }
      const t = e.t || 0;
      if (t <= corte) { if (!visto && ['voz', 'modelo', 'acesso', 'estado'].includes(e.tipo)) evento(e); return; }   // já passou: não reencena
      if (t > visto) visto = t;
      evento(e); };
    es.onerror = () => { corte = visto || corte; };
  }
  sse(); rotulo();
  window.JarvisTela = { evento };                 // para testes e para outras telas

  /* ───────────── controles ───────────── */
  const falar = texto => post('/hud/falar', { texto });
  window.JarvisFalar = falar;
  document.querySelectorAll('#baixo .mini, #mic').forEach(b => b.setAttribute('data-mao', ''));    // a mão pode clicar nos controles da tela
  $('btBriefing').onclick = () => falar('me dá o briefing');
  $('btMonitor').onclick = () => falar('ativar monitor');
  $('btDesenho').onclick = () => falar('quero desenhar');
  $('btMao').onclick = () => { const on = !(window.Sentidos && Sentidos.estado().computador); falar(on ? 'liga o controle do computador' : 'desliga o controle do computador'); };
  $('btOrbe').onclick = () => Orbe.estilo(Orbe.estiloAtual === 'fios' ? 'particulas' : 'fios');
  let mudo = false;
  $('mic').onclick = async () => { mudo = !mudo; $('mic').classList.toggle('mudo', mudo); await post('/hud/voz', { ativa: !mudo }); };
  const entrada = $('entrada'), tx = $('entradaTx');
  const teclado = on => { entrada.style.display = on ? 'block' : 'none'; if (on) tx.focus(); };
  $('btTeclado').onclick = () => teclado(entrada.style.display !== 'block');
  addEventListener('keydown', ev => {
    if (ev.key === '/' && document.activeElement !== tx) { ev.preventDefault(); teclado(true); }
    else if (ev.key === 'Escape') teclado(false);
    else if (ev.key.toLowerCase() === 'l' && document.activeElement !== tx) $('legenda').classList.toggle('on');
  });
  tx.addEventListener('keydown', ev => { if (ev.key === 'Enter' && tx.value.trim()) { falar(tx.value.trim()); tx.value = ''; teclado(false); } });
})();
