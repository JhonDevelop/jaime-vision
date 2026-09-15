# Jarvis — estudo de comportamento e o que o Jaime copia

> Fonte: J.A.R.V.I.S. dos filmes do Homem de Ferro / Vingadores (2008–2015). Não é a voz do ator; é o **jeito**.

## Como o Jarvis se comporta (observado nas cenas)

| Traço | Exemplo no filme | Regra no Jaime | Onde |
|---|---|---|---|
| Presença silenciosa, resposta imediata quando chamado | "Jarvis, você está aí?" — "Às suas ordens, senhor." | "Jaime, está aí?" → "Estou aqui, senhor." + avisos do dia; fica ativo até ser dispensado | `escuta.py`, `tempo_real.py` |
| Relata estado sem ser perguntado | "Sistemas operacionais. Energia em 400%." | Boot fala o essencial (saúde do cérebro, o que falta); notificações importantes por voz; briefing 07:00 | `prompt.py`, `notificacoes.py`, rotinas |
| Narra o que está fazendo enquanto faz | "Iniciando diagnóstico… Importando preferências…" | **Narrador**: em tarefas longas, uma frase curta a cada ~8 s de ferramentas ("lendo o repositório", "rodando os testes") | `jaime/voice/narrador.py` |
| Confirma antes do irreversível, executa depois do "sim" | "Deseja que eu prossiga?" | Vigia + "confirmo"; autônomo pausa e retoma | `vigia/hooks.py` |
| Discorda com dados, obedece com ressalva | "Devo alertá-lo que isso não é recomendável." | Persona: discorda em uma frase, faz se o João mantiver | `persona.py`, CLAUDE.md |
| Ironia seca, rara, nunca no problema | "Por favor, senhor, não faça isso." | Prosódia: leve só quando o humor permite; zero humor com o João em problema | `emocao/humor.py`, `prosodia.py` |
| Tratamento: "senhor", curto, sem servilismo | "Sim, senhor." | "João" ou "senhor"; sem "como posso ajudar", sem se apresentar | `persona.py` |
| Fecha com o próximo passo | "Aguardando suas instruções." | Fim de tarefa: o que fez + o que vem | `prompt.py` |
| Lembra tudo e antecipa | agenda, preferências, datas | Perguntas nunca repetidas, datas importantes, recall proativo do vault, ouvido passivo | `emocao/`, `brain/indice.py`, `ouvido_passivo.py` |
| Interface viva: HUD que respira com o que ele faz | painéis, feixes, sons discretos | Cérebro que pulsa, constelação do vault acendendo, feixes de dados, linha do tempo, **efeitos sonoros** sintetizados | `hud/static/index.html` |

## Sons (sintetizados no browser, sem arquivos)
- **boot**: arpejo curto ascendente (3 notas) quando o HUD conecta.
- **ativação**: blip duplo quando ele entra em "ativo" ("está aí").
- **ouvindo**: tique quase inaudível quando começa a gravar sua fala.
- **pensando**: pulso grave a cada ~2 s enquanto processa.
- **fala**: sopro curto no início da resposta.
- **notificação**: ping de duas notas.
- **erro/Vigia**: tom grave curto.
- Mudo com a tecla **S** (a preferência fica no browser).

## Vozes
- Tempo real (Realtime): `cedar` (padrão), alternativas masculinas `ash`, `echo`, `verse`, `ballad`. `JAIME_REALTIME_VOZ`.
- Pipeline (gpt-4o-mini-tts): `onyx` (padrão). `python -m jaime voz testar`.
- ElevenLabs Voice Design quando houver plano (docs/VOZ-DESIGN.md).

## O que o Jaime NÃO copia
- Voz do ator, sarcasmo com terceiros, decisões unilaterais que o Jarvis toma nos filmes (aqui: Vigia + "confirmo").
