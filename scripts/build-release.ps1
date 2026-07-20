[CmdletBinding()]
param(
    [switch]$WithVoice,
    [switch]$SkipDependencyInstall,
    [switch]$SkipSmoke,
    [switch]$SkipGuiSmoke,
    [switch]$SkipArchive,
    [switch]$NoClean,
    [switch]$PreflightOnly,
    [string]$Python = "",
    [string]$ArabicVoskModel = "",
    [string]$EnglishVoskModel = "",
    [string]$WhisperModel = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$spec = Join-Path $root "packaging\future_assistant.spec"
$distRoot = Join-Path $root "dist"
$releaseDir = Join-Path $distRoot "Rayluno"
$buildId = [Guid]::NewGuid().ToString("N")
$stagingRoot = Join-Path $distRoot ".Rayluno-staging-$buildId"
$stagingReleaseDir = Join-Path $stagingRoot "Rayluno"
$workDir = Join-Path $stagingRoot "_pyinstaller-work"
$defaultPython = Join-Path $root ".venv\Scripts\python.exe"
$arabicModelName = "vosk-model-ar-mgb2-0.4"
$englishModelName = "vosk-model-small-en-us-0.15"
$whisperModelName = "ggml-base.bin"
$whisperModelSha256 = "60ED5BC3DD14EEA856493D334349B405782DDCAF0028D4B5DF4088345FBA2EFE"
$versionFile = Join-Path $root "src\future_assistant\__init__.py"
$versionMatch = Select-String -LiteralPath $versionFile -Pattern '^__version__\s*=\s*"([^"]+)"'
if ($null -eq $versionMatch -or $versionMatch.Matches.Count -eq 0) {
    throw "Unable to read the package version."
}
$projectVersion = $versionMatch.Matches[0].Groups[1].Value
if ($projectVersion -notmatch '^\d+\.\d+\.\d+$') {
    throw "The Windows product version must contain exactly three numeric components: $projectVersion"
}
foreach ($versionComponent in $projectVersion.Split(".")) {
    if ([int64]$versionComponent -gt 65535) {
        throw "Windows version components must not exceed 65535: $projectVersion"
    }
}

function Invoke-Python {
    param([string[]]$Arguments)

    & $script:PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

function Resolve-RequiredInput {
    param(
        [string]$RequestedPath,
        [string]$BuildEnvironmentName,
        [string]$RuntimeEnvironmentName,
        [string]$DefaultPath,
        [ValidateSet("Container", "Leaf")][string]$PathType,
        [string]$Label
    )

    $candidate = $RequestedPath
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = [Environment]::GetEnvironmentVariable($BuildEnvironmentName, "Process")
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = [Environment]::GetEnvironmentVariable($RuntimeEnvironmentName, "Process")
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = $DefaultPath
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        throw "$Label has no configured source path. Pass its build parameter or set $BuildEnvironmentName."
    }

    $candidate = [Environment]::ExpandEnvironmentVariables($candidate)
    if (-not (Test-Path -LiteralPath $candidate -PathType $PathType)) {
        throw "Required $Label source is missing or has the wrong type: $candidate"
    }
    return (Resolve-Path -LiteralPath $candidate).Path
}

function Assert-VoskModel {
    param(
        [string]$ModelPath,
        [string]$Label
    )

    foreach ($relativePath in @("am\final.mdl", "conf\mfcc.conf", "conf\model.conf")) {
        $requiredFile = Join-Path $ModelPath $relativePath
        if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
            throw "Required $Label file is missing: $requiredFile"
        }
    }
}

