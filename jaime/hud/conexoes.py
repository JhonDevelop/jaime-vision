"""Estado real das conexões do Jaime, para o HUD desenhar os nós em volta do cérebro.

Cada conexão: {nome, ligado, detalhe}. O que é local (vault, voz) é checado na hora; os MCPs remotos
vêm de `claude mcp list`, sondado uma vez no boot e a cada 10 min (é lento: ~5-20 s)."""
from __future__ import annotations
import asyncio, re, time
from ..hud.events import bus

# nome no `claude mcp list` → id do nó no HUD
MCP_NOS = {"github": "github", "notion": "notion", "gmail": "gmail",
           "google drive": "drive", "figma": "figma", "postman": "postman"}
INTERVALO_S = 600

class Conexoes:
    def __init__(self, settings, jaime):
        self.s, self.jaime = settings, jaime
        self.mcps: dict[str, dict] = {}
        self.sondado_em = 0.0

    def estado(self) -> dict:
        s, j = self.s, self.jaime
        nos = {
            "vault":    {"nome": "Obsidian", "ligado": s.vault.is_dir(), "detalhe": str(s.vault.name)},
            "voz":      {"nome": "Voz", "ligado": s.voz != "off",
                         "detalhe": {"openai": "OpenAI onyx", "elevenlabs": "ElevenLabs"}.get(__import__("os").environ.get("JAIME_TTS", "auto"), "auto") + " · " + ("Deepgram" if s.deepgram_key else f"Whisper {s.whisper_modelo}")},
            "notion":   {"nome": "Notion", "ligado": bool(j.notion.ativo), "detalhe": "espelho" if j.notion.ativo else "sem token"},
            "whatsapp": {"nome": "WhatsApp", "ligado": bool(s.evolution_url and s.evolution_key), "detalhe": s.evolution_instance},
            "github":   {"nome": "GitHub", "ligado": False, "detalhe": "mcp"},
            "gmail":    {"nome": "Gmail", "ligado": False, "detalhe": "mcp"},
            "drive":    {"nome": "Drive", "ligado": False, "detalhe": "mcp"},
        }
        for no, info in self.mcps.items():
            if no in nos:
                nos[no].update(info)
        return {"nos": nos, "sondado_em": self.sondado_em}

    async def sondar(self):
        while True:
            try:
                self.mcps = await self._claude_mcp_list()
                self.sondado_em = time.time()
                bus.emitir("conexoes", **self.estado())
            except Exception as e:
                bus.emitir("conexoes", erro=f"{type(e).__name__}: {e}"[:160], **self.estado())
            await asyncio.sleep(INTERVALO_S)

    async def _claude_mcp_list(self) -> dict[str, dict]:
        proc = await asyncio.create_subprocess_exec("claude", "mcp", "list",
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=90)
        except asyncio.TimeoutError:
            proc.kill(); raise
        return parse_mcp_list(out.decode("utf-8", "replace"))

def parse_mcp_list(texto: str) -> dict[str, dict]:
    """'claude.ai GitHub: https://... - ✔ Connected' → {'github': {'ligado': True, 'detalhe': 'Connected'}}"""
    achados: dict[str, dict] = {}
    for linha in texto.splitlines():
        m = re.match(r"\s*(.+?):\s+\S+\s+-\s+(.+)$", linha)
        if not m:
            continue
        nome, status = m.group(1).lower(), m.group(2).strip()
        for chave, no in MCP_NOS.items():
            if chave in nome:
                achados[no] = {"ligado": "connected" in status.lower() and "failed" not in status.lower(),
                               "detalhe": re.sub(r"^[^\w]+", "", status)[:60]}
    return achados
