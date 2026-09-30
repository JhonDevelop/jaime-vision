"""Arquivos 3D dos hologramas: OBJ, STL e GLB, sem dependência nova (só a biblioteca padrão).

Duas origens de malha:
- a TELA manda as malhas do jeito que o João deixou (peças movidas, giradas, escaladas, escondidas) — é o caminho
  normal, vale para os pré-fabricados, os gerados, os .glb e os desenhos;
- sem tela aberta, o servidor monta as malhas a partir da descrição em peças (`pecas` do holograma gerado).

Saída em `~/Jaime/hologramas/exportados/<nome>.<fmt>`; "abre no Blender" importa o GLB e salva um .blend ao lado.
"""
from __future__ import annotations
import json, math, os, platform, struct, subprocess, time
from pathlib import Path

from .holograma import PASTA, _slug

EXPORTADOS = PASTA / "exportados"
FORMATOS = ("stl", "obj", "glb")
MAX_VERTICES = 400_000


# ── primitivas (mesmas convenções do three.js da tela: y para cima, rot em XYZ) ─────────────────────
def _caixa(a, b, c):
    x, y, z = a / 2, b / 2, c / 2
    v = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z), (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (3, 7, 6), (3, 6, 2), (0, 4, 7), (0, 7, 3), (1, 2, 6), (1, 6, 5)]
    return v, f


def _revolucao(perfil, n=24):
    """Gira um perfil [(raio, y)] em torno do eixo y (cilindro, cone, esfera)."""
    v, f = [], []
    for r, y in perfil:
        for i in range(n):
            a = 2 * math.pi * i / n
            v.append((r * math.sin(a), y, r * math.cos(a)))
    for j in range(len(perfil) - 1):
        for i in range(n):
            a, b = j * n + i, j * n + (i + 1) % n
            c, d = a + n, b + n
            f += [(a, b, d), (a, d, c)]
    base, topo = len(v), len(v) + 1
    v += [(0, perfil[0][1], 0), (0, perfil[-1][1], 0)]
    ult = (len(perfil) - 1) * n
    for i in range(n):
        f.append((base, (i + 1) % n, i))
        f.append((topo, ult + i, ult + (i + 1) % n))
    return v, f


def _toro(R, r, n=32, m=10):
    v, f = [], []
    for i in range(n):
        u = 2 * math.pi * i / n
        for j in range(m):
            w = 2 * math.pi * j / m
            v.append(((R + r * math.cos(w)) * math.cos(u), (R + r * math.cos(w)) * math.sin(u), r * math.sin(w)))
    for i in range(n):
        for j in range(m):
            a, b = i * m + j, ((i + 1) % n) * m + j
            c, d = i * m + (j + 1) % m, ((i + 1) % n) * m + (j + 1) % m
            f += [(a, b, d), (a, d, c)]
    return v, f


def _tubo(pontos, raio, m=8):
    """Traço do desenho: um tubo ao longo da linha (quadro de referência simples, sem torção)."""
    pts = [tuple(map(float, p)) for p in pontos]
    if len(pts) < 2:
        return [], []
    v, f = [], []
    for k, p in enumerate(pts):
        q0, q1 = pts[max(0, k - 1)], pts[min(len(pts) - 1, k + 1)]
        t = _norm((q1[0] - q0[0], q1[1] - q0[1], q1[2] - q0[2]))
        up = (0, 1, 0) if abs(t[1]) < .9 else (1, 0, 0)
        n1 = _norm(_cruz(t, up)); n2 = _cruz(t, n1)
        for j in range(m):
            w = 2 * math.pi * j / m
            v.append(tuple(p[i] + raio * (math.cos(w) * n1[i] + math.sin(w) * n2[i]) for i in range(3)))
    for k in range(len(pts) - 1):
        for j in range(m):
            a, b = k * m + j, k * m + (j + 1) % m
            f += [(a, b, b + m), (a, b + m, a + m)]
    return v, f


def _norm(a):
    s = math.sqrt(sum(x * x for x in a)) or 1.0
    return tuple(x / s for x in a)


