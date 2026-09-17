"""Narrador — em tarefas longas, o Jaime diz em voz o que está fazendo, como o Jarvis ("iniciando diagnóstico…").

Observa os eventos de ferramenta do turno atual; se a resposta ainda não começou e já passaram NARRAR_A_CADA_S
segundos desde a última narração, fala UMA frase curta derivada da ferramenta. Nunca narra duas vezes a mesma coisa
seguida, nunca em turnos curtos (< PRIMEIRA_S), e para quando a fala de verdade começa."""
from __future__ import annotations
import re, time

PRIMEIRA_S = 2.5          # narra antes de a muleta pensar em disparar (MULETA_S = 5 s), porque dizer
                          # "lendo os arquivos" é verdade sobre o que ele faz, e "deixa eu ver" é enfeite.
                          # Quem está trabalhando conta o que está fazendo; quem não está, fica quieto.
NARRAR_A_CADA_S = 8.0

# O que ele NUNCA narra, por mais que demore: a contabilidade interna dele.
#
# Pedido do João em 17/09, o terceiro seguido da mesma família («não quero que ele fique me falando gemini
# ou codex entregou», «eu digo coisas básicas e ele fica ok um segundo», e agora «não quero que ele fique
# me avisando sobre: escrevendo no vault, não quero saber isso»). A regra que sai dos três é uma só:
#
#     ele narra o que o JOÃO pediu, não o que ELE precisa fazer para lembrar.
#
# Escrever no vault, ler a própria memória e atualizar o próprio estado são o equivalente a uma pessoa
# anotando na agenda enquanto conversa: acontece, é necessário, e ninguém comenta em voz alta. O painel do
# cockpit continua mostrando tudo — quem quiser ver, vê; quem não quiser ouvir, não ouve.
SILENCIOSAS = (
    r"^mcp__cerebro__",       # lembrar, registrar_diario, criar_tarefa, buscar_memoria, ler_nota, ler_estado…
    r"^mcp__mente__",         # pensar por conta própria é dele, não é recado
    r"^mcp__emocao__",        # humor e datas: leitura interna
    r"^mcp__meta__",          # instrumentação de si mesmo
    r"^mcp__espelho__",       # sincronizar o espelho é manutenção
)

FRASES = [
    (r"^Bash$", "rodando um comando"),
    (r"^(Read|Glob|Grep)$", "lendo os arquivos"),
    (r"^(Write|Edit|MultiEdit)$", "escrevendo o código"),
    (r"^Task$", "delegando a um maester"),
    (r"^Web(Search|Fetch)$", "pesquisando na web"),
    (r"^mcp__maos__(abrir|ler_pagina|clicar|preencher|extrair)", "no browser"),
    (r"^mcp__maos__criar_projeto", "criando o projeto"),
    (r"^mcp__google__email", "olhando os e-mails"),
    (r"^mcp__google__agenda", "olhando a agenda"),
    (r"^mcp__midia__gerar_imagem", "gerando a imagem"),
    (r"^mcp__midia__(cortar|legendar|ver)_video", "processando o vídeo"),
    (r"^mcp__tela__", "olhando a tela"),
    (r"^mcp__casa__", "falando com a casa"),
    (r"^mcp__estudo__", "no laboratório"),
    (r"^mcp__evolucao__", "revendo o próprio código"),
]

def frase_para(ferramenta: str, alvo: str = "") -> str:
    # O silêncio vem ANTES da lista, não depois: assim nenhuma frase nova consegue reintroduzir a
    # contabilidade interna por descuido, e uma regra larga (^mcp__tela__ e companhia) não pega uma
    # ferramenta de memória de raspão.
    for rx in SILENCIOSAS:
        if re.match(rx, ferramenta or ""):
            return ""
    for rx, f in FRASES:
        if re.match(rx, ferramenta or ""):
            if f == "rodando um comando" and alvo:
                cmd = alvo.strip().split()[0] if alvo.strip() else ""
                if cmd in ("pytest", "python", "npm", "git", "open", "osascript", "ls", "cat", "grep", "find"):
                    return {"pytest": "rodando os testes", "python": "rodando um script", "npm": "instalando dependências", "git": "mexendo no git",
                            "open": "abrindo o app", "osascript": "controlando o app", "ls": "olhando as pastas", "cat": "lendo um arquivo",
                            "grep": "procurando no código", "find": "procurando arquivos"}[cmd]
            return f
    return ""

class Narrador:
    def __init__(self, falar, primeira_s: float = PRIMEIRA_S, a_cada_s: float = NARRAR_A_CADA_S, relogio=time.time):
        self.falar, self.primeira_s, self.a_cada_s, self.relogio = falar, primeira_s, a_cada_s, relogio
        self.inicio = 0.0; self.ultima = 0.0; self.ultima_frase = ""; self.ativo = False; self.n = 0

    def comecar(self):
        self.inicio = self.relogio(); self.ultima = self.inicio - self.a_cada_s; self.ultima_frase = ""; self.ativo = True; self.n = 0

    def parar(self):
        self.ativo = False

    def evento(self, ferramenta: str, alvo: str = "") -> str | None:
        """Chamado a cada evento de ferramenta. Devolve a frase narrada, ou None."""
        if not self.ativo:
            return None
        agora = self.relogio()
        if agora - self.inicio < self.primeira_s or agora - self.ultima < self.a_cada_s:
            return None
        f = frase_para(ferramenta, alvo)
        if not f or f == self.ultima_frase:
            return None
        self.ultima, self.ultima_frase = agora, f; self.n += 1
        texto = f.capitalize() + "…" if self.n == 1 else f.capitalize() + "."
        self.falar(texto)
        return texto
