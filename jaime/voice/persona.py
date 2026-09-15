"""Persona de voz — como o Jaime fala (docs/FASE-2-JARVIS.md §2.7). Pós-processador de tudo que vai para o TTS.

Regras: nada de "Olá, sou o Jaime, seu assistente"; sem saudação de abertura repetida; sem "Como posso ajudar?"
de fechamento; sem muletas de assistente ("Claro!", "Com certeza!", "Ótima pergunta"); chama de "João"
(nunca "senhor" — só se ele pedir); sem markdown, URL ou lista (isso `limpar_para_fala` já tira).
O que dá o efeito Jarvis é 70% jeito de falar: frases curtas, seco, fecha com o próximo passo."""
from __future__ import annotations
import re

APRESENTACAO_RX = re.compile(r"^\s*(ol[aá]|oi|e a[ií])[,!.\s]*(jo[aã]o[,!.\s]*)?(eu\s+)?sou\s+o\s+jaime[^.!?]*[.!?]\s*", re.I)
SAUDACAO_RX = re.compile(r"^\s*(ol[aá]|oi|opa|e a[ií]|bom dia|boa tarde|boa noite)[,!.\s]+(jo[aã]o[,!.\s]+)?", re.I)
MULETAS_RX = re.compile(r"^\s*(claro|com certeza|certamente|[óo]tima pergunta|boa pergunta|sem problemas?|perfeito|excelente|entendido|entendi)[,!.\s]+", re.I)
FECHOS_RX = re.compile(r"\s*(como posso (te )?ajudar( hoje)?|posso ajudar em (mais )?algo( mais)?|precisa de (mais )?alguma coisa|em que (mais )?posso ajudar|qualquer coisa,? (é só|me) (chamar|falar|avisar)|estou à disposição|fico à disposição)[^.!?]*[.!?]?\s*$", re.I)
SENHOR_RX = re.compile(r"\bsenhor\b", re.I)

def aplicar(texto: str, primeira_do_dia: bool = False, permitir_senhor: bool = False) -> str:
    t = texto.strip()
    if not t:
        return t
    t = APRESENTACAO_RX.sub("", t)
    if not primeira_do_dia:
        t = SAUDACAO_RX.sub("", t)
    t = MULETAS_RX.sub("", t)
    t = FECHOS_RX.sub("", t)
    if not permitir_senhor:
        t = SENHOR_RX.sub("João", t)
    t = t.strip()
    if t and t[0].islower():
        t = t[0].upper() + t[1:]
    return t
