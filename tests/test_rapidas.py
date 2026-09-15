from datetime import datetime
from types import SimpleNamespace
from jaime.voice.rapidas import responder

class _V:
    def tarefas_abertas(self): return ["- [ ] ligar pro contador", "- [ ] revisar pitch"]
class _H:
    def rotulo(self): return "neutro"
J = SimpleNamespace(humor=_H(), vault=_V(), identidade=SimpleNamespace(nome="Jaime"), perfil=None)

def test_saudacoes_e_social_sem_modelo():
    assert responder("Bom dia, Jaime!", J, datetime(2026, 9, 15, 8)).startswith("Bom dia")
    assert responder("boa noite", J, datetime(2026, 9, 15, 21)).startswith("Boa noite")
    assert "E você" in responder("tudo bem?", J) or "senhor" in responder("tudo bem?", J)
    assert responder("valeu", J) in ("De nada.", "Às ordens.", "Disponha, senhor.", "É pra isso que estou aqui.")
    assert "assistente operacional" in responder("quem é você?", J)
    r = responder("como está o dia hoje?", J); assert "ligar pro contador" in r
    assert responder("bom dia, abre o Finder", J) is None and responder("abre o Finder", J) is None
