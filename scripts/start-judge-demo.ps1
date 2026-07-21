[CmdletBinding()]
param(
    [switch]$UseOllama,
    [switch]$EnableTts,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv. Run: py -3.11 -m venv .venv"
}

$env:RAYLUNO_LANGUAGE = "ar"
$env:RAYLUNO_STT_BACKEND = "vosk"
$env:RAYLUNO_WHISPER_LANGUAGE = "ar"
$env:RAYLUNO_RMS_THRESHOLD = "250"
$env:RAYLUNO_TTS_ENABLED = if ($EnableTts) { "true" } else { "false" }

Push-Location $RepoRoot
try {
    Write-Host "Rayluno judge preflight" -ForegroundColor Cyan
    Write-Host "  Voice input : local Vosk push-to-talk"
    Write-Host "  Voice reply : $($env:RAYLUNO_TTS_ENABLED)"
    Write-Host "  Local AI    : $($UseOllama.IsPresent)"
    Write-Host "  Permissions : existing registered skills only"

    & $Python -m future_assistant.safe_voice_cli --doctor
    if ($LASTEXITCODE -ne 0) {
        throw "Rayluno preflight failed. Resolve the reported dependency or model issue first."
    }
    if ($CheckOnly) {
        Write-Host "Preflight passed." -ForegroundColor Green
        exit 0
    }

    $LaunchArguments = @(
        "-m",
        "future_assistant.safe_voice_cli",
        "--ui",
        "--judge-demo"
    )
    if ($UseOllama) {
        $LaunchArguments += "--ollama"
    }

    & $Python @LaunchArguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
