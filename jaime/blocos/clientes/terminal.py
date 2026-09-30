"""Cliente de TERMINAL dos blocos — a prova de que a interface do Jaime não depende de navegador.

`python -m jaime blocos terminal [ws://127.0.0.1:8787/blocos/ws]`

Conecta no JBP como perfil `terminal`, desenha cada bloco como uma caixa de texto e redesenha a cada mudança.
Comandos (digite e Enter): `f <id>` fecha · `l <id>` lê em voz · `d` desfaz · `q` sai."""
from __future__ import annotations
import json, os, shutil, sys, threading

CINZA, CIANO, AMBAR, VERMELHO, VERDE, FIM = "\033[90m", "\033[96m", "\033[33m", "\033[91m", "\033[92m", "\033[0m"
COR = {0: CINZA, 1: CIANO, 2: AMBAR, 3: VERMELHO}


def caixa(b: dict, largura: int, cores: bool = True) -> list[str]:
    """Um bloco adaptado (dict do protocolo) → linhas de uma caixa com moldura."""
    c = (COR.get(b.get("prioridade", 1), CIANO) if cores else "")
    f = FIM if cores else ""
    w = max(20, largura - 4)
    titulo = f" {b.get('titulo', '')} " + ("· privado " if b.get("privado") else "") + ("· ao vivo " if b.get("fonte") else "")
    topo = f"{c}╭─{titulo[:w - 2]}{'─' * max(0, w - len(titulo[:w - 2]))}╮{f}"
    corpo = [f"{c}│{f} {ln[:w].ljust(w)}{c}│{f}" for ln in (b.get("linhas") or ["(vazio)"])]
    rodape = f"{c}╰{'─' * (w + 1)}╯{f}  {CINZA if cores else ''}{b.get('id', '')}{f}"
    return [topo, *corpo, rodape]


def tela(blocos: dict[str, dict], largura: int, cores: bool = True, aviso: str = "") -> str:
    linhas = [f"{CIANO if cores else ''}J.A.I.M.E · blocos{FIM if cores else ''}  ({len(blocos)} abertos)", ""]
    for b in sorted(blocos.values(), key=lambda b: (-b.get("prioridade", 1), b.get("titulo", ""))):
        linhas += caixa(b, largura, cores) + [""]
    if not blocos:
        linhas.append('Nenhum bloco aberto. Peça por voz: "abre o bloco da máquina".')
    if aviso:
        linhas += ["", aviso]
    linhas.append("f <id> fecha · l <id> lê · d desfaz · q sai")
    return "\n".join(linhas)


def rodar(url: str = "ws://127.0.0.1:8787/blocos/ws", cores: bool | None = None) -> int:
    try:
        from websockets.sync.client import connect
    except ImportError:
        print("preciso do pacote websockets (pip install websockets)"); return 1
    cores = sys.stdout.isatty() if cores is None else cores
    blocos: dict[str, dict] = {}
    estado = {"aviso": ""}
    trava = threading.Lock()

    def redesenhar():
        largura = min(100, shutil.get_terminal_size((100, 40)).columns)
        with trava:
            sys.stdout.write("\033[2J\033[H" if cores else "\n" + "=" * largura + "\n")
            sys.stdout.write(tela(blocos, largura, cores, estado["aviso"]) + "\n")
            sys.stdout.flush()

    with connect(url, additional_headers={"Origin": "http://127.0.0.1"}) as ws:
        ws.send(json.dumps({"op": "ola", "perfil": "terminal", "nome": "terminal",
                            "capacidades": {"largura": min(100, shutil.get_terminal_size((100, 40)).columns)}}))

        def teclado():
            for linha in sys.stdin:
                p = linha.strip().split(maxsplit=1)
                if not p:
                    continue
                if p[0] == "q":
                    ws.close(); return
                if p[0] == "f" and len(p) > 1:
                    ws.send(json.dumps({"op": "fechar", "id": p[1]}))
                elif p[0] == "l" and len(p) > 1:
                    ws.send(json.dumps({"op": "ler", "id": p[1]}))
                elif p[0] == "d":
                    ws.send(json.dumps({"op": "desfazer"}))
        threading.Thread(target=teclado, daemon=True).start()
        try:
            for bruto in ws:
                m = json.loads(bruto)
                op = m.get("op")
                if op in ("abrir", "atualizar"):
                    blocos[m["bloco"]["id"]] = m["bloco"]
                elif op == "fechar":
                    blocos.pop(m.get("id"), None)
                elif op in ("falar", "erro"):
                    estado["aviso"] = ("» " if op == "falar" else "! ") + m.get("texto", m.get("msg", ""))
                redesenhar()
        except Exception:
            pass
    return 0
