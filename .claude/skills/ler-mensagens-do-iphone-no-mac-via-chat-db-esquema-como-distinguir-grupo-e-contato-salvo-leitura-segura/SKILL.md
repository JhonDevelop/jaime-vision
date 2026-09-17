---
name: ler-mensagens-do-iphone-no-mac-via-chat-db-esquema-como-distinguir-grupo-e-contato-salvo-leitura-segura
description: Próximo passo do roadmap: módulo de leitura de Mensagens do .venv/bin/python (Full Disk Access já liberado) — usar attributedbody.py como decoder e as
---

Para decodificar attributedBody do chat.db: 1) localizar bytes 0x01 0x2b (início) e 0x86 0x84 (fim) no blob; 2) decodificar UTF-8 o trecho entre eles (fallback errors='replace' se inválido); 3) descartar 1 caractere do início (3 se caiu no fallback) — esse é o byte de tamanho embutido. Para grupo vs 1:1: chat.guid contém ';+;' (grupo) ou ';-;' (individual). Para nome de contato: juntar handle.id com AddressBook-v22.abcddb (ZABCDRECORD/ZABCDPHONENUMBER/ZABCDEMAILADDRESS), casando e-mail direto e telefone pelos últimos 10-11 dígitos normalizados. Para abrir sem travar o Mensagens: sqlite3.connect(f'file:{path}?mode=ro', uri=True) + PRAGMA busy_timeout=5000 + PRAGMA query_only=TRUE, nunca immutable=1 nem copiar o arquivo por padrão.
