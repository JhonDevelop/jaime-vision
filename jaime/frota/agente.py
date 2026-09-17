"""O lado da OUTRA máquina: o programa que dá ao J.A.I.M.E acesso a este computador.

    python3 -m jaime.frota.agente --servidor http://192.168.200.23:8787 --token TOKEN_DESTA_MAQUINA \
                                  --nivel operador --pasta ~/Projetos

Ou, sem clonar nada (é o caminho normal numa máquina nova):

    curl -fsSL http://192.168.200.23:8787/frota/instalar | sh

O que ele faz: lê o hostname desta máquina, liga no servidor do João, se apresenta e fica buscando trabalho.
Nada entra aqui — a conexão sai. Sem porta aberta, sem IP fixo, sem firewall mexido.

**Quem manda é este arquivo, não o servidor.** O nível e a pasta são conferidos aqui, no lado de quem é dono
da máquina, antes de qualquer leitura. O servidor também confere, mas por educação e para dar uma mensagem
melhor; se os dois discordarem, quem está na máquina ganha. É a única disposição honesta: quem está sentado
no computador decide o que sai dele.

Os níveis:
    leitor      lista e lê, dentro da pasta. Nada mais.
    operador    lê, escreve e roda comando, dentro da pasta.
    dono        o mesmo, na casa do usuário inteira. Só para as máquinas do próprio João.

Ctrl-C encerra e o acesso acaba junto. Este arquivo é feito para ser lido antes de ser rodado: se algo aqui
não fizer sentido para você, não rode."""
from __future__ import annotations
import argparse, json, os, platform, shutil, subprocess, sys, time
from pathlib import Path
from urllib import request as urlrequest, error as urlerror

LIMITE_LEITURA = 200_000
LIMITE_SAIDA = 20_000
TEMPO_COMANDO_S = 120
NIVEIS = ("leitor", "operador", "dono")
ACOES = {
    "leitor":   {"listar", "ler", "conhecer"},
    "operador": {"listar", "ler", "escrever", "rodar", "conhecer"},
    "dono":     {"listar", "ler", "escrever", "rodar", "conhecer"},
}
# Pasta que não se entrega nem no nível dono. Segredo de um dono não é assunto do assistente de outro —
# e o do próprio João mora no vault dele, não espalhado por chave de ssh.
PROIBIDAS = (".ssh", ".gnupg", ".aws", ".config/gcloud", "Library/Keychains", ".env", ".netrc",
             ".docker/config.json", ".kube/config", ".password-store")


def _proibido(rel: str) -> bool:
    r = rel.replace("\\", "/").strip("/").lower()
    return any(r == p.lower() or r.startswith(p.lower() + "/") or f"/{p.lower()}/" in f"/{r}/"
               for p in PROIBIDAS)


def _dentro(raiz: Path, alvo: str) -> Path | None:
    """O caminho cai dentro do alcance desta máquina? Resolve link simbólico ANTES de decidir.

    Sem resolver, um atalho dentro da pasta que aponta para `/` entregaria o disco inteiro — e pareceria
    obediente ao fazê-lo."""
    try:
        p = (raiz / alvo).resolve() if not os.path.isabs(alvo) else Path(alvo).resolve()
        rel = p.relative_to(raiz.resolve())
    except (ValueError, OSError):
        return None
    return None if _proibido(str(rel)) else p


def conhecer(raiz: Path) -> str:
    """O retrato desta máquina: o que ela é e com o que se trabalha nela.

    É isto que responde ao «saber como mexer neles». Sem este retrato, ele chutaria `apt` num Mac, `brew`
    num Linux, ou `python` onde só existe `python3` — e o João veria um assistente confuso em vez de um
    assistente informado. Só leitura, então até o nível leitor pode pedir."""
    def tem(*cmds):
        return " ".join(c for c in cmds if shutil.which(c)) or "—"

    def versao(cmd, *args):
        if not shutil.which(cmd):
            return "não tem"
        try:
            r = subprocess.run([cmd, *(args or ["--version"])], capture_output=True, text=True, timeout=10)
            return (r.stdout or r.stderr).strip().splitlines()[0][:70] or "?"
        except Exception:
            return "?"

    linhas = [
        f"host: {platform.node()}",
        f"sistema: {platform.system()} {platform.release()} ({platform.machine()})",
        f"usuário: {os.environ.get('USER') or os.environ.get('USERNAME') or '?'}",
        f"shell: {os.environ.get('SHELL', '?')}",
        f"casa: {Path.home()}",
        f"meu alcance aqui: {raiz}",
        f"python: {versao('python3')}",
        f"git: {versao('git')}",
        f"node: {versao('node')}",
        f"gerenciador de pacote: {tem('brew', 'apt', 'dnf', 'pacman', 'winget', 'port')}",
        f"editor/ferramenta: {tem('code', 'vim', 'nvim', 'docker', 'ollama', 'claude', 'codex', 'gemini')}",
    ]
    try:
        projetos = [f"  {'📁' if x.is_dir() else '  '} {x.name}"
                    for x in sorted(raiz.iterdir())[:40] if not x.name.startswith(".")]
        linhas += ["", f"o que tem em {raiz.name or raiz}:"] + (projetos or ["  (vazio)"])
    except OSError as e:
        linhas += ["", f"não consegui listar {raiz}: {type(e).__name__}"]
    return "\n".join(linhas)


