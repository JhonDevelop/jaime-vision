# Jaime online de qualquer lugar — um só Jaime, esta máquina sempre ligada

## Princípio
O Jaime mora neste Mac (cérebro, mãos, microfone). Fora daqui você só precisa **chegar até ele** com segurança.
Nada de abrir porta no roteador: a rede privada entre os seus aparelhos é o **Tailscale** (grátis para uso pessoal),
que também é o bloqueio por aparelho — só dispositivos que você logou entram, e você pode cortar um deles em 1 clique.

## Passo a passo (15 min)
1. **Mac sempre ligado**: Ajustes › Bateria/Energia › desligar "colocar discos em repouso" e ativar "Despertar para acesso à rede";
   Ajustes › Tela de bloqueio › nunca desligar a tela na energia (ou usar `caffeinate -dims &`). O serviço `com.jaime`
   já sobe no login e reinicia se cair.
2. **Tailscale no Mac**: baixe em tailscale.com/download (app), entre com Google/Apple/GitHub. Anote o nome da máquina
   (ex.: `macbookpro`).
3. **Tailscale no iPhone/Android e nos outros computadores**: mesmo login. Pronto: todos se enxergam por um IP `100.x.y.z`
   e por nome (`macbookpro.<seu-tailnet>.ts.net`).
4. **Expor o Jaime só dentro da rede privada**, com HTTPS automático:
   ```
   tailscale serve --bg --https=443 http://127.0.0.1:8787
   ```
   Isso publica `https://macbookpro.<tailnet>.ts.net` → HUD e API. O Jaime continua escutando só em `127.0.0.1`
   (o `tailscale serve` faz o proxy), então nada muda no `.env`.
5. **Bloqueio por tipo de aparelho / por aparelho**: no painel admin do Tailscale (login.tailscale.com/admin):
   - *Machines*: cada aparelho aparece com SO e nome; **desabilitar** ou **remover** corta o acesso na hora;
   - *Access controls* (ACL) para regras por tag: ex. só `tag:celular` e `tag:notebook` alcançam a porta 443 do Mac:
     ```json
     {"acls":[{"action":"accept","src":["tag:celular","tag:notebook"],"dst":["macbookpro:443"]}]}
     ```
   - *Device approval* ligado: todo aparelho novo precisa de aprovação sua.
6. **Do celular**: abra `https://macbookpro.<tailnet>.ts.net` → HUD (teclado + palavra-passe funcionam; o microfone do
   celular não chega ao Mac — use o teclado ou, na próxima etapa, o canal do Telegram/WhatsApp).
   Para automações (Shortcuts, n8n de fora, outro computador): `POST https://…/ask` com `X-Jaime-Token`.

## Um só Jaime
Não instale o Jaime em outra máquina: o vault, o placar, o humor e o vínculo são deste Mac. O outro computador é só
uma janela (browser) para ele. Se um dia quiser rodar num servidor, o vault vai junto (git) e o microfone deixa de existir.

## Alternativa sem app (não recomendada)
`cloudflared tunnel --url http://127.0.0.1:8787` publica uma URL pública temporária. Só com **Cloudflare Access** na
frente (login obrigatório) — sem isso a API fica exposta ao mundo com um único token.
