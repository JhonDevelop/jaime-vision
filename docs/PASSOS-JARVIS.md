# Os 9 passos do vídeo, no J.A.I.M.E

O vídeo ensina a montar um "Jarvis" em 9 passos. Esta tabela diz onde cada passo já existe no Jaime, o que foi
feito agora (30/09/2026) e o que ainda depende do João. Os passos são do vídeo; o "como" é do Jaime.

| # | Passo do vídeo | No Jaime | Estado |
|---|---|---|---|
| 1 | Um lar para ele (notebook velho ou servidor na nuvem) | O Mac hoje (serviço `com.jaime`, LaunchAgent); o Windows depois (reinstalação) | ✅ Mac rodando · ⏳ Windows |
| 2 | Escolher a IA (ChatGPT, Claude, Gemini) | Os três: Central = Claude, Esquerdo = Codex, Direito = Gemini/Antigravity; Córtex decide por tarefa e mede no placar; IA local por rota explícita | ✅ |
| 3 | Um programa que transforma a IA em agente de verdade — "tipo o **Hermes Agent**" | Claude Agent SDK (mãos, MCP, Vigia) **+ Hermes Agent** como segundo par de mãos por delegação (`mcp__hermes__*`, docs/HERMES.md) | ✅ integração testada contra o Hermes real · ⏳ instalar no Windows (Mac Intel não é suportado pelo Hermes) |
| 4 | Ensinar quem você é e como funciona o seu trabalho | Vault `10-Eu/`, `20-Projetos/`, `00-Jaime/`; perguntas ao João (`mcp__emocao`); `hermes import-agent claude-code` leva as instruções para o Hermes | ✅ |
| 5 | Conectar nas ferramentas: e-mail, Google Agenda, Notion, navegador | `jaime/conexoes/google.py` (Gmail + Agenda + Drive), Notion (espelho), `jaime/maos/browser.py`, Spotify, Home Assistant/Alexa | ✅ · ⚠ Notion devolvendo 404 (página do espelho) · ⚠ token do Spotify expirado |
| 6 | Memória "como o Letta", para ele nunca esquecer | Vault (memória longa) + Mente contínua (`01-Estado/Pensamentos.md`) + memória semântica; o Hermes tem a memória dele (MEMORY.md, sessões com busca) | ✅ |
| 7 | Habilidades para coisas específicas (design, edição…) | 38 skills em `.claude/skills/` + ~650 agentes em `.claude/agents/`; o Hermes traz as skills dele e importa as nossas | ✅ |
| 8 | Colocar no WhatsApp ou Telegram e dar voz (Hermes ou ElevenLabs) | Telegram (`conexoes/telegram.py`), WhatsApp (Evolution API), voz duplex com TTS (ElevenLabs/OpenAI/afplay) | ✅ · ⏳ `ELEVENLABS_API_KEY` |
| 9 | O toque final: montar numa tela (Claude Design) e ligar a voz | **Tela Jarvis** `/hud/jarvis` (docs/TELA-JARVIS.md): orbe, "FALANDO", briefing do bom dia com cards sincronizados com a voz, "ativar monitor", holograma com a mão, orbe de partículas | ✅ (validado com demo e navegador; ⏳ câmera física e voz real no Mac/Windows) |

## O que falta o João fazer (uma vez)
1. **Windows**: instalar o Jaime e rodar `scripts/hermes/instalar.ps1` (o Hermes pede o provedor de modelo no `hermes setup`).
2. **Bibliotecas da câmera**: `python -m jaime jarvis baixar` (face-api + MediaPipe, ~34 MB, ficam na máquina).
3. **Rosto**: dizer "aprende meu rosto" com a tela Jarvis aberta (serve para cortesia; nunca destranca nada).
4. **Treino/saúde**: no iPhone, app *Health Auto Export* → REST API → `http://<máquina>:8787/webhook/saude` com o
   cabeçalho `X-Jaime-Token` (precisa de `JAIME_BIND` aberto ou de um túnel; ver docs/TELA-JARVIS.md).
5. **Chaves pendentes**: `ELEVENLABS_API_KEY` (voz), renovar Spotify, conferir a página do Notion.