def executar(raiz: Path, acao: str, args: dict, nivel: str) -> str:
    if acao not in ACOES.get(nivel, ACOES["leitor"]):
        return f"nesta máquina eu autorizei nível «{nivel}», e «{acao}» não está incluído"

    if acao == "conhecer":
        return conhecer(raiz)

    if acao == "listar":
        p = _dentro(raiz, args.get("caminho") or ".")
        if p is None:
            return "fora do meu alcance nesta máquina (ou é pasta protegida)"
        if not p.is_dir():
            return f"{p.name} não é pasta"
        itens = []
        for x in sorted(p.iterdir())[:200]:
            if x.name.startswith("."):
                continue
            try:
                tam = "" if x.is_dir() else f"  ({x.stat().st_size // 1024 or 1} KB)"
            except OSError:
                tam = ""
            itens.append(f"{'📁' if x.is_dir() else '  '} {x.name}{tam}")
        return "\n".join(itens) or "(pasta vazia)"

    if acao == "ler":
        p = _dentro(raiz, args.get("caminho") or "")
        if p is None:
            return "fora do meu alcance nesta máquina (ou é arquivo protegido)"
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
            return "fora do meu alcance nesta máquina (ou é arquivo protegido)"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args.get("conteudo") or "", encoding="utf-8")
        except OSError as e:
            return f"não consegui escrever: {type(e).__name__}"
        return f"escrito: {p} ({len(args.get('conteudo') or '')} caracteres)"

    if acao == "rodar":
        cmd = (args.get("comando") or "").strip()
        if not cmd:
            return "faltou o comando"
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


def _http(url: str, token: str, host: str, corpo: dict | None = None, timeout: float = 40) -> dict:
    dados = json.dumps(corpo or {}).encode()
    req = urlrequest.Request(url, data=dados, method="POST",
                             headers={"X-Jaime-Token": token, "X-Jaime-Host": host,
                                      "Content-Type": "application/json"})
    with urlrequest.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Agente da frota do J.A.I.M.E: dá a ele acesso controlado a este computador.")
    ap.add_argument("--servidor", default=os.environ.get("JAIME_SERVIDOR", ""),
                    help="onde o Jaime roda, ex.: http://192.168.200.23:8787")
    ap.add_argument("--token", default=os.environ.get("JAIME_FROTA_TOKEN", ""),
                    help="o token DESTA máquina (o João gera com `token_da_maquina`)")
    ap.add_argument("--nivel", default=os.environ.get("JAIME_NIVEL", "operador"), choices=NIVEIS)
    ap.add_argument("--pasta", default=os.environ.get("JAIME_PASTA", ""),
                    help="o alcance dele aqui. Vazio + nível dono = a casa do usuário")
    a = ap.parse_args(argv)

    if not a.servidor or not a.token:
        print("✗ faltou --servidor e/ou --token"); return 2
    raiz = Path(a.pasta).expanduser().resolve() if a.pasta else Path.home()
    if a.nivel != "dono" and not a.pasta:
        print("✗ nível leitor/operador exige --pasta: só o nível dono alcança a casa inteira"); return 2
    if not raiz.is_dir():
        print(f"✗ {raiz} não existe ou não é pasta"); return 2

    host, base = platform.node(), a.servidor.rstrip("/")
    print(f"Agente da frota do J.A.I.M.E\n"
          f"  esta máquina: {host} · {platform.system()} {platform.release()}\n"
          f"  usuário: {os.environ.get('USER', '?')}\n"
          f"  nível que eu autorizei: {a.nivel}\n"
          f"  alcance dele aqui: {raiz}\n"
          f"  servidor: {base}\n"
          f"Ctrl-C encerra e o acesso acaba junto.\n")
    try:
        r = _http(f"{base}/frota/registrar", a.token, host,
                  {"host": host, "usuario": os.environ.get("USER", ""),
                   "so": f"{platform.system()} {platform.release()}", "raiz": str(raiz)})
    except urlerror.HTTPError as e:
        corpo = ""
        try:
            corpo = e.read().decode()[:200]
        except Exception:
            pass
        print(f"✗ o servidor recusou ({e.code} {e.reason}). {corpo}")
        print("  Token errado, ou esta máquina ainda não está na frota — peça ao João para cadastrar.")
        return 3
    except Exception as e:
        print(f"✗ não alcancei o servidor: {type(e).__name__}: {e}"); return 3
    if not r.get("ok"):
        print(f"✗ {r.get('erro') or 'o servidor não me aceitou'}"); return 3
    print(f"✓ {r.get('estado') or 'registrado'}\nEsperando trabalho…")

    while True:
        try:
            t = _http(f"{base}/frota/proximo", a.token, host, {"host": host}, timeout=40)
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
            saida = executar(raiz, t["acao"], t.get("args") or {}, a.nivel)
        except Exception as e:
            saida = f"erro aqui: {type(e).__name__}: {e}"
        try:
            _http(f"{base}/frota/responder", a.token, host,
                  {"host": host, "id": t["id"], "saida": saida})
        except Exception as e:
            print(f"… não consegui responder: {type(e).__name__}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAgente encerrado. Ele não alcança mais nada desta máquina.")
