"""Autoconsciência do Jaime — quem é, para que existe, em que fase está, o que estava fazendo.

`01-Estado/Estado.md` é o único arquivo do vault que o Jaime reescreve por conta própria.
O código atualiza os campos mecânicos (última conversa, máquina); o próprio Jaime, numa
reflexão a cada N turnos, atualiza fase, situação, andamento, próximos passos e aprendizados."""
from __future__ import annotations
import getpass, hashlib, platform, socket
from datetime import date, datetime
from .vault import Vault
from ..identidade import Identidade

ESTADO_REL = "01-Estado/Estado.md"
MAQUINAS_REL = "01-Estado/Maquinas.md"
CONVERSAS_DIR = "60-Conversas"
REFLEXAO_A_CADA = 6

ESTADO_TEMPLATE = """# Estado
> Reescrito pelo próprio Jaime. O João lê; o Jaime mantém.

## Fase
0 — esqueleto criado; ainda não operei de verdade

## Situação agora
Acabei de ser criado. Preciso ser ligado, receber a palavra-passe e conhecer a máquina.

## Última conversa
- canal: —
- quando: —
- tema: —

## Em andamento
- nada ainda

## Próximos passos
- primeiro boot: apresentar-me, registrar a máquina, sincronizar com o Notion

## Aprendizados recentes
- nenhum
"""

def maquina() -> dict:
    info = {"host": socket.gethostname(), "user": getpass.getuser(),
            "os": f"{platform.system()} {platform.release()}", "arch": platform.machine()}
    info["id"] = hashlib.sha1(f"{info['host']}|{info['user']}|{info['os']}".encode()).hexdigest()[:10]
    return info

class Estado:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.turnos = 0
        self.sessao_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        if not vault.read(ESTADO_REL):
            vault.write(ESTADO_REL, ESTADO_TEMPLATE)

    # ── máquinas ───────────────────────────────────────
    def maquina_nova(self) -> bool:
        return maquina()["id"] not in self.vault.read(MAQUINAS_REL)

    def registrar_maquina(self) -> bool:
        """Registra a máquina atual; devolve True se era desconhecida (→ apresentar-se)."""
        nova = self.maquina_nova()
        if not self.vault.read(MAQUINAS_REL):
            self.vault.write(MAQUINAS_REL, "# Máquinas onde já fui ligado\n\n| id | host | usuário | SO | primeira vez | último boot |\n|---|---|---|---|---|---|\n")
        m = maquina()
        if nova:
            self.vault.append(MAQUINAS_REL, f"| {m['id']} | {m['host']} | {m['user']} | {m['os']} | {date.today()} | {date.today()} |")
        else:
            linhas = self.vault.read(MAQUINAS_REL).splitlines()
            for i, l in enumerate(linhas):
                if l.startswith(f"| {m['id']} |"):
                    partes = l.split("|"); partes[-2] = f" {date.today()} "; linhas[i] = "|".join(partes)
            self.vault.write(MAQUINAS_REL, "\n".join(linhas) + "\n")
        return nova

    # ── seções do Estado ───────────────────────────────
    def ler(self) -> str:
        return self.vault.read(ESTADO_REL)

    def secao(self, titulo: str) -> str:
        txt = self.ler(); marker = f"## {titulo}"
        if marker not in txt:
            return ""
        corpo = txt.split(marker, 1)[1]
        return corpo.split("\n## ", 1)[0].strip()

    def fase(self) -> str:
        return self.secao("Fase").splitlines()[0] if self.secao("Fase") else "?"

    def atualizar_secao(self, titulo: str, corpo: str) -> None:
        txt = self.ler() or ESTADO_TEMPLATE; marker = f"## {titulo}"
        if marker not in txt:
            txt = txt.rstrip("\n") + f"\n\n{marker}\n{corpo.strip()}\n"
        else:
            head, tail = txt.split(marker, 1)
            resto = tail.split("\n## ", 1)
            depois = ("\n## " + resto[1]) if len(resto) > 1 else ""
            txt = f"{head}{marker}\n{corpo.strip()}\n{depois}"
        self.vault.write(ESTADO_REL, txt)

    # ── conversas ──────────────────────────────────────
    def registrar_turno(self, canal: str, pergunta: str, resposta: str) -> None:
        self.turnos += 1
        rel = f"{CONVERSAS_DIR}/{date.today().isoformat()}.md"
        if not self.vault.read(rel):
            self.vault.write(rel, f"# Conversas — {date.today():%d/%m/%Y}\n")
        self.vault.append(rel, f"\n### {datetime.now():%H:%M} · {canal} · sessão {self.sessao_id}\n"
                               f"**João:** {pergunta.strip()}\n\n**{Identidade(self.vault.root).nome}:** {resposta.strip()}\n")
        m = maquina()
        self.atualizar_secao("Última conversa",
            f"- canal: {canal}\n- quando: {datetime.now():%d/%m/%Y %H:%M} em {m['host']}\n- tema: {pergunta.strip()[:100]}")

    def precisa_refletir(self) -> bool:
        return self.turnos > 0 and self.turnos % REFLEXAO_A_CADA == 0

    def resumo_curto(self) -> str:
        return f"Fase: {self.fase()}. Situação: {self.secao('Situação agora')[:160]}"
