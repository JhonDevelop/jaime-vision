"""O instalador de uma linha, montado sob medida para cada máquina convidada.

    curl -fsSL http://192.168.200.23:8787/frota/instalar?c=CODIGO | sh

O João pediu «se precisar baixar a parte do Jaime também». Esta é a parte: o agente da frota, e só ele.
Nada de vault, nada de voz, nada de servidor — numa máquina da frota o Jaime não fala nem escuta, porque
quem fala e escuta é o Jaime da máquina do João. Dois Jaimes com microfone no mesmo ambiente se ouvem e se
interrompem; um Jaime com vários braços não.

O que o script faz, em ordem, e por que dá para ler antes de rodar:

 1. escreve `~/.jaime-frota/` com o agente e a configuração (o token já dentro, com permissão 600);
 2. mostra o que vai poder ser feito ali, em português, e ESPERA o dono confirmar;
 3. opcionalmente instala o serviço que sobe no boot — só se o dono pedir;
 4. liga o agente.

O passo 2 existe porque um instalador que não mostra o que instala é um instalador em que não se deve
confiar, ainda mais vindo por `curl | sh`. Quem estiver na frente da máquina lê e decide."""
from __future__ import annotations

from .registro import NaFrota

# O agente é baixado do próprio servidor do João em vez de embutido aqui: assim a máquina nova pega sempre
# a versão que está rodando na casa, e uma correção de segurança no agente chega a todas de uma vez.
CAMINHO_AGENTE = "/frota/agente.py"


def script(base: str, m: NaFrota, token: str) -> str:
    """O shell script daquela máquina, com o token e o nível dela já dentro."""
    alcance = m.pasta or "$HOME"
    pode = ("ler, escrever e rodar comando" if m.nivel in ("operador", "dono") else "apenas ler e listar")
    return f"""#!/bin/sh
# Agente da frota do J.A.I.M.E — máquina «{m.apelido}», de {m.dono}
# Gerado sob medida para esta máquina. Leia antes de deixar rodar.
set -eu

PASTA="$HOME/.jaime-frota"
ALCANCE="{alcance}"

printf '\\n'
printf '  J.A.I.M.E — entrar na frota do João\\n'
printf '  ═══════════════════════════════════\\n\\n'
printf '  Esta máquina entraria como : {m.apelido}  (dono: {m.dono})\\n'
printf '  O Jaime poderia            : {pode}\\n'
printf '  E somente dentro de        : %s\\n' "$ALCANCE"
printf '  A conexão                  : SAI desta máquina. Nada entra; nenhuma porta é aberta.\\n'
printf '  Protegido sempre           : .ssh, .env, chaves, keychain — nem no nível dono.\\n'
printf '  Para encerrar              : Ctrl-C, ou apagar %s\\n' "$PASTA"
printf '\\n  Voz e microfone continuam SÓ na máquina do João. Aqui não fala nem escuta.\\n'
printf '\\n  Digite «sim» para instalar: '
read RESPOSTA
[ "$RESPOSTA" = "sim" ] || {{ printf '  Cancelado. Nada foi instalado.\\n'; exit 1; }}

command -v python3 >/dev/null 2>&1 || {{ printf '\\n  ✗ Preciso de python3 nesta máquina.\\n'; exit 1; }}

mkdir -p "$PASTA"
chmod 700 "$PASTA"
printf '  … baixando o agente\\n'
curl -fsSL '{base}{CAMINHO_AGENTE}' -o "$PASTA/agente.py"

cat > "$PASTA/config.env" <<CFG
JAIME_SERVIDOR={base}
JAIME_FROTA_TOKEN={token}
JAIME_NIVEL={m.nivel}
JAIME_PASTA={m.pasta}
CFG
chmod 600 "$PASTA/config.env"

cat > "$PASTA/ligar.sh" <<'LIGA'
#!/bin/sh
set -eu
. "$HOME/.jaime-frota/config.env"
export JAIME_SERVIDOR JAIME_FROTA_TOKEN JAIME_NIVEL JAIME_PASTA
exec python3 "$HOME/.jaime-frota/agente.py"
LIGA
chmod +x "$PASTA/ligar.sh"

printf '\\n  ✓ Instalado em %s\\n' "$PASTA"
printf '    Religar depois:  sh ~/.jaime-frota/ligar.sh\\n\\n'
printf '  Quer que ele suba sozinho quando esta máquina ligar? (sim/não): '
read NOBOOT
if [ "$NOBOOT" = "sim" ]; then
  if [ "$(uname)" = "Darwin" ]; then
    PLIST="$HOME/Library/LaunchAgents/com.jaime.frota.plist"
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.jaime.frota</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string><string>$HOME/.jaime-frota/ligar.sh</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/.jaime-frota/log.txt</string>
  <key>StandardErrorPath</key><string>$HOME/.jaime-frota/log.txt</string>
</dict></plist>
PL
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    printf '  ✓ Sobe no boot. Desligar de vez:  launchctl unload %s && rm %s\\n\\n' "$PLIST" "$PLIST"
    printf '  Já está rodando pelo serviço. Pronto.\\n'
    exit 0
  else
    printf '  (boot automático aqui só no macOS por enquanto; rode ~/.jaime-frota/ligar.sh)\\n'
  fi
fi

printf '\\n  Ligando agora. Ctrl-C encerra e o acesso acaba junto.\\n\\n'
exec sh "$PASTA/ligar.sh"
"""
