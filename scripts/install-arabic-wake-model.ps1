param(
    # Rayluno intentionally retains this legacy technical user-data path so an
    # existing downloaded model remains usable after the product rebrand.
    [string]$Destination = (Join-Path $env:LOCALAPPDATA "FutureAssistant\models"),
    [switch]$SetUserEnvironment
)

$ErrorActionPreference = "Stop"
$modelName = "vosk-model-ar-mgb2-0.4"
$modelUrl = "https://alphacephei.com/vosk/models/$modelName.zip"
$root = [System.IO.Path]::GetFullPath($Destination)
$target = [System.IO.Path]::GetFullPath((Join-Path $root $modelName))
$archive = [System.IO.Path]::GetFullPath((Join-Path $root "$modelName.zip"))

if (-not $target.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "The model path is outside the destination directory."
}

New-Item -ItemType Directory -Path $root -Force | Out-Null
if (-not (Test-Path -LiteralPath $target)) {
    Invoke-WebRequest -UseBasicParsing -Uri $modelUrl -OutFile $archive
    try {
        Expand-Archive -LiteralPath $archive -DestinationPath $root -Force
    }
    finally {
        if (Test-Path -LiteralPath $archive) {
            Remove-Item -LiteralPath $archive -Force
        }
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $target "am\final.mdl"))) {
    throw "The download completed, but the Vosk model structure is invalid."
}

if ($SetUserEnvironment) {
    [Environment]::SetEnvironmentVariable(
        "FUTURE_ASSISTANT_VOSK_MODEL_PATH",
        $target,
        "User"
    )
}
$env:FUTURE_ASSISTANT_VOSK_MODEL_PATH = $target

Write-Output $target
