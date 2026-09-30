# Hermes Agent ao lado do J.A.I.M.E (Windows) — rode VOCÊ, João, no PowerShell: .\scripts\hermes\instalar.ps1
# Mesmo roteiro do instalar.sh (docs/HERMES.md): instalador oficial (pergunta antes), API local 127.0.0.1:8642 com
# chave aleatória, aprovação MANUAL, chave gravada no .env do Jaime sem aparecer, gateway como Tarefa Agendada no logon.
$ErrorActionPreference = "Stop"
$Raiz = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$EnvJaime = Join-Path $Raiz ".env"
function Pergunta($t) { (Read-Host "$t [s/N]") -match '^[sS]' }

if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
  Write-Host "Hermes não encontrado. Instalador oficial: iex (irm https://hermes-agent.nousresearch.com/install.ps1)"
  if (-not (Pergunta "Rodar o instalador oficial agora?")) { Write-Host "ok, nada instalado."; exit 0 }
  Invoke-Expression (Invoke-RestMethod https://hermes-agent.nousresearch.com/install.ps1)
  $env:Path = "$env:LOCALAPPDATA\hermes\bin;$env:Path"
}
hermes --version | Select-Object -First 1
if (-not (hermes config get model 2>$null)) { hermes setup }

hermes config set approvals.mode manual
hermes config set approvals.deny '["git push --force*", "git push*main*", "*curl*|*sh*", "*iex*irm*", "Remove-Item * -Recurse*", "format *"]'

$bytes = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$Chave = -join ($bytes | ForEach-Object { $_.ToString("x2") })
hermes config set API_SERVER_ENABLED true | Out-Null
hermes config set API_SERVER_KEY $Chave | Out-Null
hermes config set API_SERVER_HOST 127.0.0.1 | Out-Null
$linhas = @(); if (Test-Path $EnvJaime) { $linhas = Get-Content $EnvJaime | Where-Object { $_ -notmatch '^(HERMES_API_KEY|JAIME_HERMES|HERMES_URL)=' } }
$linhas + @("JAIME_HERMES=on", "HERMES_URL=http://127.0.0.1:8642", "HERMES_API_KEY=$Chave") | Set-Content -Encoding UTF8 $EnvJaime
Remove-Variable Chave
Write-Host "  chave gravada no .env do Jaime e no .env do Hermes (não mostrada)."

if (Pergunta "Importar skills, MCPs e instruções do Claude Code para o Hermes?") {
  hermes import-agent claude-code --dry-run; if (Pergunta "Aplicar?") { hermes import-agent claude-code --yes }
}
if (Pergunta "Deixar o gateway do Hermes ligado no logon (Tarefa Agendada 'Jaime Hermes')?") {
  $exe = (Get-Command hermes).Source
  $acao = New-ScheduledTaskAction -Execute $exe -Argument "gateway"
  $gatilho = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
  Register-ScheduledTask -TaskName "Jaime Hermes" -Action $acao -Trigger $gatilho -Force | Out-Null
  Start-ScheduledTask -TaskName "Jaime Hermes"
} else { Write-Host "Para subir na mão: hermes gateway   (API em http://127.0.0.1:8642)" }
Write-Host "Pronto. Reinicie o Jaime e pergunte: 'Jaime, o Hermes está no ar?'"
