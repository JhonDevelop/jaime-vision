---
name: notificacoes-do-instagram-num-mac-intel-por-onde-chegam-e-qual-o-formato-na-central-de-notificacoes
description: jaime/ops/notificacoes.py (filtro por app_id/titl/subt/body); qualquer Mac Intel do João ou de outro usuário rodando os mesmos 2 comandos de diagnósti
---

Diagnóstico de notificações no Mac: (1) system_profiler SPiBridgeDataType → confirma T2/Espelhamento do iPhone; (2) sqlite3 no banco do usernoted (~/Library/Group Containers/group.com.apple.usernoted/db2/db), tabela app (app_id, identifier) pra mapear bundle ids/origens já registrados, tabela record (data = bplist com req.titl/req.subt/req.body) decodificado via plistlib em Python; (3) web push por-origem no Safari usa identifier '_web_center_:web.<host>', Chrome usa bundle id genérico fixo sem origem — útil pra qualquer investigação futura de notificacoes.py.
