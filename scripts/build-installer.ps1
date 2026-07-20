[CmdletBinding()]
param(
    [string]$ReleaseDir = "",
    [string]$OutputDir = "",
    [string]$Makensis = "",
    [switch]$BuildRelease,
    [switch]$WithVoice,
    [switch]$SkipCompile,
    [switch]$TestInstall,
    [switch]$RequireAuthenticode,
    [string]$SignTool = "",
    [string]$SigningCertificateThumbprint = "",
    [string]$TimestampUrl = "",
    [string]$ExpectedPublisher = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$installerScript = Join-Path $root "packaging\future_assistant.nsi"
$versionFile = Join-Path $root "src\future_assistant\__init__.py"

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
}

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ParentDirectory,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $resolvedParent = Get-NormalizedPath -Path $ParentDirectory
    $resolvedPath = Get-NormalizedPath -Path $Path
    if (-not $resolvedPath.StartsWith(
            $resolvedParent + "\",
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
        throw "$Label must remain inside '$resolvedParent': $resolvedPath"
    }
}

function Copy-ReleaseSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDirectory,
        [Parameter(Mandatory = $true)][string]$DestinationDirectory
    )

    if (Test-Path -LiteralPath $DestinationDirectory) {
        throw "Release snapshot destination already exists: $DestinationDirectory"
    }
    $sourceRoot = (Resolve-Path -LiteralPath $SourceDirectory).Path.TrimEnd("\")
    $sourcePrefix = $sourceRoot + "\"
    New-Item -ItemType Directory -Path $DestinationDirectory | Out-Null
    $entries = @(Get-ChildItem -LiteralPath $sourceRoot -Force -Recurse)
    foreach ($entry in $entries) {
        if (($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Release snapshots do not accept links or junctions: $($entry.FullName)"
        }
        if (-not $entry.FullName.StartsWith(
                $sourcePrefix,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
            throw "Release entry escaped its source directory: $($entry.FullName)"
        }
    }
    foreach ($directory in @($entries | Where-Object { $_.PSIsContainer })) {
        $relativePath = $directory.FullName.Substring($sourcePrefix.Length)
        New-Item `
            -ItemType Directory `
            -Force `
            -Path (Join-Path $DestinationDirectory $relativePath) | Out-Null
    }
    foreach ($file in @($entries | Where-Object { -not $_.PSIsContainer })) {
        $relativePath = $file.FullName.Substring($sourcePrefix.Length)
        $destinationPath = Join-Path $DestinationDirectory $relativePath
        $destinationParent = Split-Path -Parent $destinationPath
        if (-not (Test-Path -LiteralPath $destinationParent -PathType Container)) {
            New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
        }
        Copy-Item -LiteralPath $file.FullName -Destination $destinationPath -Force
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $FilePath"
    }
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$ExpectedText = ""
    )

    # Voice runtimes can write normal diagnostics to stderr. Judge the frozen
    # CLI by its exit code and required success marker instead of converting
    # those diagnostics into a PowerShell NativeCommandError.
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& $FilePath @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    foreach ($line in $output) {
        Write-Host $line
    }
    if ($exitCode -ne 0) {
        throw "Command failed with exit code $exitCode`: $FilePath"
    }
    if ($ExpectedText -and -not (($output -join "`n").Contains($ExpectedText))) {
        throw "Command output did not contain the required success marker: $ExpectedText"
    }
}

function Invoke-GuiChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $quotedArguments = @()
    foreach ($argument in $Arguments) {
        if ($argument.Contains('"')) {
            throw "An installer argument contains an unsupported quote."
        }
        if ($argument.StartsWith("/D=", [System.StringComparison]::OrdinalIgnoreCase)) {
            # NSIS requires /D= to be last and consumes the remainder verbatim,
            # so quoting the entire switch prevents it from being recognized.
            $quotedArguments += $argument
        }
        elseif ($argument -match '\s') {
            $quotedArguments += ('"' + $argument + '"')
        }
        else {
            $quotedArguments += $argument
        }
    }
    $process = Start-Process -FilePath $FilePath -ArgumentList $quotedArguments -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(300000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw "Installer command timed out after 300 seconds: $FilePath"
    }
    $process.Refresh()
    if ($process.ExitCode -ne 0) {
        throw "Installer command failed with exit code $($process.ExitCode)`: $FilePath"
    }
}

function Find-Makensis {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        if (-not (Test-Path -LiteralPath $RequestedPath -PathType Leaf)) {
            throw "makensis.exe was not found: $RequestedPath"
        }
        return (Get-NormalizedPath -Path $RequestedPath)
    }

    $command = Get-Command "makensis.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\NSIS\makensis.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "NSIS\makensis.exe"),
        (Join-Path $env:ProgramFiles "NSIS\makensis.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Get-NormalizedPath -Path $candidate)
        }
    }

    throw "NSIS was not found. Install it with: winget install --id NSIS.NSIS --exact"
}

function Test-X64Pe {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = [System.IO.File]::OpenRead($Path)
    $reader = New-Object System.IO.BinaryReader($stream)
    try {
        if ($reader.ReadUInt16() -ne 0x5A4D) {
            return $false
        }
        $stream.Position = 0x3C
        $peOffset = $reader.ReadInt32()
        $stream.Position = $peOffset
        if ($reader.ReadUInt32() -ne 0x00004550) {
            return $false
        }
        return ($reader.ReadUInt16() -eq 0x8664)
    }
    finally {
        $reader.Dispose()
        $stream.Dispose()
    }
}

