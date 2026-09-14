"""Partes puras do sistema de voz e do HUD: segmentador por VAD, corte em frases, ativação por nome,
pedidos de teclado, parser do `claude mcp list`. Nada aqui toca microfone, rede ou modelo."""
from jaime.voice.escuta import Segmentador, frases, quer_teclado, interpretar_chamada
from jaime.hud.conexoes import parse_mcp_list

F = b"\x00" * 1024   # um frame de 512 amostras int16

def _rodar(seg, sequencia):
    """sequencia: lista de (probabilidade_de_voz, quantos_frames). Devolve as falas completas que saíram."""
    falas = []
    for prob, n in sequencia:
        for _ in range(n):
            f = seg.alimentar(prob, F)
            if f: falas.append(f)
    return falas

def test_segmentador_detecta_fala_e_fim_por_silencio():
    seg = Segmentador(silencio_ms=640, min_fala_ms=300)
    falas = _rodar(seg, [(0.05, 40), (0.95, 20), (0.05, 30)])   # silêncio, 640 ms de voz, 960 ms de silêncio
    assert len(falas) == 1
    assert len(falas[0]) > 20 * len(F)          # inclui o pré-roll além dos frames de voz

def test_segmentador_ignora_ruido_curto():
    seg = Segmentador(silencio_ms=640, min_fala_ms=350)
    assert _rodar(seg, [(0.05, 40), (0.95, 3), (0.05, 40)]) == []   # 96 ms de "voz" = porta batendo

def test_segmentador_histerese_nao_corta_pausa_curta():
    seg = Segmentador(silencio_ms=640, min_fala_ms=300)
    falas = _rodar(seg, [(0.9, 10), (0.4, 8), (0.9, 10), (0.05, 30)])  # queda para 0.4 (>= fim) não é silêncio
    assert len(falas) == 1

def test_frases_corta_por_pontuacao_e_guarda_resto():
    prontas, resto = frases("Oi, João. Estou online! Tudo certo? Ainda estou falando")
    assert prontas == ["Oi, João.", "Estou online!", "Tudo certo?"]
    assert resto == "Ainda estou falando"
    assert frases("sem ponto") == ([], "sem ponto")

def test_quer_teclado():
    assert quer_teclado("Teclado.") and quer_teclado("deixa eu escrever")
    assert not quer_teclado("abre o navegador")

def test_ativacao_por_nome():
    assert interpretar_chamada("Jaime, está aí?") == ("chamou", "")
    assert interpretar_chamada("Ô Jaime!") == ("chamou", "")
    assert interpretar_chamada("Jaime, abre o Finder.") == ("pediu", "abre o Finder.")
    assert interpretar_chamada("Ei Jaime, que horas são?") == ("pediu", "que horas são?")
    assert interpretar_chamada("Jayme me ouve?") == ("chamou", "")
    assert interpretar_chamada("abre o Finder") == ("sem_nome", "abre o Finder")
    assert interpretar_chamada("abre o Finder", modo="sempre") == ("pediu", "abre o Finder")

def test_parse_mcp_list():
    saida = """Checking MCP server health…

claude.ai GitHub: https://api.githubcopilot.com/mcp - ✔ Connected
claude.ai n8n: https://x.app.n8n.cloud/mcp-server/http - ✘ Failed to connect — HTTP 404
claude.ai Notion: https://mcp.notion.com/mcp - ✔ Connected
claude.ai Canva: https://mcp.canva.com/mcp - ! Needs authentication
"""
    r = parse_mcp_list(saida)
    assert r["github"]["ligado"] and r["notion"]["ligado"] and not r["n8n"]["ligado"]
    assert "404" in r["n8n"]["detalhe"] and "canva" not in r
