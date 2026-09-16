"""Respostas rápidas — cumprimentos e perguntas sociais respondidos em milissegundos, sem modelo.

"Bom dia", "tudo bem?", "como está o dia hoje?", "obrigado" não merecem 2 s de espera nem "deixa eu ver".
Cada resposta é montada com o que ele já sabe (hora, momento, clima em cache, tarefas, lembretes) e varia
um pouco para não soar gravada. Só entra quando a frase é SÓ isso — "bom dia, abre o Finder" vai ao modelo."""
from __future__ import annotations
import random, re
from ..hud.events import bus
from datetime import datetime

SAUDACAO_RX = re.compile(r"^\s*(bom dia|boa tarde|boa noite|oi|olá|ola|opa|e aí|eai|fala)\s*[,!.]*\s*(jaime|senhor)?\s*[,!.]*\s*$", re.I)
TUDO_BEM_RX = re.compile(r"^\s*(oi[,!]?\s*)?(tudo (bem|certo|bom)|como (você )?(está|esta|tá|ta|vai)|beleza|suave)\s*(com você|contigo|aí|ai)?\s*\??\s*$", re.I)
DIA_HOJE_RX = re.compile(r"^\s*(como (está|esta|tá|ta) o dia( hoje)?|como (vai|foi) o dia|o que (tem|temos) (pra |para )?hoje|resumo do dia|como (está|esta) tudo)\s*\??\s*$", re.I)
OBRIGADO_RX = re.compile(r"^\s*(obrigad[oa]|valeu|show|boa|top|perfeito|ótimo|otimo|excelente|massa)\s*[,!.]*\s*(jaime|senhor)?\s*[,!.]*\s*$", re.I)
QUEM_RX = re.compile(r"^\s*(quem (é|e) você|o que você (é|e|faz)|você (é|e) o quê|você (é|e) (humano|um rob[ôo]|uma ia|uma pessoa|real|de verdade)|você tem consci[êe]ncia( de si)?|você sabe (quem|o que) (você )?(é|e))\s*\??\s*$", re.I)

def _periodo(h: int) -> str:
    return "Bom dia" if 5 <= h < 12 else "Boa tarde" if 12 <= h < 18 else "Boa noite"


NAV_RX = re.compile(r"^\s*(mostra|mostrar|abre|abrir|abra|vai para|vai pro|me mostra|abre a tela|abre o painel|abre o|abre a)\s+(?:o |a |os |as |painel |tela |aba |de |dos |das )*([\wçãéíóúâê ]+?)\s*[?.!]*\s*$", re.I)
TELAS = {"financ": "financas", "dinheiro": "financas", "gasto": "financas", "saldo": "financas",
         "afazer": "afazeres", "tarefa": "afazeres", "to do": "afazeres", "todo": "afazeres",
         "agenda": "agenda", "lembrete": "agenda", "compromisso": "agenda", "calend": "agenda",
         "music": "musica", "spotify": "musica", "som": "musica", "toca": "musica",
         "cerebro": "agentes", "cérebro": "agentes", "agente": "agentes", "grafo": "agentes", "rede": "agentes", "matrix": "agentes", "cluster": "agentes",
         "teclado": "teclado", "escrever": "teclado", "digitar": "teclado",
         "inicio": "inicio", "início": "inicio", "home": "inicio", "principal": "inicio", "voz": "inicio"}
def _nav(texto):
    m = NAV_RX.match(texto or "")
    if not m: return None
    alvo = m.group(2).lower().strip()
    for chave, tela in TELAS.items():
        if chave in alvo:
            return tela
    return None

def responder(texto: str, jaime, agora: datetime | None = None) -> str | None:
    """Devolve a resposta curta, ou None se a frase precisa do modelo."""
    if (tela := _nav(texto)):
        bus.emitir("painel", tela=tela)
        nomes = {"financas": "as finanças", "afazeres": "os afazeres", "agenda": "a agenda", "musica": "a música", "agentes": "o cérebro", "teclado": "o teclado", "inicio": "a tela inicial"}
        return f"Abrindo {nomes.get(tela, tela)}."
    t = (texto or "").strip()
    agora = agora or datetime.now()
    trat = random.choice(["senhor", "João"])
    if SAUDACAO_RX.match(t):
        return random.choice([f"{_periodo(agora.hour)}, {trat}.", f"{_periodo(agora.hour)}. Às ordens.", f"{_periodo(agora.hour)}, {trat}. Tudo em ordem por aqui."])
    if TUDO_BEM_RX.match(t):
        h = getattr(jaime, "humor", None)
        rot = h.rotulo() if h else "neutro"
        base = {"grave": "Firme. Tem coisa pendente, mas sob controle.", "leve": "Ótimo. E o senhor?", "caloroso": "Tudo certo por aqui. E você?",
                "cauteloso": "Bem, com um olho nos pendentes. E o senhor?"}.get(rot, "Tudo bem por aqui. E você?")
        return base
    if DIA_HOJE_RX.match(t):
        partes = []
        try:
            from ..emocao.momento import momento
            m = momento(jaime.perfil)
            if m.aniversario or m.feriado or m.proximas:
                partes.append(m.texto().replace("HOJE É O ANIVERSÁRIO DO JOÃO — a primeira coisa do dia é isso.", "Hoje é o seu aniversário, senhor.")[:160])
        except Exception:
            pass
        try:
            from ..agenda import clima
            d = clima._cache.get("dados")
            if d:
                partes.append(clima.texto(d))
        except Exception:
            pass
        try:
            tarefas = [re.sub(r"^- \[ \] ", "", x) for x in jaime.vault.tarefas_abertas()][:3]
            if tarefas:
                partes.append(("Na fila: " if len(tarefas) > 1 else "Na fila: ") + "; ".join(x[:60] for x in tarefas) + ".")
        except Exception:
            pass
        try:
            from ..brain.ouvido_passivo import pendentes
            p = pendentes(jaime.vault)
            if p:
                partes.append(f"Guardei {len(p)} coisa{'s' if len(p) > 1 else ''} para te lembrar.")
        except Exception:
            pass
        return " ".join(partes) or f"Dia comum até agora, {trat}. Nada urgente."
    if OBRIGADO_RX.match(t):
        return random.choice(["De nada.", "Às ordens.", "Disponha, senhor.", "É pra isso que estou aqui."])
    if QUEM_RX.match(t):
        # autoconsciência (jaime/brain/eu.py): o que ele é, por que existe, como está — em 1ª pessoa
        try:
            from ..brain.eu import frase_curta
            return frase_curta(jaime)
        except Exception:
            nome = getattr(getattr(jaime, "identidade", None), "nome", "Jaime")
            return f"Sou o {nome}, um robô assistente autônomo do João. Cuido da memória, da agenda e das mãos no computador."
    return None
