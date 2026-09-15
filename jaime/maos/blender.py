"""Blender headless: o Jaime escreve um script Python (bpy) e roda `blender -b -P script.py -- saida.blend`.
Sem o Blender instalado, devolve o script salvo e a instrução de onde baixar (blender.org)."""
from __future__ import annotations
import os, shutil, subprocess, time
from pathlib import Path
from ..identidade import slug

PASTA = Path(os.environ.get("JAIME_3D", "~/Jaime/3d")).expanduser()
CANDIDATOS = [os.environ.get("JAIME_BLENDER", ""), "/Applications/Blender.app/Contents/MacOS/Blender", shutil.which("blender") or ""]

def binario() -> str | None:
    for c in CANDIDATOS:
        if c and Path(c).exists():
            return c
    return None

CABECALHO = '''import bpy, sys
# limpa a cena padrão
bpy.ops.wm.read_factory_settings(use_empty=True)
saida = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "saida.blend"
'''
RODAPE = '''
bpy.ops.wm.save_as_mainfile(filepath=saida)
print("BLEND_OK", saida)
'''

def montar_script(corpo_bpy: str) -> str:
    """corpo_bpy: código bpy que cria a cena (objetos, materiais, câmera, luz). Cabeçalho e salvamento são nossos."""
    return CABECALHO + "\n" + corpo_bpy.strip() + "\n" + RODAPE

def gerar_blend(nome: str, corpo_bpy: str, timeout: int = 300) -> dict:
    PASTA.mkdir(parents=True, exist_ok=True)
    base = PASTA / f"{slug(nome)[:40] or 'modelo'}-{time.strftime('%Y%m%d-%H%M%S')}"
    script, blend = base.with_suffix(".py"), base.with_suffix(".blend")
    script.write_text(montar_script(corpo_bpy), encoding="utf-8")
    b = binario()
    if not b:
        return {"ok": False, "script": str(script), "blend": None,
                "erro": "Blender não instalado. Baixe em https://www.blender.org/download/ (macOS Intel) e arraste para /Applications; ou aponte JAIME_BLENDER no .env."}
    try:
        r = subprocess.run([b, "-b", "-P", str(script), "--", str(blend)], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "script": str(script), "blend": None, "erro": f"Blender passou de {timeout}s"}
    ok = blend.exists() and "BLEND_OK" in r.stdout
    return {"ok": ok, "script": str(script), "blend": str(blend) if ok else None,
            "erro": "" if ok else (r.stderr or r.stdout)[-400:]}
