---
name: ferramenta-falha-repetidamente-tool-use-error-error-no-such-tool-available-glob-glob-is-not-available-in-th
description: Qualquer sessão/ambiente Claude Code onde a tool Glob esteja ausente do toolset (sessões restritas, containers custom, harness com allowlist de tools 
---

Quando receber tool_use_error dizendo que uma tool X não está disponível nesta sessão: (1) não repita a chamada a X — trate como falha permanente para a sessão inteira, não transitória; (2) leia a mensagem de erro, ela geralmente já sugere a ferramenta alternativa (aqui: Bash+find); (3) se for Glob especificamente, use o script /tmp/jaime-lab/P-0007/glob.sh '<padrão>' [dir_base] que emula **/*.ext, dir/**/*.ext, *.ext e dir/*.ext via find, ordenado por mtime desc; (4) generalize: mantenha um registro mental de 'tools indisponíveis nesta sessão' e não as tente de novo até o fim da sessão.
