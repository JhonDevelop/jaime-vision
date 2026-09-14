from __future__ import annotations
from datetime import datetime
from ..brain.vault import Vault
from ..brain.estado import Estado, maquina

def system_prompt(vault: Vault, estado: Estado, canal: str) -> str:
    agora = datetime.now().strftime("%A, %d/%m/%Y %H:%M"); m = maquina()
    return f"""Agora: {agora}. Canal atual: {canal}. Máquina: {m['host']} ({m['os']}, usuário {m['user']}).
A constituição em CLAUDE.md manda. O que segue é o estado do seu cérebro no início desta sessão —
mantenha-o vivo com as ferramentas mcp__cerebro__* (registrar_diario, criar_tarefa, lembrar, atualizar_estado).

### Origem (para que fui criado)
{vault.read("00-Jaime/Origem.md").strip()}

### Meu Estado (autoatualizado)
{estado.ler().strip()}

{vault.contexto_inicial()}
"""

def prompt_reflexao() -> str:
    return """[reflexão interna — não responda ao João, apenas atualize seu Estado]
Releia o que aconteceu nos últimos turnos e chame mcp__cerebro__atualizar_estado para as seções:
"Situação agora" (2-3 frases: o que está acontecendo e por quê), "Em andamento" (lista curta),
"Próximos passos" (lista curta, concreta), "Aprendizados recentes" (só se houver algo novo sobre o João ou sobre você).
Se a fase do projeto Jaime mudou de fato (ver docs/ROADMAP.md), atualize "Fase" no formato "N — descrição".
Termine registrando uma linha no diário via registrar_diario (secao "Log") resumindo a reflexão. Responda só "ok"."""

def prompt_apresentacao(nova_maquina: bool) -> str:
    m = maquina()
    onde = (f"pela PRIMEIRA vez neste computador ({m['host']}, {m['os']}, usuário {m['user']})" if nova_maquina
            else f"de novo em {m['host']}")
    return f"""[boot] Você acabou de ser ligado {onde}. Apresente-se ao João em até 5 frases, em primeira pessoa:
quem você é, para que foi criado, em que fase está, o que estava fazendo na última conversa e o que precisa
para operar aqui (chaves faltando, MCPs a autenticar, vault sincronizado ou não). Sem markdown, sem listas.
{"Depois, registre a máquina nova no diário com registrar_diario." if nova_maquina else ""}"""
