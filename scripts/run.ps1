param(
    [switch]$WithAI
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Run scripts\setup.ps1 first."
}

$arguments = @("-m", "future_assistant", "--ui")
if ($WithAI) {
    $arguments += "--ollama"
}
& $python @arguments
