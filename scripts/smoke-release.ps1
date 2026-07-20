[CmdletBinding()]
param(
    [string]$ReleaseDir = "",
    [switch]$ExpectVoice,
    [switch]$LaunchGui,
    [switch]$IntegrityOnly
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
if (-not $ReleaseDir) {
    $ReleaseDir = Join-Path $root "dist\Rayluno"
}
if (-not (Test-Path -LiteralPath $ReleaseDir)) {
    throw "Release directory was not found: $ReleaseDir"
}
$ReleaseDir = (Resolve-Path -LiteralPath $ReleaseDir).Path

function Assert-FileHashManifest {
    param(
        [Parameter(Mandatory = $true)][string]$RootDirectory,
        [Parameter(Mandatory = $true)][string]$ManifestPath,
        [string[]]$ExcludedRelativePaths = @()
    )

    $resolvedRoot = (Resolve-Path -LiteralPath $RootDirectory).Path.TrimEnd("\")
    $rootPrefix = $resolvedRoot + "\"
    $excluded = New-Object 'System.Collections.Generic.HashSet[string]' `
        ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($excludedPath in $ExcludedRelativePaths) {
        [void]$excluded.Add($excludedPath.Replace("\", "/"))
    }
    $listed = New-Object 'System.Collections.Generic.HashSet[string]' `
        ([System.StringComparer]::OrdinalIgnoreCase)
    $lines = @(Get-Content -LiteralPath $ManifestPath)
    if ($lines.Count -eq 0) {
        throw "File hash manifest is empty: $ManifestPath"
    }

    foreach ($line in $lines) {
        if ($line -notmatch '^(?<hash>[0-9A-Fa-f]{64})  (?<path>.+)$') {
            throw "Malformed file hash manifest line in '$ManifestPath': $line"
        }
        $expectedHash = $Matches.hash.ToLowerInvariant()
        $relativePath = $Matches.path
        if ($relativePath.Contains("\") -or
            $relativePath.StartsWith("/") -or
            $relativePath -match '^[A-Za-z]:' -or
            $relativePath -match '[<>:"|?*]') {
            throw "Unsafe or non-canonical manifest path in '$ManifestPath': $relativePath"
        }
        $segments = @($relativePath.Split("/"))
        if ($segments.Count -eq 0 -or
            @($segments | Where-Object { $_ -eq "" -or $_ -eq "." -or $_ -eq ".." }).Count -ne 0) {
            throw "Manifest path traversal or empty segment in '$ManifestPath': $relativePath"
        }
        if ($excluded.Contains($relativePath)) {
            throw "The hash manifest must not list itself or another excluded path: $relativePath"
        }
        if (-not $listed.Add($relativePath)) {
            throw "Duplicate file hash manifest path in '$ManifestPath': $relativePath"
        }

        $candidatePath = [System.IO.Path]::GetFullPath(
            (Join-Path $resolvedRoot ($relativePath.Replace("/", "\")))
        )
        if (-not $candidatePath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Manifest path escapes its payload root in '$ManifestPath': $relativePath"
        }
        if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
            throw "File listed by hash manifest is missing: $relativePath"
        }
        $actualHash = (Get-FileHash -LiteralPath $candidatePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw "File checksum mismatch for '$relativePath' in '$ManifestPath'."
        }
    }

    $actualFiles = @(
        Get-ChildItem -LiteralPath $resolvedRoot -Recurse -File |
            ForEach-Object {
                $_.FullName.Substring($resolvedRoot.Length + 1).Replace("\", "/")
            } |
            Where-Object { -not $excluded.Contains($_) }
    )
    foreach ($relativePath in $actualFiles) {
        if (-not $listed.Contains($relativePath)) {
            throw "Payload file is not covered by '$ManifestPath': $relativePath"
        }
    }
    if ($listed.Count -ne $actualFiles.Count) {
        throw "File hash manifest coverage count mismatch in '$ManifestPath'."
    }

    return [ordered]@{
        file_count = $actualFiles.Count
        size_bytes = [long](
            (
                Get-ChildItem -LiteralPath $resolvedRoot -Recurse -File |
                    Where-Object {
                        $relativePath = $_.FullName.Substring($resolvedRoot.Length + 1).Replace("\", "/")
                        -not $excluded.Contains($relativePath)
                    } |
                    Measure-Object -Property Length -Sum
            ).Sum
        )
    }
}

function ConvertTo-FourPartVersion {
    param(
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $trimmed = $Value.Trim()
    if ($trimmed -notmatch '^\d+\.\d+\.\d+(\.\d+)?$') {
        throw "$Label is not a numeric three- or four-part version: $Value"
    }
    $parts = @($trimmed.Split("."))
    if ($parts.Count -eq 3) {
        $parts += "0"
    }
    return (($parts | ForEach-Object { [int]$_ }) -join ".")
}

$guiExe = Join-Path $ReleaseDir "Rayluno.exe"
$cliExe = Join-Path $ReleaseDir "RaylunoCLI.exe"
$internalDir = Join-Path $ReleaseDir "_internal"
$requiredFiles = @(
    $guiExe,
    $cliExe,
    (Join-Path $internalDir "future_assistant\ui\index.html"),
    (Join-Path $internalDir "future_assistant\ui\app.js"),
    (Join-Path $internalDir "future_assistant\ui\styles.css"),
    (Join-Path $internalDir "future_assistant\assets\license-public.pem"),
    (Join-Path $internalDir "future_assistant\assets\updates-public.pem"),
    (Join-Path $internalDir "webview\js\api.js"),
    (Join-Path $internalDir "webview\lib\Microsoft.Web.WebView2.Core.dll"),
    (Join-Path $internalDir "webview\lib\Microsoft.Web.WebView2.WinForms.dll"),
    (Join-Path $ReleaseDir "release-build.json"),
    (Join-Path $ReleaseDir "release-files.sha256"),
    (Join-Path $ReleaseDir "THIRD_PARTY_NOTICES.md"),
    (Join-Path $ReleaseDir "THIRD_PARTY_LICENSES\license-manifest.json"),
    (Join-Path $ReleaseDir "THIRD_PARTY_LICENSES\sbom.cdx.json")
)

if ($ExpectVoice) {
    $requiredFiles += @(
        (Join-Path $internalDir "models\vosk-model-ar-mgb2-0.4\am\final.mdl"),
        (Join-Path $internalDir "models\vosk-model-ar-mgb2-0.4\conf\model.conf"),
        (Join-Path $internalDir "models\vosk-model-small-en-us-0.15\am\final.mdl"),
        (Join-Path $internalDir "models\vosk-model-small-en-us-0.15\conf\model.conf"),
        (Join-Path $internalDir "models\whisper\ggml-base.bin"),
        (Join-Path $ReleaseDir "voice-model-files.sha256")
    )
}

foreach ($requiredFile in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required release file is missing: $requiredFile"
    }
}

$releaseFilesManifestPath = Join-Path $ReleaseDir "release-files.sha256"
Assert-FileHashManifest `
    -RootDirectory $ReleaseDir `
    -ManifestPath $releaseFilesManifestPath `
    -ExcludedRelativePaths @("release-files.sha256") | Out-Null

$forbiddenCrossPlatformFiles = @(
    (Join-Path $internalDir "webview\lib\pywebview-android.jar"),
    (Join-Path $internalDir "webview\lib\WebBrowserInterop.x86.dll"),
    (Join-Path $internalDir "webview\lib\runtimes\win-arm64\native\WebView2Loader.dll"),
    (Join-Path $internalDir "webview\lib\runtimes\win-x86\native\WebView2Loader.dll"),
    (Join-Path $internalDir "clr_loader\ffi\dlls\x86\ClrLoader.dll"),
    (Join-Path $internalDir "win32com\test\testall.py"),
    (Join-Path $internalDir "win32com\demos\connect.py")
)
foreach ($forbiddenFile in $forbiddenCrossPlatformFiles) {
    if (Test-Path -LiteralPath $forbiddenFile) {
        throw "The x64 release contains an unused cross-platform runtime: $forbiddenFile"
    }
}

$forbiddenBundledToolDirectories = @(
    (Join-Path $internalDir "pywhispercpp\examples"),
    (Join-Path $internalDir "vosk\transcriber"),
    (Join-Path $internalDir "win32com\test")
)
foreach ($forbiddenDirectory in $forbiddenBundledToolDirectories) {
    if (Test-Path -LiteralPath $forbiddenDirectory) {
        throw "The release contains an unsupported third-party example or test payload: $forbiddenDirectory"
    }
}

function Assert-ReleasePattern {
    param(
        [string]$RelativePattern,
        [string]$Label
    )

    $matches = @(Get-ChildItem -Path (Join-Path $internalDir $RelativePattern) -File -ErrorAction SilentlyContinue)
    if ($matches.Count -eq 0) {
        throw "Required $Label payload is missing (pattern: $RelativePattern)."
    }
}

Assert-ReleasePattern -RelativePattern "cryptography\hazmat\bindings\_rust*.pyd" -Label "cryptography native"

$releaseManifest = Get-Content -LiteralPath (Join-Path $ReleaseDir "release-build.json") -Raw | ConvertFrom-Json
if ([string]$releaseManifest.product -ne "Rayluno") {
    throw "Release product mismatch. Expected Rayluno, found $($releaseManifest.product)."
}
$expectedProfile = if ($ExpectVoice) { "commercial-local-voice" } else { "commercial-desktop" }
if ($releaseManifest.profile -ne $expectedProfile) {
    throw "Release profile mismatch. Expected $expectedProfile, found $($releaseManifest.profile)."
}
$minimumCryptographyVersion = [version]"48.0.1"
$packagedCryptographyVersion = $null
if ($null -ne $releaseManifest.dependencies) {
    $packagedCryptographyVersion = $releaseManifest.dependencies.cryptography
}
if ([string]::IsNullOrWhiteSpace([string]$packagedCryptographyVersion)) {
    throw "Release metadata does not identify the packaged cryptography version."
}
if ([version]$packagedCryptographyVersion -lt $minimumCryptographyVersion) {
    throw "Packaged cryptography $packagedCryptographyVersion is below the secure minimum $minimumCryptographyVersion."
}
$licenseManifestPath = Join-Path $ReleaseDir "THIRD_PARTY_LICENSES\license-manifest.json"
$licenseManifest = Get-Content -LiteralPath $licenseManifestPath -Raw | ConvertFrom-Json
if ($licenseManifest.product_version -ne $releaseManifest.version -or
    $licenseManifest.profile -ne $releaseManifest.profile) {
    throw "Third-party license inventory does not match the release metadata."
}
$licenseCryptography = @($licenseManifest.packages | Where-Object { $_.canonical_name -eq "cryptography" })
if ($licenseCryptography.Count -ne 1 -or
    $licenseCryptography[0].version -ne $packagedCryptographyVersion) {
    throw "Third-party license inventory does not match the packaged cryptography version."
}
$sbom = Get-Content -LiteralPath (Join-Path $ReleaseDir "THIRD_PARTY_LICENSES\sbom.cdx.json") -Raw | ConvertFrom-Json
if ($sbom.bomFormat -ne "CycloneDX" -or $sbom.metadata.component.version -ne $releaseManifest.version) {
    throw "CycloneDX SBOM metadata does not match the release."
}
if ($ExpectVoice) {
    Assert-ReleasePattern -RelativePattern "_pywhispercpp*.pyd" -Label "pywhispercpp native"
    Assert-ReleasePattern -RelativePattern "whisper-*.dll" -Label "whisper.cpp runtime"
    Assert-ReleasePattern -RelativePattern "vosk\libvosk.dll" -Label "Vosk runtime"
    Assert-ReleasePattern -RelativePattern "winrt\_winrt*.pyd" -Label "WinRT projections"
    Assert-ReleasePattern `
        -RelativePattern "_sounddevice_data\portaudio-binaries\libportaudio*.dll" `
        -Label "PortAudio runtime"
    $asioRuntime = Join-Path $internalDir "_sounddevice_data\portaudio-binaries\libportaudio64bit-asio.dll"
    if (Test-Path -LiteralPath $asioRuntime) {
        throw "The unused ASIO-enabled PortAudio runtime must not be distributed."
    }

    $modelHashManifest = Join-Path $ReleaseDir "voice-model-files.sha256"
    $actualModelManifestHash = (Get-FileHash -LiteralPath $modelHashManifest -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualModelManifestHash -ne $releaseManifest.voice_models.file_manifest.sha256) {
        throw "Voice model file manifest checksum mismatch."
    }
    if (@(Get-Content -LiteralPath $modelHashManifest).Count -ne
        $releaseManifest.voice_models.file_manifest.file_count) {
        throw "Voice model file manifest count mismatch."
    }
    $modelPayloadSummary = Assert-FileHashManifest `
        -RootDirectory (Join-Path $internalDir "models") `
        -ManifestPath $modelHashManifest
    if ($modelPayloadSummary.file_count -ne $releaseManifest.voice_models.file_manifest.file_count -or
        $modelPayloadSummary.size_bytes -ne $releaseManifest.voice_models.file_manifest.size_bytes) {
        throw "Voice model payload does not match its release metadata."
    }

    $expectedWhisperHash = "60ED5BC3DD14EEA856493D334349B405782DDCAF0028D4B5DF4088345FBA2EFE"
    $actualWhisperHash = (Get-FileHash `
        -LiteralPath (Join-Path $internalDir "models\whisper\ggml-base.bin") `
        -Algorithm SHA256).Hash
    if ($actualWhisperHash -ne $expectedWhisperHash) {
        throw "Packaged Whisper model checksum mismatch."
    }
}

$guiVersion = (Get-Item -LiteralPath $guiExe).VersionInfo
$cliVersion = (Get-Item -LiteralPath $cliExe).VersionInfo
$expectedPeVersion = ConvertTo-FourPartVersion `
    -Value ([string]$releaseManifest.version) `
    -Label "Release manifest version"
foreach ($executableVersion in @(
        [ordered]@{ label = "GUI"; value = $guiVersion },
        [ordered]@{ label = "CLI"; value = $cliVersion }
    )) {
    $fileVersion = [string]$executableVersion.value.FileVersion
    $productVersion = [string]$executableVersion.value.ProductVersion
    $productName = [string]$executableVersion.value.ProductName
    if ([string]::IsNullOrWhiteSpace($fileVersion)) {
        throw "The $($executableVersion.label) executable has no file version."
    }
    if ([string]::IsNullOrWhiteSpace($productVersion)) {
        throw "The $($executableVersion.label) executable has no product version."
    }
    if ($productName -ne "Rayluno") {
        throw "The $($executableVersion.label) executable product name is not Rayluno."
    }
    $normalizedFileVersion = ConvertTo-FourPartVersion `
        -Value $fileVersion `
        -Label "$($executableVersion.label) executable file version"
    $normalizedProductVersion = ConvertTo-FourPartVersion `
        -Value $productVersion `
        -Label "$($executableVersion.label) executable product version"
    if ($normalizedFileVersion -ne $expectedPeVersion) {
        throw "$($executableVersion.label) executable file version $fileVersion does not match release $($releaseManifest.version)."
    }
    if ($normalizedProductVersion -ne $expectedPeVersion) {
        throw "$($executableVersion.label) executable product version $productVersion does not match release $($releaseManifest.version)."
    }
}

if ($IntegrityOnly) {
    Write-Host "Release integrity checks passed: $ReleaseDir"
    return
}

function Invoke-ReleaseCommand {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$Label,
        [string[]]$ExpectedText = @()
    )

    # Native voice libraries (notably Vosk) emit normal model diagnostics to
    # stderr. Capture those lines and judge the command by its real exit code
    # and expected output instead of PowerShell's NativeCommandError wrapper.
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& $Executable @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    foreach ($line in $output) {
        Write-Host $line
    }
    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode."
    }
    if ($output.Count -eq 0) {
        throw "$Label produced no output."
    }
    $joinedOutput = $output -join "`n"
    foreach ($expected in $ExpectedText) {
        if (-not $joinedOutput.Contains($expected)) {
            throw "$Label output did not contain: $expected"
        }
    }
}

$savedEnvironment = @{}
Get-ChildItem Env: | Where-Object {
    $_.Name -like "FUTURE_ASSISTANT_*" -or $_.Name -like "RAYLUNO_*"
} | ForEach-Object {
    $savedEnvironment[$_.Name] = $_.Value
}
$hadPywebviewGui = Test-Path "Env:PYWEBVIEW_GUI"
$savedPywebviewGui = $env:PYWEBVIEW_GUI
$hadLocalAppData = Test-Path "Env:LOCALAPPDATA"
$savedLocalAppData = $env:LOCALAPPDATA
$hadAppData = Test-Path "Env:APPDATA"
$savedAppData = $env:APPDATA
$temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd("\")
$smokeUserRoot = Join-Path $temporaryRoot ("RaylunoSmoke-" + [Guid]::NewGuid().ToString("N"))
$smokeLocalAppData = Join-Path $smokeUserRoot "LocalAppData"
$smokeAppData = Join-Path $smokeUserRoot "RoamingAppData"
if (-not [System.IO.Path]::GetFullPath($smokeUserRoot).StartsWith(
        $temporaryRoot + "\",
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
    throw "The isolated smoke-test profile escaped the Windows temporary directory."
}
New-Item -ItemType Directory -Force -Path $smokeLocalAppData, $smokeAppData | Out-Null

try {
    Get-ChildItem Env: | Where-Object {
        $_.Name -like "FUTURE_ASSISTANT_*" -or $_.Name -like "RAYLUNO_*"
    } | ForEach-Object {
        Remove-Item ("Env:" + $_.Name)
    }
    $env:RAYLUNO_OLLAMA_ENDPOINT = "http://127.0.0.1:9"
    $env:RAYLUNO_AUDIT_PATH = ""
    $env:LOCALAPPDATA = $smokeLocalAppData
    $env:APPDATA = $smokeAppData
    Remove-Item "Env:PYWEBVIEW_GUI" -ErrorAction SilentlyContinue

    $releaseSelfTest = if ($ExpectVoice) { "--release-self-test-voice" } else { "--release-self-test" }
    $releaseSelfTestOutput = if ($ExpectVoice) {
        "[OK] Full local voice release self-test"
    }
    else {
        "[OK] Commercial release self-test"
    }
    Invoke-ReleaseCommand `
        -Executable $cliExe `
        -Arguments @($releaseSelfTest) `
        -Label "Frozen dependency self-test" `
        -ExpectedText @($releaseSelfTestOutput)

    Invoke-ReleaseCommand `
        -Executable $cliExe `
        -Arguments @("--doctor") `
        -Label "Doctor check" `
        -ExpectedText "[OK] Python"

    Invoke-ReleaseCommand `
        -Executable $cliExe `
        -Arguments @("--once", "open youtube", "--dry-run", "--no-audit", "--no-wake-word") `
        -Label "One-command check"

    if ($LaunchGui) {
        $process = $null
        try {
            $process = Start-Process -FilePath $guiExe -PassThru
            if ($process.WaitForExit(5000)) {
                throw "The desktop executable exited during the GUI smoke window with code $($process.ExitCode)."
            }
        }
        finally {
            if ($null -ne $process -and -not $process.HasExited) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
finally {
    Get-ChildItem Env: | Where-Object {
        $_.Name -like "FUTURE_ASSISTANT_*" -or $_.Name -like "RAYLUNO_*"
    } | ForEach-Object {
        Remove-Item ("Env:" + $_.Name)
    }
    foreach ($name in $savedEnvironment.Keys) {
        Set-Item -Path ("Env:" + $name) -Value $savedEnvironment[$name]
    }
    if ($hadPywebviewGui) {
        $env:PYWEBVIEW_GUI = $savedPywebviewGui
    }
    else {
        Remove-Item "Env:PYWEBVIEW_GUI" -ErrorAction SilentlyContinue
    }
    if ($hadLocalAppData) {
        $env:LOCALAPPDATA = $savedLocalAppData
    }
    else {
        Remove-Item "Env:LOCALAPPDATA" -ErrorAction SilentlyContinue
    }
    if ($hadAppData) {
        $env:APPDATA = $savedAppData
    }
    else {
        Remove-Item "Env:APPDATA" -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $smokeUserRoot -PathType Container) {
        try {
            Remove-Item -LiteralPath $smokeUserRoot -Recurse -Force -ErrorAction Stop
        }
        catch {
            Write-Warning "Could not remove the isolated smoke-test profile: $smokeUserRoot"
        }
    }
}

# Runtime checks must not be able to mutate or add files beneath the release
# root without making the smoke test fail.
Assert-FileHashManifest `
    -RootDirectory $ReleaseDir `
    -ManifestPath $releaseFilesManifestPath `
    -ExcludedRelativePaths @("release-files.sha256") | Out-Null

Write-Host "Release smoke checks passed: $ReleaseDir"
