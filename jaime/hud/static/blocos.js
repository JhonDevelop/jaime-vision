/* Blocos no cockpit — o cockpit é só MAIS UMA superfície do protocolo JBP (/blocos/ws), igual aos óculos,
 * ao terminal e à janela nativa. Nada aqui sabe de finanças ou agenda: desenha o que chega, por tipo.
 *
 * Desenho: lâminas translúcidas com um trilho de luz à esquerda (cor = estado/prioridade) e cantos de mira em
 * vez de moldura — instrumento de HUD, não cartão de site. Arrasta pela cabeça, fecha no ×, lê em voz no ◉.
 * Teclado: K abre o seletor de blocos; com um bloco focado, Delete fecha e L lê. */
(function () {
  'use strict';
  const S = { ws: null, blocos: new Map(), tentativa: 0, z: 30 };
  const PERFIL = window.JAIME_PERFIL || 'cockpit';           // /blocos/leve?perfil=oculos usa a mesma lâmina, empilhada
  const COR = { 0: '#3a5068', 1: '#38e1ff', 2: '#ffb347', 3: '#ff5c72' };
  const ESTADO = { ok: '#49e6a0', atencao: '#ffb347', ruim: '#ff5c72' };
  const reduz = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const css = document.createElement('style');
  css.textContent = `
  .jb{position:fixed;z-index:30;width:340px;max-width:min(440px,92vw);max-height:62vh;display:flex;flex-direction:column;
    background:linear-gradient(180deg,rgba(10,17,29,.86),rgba(6,10,18,.8));backdrop-filter:blur(10px) saturate(1.2);
    -webkit-backdrop-filter:blur(10px) saturate(1.2);color:#dfe9f5;font:12.5px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    border-radius:3px;box-shadow:0 18px 50px rgba(0,0,0,.45);outline:none;transform-origin:left center}
  .jb::before{content:"";position:absolute;left:0;top:10px;bottom:10px;width:2px;background:var(--trilho);box-shadow:0 0 12px var(--trilho);border-radius:2px}
  .jb::after{content:"";position:absolute;inset:0;pointer-events:none;border-radius:3px;
    background:linear-gradient(var(--trilho),var(--trilho)) top right/14px 1px no-repeat,linear-gradient(var(--trilho),var(--trilho)) top right/1px 14px no-repeat,
      linear-gradient(var(--trilho),var(--trilho)) bottom right/14px 1px no-repeat,linear-gradient(var(--trilho),var(--trilho)) bottom right/1px 14px no-repeat;opacity:.55}
  .jb:focus-visible{box-shadow:0 0 0 1px var(--trilho),0 18px 50px rgba(0,0,0,.45)}
  .jb.abrindo{animation:jbAbre .18s ease-out}
  @keyframes jbAbre{from{opacity:0;transform:scaleX(.6)}to{opacity:1;transform:none}}
  .jb header{display:flex;align-items:baseline;gap:8px;padding:9px 10px 6px 16px;cursor:grab;user-select:none}
  .jb header:active{cursor:grabbing}
  .jb h3{margin:0;font-size:13px;font-weight:600;letter-spacing:.01em;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .jb .fonte{font-size:10.5px;color:#7f93ab}
  .jb button.ic{all:unset;cursor:pointer;color:#7f93ab;font-size:13px;padding:0 3px;line-height:1}
  .jb button.ic:hover,.jb button.ic:focus-visible{color:#fff}
  .jb .corpo{padding:2px 14px 12px 16px;overflow:auto}
  .jb p{margin:0 0 6px}
  .jb ul{list-style:none;margin:0;padding:0}.jb li{padding:3px 0;border-bottom:1px solid rgba(127,147,171,.12);display:flex;gap:8px}
  .jb li:last-child{border:0}.jb li .d{margin-left:auto;color:#7f93ab;white-space:nowrap}.jb li.feito{color:#7f93ab;text-decoration:line-through}
  .jb table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
  .jb th{font-weight:500;color:#7f93ab;text-align:left;padding:3px 8px 3px 0;border-bottom:1px solid rgba(127,147,171,.25)}
  .jb td{padding:3px 8px 3px 0;border-bottom:1px solid rgba(127,147,171,.08);white-space:nowrap}
  .jb .mets{display:grid;grid-template-columns:repeat(auto-fit,minmax(92px,1fr));gap:10px 16px}
  .jb .met b{display:block;font-size:22px;font-weight:300;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
  .jb .met b small{font-size:12px;color:#7f93ab;margin-left:2px}
  .jb .met span{color:#7f93ab;font-size:11px}.jb .met i{font-style:normal;font-size:11px;margin-left:6px}
  .jb .met{border-left:2px solid var(--m,transparent);padding-left:8px}
  .jb svg{display:block;width:100%;height:auto}
  .jb .st{display:flex;gap:8px;align-items:center}.jb .st i{width:8px;height:8px;border-radius:50%;background:var(--c);box-shadow:0 0 10px var(--c)}
  .jb .barra{height:3px;background:rgba(127,147,171,.2);margin:6px 0 4px}.jb .barra i{display:block;height:100%;background:#38e1ff}
  .jb .bts{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
  .jb .bts button{all:unset;cursor:pointer;padding:5px 11px;border:1px solid #25405a;border-radius:2px;color:#dfe9f5}
  .jb .bts button:hover,.jb .bts button:focus-visible{border-color:#38e1ff;color:#fff}
  .jb iframe{border:0;width:100%;min-height:220px;background:transparent}
  .jb img{max-width:100%;display:block}
  #jbSel{position:fixed;left:50%;top:84px;transform:translateX(-50%);z-index:40;display:none;min-width:280px;
    background:rgba(8,12,20,.94);border:1px solid #1d2c3e;border-radius:3px;padding:6px;font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#dfe9f5}
  #jbSel.on{display:block}#jbSel button{all:unset;display:block;width:calc(100% - 20px);padding:7px 10px;cursor:pointer;border-radius:2px}
  #jbSel button:hover,#jbSel button:focus-visible{background:rgba(56,225,255,.1);color:#fff}
  #jbSel p{margin:4px 10px 6px;color:#7f93ab;font-size:11.5px}
  @media (prefers-reduced-motion: reduce){.jb.abrindo{animation:none}}`;
  document.head.appendChild(css);

  /* ── conexão JBP ── */
  function conectar() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const q = new URLSearchParams(location.search), auth = new URLSearchParams();
    if (q.get('dispositivo')) { auth.set('dispositivo', q.get('dispositivo')); auth.set('t', q.get('t') || ''); }
    const ws = new WebSocket(`${proto}://${location.host}/blocos/ws${auth.toString() ? '?' + auth : ''}`);
    S.ws = ws;
    ws.onopen = () => {
      S.tentativa = 0;
      ws.send(JSON.stringify({ op: 'ola', perfil: PERFIL, nome: PERFIL, v: 1,
        capacidades: { largura: innerWidth, altura: innerHeight } }));
    };
    ws.onmessage = ev => { let m; try { m = JSON.parse(ev.data); } catch (e) { return; } receber(m); };
    ws.onclose = ev => {
      if (ev.code === 4409) return;                                   // blocos desligados: não insiste
      for (const id of [...S.blocos.keys()]) remover(id, true);
      const espera = Math.min(15000, 800 * 2 ** S.tentativa++);
      setTimeout(conectar, espera);
    };
  }
  function enviar(m) { if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify(m)); }

  function receber(m) {
    if (m.op === 'abrir' || m.op === 'atualizar') desenhar(m.bloco, m.op === 'abrir');
    else if (m.op === 'fechar') remover(m.id);
    else if (m.op === 'falar' && m.texto && typeof window.rac === 'function') window.rac('bloco', m.texto);
  }

  /* ── lâmina ── */
  function posicaoLivre(el) {
    const n = [...S.blocos.values()].filter(x => x.el !== el).length;
    const col = Math.floor(n / 3), lin = n % 3;
    return { left: innerWidth - 470 - col * 460, top: 200 + lin * 190 };
  }

  function desenhar(b, novo) {
    let reg = S.blocos.get(b.id);
    if (!reg) {
      const el = document.createElement('section');
      el.className = 'jb'; el.tabIndex = 0; el.setAttribute('role', 'region');
      el.innerHTML = `<header><h3></h3><span class="fonte"></span>
        <button class="ic" data-a="ler" title="ler em voz" aria-label="ler em voz">◉</button>
        <button class="ic" data-a="fechar" title="fechar" aria-label="fechar">×</button></header><div class="corpo"></div>`;
      document.body.appendChild(el);
      reg = { el, b };
      S.blocos.set(b.id, reg);
      el.addEventListener('click', e => {
        const a = e.target.closest('[data-a]'); if (!a) return;
        if (a.dataset.a === 'fechar') enviar({ op: 'fechar', id: reg.b.id });
        if (a.dataset.a === 'ler') enviar({ op: 'ler', id: reg.b.id });
        if (a.dataset.a === 'acao') enviar({ op: 'acao', id: reg.b.id, intencao: a.dataset.i });
      });
      el.addEventListener('keydown', e => {
        if (e.target !== el) return;
        if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); enviar({ op: 'fechar', id: reg.b.id }); }
        if (e.key === 'l' || e.key === 'L') { e.preventDefault(); enviar({ op: 'ler', id: reg.b.id }); }
      });
      arrastavel(el, reg);
      if (!reduz && novo) { el.classList.add('abrindo'); el.addEventListener('animationend', () => el.classList.remove('abrindo'), { once: true }); }
    }
    reg.b = b;
    const el = reg.el;
    el.style.setProperty('--trilho', b.tipo === 'status' && b.conteudo ? (ESTADO[b.conteudo.estado] || COR[1]) : COR[b.prioridade] || COR[1]);
    el.setAttribute('aria-label', b.titulo);
    el.querySelector('h3').textContent = b.titulo;
    el.querySelector('.fonte').textContent = b.privado ? 'privado' : (b.fonte ? 'ao vivo' : '');
    el.querySelector('.corpo').innerHTML = corpo(b);
    const a = b.ancoragem || {};
    if (!reg.arrastado) {
      if (a.x != null && a.y != null) { el.style.left = Math.round(a.x * innerWidth) + 'px'; el.style.top = Math.round(a.y * innerHeight) + 'px'; }
      else if (!el.style.left) { const p = posicaoLivre(el); el.style.left = Math.max(12, p.left) + 'px'; el.style.top = p.top + 'px'; }
    }
    if (a.largura) el.style.width = Math.round(a.largura * innerWidth) + 'px';
    el.style.zIndex = ++S.z;
  }

  function remover(id, silencioso) {
    const reg = S.blocos.get(id); if (!reg) return;
    S.blocos.delete(id);
    if (reduz || silencioso) return reg.el.remove();
    reg.el.animate([{ opacity: 1 }, { opacity: 0, transform: 'scaleX(.7)' }], { duration: 140, easing: 'ease-in' }).onfinish = () => reg.el.remove();
  }

  function arrastavel(el, reg) {
    const cab = el.querySelector('header');
    cab.addEventListener('pointerdown', e => {
      if (e.target.closest('button')) return;
      e.preventDefault(); cab.setPointerCapture(e.pointerId);
      const r = el.getBoundingClientRect(), dx = e.clientX - r.left, dy = e.clientY - r.top;
      el.style.zIndex = ++S.z;
      const mover = ev => { el.style.left = Math.max(0, Math.min(innerWidth - 80, ev.clientX - dx)) + 'px'; el.style.top = Math.max(56, Math.min(innerHeight - 40, ev.clientY - dy)) + 'px'; };
      const soltar = () => {
        cab.removeEventListener('pointermove', mover); cab.removeEventListener('pointerup', soltar);
        reg.arrastado = true;
        const rr = el.getBoundingClientRect();
        enviar({ op: 'mover', id: reg.b.id, ancoragem: { x: +(rr.left / innerWidth).toFixed(3), y: +(rr.top / innerHeight).toFixed(3) } });
        setTimeout(() => { reg.arrastado = false; }, 400);
      };
      cab.addEventListener('pointermove', mover); cab.addEventListener('pointerup', soltar);
    });
  }

  /* ── corpo por tipo ── */
  function corpo(b) {
    const c = b.conteudo;
    if (!c) return (b.linhas || []).map(l => `<p>${esc(l)}</p>`).join('');
    switch (b.tipo) {
      case 'texto': return c.texto.split(/\n+/).map(p => `<p>${esc(p)}</p>`).join('');
      case 'lista': return `<ul>${c.itens.map(i => `<li class="${i.feito ? 'feito' : ''}"><span>${esc(i.texto)}</span>${i.detalhe ? `<span class="d">${esc(i.detalhe)}</span>` : ''}</li>`).join('') || '<li>vazio</li>'}</ul>`;
      case 'tabela': return `<table><thead><tr>${c.colunas.map(x => `<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${c.linhas.map(l => `<tr>${l.map(x => `<td>${esc(x)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
      case 'metricas': return `<div class="mets">${c.itens.map(m => {
        const v = m.variacao == null ? '' : `<i style="color:${m.variacao >= 0 ? '#49e6a0' : '#ff5c72'}">${m.variacao >= 0 ? '▲' : '▼'}${Math.abs(m.variacao)}%</i>`;
        return `<div class="met" style="--m:${ESTADO[m.estado] || 'transparent'}"><b>${esc(m.valor)}<small>${esc(m.unidade)}</small></b><span>${esc(m.rotulo)}</span>${v}</div>`;
      }).join('')}</div>`;
      case 'grafico': return grafico(c);
      case 'grafo': return grafo(c);
      case 'status': return `<div class="st" style="--c:${ESTADO[c.estado] || '#38e1ff'}"><i></i><span>${esc(c.texto || c.estado)}</span></div>`;
      case 'progresso': return `<div class="barra"><i style="width:${Math.round(c.valor * 100)}%"></i></div><p>${Math.round(c.valor * 100)}% ${esc(c.texto)}</p>`;
      case 'acoes': return `${c.texto ? `<p>${esc(c.texto)}</p>` : ''}<div class="bts">${c.botoes.map(bt => `<button data-a="acao" data-i="${esc(bt.intencao)}">${esc(bt.rotulo)}</button>`).join('')}</div>`;
      case 'imagem': return `<img src="${esc(c.src)}" alt="${esc(c.legenda)}"><p>${esc(c.legenda)}</p>`;
      case 'html': return `<iframe sandbox="" referrerpolicy="no-referrer" srcdoc="${esc(`<style>body{margin:0;color:#dfe9f5;font:13px -apple-system,sans-serif;background:transparent}</style>${c.html}`)}"></iframe>`;
    }
    return (b.linhas || []).map(l => `<p>${esc(l)}</p>`).join('');
  }

  function grafico(c) {
    const W = 380, H = 130, P = 18, cores = ['#38e1ff', '#ffb347', '#7d5cff', '#49e6a0'];
    const series = c.series.filter(s => s.pontos.length);
    if (!series.length) return '<p>sem dados</p>';
    const ys = series.flatMap(s => s.pontos.map(p => p.y)), min = Math.min(0, ...ys), max = Math.max(...ys, min + 1);
    const n = Math.max(...series.map(s => s.pontos.length));
    const Y = y => H - P - (y - min) / (max - min) * (H - 2 * P);
    let g = '';
    if (c.forma === 'linha') {
      series.forEach((s, k) => {
        const X = i => P + i * (W - 2 * P) / Math.max(1, s.pontos.length - 1);
        g += `<polyline fill="none" stroke="${cores[k % 4]}" stroke-width="1.6" points="${s.pontos.map((p, i) => `${X(i).toFixed(1)},${Y(p.y).toFixed(1)}`).join(' ')}"/>`;
        const u = s.pontos[s.pontos.length - 1];
        g += `<circle cx="${X(s.pontos.length - 1)}" cy="${Y(u.y)}" r="2.6" fill="${cores[k % 4]}"/>`;
      });
    } else {
      const bw = (W - 2 * P) / n / series.length * 0.78;
      series.forEach((s, k) => s.pontos.forEach((p, i) => {
        const x = P + i * (W - 2 * P) / n + k * bw + 2;
        g += `<rect x="${x.toFixed(1)}" y="${Y(Math.max(0, p.y)).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.abs(Y(p.y) - Y(0)).toFixed(1)}" fill="${cores[k % 4]}" opacity=".85"><title>${esc(s.nome)} ${esc(p.x)}: ${p.y}</title></rect>`;
      }));
    }
    const p0 = series[0].pontos, rot = (t, x, anc) => `<text x="${x}" y="${H - 3}" fill="#7f93ab" font-size="10" text-anchor="${anc}">${esc(t)}</text>`;
    const leg = series.length > 1 ? `<p>${series.map((s, k) => `<span style="color:${cores[k % 4]}">■</span> ${esc(s.nome)}`).join('&ensp;')}</p>` : '';
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="gráfico"><line x1="${P}" x2="${W - P}" y1="${Y(0)}" y2="${Y(0)}" stroke="rgba(127,147,171,.25)"/>${g}
      ${rot(p0[0].x, P, 'start')}${rot(p0[p0.length - 1].x, W - P, 'end')}
      <text x="${W - P}" y="12" fill="#7f93ab" font-size="10" text-anchor="end">${esc(max.toLocaleString('pt-BR'))} ${esc(c.unidade)}</text></svg>${leg}`;
  }

  function grafo(c) {
    const W = 380, H = 220, R = 86, cx = W / 2, cy = H / 2, pos = {};
    c.nos.forEach((n, i) => { const a = -Math.PI / 2 + i * 2 * Math.PI / c.nos.length; pos[n.id] = [cx + R * 1.5 * Math.cos(a), cy + R * Math.sin(a)]; });
    const ar = c.arestas.map(e => { const [x1, y1] = pos[e.de], [x2, y2] = pos[e.para];
      return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="rgba(56,225,255,.4)"/>${e.rotulo ? `<text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 3}" fill="#7f93ab" font-size="9.5" text-anchor="middle">${esc(e.rotulo)}</text>` : ''}`; }).join('');
    const nos = c.nos.map(n => { const [x, y] = pos[n.id];
      return `<circle cx="${x}" cy="${y}" r="4" fill="#38e1ff"/><text x="${x}" y="${y + 15}" fill="#dfe9f5" font-size="11" text-anchor="middle">${esc(n.rotulo)}</text>`; }).join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="grafo">${ar}${nos}</svg>`;
  }

  /* ── seletor (K) ── */
  const sel = document.createElement('div'); sel.id = 'jbSel'; sel.setAttribute('role', 'dialog'); sel.setAttribute('aria-label', 'abrir bloco');
  document.body.appendChild(sel);
  async function seletor(abrir) {
    if (!abrir) { sel.classList.remove('on'); return; }
    let d; try { d = await (await fetch('/blocos')).json(); } catch (e) { return; }
    if (!d.ativo) return;
    const abertos = new Set(d.abertos.map(a => a.id));
    sel.innerHTML = `<p>Abrir um bloco — ou peça por voz: "abre o bloco de…"</p>` +
      d.modelos.map(m => `<button data-m="${esc(m)}">${esc((d.titulos || {})[m] || m)}${abertos.has(m) ? ' — aberto' : ''}</button>`).join('') +
      (d.layouts.length ? `<p>Layouts</p>` + d.layouts.map(l => `<button data-l="${esc(l)}">${esc(l)}</button>`).join('') : '');
    sel.classList.add('on');
    const b = sel.querySelector('button'); if (b) b.focus();
  }
  sel.addEventListener('click', async e => {
    const b = e.target.closest('button'); if (!b) return;
    const pedir = (url, corpo) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) });
    if (b.dataset.m) await pedir('/blocos', { modelo: b.dataset.m });
    if (b.dataset.l) await pedir(`/blocos/layout/${encodeURIComponent(b.dataset.l)}`, { acao: 'abrir' });
    seletor(false);
  });
  addEventListener('keydown', e => {
    const kb = document.getElementById('kbIn');
    if (kb && document.activeElement === kb) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'k' || e.key === 'K') { e.preventDefault(); seletor(!sel.classList.contains('on')); }
    else if (e.key === 'Escape' && sel.classList.contains('on')) { e.stopImmediatePropagation(); seletor(false); }
  }, true);

  window.JaimeBlocos = { estado: S, enviar };
  conectar();
})();
