"""Rastreador NATIVO das mãos para o controle do computador — funciona com o Safari fechado ou escondido.

A aba do Jarvis já rastreia as mãos pelo navegador, mas o Safari para de processar quando a janela some. Este
módulo faz o mesmo aqui no servidor: webcam (OpenCV) → MediaPipe Hands → `ControleMaos.receber`. Só abre a câmera
enquanto o controle do computador estiver LIGADO, e fecha ao desligar.

Depende de `opencv-python` e `mediapipe`, que o Jaime NÃO instala sozinho (decisão do João, 30/09: "os dois" —
navegador agora, nativo pronto para quando instalar): `bash scripts/maos/instalar-nativo.sh`, depois
`JAIME_MAOS_NATIVO=on` no .env e reiniciar. No macOS o Python do Jaime precisa da permissão de Câmera.
"""
from __future__ import annotations
import asyncio, os


def ligado(env=None) -> bool:
    e = os.environ if env is None else env
    return (e.get("JAIME_MAOS_NATIVO", "off") or "off").strip().lower() in ("1", "on", "true", "sim")


def disponivel() -> tuple[bool, str]:
    try:
        import cv2  # noqa: F401
        import mediapipe  # noqa: F401
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: rode scripts/maos/instalar-nativo.sh"


def poses_para_maos(poses) -> list[dict]:
    """HandPose (lateralidade já corrigida do espelho) → formato do ControleMaos."""
    lado = {"right": "direita", "left": "esquerda"}
    return [{"lado": lado.get(p.hand_id, "direita"), "p": [[x, y] for x, y, *_ in p.landmarks]} for p in poses if p.valida()]


async def rodar(controle, emitir=None, fonte_fn=None, rastreador_fn=None, espera: float = 0.5):
    """Laço do serviço. `fonte_fn`/`rastreador_fn` injetáveis (teste); padrão: OpenCV + MediaPipe do pacote espacial."""
    emitir = emitir or (lambda *a, **k: None)
    if fonte_fn is None or rastreador_fn is None:
        ok, motivo = disponivel()
        if not ok:
            emitir("maos_so", nativo=False, erro=motivo)
            return
        from ..spatial.fontes import FonteOpenCV, RastreadorMediaPipe
        fonte_fn = fonte_fn or (lambda: FonteOpenCV(int(os.environ.get("JAIME_MAOS_CAMERA", "0"))))
        rastreador_fn = rastreador_fn or (lambda: RastreadorMediaPipe(max_maos=2, conf_min=0.6))
    while True:
        if not controle.ligado:
            await asyncio.sleep(espera)
            continue
        fonte, rastreador = fonte_fn(), rastreador_fn()
        controle.nativo = True
        emitir("maos_so", nativo=True)
        try:
            async for frame in fonte.frames():
                if not controle.ligado:
                    break
                poses = await asyncio.to_thread(rastreador.detect, frame)
                controle.receber(poses_para_maos(poses))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            emitir("maos_so", nativo=False, erro=f"{type(e).__name__}: {str(e)[:120]}")
            await asyncio.sleep(5)
        finally:
            controle.nativo = False
            controle.soltar_tudo()
            fonte.fechar(); rastreador.fechar()
