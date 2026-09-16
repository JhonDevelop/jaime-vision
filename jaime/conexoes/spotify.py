"""Spotify — o J.A.I.M.E toca música e aprende o gosto do João, pela API oficial (OAuth do app dele).

Fluxo: `python -m jaime conectar spotify` abre o navegador uma vez; o token fica em `SPOTIFY_TOKEN_FILE`
(~/Jaime/spotify-token.json) e é renovado sozinho. Precisa de um app em https://developer.spotify.com com
Redirect URI http://127.0.0.1:8899/callback, e SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET no .env.

Ler o gosto (top artistas/músicas, o que está tocando) funciona em qualquer conta. Controlar a reprodução
(tocar/pausar/pular) exige Spotify Premium e um aparelho ativo. `cliente` é injetável para testes."""
from __future__ import annotations
import base64, json, os, threading, time, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

AUTH = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
PORTA = int(os.environ.get("SPOTIFY_REDIRECT_PORT", "8899"))
REDIRECT = f"http://127.0.0.1:{PORTA}/callback"
ESCOPOS = "user-read-currently-playing user-read-playback-state user-modify-playback-state user-top-read user-read-recently-played"

def conectar(client_id: str, client_secret: str, token_path: Path) -> str:
    """Abre o consentimento do Spotify no navegador, troca o code por token e salva. Devolve o nome do usuário."""
    if not client_id or not client_secret:
        raise RuntimeError("faltam SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET no .env")
    import httpx
    codigo = {}
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            codigo["code"] = (q.get("code") or [""])[0]; codigo["error"] = (q.get("error") or [""])[0]
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write("<h2>Spotify conectado. Pode fechar esta aba.</h2>".encode())
        def log_message(self, *a): pass
    srv = HTTPServer(("127.0.0.1", PORTA), H)
    url = AUTH + "?" + urllib.parse.urlencode({"client_id": client_id, "response_type": "code", "redirect_uri": REDIRECT,
                                               "scope": ESCOPOS, "show_dialog": "true"})
    webbrowser.open(url); print(f"Abrindo o Spotify no navegador… se não abrir, cole: {url}")
    threading.Thread(target=srv.handle_request, daemon=True).start()
    for _ in range(300):
        if codigo:
            break
        time.sleep(0.5)
    srv.server_close()
    if codigo.get("error") or not codigo.get("code"):
        raise RuntimeError(f"autorização negada: {codigo.get('error') or 'sem code'}")
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = httpx.post(TOKEN, data={"grant_type": "authorization_code", "code": codigo["code"], "redirect_uri": REDIRECT},
                   headers={"Authorization": f"Basic {auth}"}, timeout=20)
    r.raise_for_status(); tok = r.json(); tok["obtido_em"] = time.time()
    Path(token_path).parent.mkdir(parents=True, exist_ok=True)
    Path(token_path).write_text(json.dumps(tok), encoding="utf-8"); Path(token_path).chmod(0o600)
    return Spotify(token_path, client_id, client_secret).me()

class Spotify:
    def __init__(self, token_path: Path, client_id: str = "", client_secret: str = "", cliente=None):
        self.token_path = Path(token_path)
        self.client_id, self.client_secret = client_id, client_secret
        self._cli = cliente          # injetável (teste): objeto com .get/.put/.post(path, ...) -> dict

    @property
    def conectado(self) -> bool:
        return self._cli is not None or self.token_path.exists()

    def _access_token(self) -> str:
        tok = json.loads(self.token_path.read_text(encoding="utf-8"))
        if time.time() - tok.get("obtido_em", 0) > tok.get("expires_in", 3600) - 60:
            import httpx
            auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            r = httpx.post(TOKEN, data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]},
                           headers={"Authorization": f"Basic {auth}"}, timeout=20)
            r.raise_for_status(); novo = r.json()
            tok.update(novo); tok["obtido_em"] = time.time()
            self.token_path.write_text(json.dumps(tok), encoding="utf-8")
        return tok["access_token"]

    def _req(self, metodo: str, path: str, **kw) -> dict:
        if self._cli is not None:
            return getattr(self._cli, metodo.lower())(path, **kw)
        import httpx
        h = {"Authorization": f"Bearer {self._access_token()}"}
        r = httpx.request(metodo, API + path, headers=h, timeout=20, **kw)
        if r.status_code == 204 or not r.content:
            return {}
        r.raise_for_status(); return r.json()

    # ── ler o gosto ────────────────────────────────────
    def me(self) -> str:
        return self._req("GET", "/me").get("display_name", "você")

    def o_que_toca(self) -> str:
        d = self._req("GET", "/me/player/currently-playing")
        item = (d or {}).get("item") or {}
        if not item:
            return "Nada tocando agora."
        art = ", ".join(a["name"] for a in item.get("artists", []))
        return f"{item.get('name', '?')} — {art}"

    def top(self, tipo: str = "artists", prazo: str = "medium_term", limite: int = 8) -> list[str]:
        d = self._req("GET", f"/me/top/{tipo}", params={"time_range": prazo, "limit": limite})
        itens = d.get("items", [])
        if tipo == "artists":
            return [a["name"] for a in itens]
        return [f"{a['name']} — {', '.join(x['name'] for x in a.get('artists', []))}" for a in itens]

    def gosto(self) -> str:
        arts = self.top("artists"); muss = self.top("tracks")
        generos = []
        d = self._req("GET", "/me/top/artists", params={"time_range": "medium_term", "limit": 10})
        for a in d.get("items", []):
            generos += a.get("genres", [])
        top_gen = [g for g, _ in _mais_comuns(generos, 5)]
        return ("Seus artistas: " + ", ".join(arts[:6]) + ".") + (f" Gêneros: {', '.join(top_gen)}." if top_gen else "") + \
               (f" Músicas do momento: {'; '.join(muss[:4])}." if muss else "")

    # ── controlar ──────────────────────────────────────
    def tocar(self, consulta: str = "") -> str:
        if consulta:
            d = self._req("GET", "/search", params={"q": consulta, "type": "track", "limit": 1})
            itens = (d.get("tracks") or {}).get("items", [])
            if not itens:
                return f"Não achei '{consulta}' no Spotify."
            uri = itens[0]["uri"]; nome = itens[0]["name"] + " — " + ", ".join(a["name"] for a in itens[0]["artists"])
            self._req("PUT", "/me/player/play", json={"uris": [uri]})
            return f"Tocando {nome}."
        self._req("PUT", "/me/player/play")
        return "Retomando."

    def pausar(self) -> str:
        self._req("PUT", "/me/player/pause"); return "Pausado."

    def proxima(self) -> str:
        self._req("POST", "/me/player/next"); return "Próxima."

def _mais_comuns(itens, n):
    from collections import Counter
    return Counter(itens).most_common(n)