function Get-DirectorySummary {
    param([string]$Path)

    $files = @(Get-ChildItem -LiteralPath $Path -Recurse -File)
    $measurement = $files | Measure-Object -Property Length -Sum
    return [ordered]@{
        file_count = $files.Count
        size_bytes = [long]$measurement.Sum
    }
}

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ParentDirectory,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $resolvedParent = [System.IO.Path]::GetFullPath($ParentDirectory).TrimEnd("\")
    $resolvedPath = [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
    if (-not $resolvedPath.StartsWith(
            $resolvedParent + "\",
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
        throw "$Label must remain inside '$resolvedParent': $resolvedPath"
    }
}

function Write-FileHashManifest {
    param(
        [Parameter(Mandatory = $true)][string]$InputDirectory,
        [Parameter(Mandatory = $true)][string]$OutputPath
    )

    $resolvedRoot = (Resolve-Path -LiteralPath $InputDirectory).Path.TrimEnd("\")
    $resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
    $files = @(
        Get-ChildItem -LiteralPath $resolvedRoot -Recurse -File |
            Where-Object {
                -not [string]::Equals(
                    [System.IO.Path]::GetFullPath($_.FullName),
                    $resolvedOutput,
                    [System.StringComparison]::OrdinalIgnoreCase
                )
            } |
            Sort-Object FullName
    )
    $lines = @()
    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($resolvedRoot.Length + 1).Replace("\", "/")
        $fileHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $lines += "$fileHash  $relativePath"
    }
    [System.IO.File]::WriteAllText(
        $OutputPath,
        ($lines -join "`n") + "`n",
        (New-Object System.Text.UTF8Encoding($false))
    )
    return [ordered]@{
        file_count = $files.Count
        size_bytes = [long](($files | Measure-Object -Property Length -Sum).Sum)
        sha256 = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

function Publish-ArchiveArtifacts {
    param(
        [Parameter(Mandatory = $true)][string]$CandidateArchive,
        [Parameter(Mandatory = $true)][string]$CandidateChecksum,
        [Parameter(Mandatory = $true)][string]$DestinationArchive,
        [Parameter(Mandatory = $true)][string]$DestinationChecksum,
        [Parameter(Mandatory = $true)][string]$BackupDirectory
    )

    $archiveBackup = Join-Path $BackupDirectory "previous-release-archive.zip"
    $checksumBackup = Join-Path $BackupDirectory "previous-release-archive.sha256"
    $archiveBackedUp = $false
    $checksumBackedUp = $false
    $archivePublished = $false
    $checksumPublished = $false
    try {
        if (Test-Path -LiteralPath $DestinationArchive -PathType Leaf) {
            Move-Item -LiteralPath $DestinationArchive -Destination $archiveBackup
            $archiveBackedUp = $true
        }
        if (Test-Path -LiteralPath $DestinationChecksum -PathType Leaf) {
            Move-Item -LiteralPath $DestinationChecksum -Destination $checksumBackup
            $checksumBackedUp = $true
        }

        Move-Item -LiteralPath $CandidateArchive -Destination $DestinationArchive
        $archivePublished = $true
        Move-Item -LiteralPath $CandidateChecksum -Destination $DestinationChecksum
        $checksumPublished = $true
    }
    catch {
        $publishError = $_
        if ($checksumPublished -and (Test-Path -LiteralPath $DestinationChecksum)) {
            Remove-Item -LiteralPath $DestinationChecksum -Force
        }
        if ($archivePublished -and (Test-Path -LiteralPath $DestinationArchive)) {
            Remove-Item -LiteralPath $DestinationArchive -Force
        }
        if ($checksumBackedUp -and (Test-Path -LiteralPath $checksumBackup)) {
            Move-Item -LiteralPath $checksumBackup -Destination $DestinationChecksum
        }
        if ($archiveBackedUp -and (Test-Path -LiteralPath $archiveBackup)) {
            Move-Item -LiteralPath $archiveBackup -Destination $DestinationArchive
        }
        throw $publishError
    }

    foreach ($obsoleteBackup in @($checksumBackup, $archiveBackup)) {
        if (Test-Path -LiteralPath $obsoleteBackup) {
            try {
                Remove-Item -LiteralPath $obsoleteBackup -Force
            }
            catch {
                Write-Warning "Published the new release archive, but could not remove rollback artifact: $obsoleteBackup"
            }
        }
    }
}

if ($Python) {
    $pythonCommand = Get-Command $Python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "Python executable was not found: $Python"
    }
    $script:PythonExe = $pythonCommand.Source
}
else {
    if (-not (Test-Path -LiteralPath $defaultPython)) {
        $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
        if ($null -eq $pyLauncher) {
            throw "Python 3.11 is required. Install it or pass -Python."
        }
        & $pyLauncher.Source -3.11 -m venv (Join-Path $root ".venv")
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create the Python 3.11 virtual environment."
        }
    }
    $script:PythonExe = $defaultPython
}

$pythonVersion = & $script:PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read the Python version."
}
$versionParts = $pythonVersion.Trim().Split(".")
if ([int]$versionParts[0] -lt 3 -or ([int]$versionParts[0] -eq 3 -and [int]$versionParts[1] -lt 11)) {
    throw "Python 3.11 or newer is required; found $pythonVersion."
}

$pythonBits = (& $script:PythonExe -c "import struct; print(struct.calcsize('P') * 8)").Trim()
if ($LASTEXITCODE -ne 0 -or $pythonBits -ne "64") {
    throw "The commercial Windows release requires 64-bit Python; found $pythonBits-bit."
}

$publicKeyDirectory = Join-Path $root "src\future_assistant\assets"
$publicKeyFiles = @(
    (Join-Path $publicKeyDirectory "license-public.pem"),
    (Join-Path $publicKeyDirectory "updates-public.pem")
)
foreach ($publicKeyFile in $publicKeyFiles) {
    if (-not (Test-Path -LiteralPath $publicKeyFile -PathType Leaf)) {
        throw "Required commercial public key is missing: $publicKeyFile"
    }
    $publicKeyText = Get-Content -LiteralPath $publicKeyFile -Raw
    if (-not $publicKeyText.Contains("-----BEGIN PUBLIC KEY-----") -or
        -not $publicKeyText.Contains("-----END PUBLIC KEY-----")) {
        throw "Commercial public key is not valid PEM text: $publicKeyFile"
    }
}

$resolvedArabicModel = $null
$resolvedEnglishModel = $null
$resolvedWhisperModel = $null
$arabicModelSummary = $null
$englishModelSummary = $null
$actualWhisperHash = $null
if ($WithVoice) {
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw "LOCALAPPDATA is required to discover the installed local voice models."
    }
    # Keep the legacy user-data directory so existing settings and downloaded
    # voice models remain available after the Rayluno program rebrand.
    $defaultModelRoot = Join-Path $env:LOCALAPPDATA "FutureAssistant\models"
    $resolvedArabicModel = Resolve-RequiredInput `
        -RequestedPath $ArabicVoskModel `
        -BuildEnvironmentName "FUTURE_ASSISTANT_BUILD_ARABIC_VOSK_MODEL" `
        -RuntimeEnvironmentName "FUTURE_ASSISTANT_VOSK_MODEL_PATH" `
        -DefaultPath (Join-Path $defaultModelRoot $arabicModelName) `
        -PathType Container `
        -Label "Arabic Vosk model"
    $resolvedEnglishModel = Resolve-RequiredInput `
        -RequestedPath $EnglishVoskModel `
        -BuildEnvironmentName "FUTURE_ASSISTANT_BUILD_ENGLISH_VOSK_MODEL" `
        -RuntimeEnvironmentName "FUTURE_ASSISTANT_VOSK_ENGLISH_MODEL_PATH" `
        -DefaultPath (Join-Path $defaultModelRoot $englishModelName) `
        -PathType Container `
        -Label "English Vosk model"
    $resolvedWhisperModel = Resolve-RequiredInput `
        -RequestedPath $WhisperModel `
        -BuildEnvironmentName "FUTURE_ASSISTANT_BUILD_WHISPER_MODEL" `
        -RuntimeEnvironmentName "FUTURE_ASSISTANT_WHISPER_MODEL" `
        -DefaultPath (Join-Path $env:LOCALAPPDATA "pywhispercpp\pywhispercpp\models\$whisperModelName") `
        -PathType Leaf `
        -Label "Whisper ggml-base model"

    Assert-VoskModel -ModelPath $resolvedArabicModel -Label "Arabic Vosk model"
    Assert-VoskModel -ModelPath $resolvedEnglishModel -Label "English Vosk model"
    $actualWhisperHash = (Get-FileHash -LiteralPath $resolvedWhisperModel -Algorithm SHA256).Hash
    if ($actualWhisperHash -ne $whisperModelSha256) {
        throw "Whisper ggml-base checksum mismatch. Expected $whisperModelSha256, found $actualWhisperHash."
    }
    $arabicModelSummary = Get-DirectorySummary -Path $resolvedArabicModel
    $englishModelSummary = Get-DirectorySummary -Path $resolvedEnglishModel
    Write-Host "Voice inputs: Arabic Vosk $($arabicModelSummary.size_bytes) bytes; English Vosk $($englishModelSummary.size_bytes) bytes; Whisper $((Get-Item -LiteralPath $resolvedWhisperModel).Length) bytes."
}

if (-not $SkipDependencyInstall) {
    $extras = "desktop,commercial"
    if ($WithVoice) {
        $extras = "desktop,commercial,voice"
    }
    $projectRequirement = "${root}[$extras]"
    Invoke-Python -Arguments @(
        "-m", "pip", "install", "--upgrade", "pyinstaller==6.21.0"
    )
    Invoke-Python -Arguments @(
        "-m", "pip", "install", "--upgrade", "--editable", $projectRequirement
    )
}

Invoke-Python -Arguments @(
    "-c",
    "import importlib.metadata, PyInstaller, webview; print('PyInstaller ' + PyInstaller.__version__ + ', pywebview ' + importlib.metadata.version('pywebview'))"
)

$dependencyProbe = "import importlib; modules=['cryptography','webview']"
if ($WithVoice) {
    $dependencyProbe += "; modules += ['_pywhispercpp','sounddevice','vosk','win32com.client','winrt.runtime','winrt.windows.foundation','winrt.windows.foundation.collections','winrt.windows.media.speechsynthesis','winrt.windows.storage.streams']"
}
$dependencyProbe += "; [importlib.import_module(name) for name in modules]; print('Release dependencies: ' + ', '.join(modules))"
Invoke-Python -Arguments @("-c", $dependencyProbe)

$releaseDependencyNames = @("cryptography", "pyinstaller", "pywebview")
if ($WithVoice) {
    $releaseDependencyNames += @(
        "numpy",
        "pywhispercpp",
        "pywin32",
        "sounddevice",
        "vosk"
    )
}
$releaseDependencies = [ordered]@{}
foreach ($dependencyName in $releaseDependencyNames) {
    $dependencyVersion = & $script:PythonExe -c `
        "import importlib.metadata as m; print(m.version('$dependencyName'))"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($dependencyVersion)) {
        throw "Unable to read the installed version of release dependency $dependencyName."
    }
    $releaseDependencies[$dependencyName] = $dependencyVersion.Trim()
}

if ($PreflightOnly) {
    Write-Host "Commercial release preflight: PASS"
    if ($WithVoice) {
        Write-Host "Profile: commercial-local-voice"
    }
    else {
        Write-Host "Profile: commercial-desktop"
    }
    return
}

Assert-ChildPath -Path $releaseDir -ParentDirectory $distRoot -Label "Release directory"
Assert-ChildPath -Path $stagingRoot -ParentDirectory $distRoot -Label "Release staging directory"
Assert-ChildPath -Path $workDir -ParentDirectory $stagingRoot -Label "PyInstaller work directory"

try {
    New-Item -ItemType Directory -Force -Path $distRoot | Out-Null
    New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null
    New-Item -ItemType Directory -Force -Path $workDir | Out-Null

    $versionInfoTool = Join-Path $root "tools\render_windows_version_info.py"
    $guiVersionInfo = Join-Path $stagingRoot "version_info_gui.txt"
    $cliVersionInfo = Join-Path $stagingRoot "version_info_cli.txt"
    Invoke-Python -Arguments @(
        $versionInfoTool,
        "--version", $projectVersion,
        "--description", "Rayluno desktop",
        "--internal-name", "Rayluno",
        "--original-filename", "Rayluno.exe",
        "--output", $guiVersionInfo
    )
    Invoke-Python -Arguments @(
        $versionInfoTool,
        "--version", $projectVersion,
        "--description", "Rayluno command line",
        "--internal-name", "RaylunoCLI",
        "--original-filename", "RaylunoCLI.exe",
        "--output", $cliVersionInfo
    )

$buildEnvironment = [ordered]@{
    FUTURE_ASSISTANT_BUILD_WITH_VOICE = if ($WithVoice) { "1" } else { "0" }
    FUTURE_ASSISTANT_BUILD_ARABIC_VOSK_MODEL = $resolvedArabicModel
    FUTURE_ASSISTANT_BUILD_ENGLISH_VOSK_MODEL = $resolvedEnglishModel
    FUTURE_ASSISTANT_BUILD_WHISPER_MODEL = $resolvedWhisperModel
    FUTURE_ASSISTANT_BUILD_GUI_VERSION_INFO = $guiVersionInfo
    FUTURE_ASSISTANT_BUILD_CLI_VERSION_INFO = $cliVersionInfo
    PYTHONUTF8 = "1"
}
$savedBuildEnvironment = @{}
foreach ($name in $buildEnvironment.Keys) {
    $savedBuildEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

try {
    foreach ($name in $buildEnvironment.Keys) {
        $value = $buildEnvironment[$name]
        if ($null -eq $value) {
            Remove-Item ("Env:" + $name) -ErrorAction SilentlyContinue
        }
        else {
            Set-Item -Path ("Env:" + $name) -Value $value
        }
    }

    $buildArguments = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--distpath", $stagingRoot,
        "--workpath", $workDir
    )
    if (-not $NoClean) {
        $buildArguments += "--clean"
    }
    $buildArguments += $spec
    Invoke-Python -Arguments $buildArguments
}
finally {
    foreach ($name in $buildEnvironment.Keys) {
        $savedValue = $savedBuildEnvironment[$name]
        if ($null -eq $savedValue) {
            Remove-Item ("Env:" + $name) -ErrorAction SilentlyContinue
        }
        else {
            Set-Item -Path ("Env:" + $name) -Value $savedValue
        }
    }
}

if (-not (Test-Path -LiteralPath $stagingReleaseDir)) {
    throw "PyInstaller did not create the expected staged release directory: $stagingReleaseDir"
}

$notices = Join-Path $root "THIRD_PARTY_NOTICES.md"
if (Test-Path -LiteralPath $notices) {
    Copy-Item -LiteralPath $notices -Destination $stagingReleaseDir -Force
}

$licenseCollector = Join-Path $root "tools\collect_third_party_licenses.py"
$supplementalLicenses = Join-Path $root "packaging\licenses"
$licenseBundle = Join-Path $stagingReleaseDir "THIRD_PARTY_LICENSES"
$pythonLicense = (& $script:PythonExe -c "import pathlib, sys; print(pathlib.Path(sys.base_prefix) / 'LICENSE.txt')").Trim()
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $pythonLicense -PathType Leaf)) {
    throw "Unable to locate the CPython license file."
}
$licenseArguments = @(
    $licenseCollector,
    "--output", $licenseBundle,
    "--product-version", $projectVersion,
    "--python-license", $pythonLicense,
    "--notice", $notices,
    "--supplemental-dir", $supplementalLicenses
)
if ($WithVoice) {
    $pythonEnvironment = Split-Path -Parent (Split-Path -Parent $script:PythonExe)
    $portAudioReadme = Join-Path $pythonEnvironment "Lib\site-packages\_sounddevice_data\portaudio-binaries\README.md"
    if (-not (Test-Path -LiteralPath $portAudioReadme -PathType Leaf)) {
        throw "Unable to locate the bundled PortAudio notice."
    }
    $licenseArguments += @(
        "--with-voice",
        "--supplemental", "PORTAUDIO_BINARY_README.md=$portAudioReadme",
        "--supplemental", "VOSK_ARABIC_MODEL_README.txt=$(Join-Path $resolvedArabicModel 'README')",
        "--supplemental", "VOSK_ENGLISH_MODEL_README.txt=$(Join-Path $resolvedEnglishModel 'README')"
    )
}
Invoke-Python -Arguments $licenseArguments
$licenseBundleSummary = Get-DirectorySummary -Path $licenseBundle

$modelHashSummary = $null
if ($WithVoice) {
    $packagedModelsRoot = Join-Path $stagingReleaseDir "_internal\models"
    $modelHashManifestPath = Join-Path $stagingReleaseDir "voice-model-files.sha256"
    $modelHashSummary = Write-FileHashManifest `
        -InputDirectory $packagedModelsRoot `
        -OutputPath $modelHashManifestPath
}

$releaseManifestPath = Join-Path $stagingReleaseDir "release-build.json"
$releaseManifest = [ordered]@{
    product = "Rayluno"
    version = $projectVersion
    profile = if ($WithVoice) { "commercial-local-voice" } else { "commercial-desktop" }
    architecture = "x64"
    python = $pythonVersion.Trim()
    dependencies = $releaseDependencies
    license_bundle = [ordered]@{
        file_count = $licenseBundleSummary.file_count
        size_bytes = $licenseBundleSummary.size_bytes
        manifest_sha256 = (Get-FileHash -LiteralPath (Join-Path $licenseBundle "license-manifest.json") -Algorithm SHA256).Hash.ToLowerInvariant()
        sbom_sha256 = (Get-FileHash -LiteralPath (Join-Path $licenseBundle "sbom.cdx.json") -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    public_keys = [ordered]@{
        license_sha256 = (Get-FileHash -LiteralPath $publicKeyFiles[0] -Algorithm SHA256).Hash.ToLowerInvariant()
        updates_sha256 = (Get-FileHash -LiteralPath $publicKeyFiles[1] -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
if ($WithVoice) {
    $releaseManifest["voice_models"] = [ordered]@{
        arabic_vosk = [ordered]@{
            name = $arabicModelName
            file_count = $arabicModelSummary.file_count
            size_bytes = $arabicModelSummary.size_bytes
        }
        english_vosk = [ordered]@{
            name = $englishModelName
            file_count = $englishModelSummary.file_count
            size_bytes = $englishModelSummary.size_bytes
        }
        whisper = [ordered]@{
            name = $whisperModelName
            size_bytes = (Get-Item -LiteralPath $resolvedWhisperModel).Length
            sha256 = $actualWhisperHash.ToLowerInvariant()
        }
        file_manifest = [ordered]@{
            name = "voice-model-files.sha256"
            file_count = $modelHashSummary.file_count
            size_bytes = $modelHashSummary.size_bytes
            sha256 = $modelHashSummary.sha256
        }
    }
}
$releaseManifestJson = $releaseManifest | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText(
    $releaseManifestPath,
    $releaseManifestJson + [Environment]::NewLine,
    (New-Object System.Text.UTF8Encoding($false))
)

$releaseFilesManifestPath = Join-Path $stagingReleaseDir "release-files.sha256"
Write-FileHashManifest `
    -InputDirectory $stagingReleaseDir `
    -OutputPath $releaseFilesManifestPath | Out-Null

if (-not $SkipSmoke) {
    $smokeScript = Join-Path $PSScriptRoot "smoke-release.ps1"
    $smokeArguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $smokeScript,
        "-ReleaseDir", $stagingReleaseDir
    )
    if ($WithVoice) {
        $smokeArguments += "-ExpectVoice"
    }
    if (-not $SkipGuiSmoke) {
        $smokeArguments += "-LaunchGui"
    }
    & powershell.exe @smokeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Release smoke checks failed with exit code $LASTEXITCODE."
    }
}

$backupDir = Join-Path $distRoot ".Rayluno-rollback-$buildId"
Assert-ChildPath -Path $backupDir -ParentDirectory $distRoot -Label "Release rollback directory"
$previousReleaseMoved = $false
if (Test-Path -LiteralPath $releaseDir) {
    Move-Item -LiteralPath $releaseDir -Destination $backupDir
    $previousReleaseMoved = $true
}
try {
    Move-Item -LiteralPath $stagingReleaseDir -Destination $releaseDir
}
catch {
    $promotionError = $_
    if ($previousReleaseMoved -and
        -not (Test-Path -LiteralPath $releaseDir) -and
        (Test-Path -LiteralPath $backupDir)) {
        try {
            Move-Item -LiteralPath $backupDir -Destination $releaseDir
            $previousReleaseMoved = $false
        }
        catch {
            throw "Release promotion failed, and the previous release could not be restored. The rollback copy remains at '$backupDir'. Promotion error: $($promotionError.Exception.Message). Rollback error: $($_.Exception.Message)"
        }
    }
    throw $promotionError
}

if ($previousReleaseMoved -and (Test-Path -LiteralPath $backupDir)) {
    try {
        Remove-Item -LiteralPath $backupDir -Recurse -Force
    }
    catch {
        Write-Warning "The new release was promoted, but the rollback directory could not be removed: $backupDir"
    }
}

if (-not $SkipArchive) {
    $machine = (& $script:PythonExe -c "import platform; print(platform.machine().lower())").Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read the build architecture."
    }
    $architecture = $machine
    if ($machine -eq "amd64" -or $machine -eq "x86_64") {
        $architecture = "x64"
    }
    elseif ($machine -eq "i386" -or $machine -eq "i686" -or $machine -eq "x86") {
        $architecture = "x86"
    }
    $archiveName = "Rayluno-$projectVersion-win-$architecture.zip"
    $archive = Join-Path $distRoot $archiveName
    $archiveChecksum = $archive + ".sha256"
    $candidateArchive = Join-Path $stagingRoot $archiveName
    $candidateChecksum = $candidateArchive + ".sha256"
    Compress-Archive `
        -LiteralPath $releaseDir `
        -DestinationPath $candidateArchive `
        -CompressionLevel Optimal
    $archiveHash = (Get-FileHash -LiteralPath $candidateArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText(
        $candidateChecksum,
        "$archiveHash  $archiveName`n",
        (New-Object System.Text.UTF8Encoding($false))
    )
    $archiveRollbackDir = Join-Path $distRoot ".Rayluno-archive-rollback-$buildId"
    Assert-ChildPath `
        -Path $archiveRollbackDir `
        -ParentDirectory $distRoot `
        -Label "Release archive rollback directory"
    New-Item -ItemType Directory -Path $archiveRollbackDir | Out-Null
    try {
        Publish-ArchiveArtifacts `
            -CandidateArchive $candidateArchive `
            -CandidateChecksum $candidateChecksum `
            -DestinationArchive $archive `
            -DestinationChecksum $archiveChecksum `
            -BackupDirectory $archiveRollbackDir
    }
    finally {
        if ((Test-Path -LiteralPath $archiveRollbackDir -PathType Container) -and
            @(Get-ChildItem -LiteralPath $archiveRollbackDir -Force).Count -eq 0) {
            Remove-Item -LiteralPath $archiveRollbackDir -Force
        }
    }
    Write-Host "Archive: $archive"
    Write-Host "Archive SHA256: $archiveHash"
    Write-Host "Archive checksum: $archiveChecksum"
}

Write-Host "Release: $releaseDir"
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
    if (Test-Path -LiteralPath $workDir) {
        Remove-Item -LiteralPath $workDir -Recurse -Force
    }
}