def _cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _rot(v, rx, ry, rz):
    """Euler XYZ do three.js (matriz = Rx·Ry·Rz aplicada ao vetor)."""
    x, y, z = v
    cz, sz = math.cos(rz), math.sin(rz); x, y = x * cz - y * sz, x * sz + y * cz
    cy, sy = math.cos(ry), math.sin(ry); x, z = x * cy + z * sy, -x * sy + z * cy
    cx, sx = math.cos(rx), math.sin(rx); y, z = y * cx - z * sx, y * sx + z * cx
    return x, y, z


def malha_da_peca(p: dict) -> dict:
    """Peça validada (holograma.validar_pecas) → {'nome', 'v': [x,y,z,...], 'f': [a,b,c,...]}."""
    a, b, c = p["tam"]
    forma = p["forma"]
    if forma == "caixa":
        v, f = _caixa(a, b, c)
    elif forma == "cilindro":
        v, f = _revolucao([(a, -b / 2), (a, b / 2)])
    elif forma == "cone":
        v, f = _revolucao([(a, -b / 2), (0.0001, b / 2)])
    elif forma == "esfera":
        v, f = _revolucao([(a * math.sin(math.pi * i / 12) + 1e-4, -a * math.cos(math.pi * i / 12)) for i in range(13)])
    elif forma == "toro":
        v, f = _toro(a, max(.02, b))
    elif forma == "tubo":
        v, f = _tubo(p.get("pontos") or [], max(.01, a))
    else:
        v, f = [], []
    rx, ry, rz = p.get("rot", [0, 0, 0])
    px, py, pz = p.get("pos", [0, 0, 0])
    vv = []
    for q in v:
        x, y, z = _rot(q, rx, ry, rz) if forma != "tubo" else q
        vv += [x + px, y + py, z + pz]
    return {"nome": p.get("nome") or forma, "v": vv, "f": [i for t in f for i in t]}


def validar_malhas(pecas) -> list[dict]:
    """O que a tela manda: nomes limpos, números finitos, índices dentro da malha, teto de vértices."""
    out, total = [], 0
    for p in (pecas or [])[:400]:
        if not isinstance(p, dict):
            continue
        v, f = p.get("v") or [], p.get("f") or []
        if len(v) < 9 or len(v) % 3 or len(f) < 3 or len(f) % 3:
            continue
        try:
            v = [float(x) for x in v]; f = [int(i) for i in f]
        except (TypeError, ValueError):
            continue
        n = len(v) // 3
        if not all(math.isfinite(x) and abs(x) < 1e4 for x in v) or any(i < 0 or i >= n for i in f):
            continue
        total += n
        if total > MAX_VERTICES:
            break
        nome = "".join(ch for ch in str(p.get("nome", "peça"))[:40] if ch.isalnum() or ch in " -_") or "peça"
        out.append({"nome": nome, "v": v, "f": f})
    return out


# ── escritores ─────────────────────────────────────────
def obj(pecas: list[dict]) -> str:
    linhas, base = ["# J.A.I.M.E · holograma"], 1
    for p in pecas:
        linhas.append(f"o {p['nome'].replace(' ', '_')}")
        v, f = p["v"], p["f"]
        linhas += [f"v {v[i]:.5f} {v[i + 1]:.5f} {v[i + 2]:.5f}" for i in range(0, len(v), 3)]
        linhas += [f"f {f[i] + base} {f[i + 1] + base} {f[i + 2] + base}" for i in range(0, len(f), 3)]
        base += len(v) // 3
    return "\n".join(linhas) + "\n"


def stl(pecas: list[dict], nome: str = "holograma") -> bytes:
    """STL binário (o que fatiador de impressora 3D e Blender esperam)."""
    tris = []
    for p in pecas:
        v, f = p["v"], p["f"]
        for i in range(0, len(f), 3):
            a, b, c = (tuple(v[3 * f[i + k]: 3 * f[i + k] + 3]) for k in range(3))
            n = _norm(_cruz(tuple(b[j] - a[j] for j in range(3)), tuple(c[j] - a[j] for j in range(3))))
            tris.append(struct.pack("<12fH", *n, *a, *b, *c, 0))
    cab = f"J.A.I.M.E {nome}".encode()[:80].ljust(80, b" ")
    return cab + struct.pack("<I", len(tris)) + b"".join(tris)


