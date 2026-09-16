# Agentes do J.A.I.M.E — 314

## Os 12 maesters (escritos para o Jaime, em português)
`maester-agenda` `maester-arquiteto` `maester-arquivista` `maester-back` `maester-comms`
`maester-dados` `maester-debug` `maester-dev` `maester-front` `maester-jaime` `maester-ops`
`maester-seguranca`

Primeira escolha sempre: conhecem o vault, o Vigia, o cockpit e o jeito da casa.

## O acervo (302 especialistas)
De **VoltAgent/awesome-claude-code-subagents** e **wshobson/agents**, ambos MIT
(`LICENSE-VoltAgent.txt`, `LICENSE-wshobson.txt`), baixados em 16/09/2026. Nenhum entrou cru:

1. **Preâmbulo em português** com as regras da casa: responder em pt-BR; nada irreversível sem o
   "confirmo" do João; segredo nunca sai; não mexer em `vault/00-Jaime/` nem em `jaime/vigia/`;
   entregar em três linhas.
2. **Protocolo do "context manager" removido** — no original, todo agente começava consultando um
   coordenador que não existe aqui. No lugar, o preâmbulo manda ler o vault.
3. **`description` entre aspas** em todos (dois-pontos solto quebra o YAML).
4. **Dedupe**: 56 agentes do wshobson foram pulados por repetirem capacidade já coberta.
5. **Prefixo do plugin removido** dos nomes do wshobson (`backend-development-backend-architect`
   virou `backend-architect`).

### Fora, por segurança
| arquivo | motivo |
|---|---|
| `healthcare-admin` | mandava instalar script remoto com `curl \| bash` |
| `scientific-literature-researcher` | apontava para servidor MCP de terceiro (bgpt.pro) |
| `protect-mcp__receipt-verifier` | serviço pago de terceiro (veritasacta.com) |
| `social-publishing-publisher` | serviço pago de terceiro (getsocialclaw.com) |

Varredura completa antes de instalar: **nenhuma tentativa de injeção de prompt**. As ocorrências de
`rm -rf` e `sudo` estavam todas em texto de orientação (como usar `--` com segurança, `trap` de
limpeza, lista de comandos a negar) ou em documentação de perícia, nunca como ordem.

## O custo — leia isto se ele ficar lento
A `description` de **todos** os agentes e skills entra no contexto a cada turno: hoje **~41 mil
tokens**. Para medir e cortar:

```bash
bash jaime/ops/enxugar-acervo.sh                                   # só mede
bash jaime/ops/enxugar-acervo.sh --tirar windows powershell azure  # corta
git checkout .claude/                                              # desfaz
```
