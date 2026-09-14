from __future__ import annotations
from datetime import datetime
from ..brain.vault import Vault

def system_prompt(vault: Vault, canal: str) -> str:
    agora = datetime.now().strftime("%A, %d/%m/%Y %H:%M")
    return f"""Agora: {agora}. Canal atual: {canal}.
A constituição em CLAUDE.md manda. O que segue é o estado do seu cérebro no início desta sessão —
use as ferramentas mcp__cerebro__* para atualizar conforme a conversa avança.

{vault.contexto_inicial()}
"""