def glb(pecas: list[dict]) -> bytes:
    """glTF 2.0 binário: um nó por peça (o Blender importa com os nomes)."""
    binario, views, acessores, malhas, nos = bytearray(), [], [], [], []
    for p in pecas:
        v, f = p["v"], p["f"]
        xs, ys, zs = v[0::3], v[1::3], v[2::3]
        off = len(binario); binario += struct.pack(f"<{len(v)}f", *v)
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(v) * 4, "target": 34962})
        acessores.append({"bufferView": len(views) - 1, "componentType": 5126, "count": len(v) // 3, "type": "VEC3",
                          "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]})
        off = len(binario); binario += struct.pack(f"<{len(f)}I", *f)
        while len(binario) % 4:
            binario += b"\0"
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(f) * 4, "target": 34963})
        acessores.append({"bufferView": len(views) - 1, "componentType": 5125, "count": len(f), "type": "SCALAR"})
        malhas.append({"name": p["nome"], "primitives": [{"attributes": {"POSITION": len(acessores) - 2}, "indices": len(acessores) - 1, "material": 0}]})
        nos.append({"name": p["nome"], "mesh": len(malhas) - 1})
    doc = {"asset": {"version": "2.0", "generator": "J.A.I.M.E"}, "scene": 0, "scenes": [{"nodes": list(range(len(nos)))}],
           "nodes": nos, "meshes": malhas, "accessors": acessores, "bufferViews": views, "buffers": [{"byteLength": len(binario)}],
           "materials": [{"name": "holograma", "pbrMetallicRoughness": {"baseColorFactor": [0.24, 1.0, 0.63, 1.0], "metallicFactor": 0.1, "roughnessFactor": 0.6}}]}
    js = json.dumps(doc, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    corpo = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(binario), 0x004E4942) + bytes(binario)
    return struct.pack("<III", 0x46546C67, 2, 12 + len(corpo)) + corpo


def exportar(titulo: str, pecas: list[dict], formatos=FORMATOS, pasta: Path | None = None) -> dict:
    """Grava os arquivos; devolve {fmt: caminho}. Nome repetido não sobrescreve: ganha data e hora."""
    pasta = pasta or EXPORTADOS
    pasta.mkdir(parents=True, exist_ok=True)
    nome = _slug(titulo) or "holograma"
    if any((pasta / f"{nome}.{fmt}").exists() for fmt in formatos):
        nome = f"{nome}-{time.strftime('%Y%m%d-%H%M%S')}"
    feitos = {}
    for fmt in formatos:
        p = pasta / f"{nome}.{fmt}"
        if fmt == "obj":
            p.write_text(obj(pecas), encoding="utf-8")
        elif fmt == "stl":
            p.write_bytes(stl(pecas, titulo))
        elif fmt == "glb":
            p.write_bytes(glb(pecas))
        else:
            continue
        feitos[fmt] = str(p)
    return feitos


# ── Blender ───────────────────────────────────────────
SCRIPT_BLENDER = '''import bpy, sys
a = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=a[0])
bpy.ops.wm.save_as_mainfile(filepath=a[1])
print("BLEND_OK")
'''


