---
name: ferramenta-falha-repetidamente-input-validation-error-corpo-is-a-required-property
description: Qualquer chamada de ferramenta (MCP ou tool custom) cujo inputSchema declare um campo obrigatório chamado 'corpo' — tipicamente ferramentas de envio d
---

Antes de chamar qualquer ferramenta nova ou pouco usada, primeiro liste/leia o inputSchema completo dela (nomes exatos e 'required') em vez de assumir nomes de campo por analogia (ex. 'body'→'corpo', 'text'→'texto'). Se um erro 'Input validation error: X is a required property' aparecer, trate como sinal de mismatch de nome de campo: (1) busque o schema real da ferramenta, (2) compare a lista 'required' com as chaves que você enviou, (3) corrija o nome da chave (não só adicione um valor genérico), (4) refaça a chamada. Isso evita repetir a mesma falha em ferramentas com nomenclatura em português.
