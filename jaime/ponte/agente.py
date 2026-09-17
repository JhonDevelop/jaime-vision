"""O lado do Gabriel: o programa que ele roda no Mac dele para o J.A.I.M.E alcançar os arquivos dele.

    python -m jaime.ponte.agente --servidor http://192.168.200.23:8787 --token SEU_TOKEN \
                                 --pasta ~/Projetos --nome "Gabriel" [--permitir-rodar]

O que ele faz: liga no servidor do João, diz "estou aqui, esta é a minha pasta", e fica buscando trabalho.
Nada entra na máquina do Gabriel — a conexão sai dela. Ctrl-C encerra e o acesso acaba junto; não instala
serviço, não fica no boot, não deixa porta aberta.

O que a pasta escolhida protege: TUDO fica dentro dela. Caminho com `..`, caminho absoluto e link simbólico
que aponte para fora são recusados aqui, no lado dele, antes de qualquer leitura. Rodar comando é uma
autorização separada e vem desligada: sem `--permitir-rodar`, o Jaime lê e escreve, e só.

Este arquivo é feito para ser lido pelo Gabriel antes de ele rodar. Se algo aqui não fizer sentido para
ele, é para não rodar."""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from urllib import request as urlrequest, error as urlerror

LIMITE_LEITURA = 200_000        # 200 KB por arquivo: o que passa disso é dado, não código para ler
LIMITE_SAIDA = 20_000
TEMPO_COMANDO_S = 120


def _dentro(raiz: Path, alvo: str) -> Path | None:
    """O caminho cai dentro da pasta que o Gabriel abriu? Resolve link simbólico antes de decidir."""
    try:
        p = (raiz / alvo).resolve() if not os.path.isabs(alvo) else Path(alvo).resolve()
        p.relative_to(raiz.resolve())
        return p
    except (ValueError, OSError):
        return None


def executar(raiz: Path, acao: str, args: dict, pode_rodar: bool) -> str:
    if acao == "listar":
        p = _dentro(raiz, args.get("caminho") or ".")
        if p is None:
            return "fora da pasta que eu abri"
        if not p.is_dir():
            return f"{p.name} não é pasta"
        itens = []
        for x in sorted(p.iterdir())[:200]:
            if x.name.startswith("."):
                continue
            itens.append(f"{'📁' if x.is_dir() else '  '} {x.name}"
                         + ("" if x.is_dir() else f"  ({x.stat().st_size // 1024 or 1} KB)"))
        return "\n".join(itens) or "(pasta vazia)"

    if acao == "ler":
        p = _dentro(raiz, args.get("caminho") or "")
        if p is None:
            return "fora da pasta que eu abri"
        if not p.is_file():
            return "não é um arquivo"
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"não consegui ler: {type(e).__name__}"
        return t[:LIMITE_LEITURA] + (" …(cortei)" if len(t) > LIMITE_LEITURA else "")

    if acao == "escrever":
        p = _dentro(raiz, args.get("caminho") or "")
        if p is None:
            return "fora da pasta que eu abri"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args.get("conteudo") or "", encoding="utf-8")
        except OSError as e:
            return f"não consegui escrever: {type(e).__name__}"
        return f"escrito: {p.relative_to(raiz)} ({len(args.get('conteudo') or '')} caracteres)"

    if acao == "rodar":
        if not pode_rodar:
            return "não autorizei rodar comando nesta máquina"
        cmd = args.get("comando") or ""
        try:
            r = subprocess.run(cmd, shell=True, cwd=str(raiz), capture_output=True, text=True,
                               timeout=TEMPO_COMANDO_S)
        except subprocess.TimeoutExpired:
            return f"o comando passou de {TEMPO_COMANDO_S}s e eu cortei"
        except Exception as e:
            return f"falhou: {type(e).__name__}: {e}"
        saida = (r.stdout + ("\n" + r.stderr if r.stderr else ""))[:LIMITE_SAIDA]
        return f"[saiu {r.returncode}]\n{saida}"

    return f"não sei fazer «{acao}»"


def _http(url: str, token: str, corpo: dict | None = None, timeout: float = 40) -> dict:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urlrequest.Request(url, data=dados, method="POST" if dados else "GET",
                             headers={"X-Jaime-Token": token, "Content-Type": "application/json"})
    with urlrequest.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ponte do J.A.I.M.E: dá a ele acesso a uma pasta desta máquina.")
    ap.add_argument("--servidor", required=True, help="onde o Jaime roda, ex.: http://192.168.200.23:8787")
    ap.add_argument("--token", required=True, help="o token que o dono do Jaime te passou")
    ap.add_argument("--pasta", required=True, help="a ÚNICA pasta que ele vai alcançar nesta máquina")
    ap.add_argument("--nome", default=os.environ.get("USER", "convidado"))
    ap.add_argument("--permitir-rodar", action="store_true",
                    help="deixa ele rodar comando nesta pasta (fica DESLIGADO se você não passar)")
    a = ap.parse_args(argv)

    raiz = Path(a.pasta).expanduser().resolve()
    if not raiz.is_dir():
        print(f"✗ {raiz} não existe ou não é pasta"); return 2
    base = a.servidor.rstrip("/")

    print(f"Ponte do J.A.I.M.E\n  eu: {a.nome} · máquina: {os.uname().nodename}\n"
          f"  ele alcança: {raiz}\n  rodar comando: {'SIM' if a.permitir_rodar else 'não'}\n"
          f"  servidor: {base}\nCtrl-C encerra e o acesso acaba junto.\n")
    try:
        _http(f"{base}/ponte/registrar", a.token,
              {"dono": a.nome, "maquina": os.uname().nodename, "raiz": str(raiz),
               "pode_rodar": bool(a.permitir_rodar)})
        print("✓ registrado. Esperando trabalho…")
    except Exception as e:
        print(f"✗ não consegui registrar: {type(e).__name__}: {e}"); return 3

    while True:
        try:
            t = _http(f"{base}/ponte/proximo", a.token, {}, timeout=40)   # corpo vazio = POST (a rota é POST)
        except urlerror.HTTPError as e:
            print(f"… o servidor respondeu {e.code} ({e.reason}); tento de novo em 5s"); time.sleep(5); continue
        except urlerror.URLError as e:
            print(f"… não alcancei o servidor ({e.reason}); tento de novo em 5s"); time.sleep(5); continue
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"… {type(e).__name__}; tento de novo em 5s"); time.sleep(5); continue
        if not t or not t.get("id"):
            continue
        print(f"→ {t['acao']} {json.dumps(t.get('args', {}), ensure_ascii=False)[:90]}")
        try:
            saida = executar(raiz, t["acao"], t.get("args") or {}, a.permitir_rodar)
        except Exception as e:
            saida = f"erro aqui: {type(e).__name__}: {e}"
        try:
            _http(f"{base}/ponte/responder", a.token, {"id": t["id"], "saida": saida})
        except Exception as e:
            print(f"… não consegui responder: {type(e).__name__}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nPonte encerrada. Ele não alcança mais nada desta máquina.")