def abrir_no_blender(glb_path: str, rodar=subprocess.run, abrir=subprocess.Popen, sistema: str | None = None) -> dict:
    """GLB → .blend (Blender em segundo plano) e abre a janela do Blender com ele. Não mexe em mais nada."""
    from ..maos.blender import binario
    b = binario()
    if not b:
        return {"ok": False, "erro": "Blender não está instalado (blender.org) ou JAIME_BLENDER não aponta para ele."}
    blend = str(Path(glb_path).with_suffix(".blend"))
    script = Path(glb_path).with_suffix(".import.py")
    script.write_text(SCRIPT_BLENDER, encoding="utf-8")
    try:
        r = rodar([b, "-b", "-P", str(script), "--", glb_path, blend], capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {"ok": False, "erro": "o Blender demorou demais para importar"}
    if "BLEND_OK" not in (r.stdout or ""):
        return {"ok": False, "erro": ((r.stderr or r.stdout) or "")[-300:]}
    s = sistema or platform.system()
    abrir(["open", "-a", b.split("/Contents/")[0], blend] if s == "Darwin" and "/Contents/" in b else [b, blend])
    return {"ok": True, "blend": blend}


# ── impressão 3D ──────────────────────────────────────
FATIADORES = {  # nome falado → apps (macOS) / binários (Windows/Linux)
    "Bambu Studio": ["/Applications/BambuStudio.app", r"C:\Program Files\Bambu Studio\bambu-studio.exe", "bambu-studio"],
    "OrcaSlicer": ["/Applications/OrcaSlicer.app", r"C:\Program Files\OrcaSlicer\orca-slicer.exe", "orca-slicer"],
    "PrusaSlicer": ["/Applications/Original Prusa Drivers/PrusaSlicer.app", "/Applications/PrusaSlicer.app",
                    r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer.exe", "prusa-slicer"],
    "Cura": ["/Applications/UltiMaker Cura.app", "/Applications/Ultimaker Cura.app", r"C:\Program Files\UltiMaker Cura\UltiMaker-Cura.exe", "cura"],
}


def para_impressao(pecas: list[dict], maior_mm: float = 100.0) -> list[dict]:
    """Holograma (metros de maquete, y para cima) → mesa da impressora: milímetros, Z para cima, apoiado em Z=0,
    centrado em X/Y, com a maior dimensão = `maior_mm`."""
    maior_mm = min(400.0, max(5.0, float(maior_mm or 100)))
    todos = [c for p in pecas for c in zip(p["v"][0::3], p["v"][1::3], p["v"][2::3])]
    if not todos:
        return []
    mn = [min(c[i] for c in todos) for i in range(3)]
    mx = [max(c[i] for c in todos) for i in range(3)]
    esc = maior_mm / (max(mx[i] - mn[i] for i in range(3)) or 1.0)
    cx, cz = (mn[0] + mx[0]) / 2, (mn[2] + mx[2]) / 2
    out = []
    for p in pecas:
        v = []
        for x, y, z in zip(p["v"][0::3], p["v"][1::3], p["v"][2::3]):
            # (x, y, z) y-up → (x, -z, y) z-up (mantém a orientação das faces)
            v += [round((x - cx) * esc, 4), round(-(z - cz) * esc, 4), round((y - mn[1]) * esc, 4)]
        out.append({"nome": p["nome"], "v": v, "f": p["f"]})
    return out


def fatiador(env=None) -> tuple[str, str] | None:
    """(nome, caminho) do primeiro fatiador instalado; JAIME_FATIADOR força um caminho."""
    import shutil
    e = os.environ if env is None else env
    if (f := e.get("JAIME_FATIADOR")) and (Path(f).exists() or shutil.which(f)):
        return Path(f).stem, f
    for nome, caminhos in FATIADORES.items():
        for c in caminhos:
            if ("/" in c or "\\" in c) and Path(c).exists():
                return nome, c
            if "/" not in c and "\\" not in c and shutil.which(c):
                return nome, shutil.which(c)
    return None


def abrir_no_fatiador(stl_path: str, abrir=subprocess.Popen, sistema: str | None = None, env=None) -> dict:
    """Só ABRE o arquivo no fatiador. Imprimir de verdade é o João quem aperta, lá."""
    f = fatiador(env)
    if not f:
        return {"ok": False, "erro": "nenhum fatiador instalado (Bambu Studio, OrcaSlicer, PrusaSlicer ou Cura)"}
    nome, caminho = f
    s = sistema or platform.system()
    abrir(["open", "-a", caminho, stl_path] if s == "Darwin" and caminho.endswith(".app") else [caminho, stl_path])
    return {"ok": True, "fatiador": nome}
