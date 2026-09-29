"""Gerenciador de blocos: a única fonte da verdade do que está aberto, para todas as superfícies ao mesmo tempo.

Abrir, atualizar, mover, fechar, desfazer, salvar e reabrir layouts; fechar sozinho por TTL; atualizar fontes vivas.
Cada mudança é difundida para as sessões conectadas (cockpit, janela nativa, terminal, óculos, visor, falante), e
cada sessão recebe só o que pode ver e mostrar (protocolo.Sessao faz o diff por superfície).

Uso vira sinal: bloco que o Jaime abriu e o João fechou em menos de 5 s conta como "não queria isso" — é assim que
a interface aprende o que vale abrir sozinho (modelos.Uso → sinais da autoevolução).
"""
from __future__ import annotations
import asyncio, copy, json, time
from pathlib import Path
from typing import Callable
from .fontes import Fontes
from .modelo import Bloco, BlocoInvalido, validar
from .superficies import resumo_falado

MAX_ABERTOS = 24
MAX_DESFAZER = 50


class Gerenciador:
    def __init__(self, fontes: Fontes, pasta: Path | None = None, dono_ok: Callable[[], bool] = lambda: True,
                 emitir: Callable[..., None] | None = None, falar: Callable[[str], None] | None = None,
                 relogio: Callable[[], float] = time.time, max_abertos: int = MAX_ABERTOS, uso=None):
        self.fontes, self.dono_ok, self.relogio, self.max_abertos = fontes, dono_ok, relogio, max_abertos
        self.pasta = Path(pasta).expanduser() if pasta else None
        self.emitir = emitir or (lambda *a, **k: None)
        self.falar = falar
        self.blocos: dict[str, Bloco] = {}
        self.sessoes: dict[str, object] = {}
        self._desfazer: list[tuple[str, dict | None, dict | None]] = []   # (op, antes, depois)
        self._ultima_leitura: dict[str, float] = {}
        self.uso = uso
        self.erros_fonte: dict[str, str] = {}

    # ── sessões (superfícies conectadas) ───────────────
    def conectar(self, sessao) -> None:
        self.sessoes[sessao.id] = sessao
        sessao.sincronizar(self.listar(), self.dono_ok())

    def desconectar(self, sessao_id: str) -> None:
        self.sessoes.pop(sessao_id, None)

    def _difundir(self) -> None:
        dono = self.dono_ok()
        blocos = self.listar()
        for sid, s in list(self.sessoes.items()):
            try:
                s.sincronizar(blocos, dono)
            except Exception:
                self.sessoes.pop(sid, None)                  # sessão quebrada/lenta sai; as outras seguem

    # ── operações ──────────────────────────────────────
    def listar(self) -> list[Bloco]:
        return list(self.blocos.values())

    def _preencher(self, b: Bloco) -> None:
        f = self.fontes.get(b.fonte) if b.fonte else None
        if b.fonte and not f:
            raise BlocoInvalido(f"fonte desconhecida: {b.fonte} (existem: {', '.join(x['nome'] for x in self.fontes.listar())})")
        if not f:
            return
        b.privado = b.privado or f.privada
        if not b.intervalo_s and f.intervalo_padrao:
            b.intervalo_s = f.intervalo_padrao
        try:
            tipo, conteudo = self.fontes.ler(b.fonte, b.parametros)
            b.tipo = tipo
            b.conteudo = validar({"tipo": tipo, "titulo": b.titulo, "conteudo": conteudo}).conteudo
            self.erros_fonte.pop(b.id, None)
        except Exception as e:
            self.erros_fonte[b.id] = f"{type(e).__name__}: {str(e)[:120]}"
            if b.id not in self._ultima_leitura:              # nunca leu: mostra o erro; já leu: mantém o último dado bom
                b.tipo, b.conteudo = "status", {"estado": "ruim", "texto": f"fonte {b.fonte} falhou: {type(e).__name__}"}
        self._ultima_leitura[b.id] = self.relogio()

    def abrir(self, d: dict | Bloco, origem: str = "jaime") -> Bloco:
        b = validar(d)
        b.criado_por = origem if origem else b.criado_por
        self._preencher(b)
        antes = self.blocos.get(b.id)
        agora = self.relogio()
        if antes:
            b.criado, b.versao = antes.criado, antes.versao + 1
        else:
            b.criado = agora
        b.atualizado = agora
        if not antes and len(self.blocos) >= self.max_abertos:
            # cheio: sai o de menor prioridade que está há mais tempo sem mudar (nunca o que acabou de chegar)
            velho = min(self.blocos.values(), key=lambda x: (x.prioridade, x.atualizado))
            self._fechar_um(velho.id, "limite de blocos abertos")
        self.blocos[b.id] = b
        self._registrar("abrir", antes, b)
        if self.uso and not antes:
            self.uso.abriu(b, agora)
        self.emitir("bloco", acao="abrir", id=b.id, titulo=b.titulo, tipo=b.tipo)
        self._difundir()
        if b.falar and self.falar:
            try:
                self.falar(resumo_falado(b))
            except Exception:
                pass
        return b

    def atualizar(self, bid: str, patch: dict) -> Bloco:
        atual = self.blocos.get(bid)
        if not atual:
            raise KeyError(bid)
        d = atual.to_dict()
        for k, v in (patch or {}).items():
            if k in ("id", "criado", "versao", "v"):
                continue
            if k == "conteudo" and isinstance(v, dict) and isinstance(d.get("conteudo"), dict) and patch.get("tipo") in (None, atual.tipo):
                d["conteudo"] = {**d["conteudo"], **v}
            elif k == "ancoragem" and isinstance(v, dict):
                d["ancoragem"] = {**(d.get("ancoragem") or {}), **v}
            else:
                d[k] = v
        novo = validar(d)
        novo.criado, novo.versao, novo.atualizado = atual.criado, atual.versao + 1, self.relogio()
        novo.criado_por = atual.criado_por
        if novo.fonte != atual.fonte or novo.parametros != atual.parametros:
            self._preencher(novo)
        self.blocos[bid] = novo
        self._registrar("atualizar", atual, novo)
        self._difundir()
        return novo

    def mover(self, bid: str, ancoragem: dict) -> Bloco:
        return self.atualizar(bid, {"ancoragem": ancoragem})

    def _fechar_um(self, bid: str, motivo: str) -> Bloco | None:
        b = self.blocos.pop(bid, None)
        if b:
            self._registrar("fechar", b, None)
            self._ultima_leitura.pop(bid, None)
            if self.uso:
                self.uso.fechou(b, self.relogio(), motivo)
            self.emitir("bloco", acao="fechar", id=bid, titulo=b.titulo, motivo=motivo)
        return b

    def fechar(self, bid: str, motivo: str = "pedido") -> list[str]:
        ids = list(self.blocos) if bid in ("todos", "*") else [bid]
        fechados = [i for i in ids if self._fechar_um(i, motivo)]
        if fechados:
            self._difundir()
        return fechados

    def ler(self, bid: str) -> str:
        b = self.blocos.get(bid)
        if not b:
            return ""
        texto = resumo_falado(b)
        if self.falar:
            self.falar(texto)
        return texto

    # ── desfazer ───────────────────────────────────────
    def _registrar(self, op: str, antes: Bloco | None, depois: Bloco | None) -> None:
        self._desfazer.append((op, antes.to_dict() if antes else None, depois.to_dict() if depois else None))
        del self._desfazer[:-MAX_DESFAZER]

    def desfazer(self) -> str:
        if not self._desfazer:
            return "nada a desfazer"
        op, antes, depois = self._desfazer.pop()
        if antes is None and depois:                          # desfazer abrir = fechar
            self.blocos.pop(depois["id"], None)
        elif antes:                                           # desfazer atualizar/fechar = voltar como era
            b = validar(antes)
            b.criado, b.versao = antes.get("criado", b.criado), int(antes.get("versao", 1))
            b.atualizado = self.relogio()
            self.blocos[b.id] = b
        self._difundir()
        return f"desfeito: {op} de «{(antes or depois or {}).get('titulo', '')}»"

    # ── layouts ────────────────────────────────────────
    def _arquivo_layouts(self) -> Path | None:
        return self.pasta / "layouts.json" if self.pasta else None

    def layouts(self) -> dict:
        a = self._arquivo_layouts()
        if not a or not a.exists():
            return {}
        try:
            return json.loads(a.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def salvar_layout(self, nome: str) -> int:
        """Guarda o que está aberto AGORA. Bloco com fonte guarda só a receita (fonte + parâmetros): reabrir traz o dado
        de hoje, não uma foto velha. Bloco privado estático não é gravado em disco — só a referência à fonte."""
        a = self._arquivo_layouts()
        if not a:
            raise RuntimeError("layouts precisam de uma pasta")
        todos = self.layouts()
        itens = []
        for b in self.listar():
            d = b.to_dict()
            if b.fonte:
                d["conteudo"] = {}
            elif b.privado:
                continue
            itens.append(d)
        todos[nome.strip().lower()] = {"blocos": itens, "salvo": time.strftime("%Y-%m-%d %H:%M")}
        a.parent.mkdir(parents=True, exist_ok=True)
        a.write_text(json.dumps(todos, ensure_ascii=False, indent=1), encoding="utf-8")
        return len(itens)

    def abrir_layout(self, nome: str, substituir: bool = True) -> list[str]:
        lay = self.layouts().get(nome.strip().lower())
        if not lay:
            raise KeyError(f"layout '{nome}' não existe (tenho: {', '.join(self.layouts()) or 'nenhum'})")
        if substituir:
            for bid in list(self.blocos):
                self._fechar_um(bid, f"layout {nome}")
        abertos = []
        for d in lay["blocos"]:
            try:
                abertos.append(self.abrir(d, origem=d.get("criado_por") or "jaime").id)
            except BlocoInvalido:
                continue
        self._difundir()
        return abertos

    # ── laço: TTL e fontes vivas ───────────────────────
    async def tique(self) -> None:
        agora = self.relogio()
        mudou = False
        for b in list(self.blocos.values()):
            if b.ttl_s and agora - b.criado >= b.ttl_s:
                self._fechar_um(b.id, "ttl"); mudou = True
                continue
            if b.fonte and b.intervalo_s and agora - self._ultima_leitura.get(b.id, 0) >= b.intervalo_s:
                antes = copy.deepcopy(b.conteudo)
                await asyncio.to_thread(self._preencher, b)
                if b.conteudo != antes:
                    b.versao += 1; b.atualizado = agora; mudou = True
        # difunde mesmo sem mudança: o cérebro pode ter trancado (bloco privado some das superfícies)
        self._difundir() if mudou else self._ressincronizar_privacidade()

    def _ressincronizar_privacidade(self) -> None:
        dono = self.dono_ok()
        if getattr(self, "_dono_antes", None) != dono:
            self._dono_antes = dono
            self._difundir()

    async def rodar(self, intervalo: float = 1.0) -> None:
        while True:
            try:
                await self.tique()
            except Exception as e:
                self.emitir("bloco", acao="erro", msg=f"{type(e).__name__}: {str(e)[:120]}")
            await asyncio.sleep(intervalo)
