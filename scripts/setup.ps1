param(
    [switch]$WithVoice
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    py -3.11 -m venv $venv
}

& $python -m pip install --upgrade pip
$extras = if ($WithVoice) { "dev,desktop,voice" } else { "dev,desktop" }
& $python -m pip install -e "${root}[$extras]"
& $python -m future_assistant --doctor

