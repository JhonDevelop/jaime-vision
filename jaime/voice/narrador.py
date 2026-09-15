"""Narrador — em tarefas longas, o Jaime diz em voz o que está fazendo, como o Jarvis ("iniciando diagnóstico…").

Observa os eventos de ferramenta do turno atual; se a resposta ainda não começou e já passaram NARRAR_A_CADA_S
segundos desde a última narração, fala UMA frase curta derivada da ferramenta. Nunca narra duas vezes a mesma coisa
seguida, nunca em turnos curtos (< PRIMEIRA_S), e para quando a fala de verdade começa."""
from __future__ import annotations
import re, time

PRIMEIRA_S = 5.0          # só narra se a tarefa já dura isto
NARRAR_A_CADA_S = 8.0

FRASES = [
    (r"^Bash$", "rodando um comando"),
    (r"^(Read|Glob|Grep)$", "lendo os arquivos"),
    (r"^(Write|Edit|MultiEdit)$", "escrevendo o código"),
    (r"^Task$", "delegando a um maester"),
    (r"^Web(Search|Fetch)$", "pesquisando na web"),
    (r"^mcp__maos__(abrir|ler_pagina|clicar|preencher|extrair)", "no browser"),
    (r"^mcp__maos__criar_projeto", "criando o projeto"),
    (r"^mcp__cerebro__(lembrar|registrar_diario|criar_tarefa)", "anotando no vault"),
    (r"^mcp__cerebro__(buscar_memoria|ler_nota|ler_estado)", "consultando a memória"),
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
