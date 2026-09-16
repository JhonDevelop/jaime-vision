"""Aprofundar — o J.A.I.M.E enche as notas rasas do vault com conhecimento DENSO e real.

O problema: as notas do mundo do João nascem como esqueleto (títulos sem conteúdo), então ele responde vago.
A solução: reunir as FONTES REAIS de um assunto (o texto da nota + os arquivos que ela cita na máquina + as
linhas do diário e das conversas que falam dele) e pedir a um modelo que reescreva a nota densa e estruturada,
com fatos, não enrolação. O Python lê as fontes (o modelo não tem as mãos); o modelo só sintetiza.

`pensador(prompt, contexto) -> texto` é injetável (testes offline). Nunca inventa: se não há fonte, diz o que falta."""
from __future__ import annotations
import os, re
from pathlib import Path

CAMINHO_RX = re.compile(r"`([~/][^`]+)`|(?<![\w`])((?:~|/Users/[^\s`]+)/[^\s`)\]]+)")
MAX_ARQ = 8
MAX_BYTES = 4000
TEXTO_EXT = {".md", ".txt", ".py", ".js", ".ts", ".json", ".csv", ".html", ".css", ".sh", ".yml", ".yaml", ".toml", ".env.example"}

SISTEMA = ("Você é o J.A.I.M.E organizando o próprio cérebro. Reescreva a nota do vault sobre este assunto do João de "
           "forma DENSA, factual e útil — como um dossiê operacional, não um esqueleto. Use SÓ o que está nas fontes; "
           "nunca invente fatos, datas, pessoas ou números. Mantenha os [[links]] existentes e o título. Estruture com as "
           "seções que fizerem sentido (Objetivo, O que é, Status atual, Decisões com datas, Próximos passos, Fatos que sei, "
           "Arquivos e onde estão, Pessoas, Riscos). Onde a fonte não disser, escreva '— (a confirmar com o João)' em vez de "
           "encher. Português do Brasil, direto. Devolva SÓ o markdown da nota, começando pelo título com #.")

def _ler_arquivo_local(caminho: str, ler=None) -> str:
    """Lê um arquivo texto (ou lista uma pasta) da máquina, com teto de bytes. `ler` é injetável nos testes."""
    if ler is not None:
        return ler(caminho)
    p = Path(os.path.expanduser(caminho))
    try:
        if p.is_dir():
            itens = sorted(x.name for x in p.iterdir())[:40]
            return f"[pasta {p}] " + ", ".join(itens)
        if p.is_file():
            if p.suffix.lower() in TEXTO_EXT or p.suffix == "":
                return p.read_text(encoding="utf-8", errors="ignore")[:MAX_BYTES]
            return f"[arquivo {p.name}, {p.stat().st_size // 1024} KB, binário — não lido]"
    except OSError:
        return ""
    return ""

def coletar_fontes(vault, alvo_rel: str, ler=None, max_arq: int = MAX_ARQ) -> str:
    """Texto da nota + arquivos que ela cita + menções no diário e nas conversas. Tudo que o modelo precisa ler."""
    nota = ""
    try:
        nota = vault.read(alvo_rel)
    except Exception:
        pass
    nome = Path(alvo_rel).stem
    partes = [f"## Nota atual ({alvo_rel})\n{nota or '(vazia)'}"]
    # arquivos citados na nota
    caminhos, vistos = [], set()
    for m in CAMINHO_RX.finditer(nota):
        c = (m.group(1) or m.group(2) or "").rstrip(".,);")
        if c and c not in vistos:
            vistos.add(c); caminhos.append(c)
    if caminhos:
        blocos = []
        for c in caminhos[:max_arq]:
            conteudo = _ler_arquivo_local(c, ler)
            if conteudo:
                blocos.append(f"### Arquivo citado: {c}\n{conteudo[:MAX_BYTES]}")
        if blocos:
            partes.append("## Arquivos que a nota cita\n" + "\n\n".join(blocos))
    # menções no diário e nas conversas (o que o João já falou sobre isso)
    mencoes = _mencoes(vault, nome)
    if mencoes:
        partes.append("## O que já foi dito sobre isso (diário e conversas)\n" + mencoes)
    return "\n\n".join(partes)

def _mencoes(vault, nome: str, max_linhas: int = 30) -> str:
    import glob
    alvo = nome.lower()
    linhas = []
    raiz = vault.root if hasattr(vault, "root") else None
    if raiz is None:
        return ""
    for padrao in ("40-Diario/*.md", "60-Conversas/*.md"):
        for f in sorted(glob.glob(str(raiz / padrao)))[-20:]:
            try:
                for l in Path(f).read_text(encoding="utf-8", errors="ignore").splitlines():
                    if alvo in l.lower() and len(l.strip()) > 3:
                        linhas.append("- " + l.strip("- ").strip()[:200])
            except OSError:
                continue
    # sem duplicar
    unicas = list(dict.fromkeys(linhas))[-max_linhas:]
    return "\n".join(unicas)

class Aprofundador:
    def __init__(self, vault, pensador=None, s=None, ler=None):
        self.vault, self.ler = vault, ler
        from ..mente.pensar import _pensador_padrao
        self.pensador = pensador or (_pensador_padrao(s) if s is not None else None)

    async def aprofundar(self, alvo_rel: str) -> str:
        """Reúne fontes, reescreve a nota densa e grava. Devolve um resumo do que mudou."""
        if not self.pensador:
            return "sem modelo para aprofundar"
        fontes = coletar_fontes(self.vault, alvo_rel, self.ler)
        antes = 0
        try:
            antes = len(self.vault.read(alvo_rel))
        except Exception:
            pass
        prompt = f"Assunto: {Path(alvo_rel).stem}.\nFontes reunidas:\n\n{fontes[:12000]}\n\nReescreva a nota densa (só o markdown)."
        try:
            novo = (await self.pensador(prompt, SISTEMA)).strip()
        except Exception as e:
            return f"falhou: {type(e).__name__}: {e}"
        novo = re.sub(r"^```(markdown|md)?\n?|\n?```$", "", novo).strip()
        if len(novo) < 40 or not novo.lstrip().startswith("#"):
            return "o modelo não devolveu uma nota utilizável"
        self.vault.write(alvo_rel, novo + "\n")
        try:
            self.vault.diario(f"Aprofundei {alvo_rel}: {antes} → {len(novo)} caracteres", "Feito")
        except Exception:
            pass
        return f"{alvo_rel}: {antes} → {len(novo)} caracteres."

    async def aprofundar_projetos(self) -> str:
        import glob
        raiz = self.vault.root
        rels = [f"20-Projetos/{Path(p).name}" for p in sorted(glob.glob(str(raiz / "20-Projetos" / "*.md")))
                if "INDEX" not in p and "Jaime.md" not in p]
        resultados = []
        for rel in rels:
            resultados.append(await self.aprofundar(rel))
        return "\n".join(resultados) if resultados else "nenhum projeto para aprofundar"
