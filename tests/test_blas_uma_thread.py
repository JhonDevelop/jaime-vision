"""M-46: deadlock fork × OpenBLAS (21/09 15:20). Importar o pacote fixa BLAS com 1 thread antes do numpy, num processo limpo."""
import os, subprocess, sys

def test_importar_jaime_fixa_blas_com_uma_thread_antes_do_numpy():
    env = {k: v for k, v in os.environ.items() if not k.endswith("_NUM_THREADS") and k != "VECLIB_MAXIMUM_THREADS"}
    env["PYTHONPATH"] = os.getcwd()
    codigo = ("import jaime, os, numpy\n"
              "print(os.environ['OPENBLAS_NUM_THREADS'], os.environ['OMP_NUM_THREADS'], os.environ['MKL_NUM_THREADS'])")
    out = subprocess.run([sys.executable, "-c", codigo], env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-400:]
    assert out.stdout.split() == ["1", "1", "1"]

def test_valor_do_ambiente_do_joao_prevalece():
    env = dict(os.environ); env["OPENBLAS_NUM_THREADS"] = "2"; env["PYTHONPATH"] = os.getcwd()
    out = subprocess.run([sys.executable, "-c", "import jaime, os; print(os.environ['OPENBLAS_NUM_THREADS'])"], env=env, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "2"                    # setdefault: quem já configurou manda
