# Agentes do J.A.I.M.E

## Os maesters (escritos para o Jaime, em português)
`maester-agenda` `maester-arquitecto`* `maester-arquivista` `maester-back` `maester-comms`
`maester-dados` `maester-debug` `maester-dev` `maester-front` `maester-jaime` `maester-ops`
`maester-seguranca`

São estes que o Jaime usa por padrão: conhecem o vault, o Vigia, o cockpit e o jeito da casa.

## O acervo (159 especialistas)
Vindos de **VoltAgent/awesome-claude-code-subagents**, licença MIT (veja `LICENSE-VoltAgent.txt`),
baixados em 16/09/2026. Cada arquivo foi adaptado antes de entrar:

1. **Preâmbulo em português** no topo do corpo, com as regras da casa: responder em pt-BR; nada
   irreversível sem o "confirmo" do João; segredo nunca sai; não mexer em `vault/00-Jaime/` nem
   em `jaime/vigia/`; entregar em três linhas.
2. **Protocolo do "context manager" removido.** No original, todo agente começava consultando um
   agente `context-manager` que não existe aqui. No lugar, o preâmbulo manda ler o vault.
3. **`description` entre aspas** em todos (oito tinham dois-pontos solto, que quebra o YAML).
4. **Dois ficaram de fora**: `healthcare-admin` (mandava instalar script remoto com `curl | bash`)
   e `scientific-literature-researcher` (apontava para um servidor MCP de terceiro, `bgpt.pro`).

Varredura antes de instalar: nenhuma tentativa de injeção de prompt, nenhum `eval`, `base64 -d`,
`rm -rf` ou `sudo`; os únicos domínios citados eram o próprio GitHub.

As descrições somam ~8 mil tokens, que entram no contexto a cada turno. Se o Jaime ficar lento,
o corte é aqui: apagar as categorias que você não usa (idiomas que não programa, nuvem que não
tem) devolve a maior parte disso.
