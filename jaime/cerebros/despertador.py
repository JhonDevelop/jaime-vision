"""O despertador dos hemisférios — o Esquerdo e o Direito não podem viver dormindo.

O João foi direto ao ponto: hemisfério dormindo não aprende nem evolui, e isso é ruim. Antes, o Esquerdo e o
Direito só acordavam quando alguém pedia — e como quase nunca pediam, ficavam parados para sempre.

Agora este laço roda sozinho: acorda os dois (adotando terminal que já exista no canvas antes de criar mais um),
e, quando um deles está livre, dá a ele um item da PAUTA PRÓPRIA — trabalho real tirado dos problemas de estudo,
dos TODO do código e dos projetos sem nota. Assim cada lado produz, é avaliado, e o roteamento aprende.

Segurança: só acorda e delega; nada aqui é irreversível — o que os filhos fizerem continua passando pelo Vigia.
Sem Maestri aberto, o laço não faz nada e não reclama a cada volta; espera a próxima."""
from __future__ import annotations
import asyncio, os, time
from ..hud.events import bus

INTERVALO_S = int(os.environ.get("JAIME_DESPERTADOR_S", "1800"))     # de meia em meia hora
PRIMEIRA_S = 90                                                      # a primeira, logo depois do boot
DESCANSO_S = int(os.environ.get("JAIME_DESPERTADOR_DESCANSO_S", "5400"))  # não empilha trabalho no mesmo lado


async def rodar(jaime, ocioso=None) -> None:
    """Mantém os dois hemisférios acordados e com o que fazer. `ocioso()` diz se o João não está falando."""
    cerebros = getattr(jaime, "cerebros", None)
    if cerebros is None:
        return
    ultimo: dict[str, float] = {}
    await asyncio.sleep(PRIMEIRA_S)
    while True:
        try:
            livre = True
            if callable(ocioso):
                try:
                    livre = bool(ocioso())
                except Exception:
                    livre = True
            acordados_antes = cerebros.vivos()
            for h in ("esquerdo", "direito"):
                r = cerebros.acordar(h)
                if h not in acordados_antes and h in cerebros.vivos():
                    bus.emitir("cerebro", hemisferio=h, estado="acordou", detalhe=r[:90])
                    try:
                        jaime.vault.diario(f"Acordei o hemisfério {h}: {r[:120]}", "Log")
                    except Exception:
                        pass
                # dar trabalho só quando o João não está no meio de uma conversa
                if not livre or h not in cerebros.vivos():
                    continue
                if time.time() - ultimo.get(h, 0) < DESCANSO_S:
                    continue
                pauta = cerebros.pauta(h, 1)
                if not pauta:
                    continue
                ultimo[h] = time.time()
                bus.emitir("cerebro", hemisferio=h, estado="pensando", tarefa=pauta[0][:90])
                await asyncio.to_thread(cerebros.delegar, h, pauta[0])
                bus.emitir("cerebro", hemisferio=h, estado="entregou", tarefa=pauta[0][:90])
                try:
                    jaime.vault.diario(f"Dei ao hemisfério {h}, por conta própria: {pauta[0][:140]}", "Log")
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as e:
            bus.emitir("cerebro", estado="erro", detalhe=f"{type(e).__name__}: {e}"[:120])
        await asyncio.sleep(INTERVALO_S)
