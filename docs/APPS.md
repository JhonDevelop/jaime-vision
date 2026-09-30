# Apps de criação, arquivos 3D e impressão

MCP `apps` (`jaime/maos/tools_apps.py`) — o cérebro usa; a voz também, pelas cenas do Jarvis.

| Ferramenta | O que faz | Trava |
|---|---|---|
| `apps_instalados` | lista Photoshop, Premiere, Illustrator, After Effects, Blender, DaVinci, CapCut, Figma, Canva, WhatsApp, Bambu… | livre |
| `app_abrir` | abre o app (com arquivo, se houver); Canva/Figma sem app abrem na web | livre |
| `photoshop_script` | ExtendScript no Photoshop (AppleScript `do javascript` no Mac, COM no Windows) | salvar por cima, apagar, fechar sem salvar, `system()` → Vigia |
| `premiere_sequencia` | cortes em ordem → XML do Final Cut 7 → abre no Premiere (importa como sequência) | livre (arquivo novo) |
| `holograma`, `holograma_editar`, `holograma_exportar`, `holograma_imprimir` | o estúdio da tela Jarvis (docs/TELA-JARVIS.md) | imprimir só abre o fatiador |

E-mail e WhatsApp na tela: "abre minha caixa de entrada" (Gmail, com triagem do que pede ação) e "mostra as
mensagens do WhatsApp" (lidas das notificações do computador — o Jaime não entra no WhatsApp). Com visita na
linha ou na câmera, essas duas cenas não abrem.

Canva: `JAIME_CANVA=on` liga o servidor MCP oficial da Canva (`https://mcp.canva.com/mcp`). Na primeira vez é
preciso autorizar a conta Canva (OAuth). **Pendente de validação** nesta máquina: se o login não aparecer pelo Jaime,
use `app_abrir canva` (web) até configurarmos.

Pendentes de validação física (não dá para testar na nuvem): Photoshop/Premiere instalados de verdade, o fatiador
abrindo o STL, o Blender importando o GLB.
