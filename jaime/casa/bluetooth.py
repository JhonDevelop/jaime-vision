"""Bluetooth: presença (o João chegou/saiu) e o ponto de entrada para dispositivos BLE.

Duas camadas, de propósito:
1. Dispositivos BLE da casa (sensores, tomadas, fechaduras, SwitchBot, Xiaomi…) entram pelo Home Assistant
   (integração Bluetooth do HA, com adaptador local ou proxies ESPHome espalhados pela casa). Para o Jaime eles
   viram entidades comuns — `casa_estado`, `casa_ligar` — e nada de pilha Bluetooth própria para manter.
2. Presença: esta máquina escaneia anúncios BLE (`bleak`, funciona no macOS, Windows e Linux) e reconhece os
   aparelhos que o JOÃO cadastrou (celular, relógio, fone) por nome ou endereço. Chegou → evento `casa`
   ("presenca": "chegou"); sumiu por X minutos → "saiu". Histerese de sinal para não piscar na porta.

Presença NUNCA autoriza nada: anúncio BLE é fácil de imitar. Serve para cumprimentar, acender a luz do
escritório, abrir os blocos do dia — nunca para destrancar porta ou liberar o cérebro.
`bleak` não vem instalado: `pip install bleak` é decisão do João (JAIME_BT=on liga o scanner).
"""
from __future__ import annotations
import asyncio, os, time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Conhecido:
    rotulo: str                 # "celular do João"
    nome: str = ""              # nome anunciado (ex.: "iPhone de João") — casamento por substring, sem acento
    endereco: str = ""          # MAC/UUID (no macOS o CoreBluetooth dá UUID, não MAC)
    dono: str = "joao"


@dataclass
class Presenca:
    conhecidos: list[Conhecido]
    rssi_chegou: int = -75      # sinal mais forte que isso = perto
    rssi_saiu: int = -88        # histerese: só conta como longe abaixo disso
    ausencia_s: float = 300.0   # sem ver por 5 min = saiu
    relogio: Callable[[], float] = time.monotonic
    presentes: dict[str, float] = field(default_factory=dict)       # rótulo → último visto perto

    def _casa(self, nome: str, endereco: str) -> Conhecido | None:
        n, e = (nome or "").lower(), (endereco or "").lower()
        for c in self.conhecidos:
            if (c.endereco and c.endereco.lower() == e) or (c.nome and c.nome.lower() in n):
                return c
        return None

    def atualizar(self, vistos: list[tuple[str, str, int]]) -> list[dict]:
        """vistos: (nome, endereço, rssi) de um ciclo de scan → eventos de chegada/saída."""
        agora = self.relogio()
        eventos = []
        for nome, end, rssi in vistos:
            c = self._casa(nome, end)
            if not c:
                continue
            if c.rotulo in self.presentes:
                if rssi >= self.rssi_saiu:
                    self.presentes[c.rotulo] = agora
            elif rssi >= self.rssi_chegou:
                self.presentes[c.rotulo] = agora
                eventos.append({"presenca": "chegou", "quem": c.dono, "aparelho": c.rotulo, "rssi": rssi})
        for rot, visto in list(self.presentes.items()):
            if agora - visto > self.ausencia_s:
                self.presentes.pop(rot)
                c = next((x for x in self.conhecidos if x.rotulo == rot), None)
                eventos.append({"presenca": "saiu", "quem": c.dono if c else "?", "aparelho": rot})
        return eventos

    def em_casa(self, quem: str = "joao") -> bool:
        return any(c.dono == quem and c.rotulo in self.presentes for c in self.conhecidos)


def conhecidos_do_ambiente(env=None) -> list[Conhecido]:
    """JAIME_BT_CONHECIDOS="celular do João=iPhone de João;relógio=Apple Watch" (rótulo=nome ou endereço)."""
    e = os.environ if env is None else env
    out = []
    for par in (e.get("JAIME_BT_CONHECIDOS", "") or "").split(";"):
        if "=" in par:
            rot, alvo = (x.strip() for x in par.split("=", 1))
            eh_end = ":" in alvo or (len(alvo) >= 32 and "-" in alvo)
            out.append(Conhecido(rot, "" if eh_end else alvo, alvo if eh_end else ""))
    return out


async def escanear(duracao: float = 6.0) -> list[tuple[str, str, int]]:
    from bleak import BleakScanner          # import preguiçoso: sem bleak, o resto do Jaime nem percebe
    achados = await BleakScanner.discover(timeout=duracao, return_adv=True)
    return [(adv.local_name or d.name or "", d.address, int(adv.rssi)) for d, adv in achados.values()]


async def vigiar(presenca: Presenca, emitir: Callable[..., None], ao_chegar: Callable | None = None,
                 intervalo: float = 20.0, scanner=escanear) -> None:
    while True:
        try:
            for ev in presenca.atualizar(await scanner()):
                emitir("casa", **ev)
                if ev["presenca"] == "chegou" and ao_chegar:
                    try:
                        r = ao_chegar(ev)
                        if asyncio.iscoroutine(r):
                            await r
                    except Exception:
                        pass
        except ImportError:
            emitir("casa", presenca="indisponivel", motivo="bleak não instalado (pip install bleak)")
            return
        except Exception as e:
            emitir("casa", presenca="erro", motivo=f"{type(e).__name__}: {str(e)[:100]}")
        await asyncio.sleep(intervalo)


def saida_de_audio(dispositivo: str) -> str:
    """Toca a VOZ DO JAIME (não a da Alexa) num Echo usado como caixa Bluetooth: pareie o computador com o Echo
    ("Alexa, emparelhar") e troque a saída de áudio do sistema. No macOS usa o `SwitchAudioSource` se existir."""
    import platform, shutil, subprocess
    if platform.system() == "Darwin" and shutil.which("SwitchAudioSource"):
        r = subprocess.run(["SwitchAudioSource", "-s", dispositivo], capture_output=True, text=True, timeout=10)
        return f"saída de áudio: {dispositivo}" if r.returncode == 0 else f"não troquei a saída: {r.stderr.strip()[:120]}"
    return (f"para eu falar pelo '{dispositivo}': pareie o computador com o Echo (diga 'Alexa, emparelhar') e escolha-o como "
            "saída de som do sistema" + (" — ou instale o SwitchAudioSource (brew install switchaudio-osx) e eu troco sozinho"
                                          if platform.system() == "Darwin" else ""))
