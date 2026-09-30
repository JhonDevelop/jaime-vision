"""Fase 5 — várias câmeras: sincronização, triangulação (DLT) validada por erro de reprojeção, fallback 2D.

Regras que este módulo impõe:
- 3D só com ≥2 câmeras CALIBRADAS (intrínsecos K + extrínsecos R|t), observações dentro da janela de sincronia
  e confiança mínima em cada uma. Uma webcam sozinha NUNCA dá posição métrica — cai para 2D (plano do HUD).
- O ponto triangulado é reprojetado em cada câmera; erro acima do limite = rejeita (calibração velha, par
  errado, oclusão) e cai para 2D. Melhor apontar em 2D do que agir num 3D inventado.
- Calibração tem versão e impressão; frame de outra versão de calibração não é triangulado.

A calibração em si (tabuleiro de xadrez, `cv2.calibrateCamera`/`stereoCalibrate`) precisa do OpenCV e das
câmeras reais — fica PENDENTE no hardware do João; aqui entra o formato e a matemática, testados com câmeras
sintéticas."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from .core import Vec3
from .geometry import CameraObservation, synchronized


@dataclass
class Camera:
    id: str
    K: np.ndarray            # 3×3 intrínsecos (px)
    R: np.ndarray            # 3×3 rotação mundo→câmera
    t: np.ndarray            # 3 translação (m)
    largura: int = 1280
    altura: int = 720
    versao: int = 1

    @property
    def P(self) -> np.ndarray:
        return self.K @ np.hstack([self.R, self.t.reshape(3, 1)])

    def projetar(self, X: np.ndarray) -> tuple[float, float] | None:
        Xc = self.R @ X + self.t
        if Xc[2] <= 1e-6:
            return None                      # atrás da câmera
        u = self.K @ (Xc / Xc[2])
        return float(u[0]), float(u[1])

    def to_dict(self) -> dict:
        return {"id": self.id, "K": self.K.tolist(), "R": self.R.tolist(), "t": self.t.tolist(),
                "largura": self.largura, "altura": self.altura, "versao": self.versao}

    @classmethod
    def de_dict(cls, d: dict) -> "Camera":
        return cls(str(d["id"]), np.array(d["K"], float), np.array(d["R"], float), np.array(d["t"], float),
                   int(d.get("largura", 1280)), int(d.get("altura", 720)), int(d.get("versao", 1)))


def salvar(cams: list[Camera], caminho) -> Path:
    p = Path(caminho).expanduser(); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"v": 1, "cameras": [c.to_dict() for c in cams]}, indent=1), encoding="utf-8")
    return p


def carregar(caminho) -> list[Camera]:
    d = json.loads(Path(caminho).expanduser().read_text(encoding="utf-8"))
    return [Camera.de_dict(c) for c in d.get("cameras", [])]


def triangular(pares: list[tuple[np.ndarray, tuple[float, float]]]) -> np.ndarray:
    """DLT linear: cada câmera (P, (u, v)) contribui duas equações; solução = menor vetor singular."""
    A = []
    for P, (u, v) in pares:
        A.append(u * P[2] - P[0])
        A.append(v * P[2] - P[1])
    _, _, Vt = np.linalg.svd(np.asarray(A))
    X = Vt[-1]
    if abs(X[3]) < 1e-12:
        raise ValueError("ponto no infinito (câmeras paralelas ou pares inconsistentes)")
    return X[:3] / X[3]


@dataclass
class Resultado:
    modo: str                     # "3d" | "2d" | "nenhum"
    pos: Vec3 | None
    erro_px: float | None = None
    cameras: tuple[str, ...] = ()
    motivo: str = ""


class Triangulador:
    def __init__(self, cameras: list[Camera], janela_s: float = 0.025, max_reproj_px: float = 4.0, conf_min: float = 0.65):
        self.cams = {c.id: c for c in cameras}
        self.janela_s, self.max_reproj_px, self.conf_min = janela_s, max_reproj_px, conf_min

    def ponto(self, obs: list[CameraObservation], calib_versao: dict[str, int] | None = None) -> Resultado:
        validas = [o for o in obs if o.confidence >= self.conf_min]
        if not validas:
            return Resultado("nenhum", None, motivo="nenhuma câmera vê a mão com confiança")
        calibradas = [o for o in validas if o.camera_id in self.cams and
                      (calib_versao is None or calib_versao.get(o.camera_id) == self.cams[o.camera_id].versao)]
        if len(calibradas) >= 2 and synchronized(calibradas, self.janela_s):
            pares = [(self.cams[o.camera_id].P, o.point_px) for o in calibradas]
            try:
                X = triangular(pares)
            except (ValueError, np.linalg.LinAlgError) as e:
                return self._plano(validas, f"triangulação falhou: {e}")
            erros = []
            for o in calibradas:
                pr = self.cams[o.camera_id].projetar(X)
                if pr is None:
                    return self._plano(validas, "ponto atrás de uma câmera: par inconsistente")
                erros.append(((pr[0] - o.point_px[0]) ** 2 + (pr[1] - o.point_px[1]) ** 2) ** 0.5)
            e = max(erros)
            if e > self.max_reproj_px:
                return self._plano(validas, f"erro de reprojeção {e:.1f}px > {self.max_reproj_px}px — calibração/sincronia suspeita")
            return Resultado("3d", Vec3(*map(float, X)), round(e, 3), tuple(o.camera_id for o in calibradas))
        motivo = ("só uma câmera calibrada/válida" if len(calibradas) < 2 else
                  "câmeras fora de sincronia (janela excedida)")
        return self._plano(validas, motivo)

    def _plano(self, validas: list[CameraObservation], motivo: str) -> Resultado:
        """Fallback 2D: a melhor observação, normalizada pela resolução da câmera — posição no plano do HUD,
        sem profundidade métrica."""
        o = max(validas, key=lambda o: o.confidence)
        cam = self.cams.get(o.camera_id)
        w, h = (cam.largura, cam.altura) if cam else (1280, 720)
        return Resultado("2d", Vec3(o.point_px[0] / w, o.point_px[1] / h, 0.0), None, (o.camera_id,), motivo)


def parear(fluxos: dict[str, list[CameraObservation]], janela_s: float = 0.025) -> list[list[CameraObservation]]:
    """Agrupa observações de câmeras diferentes pelo instante mais próximo (câmeras com fps desigual).
    Cada observação entra em no máximo um grupo; grupos fora da janela ficam de fora."""
    if not fluxos:
        return []
    ref_id = min(fluxos, key=lambda k: len(fluxos[k]))          # a câmera mais lenta dita o ritmo
    grupos = []
    usados: dict[str, set[int]] = {k: set() for k in fluxos}
    for o in fluxos[ref_id]:
        g = [o]
        for cid, lista in fluxos.items():
            if cid == ref_id:
                continue
            melhor = None
            for i, x in enumerate(lista):
                if i in usados[cid]:
                    continue
                d = abs(x.timestamp - o.timestamp)
                if d <= janela_s and (melhor is None or d < melhor[0]):
                    melhor = (d, i, x)
            if melhor:
                usados[cid].add(melhor[1]); g.append(melhor[2])
        if len(g) >= 2:
            grupos.append(g)
    return grupos


def camera_sintetica(cid: str, posicao: tuple[float, float, float], olhando_para=(0.0, 0.0, 0.0), f: float = 900.0,
                     largura: int = 1280, altura: int = 720) -> Camera:
    """Câmera pinhole sintética (testes, simulador): posição no mundo e ponto para onde olha."""
    c = np.array(posicao, float); alvo = np.array(olhando_para, float)
    z = alvo - c; z /= np.linalg.norm(z)
    up = np.array([0.0, -1.0, 0.0])
    x = np.cross(up, z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    R = np.vstack([x, y, z])
    t = -R @ c
    K = np.array([[f, 0, largura / 2], [0, f, altura / 2], [0, 0, 1]], float)
    return Camera(cid, K, R, t, largura, altura)
