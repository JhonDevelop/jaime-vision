"""Browser do Jaime — Playwright com perfil persistente em `~/Jaime/browser-profile`.

Uma janela do Chromium própria dele (não o Chrome do João): logins que o João fizer uma vez ali ficam salvos.
Uma sessão por processo, aberta na primeira chamada. Tudo que é "clicar em enviar / comprar / pagar / confirmar"
passa pelo Vigia (regra em jaime/vigia/hooks.py) e só executa depois do "confirmo"."""
from __future__ import annotations
import asyncio, os, re
from pathlib import Path

PERFIL = Path(os.environ.get("JAIME_BROWSER_PROFILE", "~/Jaime/browser-profile")).expanduser()
CAPTURAS = Path("~/Jaime/capturas").expanduser()
MAX_TEXTO = 12_000

class Navegador:
    def __init__(self, headless: bool | None = None):
        self.headless = (os.environ.get("JAIME_BROWSER_HEADLESS", "0") == "1") if headless is None else headless
        self._pw = None
        self._ctx = None
        self._page = None
        self._lock = asyncio.Lock()

    async def _garantir(self):
        if self._page and not self._page.is_closed():
            return self._page
        from playwright.async_api import async_playwright
        PERFIL.mkdir(parents=True, exist_ok=True)
        self._pw = await async_playwright().start()
        self._ctx = await self._pw.chromium.launch_persistent_context(str(PERFIL), headless=self.headless, viewport={"width": 1280, "height": 860},
                                                                     locale="pt-BR", args=["--disable-blink-features=AutomationControlled"])
        self._page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        return self._page

    async def fechar(self):
        try:
            if self._ctx: await self._ctx.close()
            if self._pw: await self._pw.stop()
        finally:
            self._ctx = self._pw = self._page = None

    # ── ações ─────────────────────────────────────────
    async def abrir(self, url: str) -> str:
        async with self._lock:
            pg = await self._garantir()
            if not re.match(r"^[a-z]+://", url):
                url = "https://" + url
            await pg.goto(url, wait_until="domcontentloaded", timeout=30_000)
            return f"{await pg.title()} — {pg.url}"

    async def ler_pagina(self, limite: int = MAX_TEXTO) -> str:
        async with self._lock:
            pg = await self._garantir()
            texto = await pg.evaluate("() => document.body ? document.body.innerText : ''")
            texto = re.sub(r"\n{3,}", "\n\n", texto or "").strip()
            return f"[{await pg.title()}] {pg.url}\n\n{texto[:limite]}" + ("\n…(cortado)" if len(texto) > limite else "")

    async def clicar(self, alvo: str) -> str:
        """alvo: seletor CSS, ou texto visível do botão/link."""
        async with self._lock:
            pg = await self._garantir()
            loc = pg.locator(alvo) if re.match(r"^[#.\[]|^[a-z]+(\[|\.|#|:|>|\s)", alvo) else pg.get_by_text(alvo, exact=False).first
            await loc.first.click(timeout=10_000)
            await pg.wait_for_load_state("domcontentloaded", timeout=15_000)
            return f"cliquei em '{alvo}' → {await pg.title()} — {pg.url}"

    async def preencher(self, seletor: str, texto: str) -> str:
        async with self._lock:
            pg = await self._garantir()
            loc = pg.locator(seletor) if re.match(r"^[#.\[]|^[a-z]+(\[|\.|#|:)", seletor) else pg.get_by_label(seletor).or_(pg.get_by_placeholder(seletor))
            await loc.first.fill(texto, timeout=10_000)
            return f"preenchi '{seletor}'"

    async def extrair(self, seletor: str, limite: int = 200) -> list[str]:
        async with self._lock:
            pg = await self._garantir()
            itens = await pg.locator(seletor).all_inner_texts()
            return [re.sub(r"\s+", " ", i).strip() for i in itens[:limite] if i.strip()]

    async def screenshot(self, nome: str = "pagina") -> str:
        async with self._lock:
            pg = await self._garantir()
            CAPTURAS.mkdir(parents=True, exist_ok=True)
            caminho = CAPTURAS / f"{re.sub(r'[^a-z0-9]+', '-', nome.lower()).strip('-') or 'pagina'}.png"
            await pg.screenshot(path=str(caminho), full_page=False)
            return str(caminho)
