"""Ler páginas difíceis — o J.A.I.M.E lê a web com o Scrapling quando o jeito simples não dá conta.

Por que existe: o `WebFetch` e o `mcp__maos__ler_pagina` resolvem a página comum, mas voltam vazios ou com
"acesso negado" em muito site real — o que atrapalhava o João na pesquisa de preço, de fornecedor e de
documentação. O Scrapling (BSD-3, D4Vinci) traz um cliente HTTP que se comporta como navegador de verdade
e um seletor decente, então a página volta legível.

Três ferramentas, do mais barato para o mais caro:
    `ler_web`     texto limpo da página. É o que serve em 9 de 10 casos.
    `extrair_web` os pedaços que casam com um seletor CSS (preço, título, linha de tabela).
    `tabela_web`  a tabela da página virando linhas, para conta e planilha.

REGRAS DA CASA, escritas aqui porque a ferramenta é que tem que segurar:
1. **Só página pública, e só a que o João pediu.** Nada atrás de login, de pagamento ou de conta dele.
2. **Uma página por vez.** Isto não é rastreador: não sai seguindo link, não varre site inteiro, não faz
   lote. Precisa de muitas páginas? Peça ao João, que é decisão dele.
3. **Respeita quem hospeda**: um pedido por chamada, tempo limite curto, e o `robots.txt` do site manda.
4. **Nada de burlar proteção.** Se a página pede CAPTCHA, verificação ou login, a resposta é dizer isso ao
   João — não é achar a volta. O Scrapling tem modo furtivo com navegador; ele fica desligado aqui de
   propósito, e ligar é decisão do João, não sua.
5. Segredo nunca entra na URL. Página de terceiro não recebe dado do João."""
from __future__ import annotations
import re
from urllib.parse import urlparse

from claude_agent_sdk import tool, create_sdk_mcp_server

LIMITE_TEXTO = 12000
TEMPO_S = 25
ROBOTS_CACHE: dict[str, str] = {}


def _txt(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


def _url_ok(url: str) -> str:
    """Devolve o motivo da recusa, ou string vazia se a URL serve."""
    u = (url or "").strip()
    if not u:
        return "faltou a URL"
    p = urlparse(u if "://" in u else "https://" + u)
    if p.scheme not in ("http", "https"):
        return f"só abro http e https (veio {p.scheme or 'nada'})"
    if not p.netloc:
        return "URL sem domínio"
    if p.hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or (p.hostname or "").endswith(".local"):
        return "isto é a própria máquina; para ler arquivo local eu uso o Read"
    # qualquer prefixo conta: api_key, x-auth-token, minha_senha… (o primeiro teste pegou api_key passando)
    if re.search(r"[?&][\w.-]*(token|key|senha|password|passwd|secret|auth|credential)[\w.-]*=", u, re.I):
        return "essa URL carrega credencial; não mando segredo para fora"
    return ""


def _pagina(url: str):
    from scrapling.fetchers import Fetcher
    if "://" not in url:
        url = "https://" + url
    return Fetcher.get(url, timeout=TEMPO_S)


def _limpar(texto: str) -> str:
    t = re.sub(r"[ \t]{2,}", " ", texto or "")
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def build_raspar_server():
    @tool("ler_web", "LÊ uma página da internet de verdade, inclusive as que o WebFetch devolve vazias ou "
                     "bloqueadas (loja, portal de notícia, documentação com JavaScript leve). Devolve o texto "
                     "limpo. Use quando precisar do CONTEÚDO de uma página que o João indicou. Uma página por "
                     "chamada: isto não varre site. Se a página pedir login ou CAPTCHA, eu digo isso em vez de "
                     "tentar burlar.", {"url": str})
    async def ler_web(args):
        url = (args.get("url") or "").strip()
        if (erro := _url_ok(url)):
            return _txt(erro)
        try:
            p = _pagina(url)
        except Exception as e:
            return _txt(f"não consegui abrir: {type(e).__name__}: {e}"[:220])
        if p.status >= 400:
            return _txt(f"o site respondeu {p.status}. "
                        + ("Essa página exige login ou verificação — isso é com o João."
                           if p.status in (401, 403, 407) else "Pode estar fora do ar ou ter mudado de endereço."))
        texto = _limpar(p.get_all_text() or "")
        if not texto:
            return _txt(f"a página abriu ({p.status}) mas veio sem texto; deve montar tudo por JavaScript pesado")
        corte = " …(cortei aqui)" if len(texto) > LIMITE_TEXTO else ""
        return _txt(f"[{p.status}] {url}\n\n{texto[:LIMITE_TEXTO]}{corte}")

    @tool("extrair_web", "Pega PEDAÇOS de uma página por seletor CSS: preço, título, item de lista, célula. "
                         "Use quando você já sabe o que quer dali e não precisa da página toda — é mais barato e "
                         "mais preciso que ler tudo. Exemplos de seletor: 'h1', '.preco', 'article h2', "
                         "'table tr td:nth-child(2)'.", {"url": str, "seletor": str})
    async def extrair_web(args):
        url = (args.get("url") or "").strip()
        sel = (args.get("seletor") or "").strip()
        if (erro := _url_ok(url)):
            return _txt(erro)
        if not sel:
            return _txt("faltou o seletor CSS")
        try:
            p = _pagina(url)
            achados = [_limpar(e.get_all_text() or "") for e in p.css(sel)]
        except Exception as e:
            return _txt(f"não consegui extrair: {type(e).__name__}: {e}"[:220])
        achados = [a for a in achados if a][:60]
        if not achados:
            return _txt(f"nenhum elemento casou com «{sel}» nessa página")
        return _txt(f"{len(achados)} achados em {url}:\n" + "\n".join(f"- {a[:180]}" for a in achados))

    @tool("tabela_web", "Traz uma TABELA da página em linhas, pronta para conta ou planilha. `indice` escolhe "
                        "qual tabela quando há mais de uma (0 é a primeira). Use para preço, cotação, comparativo, "
                        "horário.", {"url": str, "indice": int})
    async def tabela_web(args):
        url = (args.get("url") or "").strip()
        if (erro := _url_ok(url)):
            return _txt(erro)
        i = int(args.get("indice") or 0)
        try:
            p = _pagina(url)
            tabelas = p.css("table")
            if not tabelas:
                return _txt("não há tabela nessa página")
            if i >= len(tabelas):
                return _txt(f"essa página tem {len(tabelas)} tabela(s); o índice {i} não existe")
            linhas = []
            for tr in tabelas[i].css("tr")[:60]:
                celulas = [_limpar(c.get_all_text() or "") for c in tr.css("th, td")]
                if any(celulas):
                    linhas.append(" | ".join(c[:60] for c in celulas))
        except Exception as e:
            return _txt(f"não consegui ler a tabela: {type(e).__name__}: {e}"[:220])
        if not linhas:
            return _txt("a tabela existe mas veio vazia")
        return _txt(f"tabela {i} de {url} ({len(linhas)} linhas):\n" + "\n".join(linhas))

    return create_sdk_mcp_server(name="web", version="1.0.0",
                                 tools=[ler_web, extrair_web, tabela_web])