function Assert-ValidAuthenticodeStatus {
    param(
        [Parameter(Mandatory = $true)]$Signature,
        [Parameter(Mandatory = $true)][string]$Label,
        [string]$ExpectedThumbprint = "",
        [string]$ExpectedSubject = "",
        [switch]$RequireTimestamp
    )

    if ($Signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
        throw "$Label must have a valid Authenticode signature; found $($Signature.Status)."
    }
    if ($null -eq $Signature.SignerCertificate) {
        throw "$Label has no Authenticode signer certificate."
    }
    if ($ExpectedThumbprint) {
        $actualThumbprint = ([string]$Signature.SignerCertificate.Thumbprint).Replace(" ", "")
        if (-not $actualThumbprint.Equals(
                $ExpectedThumbprint,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
            throw "$Label was not signed by the approved certificate thumbprint."
        }
    }
    if ($ExpectedSubject -and
        -not ([string]$Signature.SignerCertificate.Subject).Equals(
            $ExpectedSubject,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
        throw "$Label signer subject does not match the approved publisher identity."
    }
    if ($RequireTimestamp -and $null -eq $Signature.TimeStamperCertificate) {
        throw "$Label must include a trusted Authenticode timestamp."
    }
}

function Write-SafeUninstallInclude {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDirectory,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    $sourcePrefix = $SourceDirectory + "\"
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("; Generated by scripts\build-installer.ps1. Do not edit.")
    $lines.Add('StrCpy $UninstallDeleteFailed "0"')

    $files = @(Get-ChildItem -LiteralPath $SourceDirectory -Force -File -Recurse | Sort-Object FullName)
    foreach ($file in $files) {
        if (-not $file.FullName.StartsWith($sourcePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Release file escaped its source directory: $($file.FullName)"
        }
        $relativePath = $file.FullName.Substring($sourcePrefix.Length).Replace("/", "\")
        if ($relativePath.Contains('"') -or $relativePath.Contains('$') -or
            $relativePath.Contains("`r") -or $relativePath.Contains("`n")) {
            throw "Release path cannot be represented safely in the NSIS uninstall include: $relativePath"
        }
        $lines.Add('ClearErrors')
        $lines.Add(('Delete /REBOOTOK "$INSTDIR\{0}"' -f $relativePath))
        $lines.Add('${If} ${Errors}')
        $lines.Add('  StrCpy $UninstallDeleteFailed "1"')
        $lines.Add('${EndIf}')
        $lines.Add('${If} ${FileExists} "$INSTDIR\' + $relativePath + '"')
        $lines.Add('  StrCpy $UninstallDeleteFailed "1"')
        $lines.Add('${EndIf}')
    }

    $directories = @(
        Get-ChildItem -LiteralPath $SourceDirectory -Force -Directory -Recurse |
            ForEach-Object {
                if (-not $_.FullName.StartsWith($sourcePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                    throw "Release directory escaped its source directory: $($_.FullName)"
                }
                $_.FullName.Substring($sourcePrefix.Length).Replace("/", "\")
            } |
            Sort-Object @{ Expression = { $_.Length }; Descending = $true }, @{ Expression = { $_ }; Descending = $true }
    )
    $lines.Add('ClearErrors')
    $lines.Add('Delete /REBOOTOK "$INSTDIR\NSIS_NOTICE.txt"')
    $lines.Add('${If} ${Errors}')
    $lines.Add('  StrCpy $UninstallDeleteFailed "1"')
    $lines.Add('${EndIf}')
    $lines.Add('${If} ${FileExists} "$INSTDIR\NSIS_NOTICE.txt"')
    $lines.Add('  StrCpy $UninstallDeleteFailed "1"')
    $lines.Add('${EndIf}')
    $lines.Add('${If} $UninstallDeleteFailed != "0"')
    $lines.Add('  MessageBox MB_ICONSTOP|MB_OK "$(UninstallDeleteFailure)" /SD IDOK')
    $lines.Add('  SetErrorLevel 2')
    $lines.Add('  Abort')
    $lines.Add('${EndIf}')

    foreach ($relativePath in $directories) {
        if ($relativePath.Contains('"') -or $relativePath.Contains('$') -or
            $relativePath.Contains("`r") -or $relativePath.Contains("`n")) {
            throw "Release directory cannot be represented safely in the NSIS uninstall include: $relativePath"
        }
        $lines.Add(('RMDir "$INSTDIR\{0}"' -f $relativePath))
    }

    $lines.Add('${If} $IsUpgradeUninstall != "1"')
    $lines.Add('  ClearErrors')
    $lines.Add('  Delete /REBOOTOK "$INSTDIR\Uninstall.exe"')
    $lines.Add('  ${If} ${Errors}')
    $lines.Add('    MessageBox MB_ICONSTOP|MB_OK "$(UninstallDeleteFailure)" /SD IDOK')
    $lines.Add('    SetErrorLevel 2')
    $lines.Add('    Abort')
    $lines.Add('  ${EndIf}')
    $lines.Add('  ${If} ${FileExists} "$INSTDIR\Uninstall.exe"')
    $lines.Add('    MessageBox MB_ICONSTOP|MB_OK "$(UninstallDeleteFailure)" /SD IDOK')
    $lines.Add('    SetErrorLevel 2')
    $lines.Add('    Abort')
    $lines.Add('  ${EndIf}')
    $lines.Add('  ClearErrors')
    $lines.Add('  Delete /REBOOTOK "$INSTDIR\.rayluno-install"')
    $lines.Add('  ${If} ${Errors}')
    $lines.Add('    MessageBox MB_ICONSTOP|MB_OK "$(UninstallDeleteFailure)" /SD IDOK')
    $lines.Add('    SetErrorLevel 2')
    $lines.Add('    Abort')
    $lines.Add('  ${EndIf}')
    $lines.Add('  ${If} ${FileExists} "$INSTDIR\.rayluno-install"')
    $lines.Add('    MessageBox MB_ICONSTOP|MB_OK "$(UninstallDeleteFailure)" /SD IDOK')
    $lines.Add('    SetErrorLevel 2')
    $lines.Add('    Abort')
    $lines.Add('  ${EndIf}')
    $lines.Add('${EndIf}')
    $lines.Add('RMDir "$INSTDIR"')
    [System.IO.File]::WriteAllLines(
        $DestinationPath,
        $lines,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

function Publish-InstallerArtifacts {
    param(
        [Parameter(Mandatory = $true)][string]$CandidateInstaller,
        [Parameter(Mandatory = $true)][string]$CandidateManifest,
        [Parameter(Mandatory = $true)][string]$DestinationInstaller,
        [Parameter(Mandatory = $true)][string]$DestinationManifest,
        [Parameter(Mandatory = $true)][string]$BackupDirectory
    )

    $installerBackup = Join-Path $BackupDirectory "previous-installer.exe"
    $manifestBackup = Join-Path $BackupDirectory "previous-installer-manifest.json"
    $installerBackedUp = $false
    $manifestBackedUp = $false
    $installerPublished = $false
    $manifestPublished = $false
    try {
        if (Test-Path -LiteralPath $DestinationInstaller -PathType Leaf) {
            Move-Item -LiteralPath $DestinationInstaller -Destination $installerBackup
            $installerBackedUp = $true
        }
        if (Test-Path -LiteralPath $DestinationManifest -PathType Leaf) {
            Move-Item -LiteralPath $DestinationManifest -Destination $manifestBackup
            $manifestBackedUp = $true
        }

        Move-Item -LiteralPath $CandidateInstaller -Destination $DestinationInstaller
        $installerPublished = $true
        Move-Item -LiteralPath $CandidateManifest -Destination $DestinationManifest
        $manifestPublished = $true
    }
    catch {
        if ($manifestPublished -and (Test-Path -LiteralPath $DestinationManifest)) {
            Remove-Item -LiteralPath $DestinationManifest -Force
        }
        if ($installerPublished -and (Test-Path -LiteralPath $DestinationInstaller)) {
            Remove-Item -LiteralPath $DestinationInstaller -Force
        }
        if ($manifestBackedUp -and (Test-Path -LiteralPath $manifestBackup)) {
            Move-Item -LiteralPath $manifestBackup -Destination $DestinationManifest
        }
        if ($installerBackedUp -and (Test-Path -LiteralPath $installerBackup)) {
            Move-Item -LiteralPath $installerBackup -Destination $DestinationInstaller
        }
        throw
    }

    if ($manifestBackedUp) {
        Remove-Item -LiteralPath $manifestBackup -Force
    }
    if ($installerBackedUp) {
        Remove-Item -LiteralPath $installerBackup -Force
    }
}

if ($SkipCompile) {
    throw "-SkipCompile is disabled because it can bind a new manifest to a stale installer. Compile a fresh candidate instead."
}

if (-not (Test-Path -LiteralPath $installerScript -PathType Leaf)) {
    throw "Installer definition was not found: $installerScript"
}

$versionMatch = Select-String -LiteralPath $versionFile -Pattern '^__version__\s*=\s*"([^"]+)"'
if ($null -eq $versionMatch -or $versionMatch.Matches.Count -eq 0) {
    throw "Unable to read the package version."
}
$version = $versionMatch.Matches[0].Groups[1].Value
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    throw "The Windows product version must contain exactly three numeric components: $version"
}
foreach ($versionComponent in $version.Split(".")) {
    if ([int64]$versionComponent -gt 65535) {
        throw "Windows version components must not exceed 65535: $version"
    }
}
$fileVersion = "$version.0"

$signingValuesProvided = @(
    -not [string]::IsNullOrWhiteSpace($SignTool),
    -not [string]::IsNullOrWhiteSpace($SigningCertificateThumbprint),
    -not [string]::IsNullOrWhiteSpace($TimestampUrl),
    -not [string]::IsNullOrWhiteSpace($ExpectedPublisher)
)
$signingEnabled = @($signingValuesProvided | Where-Object { $_ }).Count -gt 0
$signCommand = ""
if ($signingEnabled) {
    if (@($signingValuesProvided | Where-Object { -not $_ }).Count -gt 0) {
        throw "SignTool, SigningCertificateThumbprint, TimestampUrl, and ExpectedPublisher must be supplied together."
    }
    if (-not $RequireAuthenticode) {
        throw "Approved signing parameters require -RequireAuthenticode so every signature is verified before publication."
    }
    if (-not (Test-Path -LiteralPath $SignTool -PathType Leaf)) {
        throw "SignTool executable was not found: $SignTool"
    }
    $SignTool = Get-NormalizedPath -Path $SignTool
    if (-not (Split-Path -Leaf $SignTool).Equals(
            "signtool.exe",
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
        throw "The constrained signing hook accepts only an executable named signtool.exe."
    }
    $SigningCertificateThumbprint = $SigningCertificateThumbprint.Replace(" ", "")
    if ($SigningCertificateThumbprint -notmatch '^[0-9A-Fa-f]{40}$') {
        throw "SigningCertificateThumbprint must be a 40-character SHA-1 certificate thumbprint."
    }
    try {
        $timestampUri = [Uri]$TimestampUrl
    }
    catch {
        throw "TimestampUrl is not a valid absolute HTTPS URL."
    }
    if (-not $timestampUri.IsAbsoluteUri -or
        $timestampUri.Scheme -ne "https" -or
        [string]::IsNullOrWhiteSpace($timestampUri.Host) -or
        $timestampUri.UserInfo) {
        throw "TimestampUrl must be an absolute HTTPS URL without user information."
    }
    foreach ($shellSensitiveValue in @($SignTool, $timestampUri.AbsoluteUri)) {
        if ($shellSensitiveValue.IndexOfAny(@('"', "'", '$', '!', '%', "`r", "`n")) -ge 0) {
            throw "The approved signing path and timestamp URL contain unsupported shell-sensitive characters."
        }
    }
    $signCommand = '"{0}" sign /sha1 {1} /fd SHA256 /tr "{2}" /td SHA256 "%1"' -f `
        $SignTool,
        $SigningCertificateThumbprint,
        $timestampUri.AbsoluteUri
}
elseif ($RequireAuthenticode) {
    throw "-RequireAuthenticode requires the approved SignTool, certificate thumbprint, HTTPS timestamp URL, and exact publisher subject."
}

if ($BuildRelease) {
    $releaseScript = Join-Path $PSScriptRoot "build-release.ps1"
    $releaseArguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $releaseScript,
        "-SkipArchive",
        "-WithVoice"
    )
    Invoke-Checked -FilePath "powershell.exe" -Arguments $releaseArguments
}

if (-not $ReleaseDir) {
    $ReleaseDir = Join-Path $root "dist\Rayluno"
}
$ReleaseDir = Get-NormalizedPath -Path $ReleaseDir
if (-not (Test-Path -LiteralPath $ReleaseDir -PathType Container)) {
    throw "PyInstaller release directory was not found: $ReleaseDir. Run scripts\build-release.ps1 first."
}

$desktopExe = Join-Path $ReleaseDir "Rayluno.exe"
$consoleExe = Join-Path $ReleaseDir "RaylunoCLI.exe"
$internalDir = Join-Path $ReleaseDir "_internal"
$releaseBuildPath = Join-Path $ReleaseDir "release-build.json"
foreach ($requiredPath in @($desktopExe, $consoleExe, $internalDir, $releaseBuildPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Incomplete PyInstaller release; missing: $requiredPath"
    }
}
if (-not (Test-X64Pe -Path $desktopExe) -or -not (Test-X64Pe -Path $consoleExe)) {
    throw "The installer definition requires x64 PyInstaller executables."
}

try {
    $releaseMetadata = Get-Content -LiteralPath $releaseBuildPath -Raw | ConvertFrom-Json
}
catch {
    throw "Unable to parse release-build.json: $($_.Exception.Message)"
}
foreach ($requiredProperty in @("product", "version", "architecture", "profile")) {
    if ($releaseMetadata.PSObject.Properties.Name -notcontains $requiredProperty) {
        throw "release-build.json is missing required property: $requiredProperty"
    }
}
if ([string]$releaseMetadata.product -ne "Rayluno") {
    throw "Release product mismatch. Expected Rayluno, found $($releaseMetadata.product)."
}
if ([string]$releaseMetadata.version -ne $version) {
    throw "Release version mismatch. Expected $version, found $($releaseMetadata.version)."
}
if ([string]$releaseMetadata.architecture -ne "x64") {
    throw "Release architecture mismatch. Expected x64, found $($releaseMetadata.architecture)."
}
if ([string]$releaseMetadata.profile -ne "commercial-local-voice") {
    throw "Release profile mismatch. Expected commercial-local-voice, found $($releaseMetadata.profile)."
}

foreach ($reservedName in @(".rayluno-install", "NSIS_NOTICE.txt", "Uninstall.exe")) {
    if (Test-Path -LiteralPath (Join-Path $ReleaseDir $reservedName)) {
        throw "Release payload uses installer-reserved path: $reservedName"
    }
}

$desktopSignature = Get-AuthenticodeSignature -LiteralPath $desktopExe
$consoleSignature = Get-AuthenticodeSignature -LiteralPath $consoleExe
if ($RequireAuthenticode) {
    Assert-ValidAuthenticodeStatus `
        -Signature $desktopSignature `
        -Label "Rayluno.exe" `
        -ExpectedThumbprint $SigningCertificateThumbprint `
        -ExpectedSubject $ExpectedPublisher `
        -RequireTimestamp
    Assert-ValidAuthenticodeStatus `
        -Signature $consoleSignature `
        -Label "RaylunoCLI.exe" `
        -ExpectedThumbprint $SigningCertificateThumbprint `
        -ExpectedSubject $ExpectedPublisher `
        -RequireTimestamp
}

$smokeScript = Join-Path $PSScriptRoot "smoke-release.ps1"
Invoke-Checked -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $smokeScript,
    "-ReleaseDir", $ReleaseDir,
    "-ExpectVoice"
)

if (-not $OutputDir) {
    $OutputDir = Join-Path $root "dist\installer"
}
$OutputDir = Get-NormalizedPath -Path $OutputDir
if ($OutputDir.Equals($ReleaseDir, [System.StringComparison]::OrdinalIgnoreCase) -or
    $OutputDir.StartsWith($ReleaseDir + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDir must not be inside ReleaseDir."
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$makensisExe = Find-Makensis -RequestedPath $Makensis
$nsisDir = Split-Path -Parent $makensisExe
$arabicLanguage = Join-Path $nsisDir "Contrib\Language files\Arabic.nlf"
if (-not (Test-Path -LiteralPath $arabicLanguage -PathType Leaf)) {
    throw "The NSIS Arabic language file is missing: $arabicLanguage"
}

$installerName = "Rayluno-Setup-$version-win-x64.exe"
$installerPath = Join-Path $OutputDir $installerName
$builderVersionInfo = (Get-Item -LiteralPath $makensisExe).VersionInfo
$builderVersion = $builderVersionInfo.ProductVersion
if ([string]::IsNullOrWhiteSpace($builderVersion)) {
    $builderVersion = $builderVersionInfo.FileVersion
}
if ([string]::IsNullOrWhiteSpace($builderVersion)) {
    $builderVersion = ((& $makensisExe /VERSION 2>$null) | Select-Object -First 1).Trim()
}
$manifestPath = Join-Path $OutputDir "installer-manifest.json"

$installerBuildId = [Guid]::NewGuid().ToString("N")
$stagingDirectory = Join-Path $OutputDir (".installer-staging-" + $installerBuildId)
$publishRollbackDirectory = Join-Path $OutputDir (".installer-rollback-" + $installerBuildId)
Assert-ChildPath `
    -Path $stagingDirectory `
    -ParentDirectory $OutputDir `
    -Label "Installer staging directory"
Assert-ChildPath `
    -Path $publishRollbackDirectory `
    -ParentDirectory $OutputDir `
    -Label "Installer rollback directory"
New-Item -ItemType Directory -Path $stagingDirectory | Out-Null
New-Item -ItemType Directory -Path $publishRollbackDirectory | Out-Null
$candidateInstallerPath = Join-Path $stagingDirectory $installerName
$candidateManifestPath = Join-Path $stagingDirectory "installer-manifest.json"
$uninstallIncludePath = Join-Path $stagingDirectory "safe-uninstall.nsh"
$payloadSnapshotDir = Join-Path $stagingDirectory "release-snapshot"
Assert-ChildPath `
    -Path $payloadSnapshotDir `
    -ParentDirectory $stagingDirectory `
    -Label "Installer release snapshot"

try {
    Copy-ReleaseSnapshot `
        -SourceDirectory $ReleaseDir `
        -DestinationDirectory $payloadSnapshotDir
    Invoke-Checked -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $smokeScript,
        "-ReleaseDir", $payloadSnapshotDir,
        "-ExpectVoice",
        "-IntegrityOnly"
    )

    $snapshotDesktopExe = Join-Path $payloadSnapshotDir "Rayluno.exe"
    $snapshotConsoleExe = Join-Path $payloadSnapshotDir "RaylunoCLI.exe"
    $snapshotReleaseBuildPath = Join-Path $payloadSnapshotDir "release-build.json"
    $snapshotReleaseFilesManifestPath = Join-Path $payloadSnapshotDir "release-files.sha256"
    $releaseFiles = @(Get-ChildItem -LiteralPath $payloadSnapshotDir -Force -File -Recurse)
    $releasePayloadBytes = ($releaseFiles | Measure-Object -Property Length -Sum).Sum
    $releaseBuildHash = (
        Get-FileHash -LiteralPath $snapshotReleaseBuildPath -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    $releaseProvenance = [ordered]@{
        snapshot = "true-copy"
        build_manifest = "release-build.json"
        build_manifest_sha256 = $releaseBuildHash
        files_manifest = "release-files.sha256"
        files_manifest_sha256 = (
            Get-FileHash -LiteralPath $snapshotReleaseFilesManifestPath -Algorithm SHA256
        ).Hash.ToLowerInvariant()
    }
    $desktopSignature = Get-AuthenticodeSignature -LiteralPath $snapshotDesktopExe
    $consoleSignature = Get-AuthenticodeSignature -LiteralPath $snapshotConsoleExe

    Write-SafeUninstallInclude `
        -SourceDirectory $payloadSnapshotDir `
        -DestinationPath $uninstallIncludePath
    $compilerArguments = @(
        "/V2",
        "/INPUTCHARSET", "UTF8",
        "/DAPP_VERSION=$version",
        "/DAPP_FILE_VERSION=$fileVersion",
        "/DSOURCE_DIR=$payloadSnapshotDir",
        "/DOUTPUT_FILE=$candidateInstallerPath",
        "/DUNINSTALL_INCLUDE=$uninstallIncludePath"
    )
    if ($signingEnabled) {
        $compilerArguments += "/DSIGN_COMMAND=$signCommand"
    }
    $compilerArguments += $installerScript
    Invoke-Checked -FilePath $makensisExe -Arguments $compilerArguments

    if (-not (Test-Path -LiteralPath $candidateInstallerPath -PathType Leaf)) {
        throw "NSIS did not create the expected staged installer: $candidateInstallerPath"
    }

    # Prove that the private source snapshot did not change while makensis read it.
    Invoke-Checked -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $smokeScript,
        "-ReleaseDir", $payloadSnapshotDir,
        "-ExpectVoice",
        "-IntegrityOnly"
    )

    $hash = Get-FileHash -LiteralPath $candidateInstallerPath -Algorithm SHA256
    $installerItem = Get-Item -LiteralPath $candidateInstallerPath
    $signature = Get-AuthenticodeSignature -LiteralPath $candidateInstallerPath
    if ($RequireAuthenticode) {
        Assert-ValidAuthenticodeStatus `
            -Signature $signature `
            -Label $installerName `
            -ExpectedThumbprint $SigningCertificateThumbprint `
            -ExpectedSubject $ExpectedPublisher `
            -RequireTimestamp
    }

    $manifest = [ordered]@{
        product = "Rayluno"
        version = $version
        architecture = "x64"
        profile = "commercial-local-voice"
        builder = "NSIS"
        builder_version = $builderVersion
        installer = $installerItem.Name
        size_bytes = $installerItem.Length
        sha256 = $hash.Hash.ToLowerInvariant()
        authenticode_status = [string]$signature.Status
        authenticode_required = [bool]$RequireAuthenticode
        artifact_class = if ($RequireAuthenticode) {
            "signed-production-candidate"
        }
        else {
            "unsigned-release-candidate"
        }
        payload_signatures = [ordered]@{
            desktop = [string]$desktopSignature.Status
            cli = [string]$consoleSignature.Status
        }
        payload_directory = "Rayluno"
        payload_file_count = $releaseFiles.Count
        payload_size_bytes = $releasePayloadBytes
        release_provenance = $releaseProvenance
        built_utc = [DateTime]::UtcNow.ToString("o")
    }
    $manifestJson = $manifest | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText(
        $candidateManifestPath,
        $manifestJson + [Environment]::NewLine,
        (New-Object System.Text.UTF8Encoding($false))
    )

    if ($TestInstall) {
        $smokeRoot = Join-Path $root "build\installer-smoke"
        $testInstallDir = Join-Path $smokeRoot "app"
        $installerRegistryPath = "HKCU:\Software\Rayluno\Installer"
        $uninstallRegistryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Rayluno"
        $machineUninstallRegistryPath = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Rayluno"
        $startMenuDirectory = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Rayluno"
        $startMenuShortcut = Join-Path $startMenuDirectory "Rayluno.lnk"
        $startMenuCliShortcut = Join-Path $startMenuDirectory "Rayluno CLI.lnk"
        $desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Rayluno.lnk"
        New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null
        Assert-ChildPath `
            -Path $testInstallDir `
            -ParentDirectory $smokeRoot `
            -Label "Installer smoke-test directory"
        if (Test-Path -LiteralPath $testInstallDir) {
            throw "Refusing to reuse any existing smoke-test installation path: $testInstallDir"
        }
        foreach ($existingState in @(
                $installerRegistryPath,
                $uninstallRegistryPath,
                $machineUninstallRegistryPath,
                $startMenuDirectory,
                $desktopShortcut
            )) {
            if (Test-Path -LiteralPath $existingState) {
                throw "Refusing to overwrite existing installation state during smoke testing: $existingState"
            }
        }

        # Runtime data intentionally retains the legacy technical directory so
        # rebranded installers neither migrate nor delete an existing profile.
        $userDataDir = Join-Path $env:LOCALAPPDATA "FutureAssistant"
        New-Item -ItemType Directory -Force -Path $userDataDir | Out-Null
        $sentinel = Join-Path $userDataDir ("installer-preserve-" + [Guid]::NewGuid().ToString("N") + ".txt")
        $foreignInstallFile = Join-Path $testInstallDir ("foreign-preserve-" + [Guid]::NewGuid().ToString("N") + ".txt")
        $installedDesktopExe = Join-Path $testInstallDir "Rayluno.exe"
        $installedConsoleExe = Join-Path $testInstallDir "RaylunoCLI.exe"
        $installMarker = Join-Path $testInstallDir ".rayluno-install"
        $uninstaller = Join-Path $testInstallDir "Uninstall.exe"
        [System.IO.File]::WriteAllText($sentinel, "preserve", [System.Text.Encoding]::ASCII)

        $testError = $null
        $cleanupFailures = New-Object System.Collections.Generic.List[string]
        try {
            Invoke-GuiChecked -FilePath $candidateInstallerPath -Arguments @(
                "/S",
                "/LANG=Arabic",
                "/D=$testInstallDir"
            )

            if (-not (Test-Path -LiteralPath $installedDesktopExe -PathType Leaf)) {
                throw "Silent install did not deploy the desktop executable."
            }
            if (-not (Test-Path -LiteralPath $installedConsoleExe -PathType Leaf)) {
                throw "Silent install did not deploy the CLI executable."
            }
            if (-not (Test-Path -LiteralPath $installMarker -PathType Leaf)) {
                throw "Silent install did not create its installation identity marker."
            }
            if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
                throw "Silent install did not create an uninstaller."
            }
            $markerValue = Get-Content -LiteralPath $installMarker -Raw
            if ($markerValue -ne "rayluno-per-user-v1") {
                throw "Silent install created an unexpected installation identity marker."
            }
            if ($RequireAuthenticode) {
                foreach ($signedInstalledFile in @(
                        [ordered]@{ path = $installedDesktopExe; label = "installed Rayluno.exe" },
                        [ordered]@{ path = $installedConsoleExe; label = "installed RaylunoCLI.exe" },
                        [ordered]@{ path = $uninstaller; label = "installed Uninstall.exe" }
                    )) {
                    Assert-ValidAuthenticodeStatus `
                        -Signature (Get-AuthenticodeSignature -LiteralPath $signedInstalledFile.path) `
                        -Label $signedInstalledFile.label `
                        -ExpectedThumbprint $SigningCertificateThumbprint `
                        -ExpectedSubject $ExpectedPublisher `
                        -RequireTimestamp
                }
            }
            foreach ($sourceFile in $releaseFiles) {
                $relativePath = $sourceFile.FullName.Substring($payloadSnapshotDir.Length + 1)
                $installedFile = Join-Path $testInstallDir $relativePath
                if (-not (Test-Path -LiteralPath $installedFile -PathType Leaf)) {
                    throw "Silent install omitted a release file: $relativePath"
                }
                $sourceHash = (Get-FileHash -LiteralPath $sourceFile.FullName -Algorithm SHA256).Hash
                $installedHash = (Get-FileHash -LiteralPath $installedFile -Algorithm SHA256).Hash
                if ($installedHash -ne $sourceHash) {
                    throw "Installed file SHA-256 differs from the release: $relativePath"
                }
            }

            Invoke-NativeChecked `
                -FilePath $installedConsoleExe `
                -Arguments @("--release-self-test-voice") `
                -ExpectedText "[OK] Full local voice release self-test"

            $installerRegistry = Get-ItemProperty -LiteralPath $installerRegistryPath
            if ([string]$installerRegistry.InstallDir -ne $testInstallDir) {
                throw "Per-user installer registry path does not match the test installation."
            }
            if ([string]$installerRegistry.InstallerLanguage -ne "1025") {
                throw "The silent Arabic installer path did not select Arabic."
            }
            if (-not (Test-Path -LiteralPath $uninstallRegistryPath)) {
                throw "The per-user uninstall registration is missing."
            }
            if (Test-Path -LiteralPath $machineUninstallRegistryPath) {
                throw "The installer unexpectedly wrote a machine-wide uninstall registration."
            }
            if (-not (Test-Path -LiteralPath $startMenuShortcut -PathType Leaf)) {
                throw "The current-user Start Menu shortcut is missing."
            }

            [System.IO.File]::WriteAllText($foreignInstallFile, "foreign", [System.Text.Encoding]::ASCII)
            # Exercise the trusted Rayluno v1 upgrade path. The previous safe uninstaller
            # must remove its owned payload while preserving the foreign file.
            Invoke-GuiChecked -FilePath $candidateInstallerPath -Arguments @(
                "/S",
                "/LANG=Arabic",
                "/D=$testInstallDir"
            )
            if (-not (Test-Path -LiteralPath $foreignInstallFile -PathType Leaf)) {
                throw "Trusted upgrade removed a foreign file from the installation directory."
            }
            foreach ($sourceFile in $releaseFiles) {
                $relativePath = $sourceFile.FullName.Substring($payloadSnapshotDir.Length + 1)
                $installedFile = Join-Path $testInstallDir $relativePath
                if (-not (Test-Path -LiteralPath $installedFile -PathType Leaf)) {
                    throw "Trusted upgrade omitted a release file: $relativePath"
                }
                $sourceHash = (Get-FileHash -LiteralPath $sourceFile.FullName -Algorithm SHA256).Hash
                $installedHash = (Get-FileHash -LiteralPath $installedFile -Algorithm SHA256).Hash
                if ($installedHash -ne $sourceHash) {
                    throw "Trusted-upgrade file SHA-256 differs from the release: $relativePath"
                }
            }

            Invoke-GuiChecked -FilePath $uninstaller -Arguments @("/S")
            for (
                $attempt = 0;
                $attempt -lt 40 -and (
                    (Test-Path -LiteralPath $installedDesktopExe) -or
                    (Test-Path -LiteralPath $uninstaller)
                );
                $attempt++
            ) {
                Start-Sleep -Milliseconds 250
            }

            foreach ($sourceFile in $releaseFiles) {
                $relativePath = $sourceFile.FullName.Substring($payloadSnapshotDir.Length + 1)
                if (Test-Path -LiteralPath (Join-Path $testInstallDir $relativePath)) {
                    throw "Silent uninstall left a packaged release file behind: $relativePath"
                }
            }
            foreach ($knownInstallerFile in @("NSIS_NOTICE.txt", ".rayluno-install", "Uninstall.exe")) {
                if (Test-Path -LiteralPath (Join-Path $testInstallDir $knownInstallerFile)) {
                    throw "Silent uninstall left an installer-owned file behind: $knownInstallerFile"
                }
            }
            if (-not (Test-Path -LiteralPath $sentinel -PathType Leaf)) {
                throw "Uninstall removed user data; this is a release blocker."
            }
            if (-not (Test-Path -LiteralPath $foreignInstallFile -PathType Leaf)) {
                throw "Uninstall removed a foreign file from the installation directory."
            }
            if (-not (Test-Path -LiteralPath $testInstallDir -PathType Container)) {
                throw "The installation directory should remain while it contains a foreign file."
            }
            if (Test-Path -LiteralPath $uninstallRegistryPath) {
                throw "Silent uninstall left its per-user uninstall registration behind."
            }
            if (Test-Path -LiteralPath $installerRegistryPath) {
                throw "Silent uninstall left its installer registry state behind."
            }
            if (Test-Path -LiteralPath $startMenuShortcut) {
                throw "Silent uninstall left the Start Menu shortcut behind."
            }
            Write-Host "Silent Arabic install/uninstall: PASS"
            Write-Host "Release payload SHA-256 verification: PASS"
            Write-Host "Installed CLI voice self-test: PASS"
            Write-Host "Per-user registry and shortcut cleanup: PASS"
            Write-Host "User data preservation: PASS"
            Write-Host "Foreign install-file preservation: PASS"
        }
        catch {
            $testError = $_
        }
        finally {
            if (Test-Path -LiteralPath $uninstaller -PathType Leaf) {
                try {
                    Invoke-GuiChecked -FilePath $uninstaller -Arguments @("/S")
                }
                catch {
                    $cleanupFailures.Add("fallback uninstall failed: $($_.Exception.Message)")
                }
            }
            foreach ($cleanupFile in @(
                    $sentinel,
                    $foreignInstallFile,
                    $startMenuShortcut,
                    $startMenuCliShortcut,
                    $desktopShortcut
                )) {
                if (Test-Path -LiteralPath $cleanupFile -PathType Leaf) {
                    try {
                        Remove-Item -LiteralPath $cleanupFile -Force -ErrorAction Stop
                    }
                    catch {
                        $cleanupFailures.Add("could not remove '$cleanupFile': $($_.Exception.Message)")
                    }
                }
            }
            foreach ($cleanupRegistryPath in @($uninstallRegistryPath, $installerRegistryPath)) {
                if (Test-Path -LiteralPath $cleanupRegistryPath) {
                    try {
                        Remove-Item -LiteralPath $cleanupRegistryPath -Force -Recurse -ErrorAction Stop
                    }
                    catch {
                        $cleanupFailures.Add("could not remove test registry state '$cleanupRegistryPath': $($_.Exception.Message)")
                    }
                }
            }
            if ((Test-Path -LiteralPath $startMenuDirectory -PathType Container) -and
                @(Get-ChildItem -LiteralPath $startMenuDirectory -Force).Count -eq 0) {
                try {
                    Remove-Item -LiteralPath $startMenuDirectory -Force -ErrorAction Stop
                }
                catch {
                    $cleanupFailures.Add("could not remove empty test shortcut directory: $($_.Exception.Message)")
                }
            }
            if (Test-Path -LiteralPath $testInstallDir) {
                try {
                    Assert-ChildPath `
                        -Path $testInstallDir `
                        -ParentDirectory $smokeRoot `
                        -Label "Installer smoke cleanup directory"
                    Remove-Item `
                        -LiteralPath $testInstallDir `
                        -Force `
                        -Recurse `
                        -ErrorAction Stop
                }
                catch {
                    $cleanupFailures.Add("could not remove isolated smoke-test directory: $($_.Exception.Message)")
                }
            }
            foreach ($unexpectedRemainder in @(
                    $sentinel,
                    $testInstallDir,
                    $installerRegistryPath,
                    $uninstallRegistryPath,
                    $startMenuDirectory,
                    $desktopShortcut
                )) {
                if (Test-Path -LiteralPath $unexpectedRemainder) {
                    $cleanupFailures.Add("smoke-test state remains after cleanup: $unexpectedRemainder")
                }
            }
        }
        if ($cleanupFailures.Count -gt 0) {
            $failureContext = if ($null -ne $testError) {
                " Original test failure: $($testError.Exception.Message)"
            }
            else {
                ""
            }
            throw "Installer smoke cleanup failed: $($cleanupFailures -join ';').$failureContext"
        }
        if ($null -ne $testError) {
            throw $testError
        }
    }

    Publish-InstallerArtifacts `
        -CandidateInstaller $candidateInstallerPath `
        -CandidateManifest $candidateManifestPath `
        -DestinationInstaller $installerPath `
        -DestinationManifest $manifestPath `
        -BackupDirectory $publishRollbackDirectory
}
finally {
    if (Test-Path -LiteralPath $stagingDirectory -PathType Container) {
        Remove-Item -LiteralPath $stagingDirectory -Force -Recurse
    }
    if ((Test-Path -LiteralPath $publishRollbackDirectory -PathType Container) -and
        @(Get-ChildItem -LiteralPath $publishRollbackDirectory -Force).Count -eq 0) {
        Remove-Item -LiteralPath $publishRollbackDirectory -Force
    }
}

$installerItem = Get-Item -LiteralPath $installerPath
$hash = Get-FileHash -LiteralPath $installerPath -Algorithm SHA256
$signature = Get-AuthenticodeSignature -LiteralPath $installerPath
Write-Host "Installer: $installerPath"
Write-Host "Size: $($installerItem.Length) bytes"
Write-Host "SHA256: $($hash.Hash.ToLowerInvariant())"
Write-Host "Authenticode: $($signature.Status)"
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    Write-Warning "UNSIGNED RELEASE CANDIDATE - NOT FOR PUBLIC DISTRIBUTION. Windows SmartScreen may warn users until an approved, timestamped Authenticode signature and publisher reputation are established."
}
else {
    Write-Host "Artifact class: signed production candidate (final release approval is still required)."
}
Write-Host "Manifest: $manifestPath"
