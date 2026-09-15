"""Ouvido passivo — o que o Jaime ouviu sem ser chamado.

Toda transcrição ignorada (não era com ele) vai para `60-Conversas/ouvido-AAAA-MM-DD.md`. À noite, a rotina
"consolida o que ouvi hoje" pede ao modelo para tirar dali o que importa (compromissos, decisões, nomes, prazos)
e gravar em `30-Tarefas/Para-lembrar.md` como `- [ ] AAAA-MM-DD · texto`. No primeiro "Jaime, está aí?" do dia
(e no briefing), ele fala esses itens e marca `[x]`."""
from __future__ import annotations
import re
from datetime import date, datetime
from ..brain.vault import Vault

PARA_LEMBRAR = "30-Tarefas/Para-lembrar.md"
CABECALHO = "# Para lembrar\n\n> O que o Jaime ouviu e guardou para te avisar. `- [ ] data · texto`; vira `[x]` quando ele te avisa.\n\n"

def arquivo_do_dia(d: date | None = None) -> str:
    return f"60-Conversas/ouvido-{(d or date.today()).isoformat()}.md"

def guardar(vault: Vault, texto: str, agora: datetime | None = None) -> None:
    """Uma linha por fala ouvida. Curto e sem juízo: a consolidação decide o que importa."""
    texto = re.sub(r"\s+", " ", texto or "").strip()
    if len(texto) < 8:
        return
    agora = agora or datetime.now()
    rel = arquivo_do_dia(agora.date())
    if not vault.read(rel):
        vault.write(rel, f"# Ouvido em {agora:%d/%m/%Y}\n\n> Falas que não eram comigo. A rotina das 22h consolida o que importa.\n\n")
    vault.append(rel, f"- {agora:%H:%M} {texto[:300]}")

def anotar_para_lembrar(vault: Vault, texto: str, quando: date | None = None) -> str:
    if not vault.read(PARA_LEMBRAR):
        vault.write(PARA_LEMBRAR, CABECALHO)
    linha = f"- [ ] {(quando or date.today()).isoformat()} · {texto.strip()[:240]}"
    vault.append(PARA_LEMBRAR, linha)
    return linha

def pendentes(vault: Vault) -> list[str]:
    return [m.group(1).strip() for l in vault.read(PARA_LEMBRAR).splitlines()
            if (m := re.match(r"- \[ \] \d{4}-\d{2}-\d{2} · (.+)$", l.strip()))]

def marcar_entregues(vault: Vault) -> int:
    txt = vault.read(PARA_LEMBRAR)
    novo, n = re.subn(r"^- \[ \] (\d{4}-\d{2}-\d{2} · )", r"- [x] \1", txt, flags=re.M)
    if n:
        vault.write(PARA_LEMBRAR, novo)
    return n

def frase_dos_pendentes(vault: Vault, tarefas_abertas: list[str] | None = None) -> str:
    """O que ele diz no primeiro contato do dia: lembretes guardados + tarefas do dia."""
    partes = []
    p = pendentes(vault)
    if p:
        partes.append(("Guardei " + (f"{len(p)} coisas" if len(p) > 1 else "uma coisa") + " de ontem: ") + "; ".join(x[:120] for x in p[:5]) + ".")
    t = [re.sub(r"^- \[ \] ", "", x) for x in (tarefas_abertas or [])][:5]
    if t:
        partes.append(("Tarefas do dia: " if len(t) > 1 else "Tarefa do dia: ") + "; ".join(x[:80] for x in t) + ".")
    return " ".join(partes)

def prompt_consolidar(vault: Vault, d: date | None = None) -> str:
    d = d or date.today()
    ouvido = vault.read(arquivo_do_dia(d))
    return (f"[rotina] Consolide o que você ouviu hoje ({d:%d/%m}) sem ser chamado. Conteúdo de {arquivo_do_dia(d)}:\n\n{ouvido or '(nada)'}\n\n"
            "Extraia SÓ o que importa para o João amanhã: compromissos, prazos, decisões, nomes, valores, pedidos que ele fez a terceiros. "
            "Para cada item chame mcp__cerebro__criar_tarefa se for tarefa, ou registre com mcp__cerebro__lembrar na nota certa; "
            "e escreva o resumo de até 5 itens em 30-Tarefas/Para-lembrar.md no formato `- [ ] AAAA-MM-DD · texto` (Write/Edit). "
            "Se não houver nada relevante, responda 'nada a lembrar'. Não fale em voz alta agora.")
