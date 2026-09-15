# Ferramenta falha repetidamente: Input validation error: 'corpo' is a required property

> Resolvido pelo cérebro de estudo em 15/09/2026 (problema P-0002, origem ferramenta_falhou).

## Como reproduzir
Chamar uma ferramenta MCP cujo inputSchema tenha 'corpo' em 'required' passando um payload sem a chave 'corpo' (ex.: usando 'mensagem'/'texto'/'body'/'conteudo' no lugar, ou omitindo o campo). O validador jsonschema do servidor rejeita com 'Input validation error: <campo> is a required property'.

## O que resolveu
Reproduzido em /tmp/jaime-lab/p0002_repro.py: confirmei que o erro vem do validador jsonschema (Draft7Validator) checando 'required' do inputSchema da ferramenta. A causa é enviar a chave errada (ex. 'mensagem' em vez de 'corpo') ou omiti-la. Corrigindo para usar exatamente a chave 'corpo' exigida pelo schema, a chamada passa a validar e funcionar.

## Onde se aplica
Qualquer chamada de ferramenta (MCP ou tool custom) cujo inputSchema declare um campo obrigatório chamado 'corpo' — tipicamente ferramentas de envio de mensagem/e-mail/nota em pt-BR. Antes de reusar, confirmar o nome exato e o schema da ferramenta real em produção (não visível a partir do laboratório).
