param(
    # Rayluno intentionally retains this legacy technical user-data path so an
    # existing downloaded model remains usable after the product rebrand.
    [string]$Destination = (Join-Path $env:LOCALAPPDATA "FutureAssistant\models"),
    [switch]$SetUserEnvironment
)

$ErrorActionPreference = "Stop"
$modelName = "vosk-model-small-en-us-0.15"
$modelUrl = "https://alphacephei.com/vosk/models/$modelName.zip"
$expectedSha256 = "30F26242C4EB449F948E42CB302DD7A686CB29A3423A8367F99FF41780942498"
$root = [System.IO.Path]::GetFullPath($Destination)
$target = [System.IO.Path]::GetFullPath((Join-Path $root $modelName))
$archive = [System.IO.Path]::GetFullPath((Join-Path $root "$modelName.zip"))

if (-not $target.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "The model path is outside the destination directory."
}

New-Item -ItemType Directory -Path $root -Force | Out-Null
if (-not (Test-Path -LiteralPath $target)) {
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -L --fail --retry 3 --output $archive $modelUrl
        if ($LASTEXITCODE -ne 0) {
            throw "The English Vosk model download failed."
        }
    }
    else {
        Invoke-WebRequest -UseBasicParsing -Uri $modelUrl -OutFile $archive
    }
    try {
        $actualSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash
        if ($actualSha256 -ne $expectedSha256) {
            throw "The English Vosk model checksum does not match the pinned release."
        }
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
        "FUTURE_ASSISTANT_VOSK_ENGLISH_MODEL_PATH",
        $target,
        "User"
    )
}
$env:FUTURE_ASSISTANT_VOSK_ENGLISH_MODEL_PATH = $target

Write-Output $target
