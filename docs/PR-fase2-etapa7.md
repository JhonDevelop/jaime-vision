# PR — Fase 2, etapa 7: mãos — browser, projetos, arquivos

**Branch:** `feat/fase2-maos` → `main`

## O que muda
- `jaime/maos/browser.py`: Playwright com perfil persistente (`~/Jaime/browser-profile`), janela própria do Jaime.
  Ferramentas MCP `maos`: `abrir`, `ler_pagina`, `clicar`, `preencher`, `extrair`, `screenshot`.
- Vigia: cliques em enviar/comprar/pagar/confirmar/assinar/checkout/excluir (texto ou `submit`) e `mover` esperam "confirmo".
- `projetos.py`: `criar_projeto(nome, tipo)` — pasta no `JAIME_WORKSPACE`, git init + commit, README, `.env.example`,
  `CLAUDE.md`, nota em `20-Projetos/` pelo template.
- `arquivos.py`: regras em `10-Eu/Jeito.md › ## Arquivos`; `organizar_arquivos` propõe, `mover` executa com confirmo.
- `python -m jaime skills instalar`: skills oficiais pdf/docx/xlsx/pptx em `.claude/skills/`.
- Instalado: `playwright` + Chromium.

## Como testar
```
pytest -q                                   # 70 testes; inclui browser headless num site local (file://)
# HUD: "abre o site da Evolution API e me diz o que é" · "cria o projeto Radar BUB em python" · "organiza a pasta Downloads"
```

## Critério §3 linha 7
"cria o projeto X" gera pasta + git + nota (teste `test_criar_projeto_python`); Playwright abre e extrai dados de um site
(teste `test_browser_le_clica_e_extrai_site_local`).
