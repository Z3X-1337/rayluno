[CmdletBinding()]
param(
    [string]$ReleaseDir = "",
    [string]$OutputDir = "",
    [string]$IdentityName = "",
    [string]$Publisher = "",
    [string]$PublisherDisplayName = "",
    [string]$DisplayName = "",
    [string]$Description = "",
    [string]$Version = "1.0.0.0",
    [string]$LogoSource = "",
    [string]$WinApp = "",
    [switch]$DevelopmentIdentity,
    [switch]$ManifestOnly,
    [switch]$SkipUploadPackage
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$templatePath = Join-Path $root "packaging\msix\Package.appxmanifest.template"
$msixBuildRoot = Join-Path $root "build\msix"
$generatedOutputRoot = Join-Path $msixBuildRoot "generated"
$runId = [Guid]::NewGuid().ToString("N")
$runRoot = Join-Path $msixBuildRoot ".run-$runId"
$metadataRoot = Join-Path $runRoot "generated"
$payloadStagingRoot = Join-Path $runRoot "payload"
$developmentDescription = "A private, bilingual local AI desktop assistant for Windows."
$distributionMarkerName = ".future-assistant-distribution"

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
}

function Assert-SafeGeneratedDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $buildRoot = Get-NormalizedPath -Path (Join-Path $root "build\msix")
    $candidate = Get-NormalizedPath -Path $Path
    if (-not $candidate.StartsWith($buildRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a generated directory outside build\msix: $candidate"
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

function ConvertTo-XmlText {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value)

    return [System.Security.SecurityElement]::Escape($Value)
}

function Assert-StoreVersion {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value -notmatch '^(\d+)\.(\d+)\.(\d+)\.(\d+)$') {
        throw "MSIX Version must use Major.Minor.Build.Revision notation: $Value"
    }
    $parts = @($Matches[1], $Matches[2], $Matches[3], $Matches[4]) | ForEach-Object { [int64]$_ }
    if ($parts[0] -lt 1) {
        throw "Microsoft Store package versions require a non-zero Major component. Use 1.0.0.0 or later."
    }
    foreach ($part in $parts) {
        if ($part -gt 65535) {
            throw "Every MSIX version component must be between 0 and 65535: $Value"
        }
    }
    if ($parts[3] -ne 0) {
        throw "The fourth MSIX version component is reserved for Microsoft Store and must be 0: $Value"
    }
}

function Assert-RequiredText {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value,
        [int]$MaximumLength = 8192
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Name is required. Copy the exact production value from Partner Center."
    }
    if ($Value.Length -gt $MaximumLength) {
        throw "$Name is longer than the supported limit of $MaximumLength characters."
    }
}

function Get-WinAppCommand {
    param([string]$RequestedPath)

    if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
        if (-not (Test-Path -LiteralPath $RequestedPath -PathType Leaf)) {
            throw "WinApp CLI was not found: $RequestedPath"
        }
        return (Get-NormalizedPath -Path $RequestedPath)
    }

    $command = Get-Command "winapp.exe" -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        $command = Get-Command "winapp" -ErrorAction SilentlyContinue
    }
    if ($null -eq $command) {
        throw "WinApp CLI 0.4.0 or newer is required. Install it with: winget install --id Microsoft.WinAppCli --version 0.4.0 --source winget"
    }
    return $command.Source
}

function ConvertFrom-MsixEntryName {
    param([Parameter(Mandatory = $true)][string]$Name)

    $slashName = $Name.Replace("\", "/")
    if ($slashName -match '(?i)%(2f|5c|00)') {
        throw "MSIX entry contains an encoded path separator or NUL byte: $Name"
    }
    try {
        $decoded = [System.Uri]::UnescapeDataString($slashName)
    }
    catch {
        throw "MSIX entry contains invalid percent encoding: $Name"
    }
    if ($decoded.StartsWith("/") -or $decoded.Contains("\")) {
        throw "MSIX entry has an unsafe absolute or backslash path: $Name"
    }
    $segments = @($decoded.Split("/"))
    if (@($segments | Where-Object { $_ -eq "." -or $_ -eq ".." }).Count -ne 0) {
        throw "MSIX entry contains path traversal: $Name"
    }
    return $decoded
}

function Get-ZipEntries {
    param([Parameter(Mandatory = $true)][string]$Path)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        return @(
            $archive.Entries | ForEach-Object {
                ConvertFrom-MsixEntryName -Name $_.FullName
            }
        )
    }
    finally {
        $archive.Dispose()
    }
}

function Read-ZipText {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$EntryName
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entry = $archive.GetEntry($EntryName)
        if ($null -eq $entry) {
            throw "Package entry is missing: $EntryName"
        }
        $reader = New-Object System.IO.StreamReader($entry.Open(), [System.Text.Encoding]::UTF8, $true)
        try {
            return $reader.ReadToEnd()
        }
        finally {
            $reader.Dispose()
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Assert-ReleaseHashManifest {
    param([Parameter(Mandatory = $true)][string]$ReleaseRoot)

    $hashManifestPath = Join-Path $ReleaseRoot "release-files.sha256"
    if (-not (Test-Path -LiteralPath $hashManifestPath -PathType Leaf)) {
        throw "The release is missing mandatory integrity manifest: $hashManifestPath"
    }

    $releaseRootPrefix = (Get-NormalizedPath -Path $ReleaseRoot) + "\"
    $seenPaths = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $expectedHashes = New-Object 'System.Collections.Generic.Dictionary[string,string]' `
        ([System.StringComparer]::OrdinalIgnoreCase)
    $verifiedCount = 0
    $verifiedReleaseMetadata = $false
    foreach ($line in Get-Content -LiteralPath $hashManifestPath -Encoding UTF8) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith("#")) {
            continue
        }
        if ($line -notmatch '^([A-Fa-f0-9]{64})\s{2}(.+)$') {
            throw "Invalid release-files.sha256 entry: $line"
        }
        $expectedHash = $Matches[1].ToLowerInvariant()
        $manifestRelativePath = $Matches[2]
        if ($manifestRelativePath.Contains("\") -or
            $manifestRelativePath.StartsWith("/") -or
            $manifestRelativePath -match '^[A-Za-z]:' -or
            $manifestRelativePath -match '[<>:"|?*]') {
            throw "release-files.sha256 contains an unsafe or non-canonical path: $manifestRelativePath"
        }
        $segments = @($manifestRelativePath.Split("/"))
        if ($segments.Count -eq 0 -or
            @($segments | Where-Object { $_ -eq "" -or $_ -eq "." -or $_ -eq ".." }).Count -ne 0) {
            throw "release-files.sha256 contains path traversal or an empty segment: $manifestRelativePath"
        }
        if ($manifestRelativePath -ieq "release-files.sha256") {
            throw "release-files.sha256 must not authenticate itself."
        }
        $relativePath = $manifestRelativePath.Replace("/", "\")
        $resolvedPath = Get-NormalizedPath -Path (Join-Path $ReleaseRoot $relativePath)
        if (-not $resolvedPath.StartsWith($releaseRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "release-files.sha256 contains a path outside the release: $relativePath"
        }
        $normalizedRelativePath = $resolvedPath.Substring($releaseRootPrefix.Length).Replace("\", "/")
        if (-not $seenPaths.Add($normalizedRelativePath)) {
            throw "release-files.sha256 contains a duplicate path: $normalizedRelativePath"
        }
        $expectedHashes.Add($normalizedRelativePath, $expectedHash)
        if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
            throw "release-files.sha256 references a missing file: $normalizedRelativePath"
        }
        $actualHash = (Get-FileHash -LiteralPath $resolvedPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw "Release file checksum mismatch: $normalizedRelativePath"
        }
        if ($normalizedRelativePath -ieq "release-build.json") {
            $verifiedReleaseMetadata = $true
        }
        $verifiedCount += 1
    }
    if ($verifiedCount -eq 0) {
        throw "release-files.sha256 contains no file checksums."
    }
    if (-not $verifiedReleaseMetadata) {
        throw "release-files.sha256 must include and authenticate release-build.json."
    }
    foreach ($releaseFile in Get-ChildItem -LiteralPath $ReleaseRoot -File -Recurse) {
        if ($releaseFile.FullName -ieq $hashManifestPath) {
            continue
        }
        $relativePath = $releaseFile.FullName.Substring($releaseRootPrefix.Length).Replace("\", "/")
        if (-not $seenPaths.Contains($relativePath)) {
            throw "release-files.sha256 omitted a release payload file: $relativePath"
        }
    }
    Write-Host "Verified release-files.sha256: $verifiedCount files"
    return ,$expectedHashes
}

function Get-ZipEntryHashes {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$EntryNames
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $required = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($entryName in $EntryNames) {
        [void]$required.Add($entryName.Replace("\", "/"))
    }
    $hashes = New-Object 'System.Collections.Generic.Dictionary[string,string]' `
        ([System.StringComparer]::OrdinalIgnoreCase)
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        foreach ($entry in $archive.Entries) {
            $normalizedName = ConvertFrom-MsixEntryName -Name $entry.FullName
            if (-not $required.Contains($normalizedName)) {
                continue
            }
            if ($hashes.ContainsKey($normalizedName)) {
                throw "MSIX contains a duplicate release payload entry: $normalizedName"
            }
            $stream = $entry.Open()
            $sha256 = [System.Security.Cryptography.SHA256]::Create()
            try {
                $digest = $sha256.ComputeHash($stream)
                $hashes.Add(
                    $normalizedName,
                    [System.BitConverter]::ToString($digest).Replace("-", "").ToLowerInvariant()
                )
            }
            finally {
                $sha256.Dispose()
                $stream.Dispose()
            }
        }
    }
    finally {
        $archive.Dispose()
    }
    foreach ($entryName in $required) {
        if (-not $hashes.ContainsKey($entryName)) {
            throw "MSIX package omitted a hashed release payload entry: $entryName"
        }
    }
    return ,$hashes
}

function Assert-PathsDoNotOverlap {
    param(
        [Parameter(Mandatory = $true)][string]$FirstName,
        [Parameter(Mandatory = $true)][string]$FirstPath,
        [Parameter(Mandatory = $true)][string]$SecondName,
        [Parameter(Mandatory = $true)][string]$SecondPath
    )

    $first = Get-NormalizedPath -Path $FirstPath
    $second = Get-NormalizedPath -Path $SecondPath
    if ($first -eq $second -or
        $first.StartsWith($second + "\", [System.StringComparison]::OrdinalIgnoreCase) -or
        $second.StartsWith($first + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$FirstName and $SecondName must not contain one another: '$first' and '$second'."
    }
}

function Promote-GeneratedMetadata {
    param(
        [Parameter(Mandatory = $true)][string]$StagedPath,
        [Parameter(Mandatory = $true)][string]$FinalPath,
        [Parameter(Mandatory = $true)][string]$BackupPath
    )

    $hadPrevious = Test-Path -LiteralPath $FinalPath
    try {
        if ($hadPrevious) {
            Move-Item -LiteralPath $FinalPath -Destination $BackupPath
        }
        Move-Item -LiteralPath $StagedPath -Destination $FinalPath
    }
    catch {
        $promotionError = $_
        if (Test-Path -LiteralPath $FinalPath) {
            Remove-Item -LiteralPath $FinalPath -Recurse -Force -ErrorAction SilentlyContinue
        }
        if ($hadPrevious -and (Test-Path -LiteralPath $BackupPath)) {
            Move-Item -LiteralPath $BackupPath -Destination $FinalPath -ErrorAction SilentlyContinue
        }
        throw $promotionError
    }
    if (Test-Path -LiteralPath $BackupPath) {
        Remove-Item -LiteralPath $BackupPath -Recurse -Force
    }
}

function Promote-OutputFiles {
    param(
        [Parameter(Mandatory = $true)][object[]]$Mappings,
        [Parameter(Mandatory = $true)][string]$BackupRoot
    )

    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
    $backups = New-Object System.Collections.Generic.List[object]
    $promoted = New-Object System.Collections.Generic.List[string]
    $promotionSucceeded = $false
    try {
        foreach ($mapping in $Mappings) {
            if (Test-Path -LiteralPath $mapping.FinalPath) {
                $backupPath = Join-Path $BackupRoot ([Guid]::NewGuid().ToString("N") + "-" + (Split-Path -Leaf $mapping.FinalPath))
                Move-Item -LiteralPath $mapping.FinalPath -Destination $backupPath
                $backups.Add([pscustomobject]@{ FinalPath = $mapping.FinalPath; BackupPath = $backupPath })
            }
        }
        foreach ($mapping in $Mappings) {
            if ([string]::IsNullOrWhiteSpace([string]$mapping.StagedPath)) {
                continue
            }
            if (-not (Test-Path -LiteralPath $mapping.StagedPath -PathType Leaf)) {
                throw "Staged MSIX output is missing: $($mapping.StagedPath)"
            }
            Move-Item -LiteralPath $mapping.StagedPath -Destination $mapping.FinalPath
            $promoted.Add([string]$mapping.FinalPath)
            if (-not [string]::IsNullOrWhiteSpace([string]$mapping.ExpectedHash)) {
                $actualHash = (Get-FileHash -LiteralPath $mapping.FinalPath -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($actualHash -ne [string]$mapping.ExpectedHash) {
                    throw "Promoted MSIX output checksum mismatch: $($mapping.FinalPath)"
                }
            }
        }
        $promotionSucceeded = $true
    }
    catch {
        $promotionError = $_
        $rollbackErrors = New-Object System.Collections.Generic.List[string]
        $promotedPaths = @($promoted.ToArray())
        [array]::Reverse($promotedPaths)
        foreach ($promotedPath in $promotedPaths) {
            try {
                Remove-Item -LiteralPath $promotedPath -Force -ErrorAction Stop
            }
            catch {
                $rollbackErrors.Add("remove '$promotedPath': $($_.Exception.Message)")
            }
        }
        $backupItems = @($backups.ToArray())
        [array]::Reverse($backupItems)
        foreach ($backup in $backupItems) {
            if (Test-Path -LiteralPath $backup.BackupPath) {
                try {
                    Move-Item -LiteralPath $backup.BackupPath -Destination $backup.FinalPath -ErrorAction Stop
                }
                catch {
                    $rollbackErrors.Add("restore '$($backup.FinalPath)': $($_.Exception.Message)")
                }
            }
        }
        if ($rollbackErrors.Count -ne 0) {
            throw "MSIX output promotion failed: $($promotionError.Exception.Message). Rollback is incomplete; preserve '$BackupRoot'. $($rollbackErrors -join '; ')"
        }
        throw $promotionError
    }
    finally {
        if ($promotionSucceeded -and (Test-Path -LiteralPath $BackupRoot)) {
            Remove-Item -LiteralPath $BackupRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Assert-ProductionLogo {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        Add-Type -AssemblyName System.Drawing
        $image = [System.Drawing.Image]::FromFile($Path)
    }
    catch {
        throw "Production LogoSource must be a readable raster image: $($_.Exception.Message)"
    }
    try {
        if ($image.Width -ne $image.Height) {
            throw "Production LogoSource must be square; found $($image.Width)x$($image.Height)."
        }
        if ($image.Width -lt 400) {
            throw "Production LogoSource must be at least 400x400 pixels; found $($image.Width)x$($image.Height)."
        }
    }
    finally {
        $image.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
    throw "MSIX manifest template was not found: $templatePath"
}

Assert-StoreVersion -Value $Version

if ($DevelopmentIdentity) {
    if ($IdentityName -or $Publisher -or $PublisherDisplayName -or $DisplayName) {
        throw "Do not combine -DevelopmentIdentity with explicit production identity values."
    }
    $IdentityName = "Rayluno.Development"
    $Publisher = "CN=Rayluno Development"
    $PublisherDisplayName = "Rayluno Development"
    $DisplayName = "Rayluno (Development)"
    if ([string]::IsNullOrWhiteSpace($Description)) {
        $Description = $developmentDescription
    }
    if ([string]::IsNullOrWhiteSpace($LogoSource)) {
        $LogoSource = Join-Path $root "website\public\og-rayluno.png"
    }
}
else {
    Assert-RequiredText -Name "IdentityName" -Value $IdentityName -MaximumLength 50
    Assert-RequiredText -Name "Publisher" -Value $Publisher
    Assert-RequiredText -Name "PublisherDisplayName" -Value $PublisherDisplayName -MaximumLength 256
    Assert-RequiredText -Name "DisplayName" -Value $DisplayName -MaximumLength 256
    Assert-RequiredText -Name "Description" -Value $Description -MaximumLength 2048
    foreach ($brandValue in @($IdentityName, $Publisher, $PublisherDisplayName, $DisplayName, $Description)) {
        if ($brandValue -match '(?i)Future[\s._-]*Assistant') {
            throw "The legacy Future Assistant working identity cannot be used in a production Store package."
        }
    }
    if ($IdentityName -eq "Rayluno.Development" -or
        $Publisher -eq "CN=Rayluno Development" -or
        $PublisherDisplayName -eq "Rayluno Development" -or
        $DisplayName -eq "Rayluno (Development)") {
        throw "Development identity values cannot be used in a production Store package. Copy the exact production identity from Partner Center."
    }
    if ($Description.Trim() -eq $developmentDescription) {
        throw "The default development description cannot be used for a production Store package. Pass reviewed final copy explicitly."
    }
    if ([string]::IsNullOrWhiteSpace($LogoSource)) {
        throw "LogoSource is required for a production package. Pass the final cleared square brand artwork."
    }
}

Assert-RequiredText -Name "Description" -Value $Description -MaximumLength 2048
if ($IdentityName.Length -lt 3 -or $IdentityName.Length -gt 50 -or
    $IdentityName -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]+[A-Za-z0-9]$') {
    throw "IdentityName must be 3-50 ASCII letters, digits, periods, or hyphens and must start/end with a letter or digit. Copy it exactly from Partner Center."
}
if ($Publisher -notmatch '(^|,)\s*(CN|OU|O|L|S|C|STREET|SERIALNUMBER|OID\.[0-9.]+)\s*=') {
    throw "Publisher must be the exact X.500 distinguished name from Partner Center."
}

if (-not $ReleaseDir) {
    $ReleaseDir = Join-Path $root "dist\Rayluno"
}
$ReleaseDir = Get-NormalizedPath -Path $ReleaseDir
if (-not (Test-Path -LiteralPath $ReleaseDir -PathType Container)) {
    throw "Release directory was not found: $ReleaseDir. Run scripts\build-release.ps1 -WithVoice first."
}
$normalizedPayloadStagingRoot = Get-NormalizedPath -Path $payloadStagingRoot
$normalizedMetadataRoot = Get-NormalizedPath -Path $metadataRoot
foreach ($generatedRoot in @($normalizedPayloadStagingRoot, $normalizedMetadataRoot)) {
    if ($generatedRoot -eq $ReleaseDir -or
        $generatedRoot.StartsWith($ReleaseDir + "\", [System.StringComparison]::OrdinalIgnoreCase) -or
        $ReleaseDir.StartsWith($generatedRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "ReleaseDir and generated MSIX working directories must not contain one another."
    }
}

$requiredReleasePaths = @(
    "Rayluno.exe",
    "RaylunoCLI.exe",
    "_internal",
    "release-build.json",
    "release-files.sha256",
    "THIRD_PARTY_NOTICES.md",
    "THIRD_PARTY_LICENSES\license-manifest.json",
    "THIRD_PARTY_LICENSES\sbom.cdx.json",
    "voice-model-files.sha256"
)
foreach ($relativePath in $requiredReleasePaths) {
    $requiredPath = Join-Path $ReleaseDir $relativePath
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "The commercial local-voice release is incomplete; missing: $requiredPath"
    }
}

$releaseHashMap = Assert-ReleaseHashManifest -ReleaseRoot $ReleaseDir
$releaseHashManifestPath = Join-Path $ReleaseDir "release-files.sha256"
$releaseHashManifestHash = (Get-FileHash -LiteralPath $releaseHashManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()

$releaseMetadata = Get-Content -Raw -LiteralPath (Join-Path $ReleaseDir "release-build.json") | ConvertFrom-Json
if ([string]$releaseMetadata.profile -ne "commercial-local-voice") {
    throw "MSIX Store packaging requires the verified commercial-local-voice release profile."
}
if ([string]$releaseMetadata.architecture -ne "x64") {
    throw "This MSIX definition supports only the verified x64 release."
}

$sourceReleaseVersion = [string]$releaseMetadata.version
$sourceVersionMatch = [regex]::Match($sourceReleaseVersion, '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
if (-not $sourceVersionMatch.Success) {
    if (-not $DevelopmentIdentity) {
        throw "Production MSIX packaging requires a three-part numeric application version; found $sourceReleaseVersion."
    }
    Write-Warning "Development package version cannot be compared with non-numeric source version $sourceReleaseVersion."
}
else {
    $packageVersionParts = @($Version.Split(".")) | ForEach-Object { [int64]$_ }
    $sourceVersionParts = @(1..3) | ForEach-Object { [int64]$sourceVersionMatch.Groups[$_].Value }
    $versionMatchesRelease = (
        $packageVersionParts[0] -eq $sourceVersionParts[0] -and
        $packageVersionParts[1] -eq $sourceVersionParts[1] -and
        $packageVersionParts[2] -eq $sourceVersionParts[2]
    )
    if (-not $versionMatchesRelease) {
        $expectedVersion = "$sourceReleaseVersion.0"
        if (-not $DevelopmentIdentity) {
            throw "Production MSIX version must match the packaged application version in its first three components. Expected $expectedVersion; found $Version."
        }
        Write-Warning "Development identity exception: MSIX $Version wraps application $sourceReleaseVersion. Production must use matching first three components."
    }
}
if ([string]$releaseMetadata.product -ne "Rayluno") {
    throw "release-build.json must identify the Rayluno product. Rebuild the rebranded release before creating an MSIX package."
}

$LogoSource = Get-NormalizedPath -Path $LogoSource
if (-not (Test-Path -LiteralPath $LogoSource -PathType Leaf)) {
    throw "Logo source was not found: $LogoSource"
}
if (-not $DevelopmentIdentity) {
    Assert-ProductionLogo -Path $LogoSource
}

if (-not $OutputDir) {
    $OutputDir = Join-Path $root "dist\msix"
}
$OutputDir = Get-NormalizedPath -Path $OutputDir
if ($OutputDir -eq $ReleaseDir -or
    $OutputDir.StartsWith($ReleaseDir + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDir must not be inside ReleaseDir."
}
Assert-PathsDoNotOverlap -FirstName "OutputDir" -FirstPath $OutputDir -SecondName "MSIX build root" -SecondPath $msixBuildRoot
if ($DevelopmentIdentity -and -not $SkipUploadPackage) {
    Write-Host "Development identity forces -SkipUploadPackage; no Store upload artifact will be created."
    $SkipUploadPackage = $true
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$outputStagingRoot = Join-Path $OutputDir ".rayluno-msix-staging-$runId"
$outputBackupRoot = Join-Path $OutputDir ".rayluno-msix-backup-$runId"
$generatedBackupRoot = Join-Path $msixBuildRoot ".generated-backup-$runId"
$buildLockPath = Join-Path $msixBuildRoot ".build.lock"
$buildLock = $null

try {
    New-Item -ItemType Directory -Force -Path $msixBuildRoot | Out-Null
    try {
        $buildLock = [System.IO.File]::Open(
            $buildLockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    }
    catch {
        throw "Another MSIX build is active, or the build lock cannot be acquired: $buildLockPath"
    }
    Assert-SafeGeneratedDirectory -Path $runRoot
    New-Item -ItemType Directory -Force -Path $metadataRoot | Out-Null
    New-Item -ItemType Directory -Force -Path $outputStagingRoot | Out-Null

    $template = Get-Content -Raw -LiteralPath $templatePath
    $replacementValues = [ordered]@{
    "@@IDENTITY_NAME@@" = $IdentityName
    "@@PUBLISHER@@" = $Publisher
    "@@VERSION@@" = $Version
    "@@DISPLAY_NAME@@" = $DisplayName
    "@@PUBLISHER_DISPLAY_NAME@@" = $PublisherDisplayName
    "@@DESCRIPTION@@" = $Description
    }
    $renderedManifest = $template
    foreach ($replacement in $replacementValues.GetEnumerator()) {
        $renderedManifest = $renderedManifest.Replace(
        $replacement.Key,
        (ConvertTo-XmlText -Value ([string]$replacement.Value))
        )
    }
    if ($renderedManifest -match '@@[A-Z_]+@@') {
        throw "The generated MSIX manifest still contains an unresolved placeholder: $($Matches[0])"
    }

    $manifestPath = Join-Path $metadataRoot "Package.appxmanifest"
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($manifestPath, $renderedManifest, $utf8)

    try {
        [xml]$manifestXml = $renderedManifest
    }
    catch {
        throw "Generated MSIX manifest is not valid XML: $($_.Exception.Message)"
    }

    $winAppExe = Get-WinAppCommand -RequestedPath $WinApp
    $versionOutput = @(& $winAppExe --version)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read the WinApp CLI version."
    }
    $winAppVersionText = ($versionOutput | Where-Object { $_ -match '^\d+\.\d+\.\d+$' } | Select-Object -Last 1)
    if ([string]::IsNullOrWhiteSpace($winAppVersionText)) {
        throw "Unable to parse the WinApp CLI version."
    }
    $winAppVersion = [version]$winAppVersionText
    if ($winAppVersion -lt [version]"0.4.0") {
        throw "WinApp CLI 0.4.0 or newer is required; found $winAppVersionText."
    }

$previousTelemetry = [Environment]::GetEnvironmentVariable("WINAPP_CLI_TELEMETRY_OPTOUT", "Process")
[Environment]::SetEnvironmentVariable("WINAPP_CLI_TELEMETRY_OPTOUT", "1", "Process")
try {
    Invoke-Checked -FilePath $winAppExe -Arguments @(
        "manifest", "update-assets", $LogoSource,
        "--manifest", $manifestPath,
        "--quiet"
    )

    if ($ManifestOnly) {
        Promote-GeneratedMetadata `
            -StagedPath $metadataRoot `
            -FinalPath $generatedOutputRoot `
            -BackupPath $generatedBackupRoot
        $generatedManifestPath = Join-Path $generatedOutputRoot "Package.appxmanifest"
        Write-Host "Generated manifest: $generatedManifestPath"
        Write-Host "Generated assets: $(Join-Path $generatedOutputRoot 'Assets')"
        if ($DevelopmentIdentity) {
            Write-Warning "Development identity output is scaffolding only. Do not submit it to Microsoft Store."
        }
        return
    }

    $safePackageName = ($IdentityName -replace '[^A-Za-z0-9.-]', '-')
    $packageFileName = "$safePackageName-$Version-x64.msix"
    $uploadFileName = "$safePackageName-$Version-x64.msixupload"
    $packagePath = Join-Path $OutputDir $packageFileName
    $expectedUploadPath = Join-Path $OutputDir "$safePackageName-$Version-x64.msixupload"
    $stagedPackagePath = Join-Path $outputStagingRoot $packageFileName
    $stagedUploadPath = Join-Path $outputStagingRoot $uploadFileName
    $buildManifestPath = Join-Path $OutputDir "msix-build-manifest.json"
    $stagedBuildManifestPath = Join-Path $outputStagingRoot "msix-build-manifest.json"

    $smokeScript = Join-Path $PSScriptRoot "smoke-release.ps1"
    Invoke-Checked -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $smokeScript,
        "-ReleaseDir", $ReleaseDir,
        "-ExpectVoice"
    )

    $releaseFiles = @(Get-ChildItem -LiteralPath $ReleaseDir -File -Recurse)
    $sourceDistributionMarkerPath = Join-Path $ReleaseDir $distributionMarkerName
    if (Test-Path -LiteralPath $sourceDistributionMarkerPath) {
        throw "The immutable release payload must not contain a distribution marker: $sourceDistributionMarkerPath"
    }
    Assert-SafeGeneratedDirectory -Path $payloadStagingRoot
    if ($releaseFiles.Count -ne ($releaseHashMap.Count + 1)) {
        throw "The release file count changed after integrity verification."
    }
    New-Item -ItemType Directory -Force -Path $payloadStagingRoot | Out-Null
    $distributionMarkerValue = if ($DevelopmentIdentity) { "msix-sideload" } else { "microsoft-store" }
    $distributionMarkerPath = Join-Path $payloadStagingRoot $distributionMarkerName
    $stagedCopyCount = 0

    foreach ($releaseFile in $releaseFiles) {
        $relativePath = $releaseFile.FullName.Substring($ReleaseDir.Length + 1)
        $normalizedRelativePath = $relativePath.Replace("\", "/")
        $expectedHash = ""
        if ($normalizedRelativePath -ieq "release-files.sha256") {
            $expectedHash = $releaseHashManifestHash
        }
        elseif (-not $releaseHashMap.TryGetValue($normalizedRelativePath, [ref]$expectedHash)) {
            throw "Release snapshot contains a file absent from release-files.sha256: $normalizedRelativePath"
        }
        $stagedPath = Join-Path $payloadStagingRoot $relativePath
        $stagedParent = Split-Path -Parent $stagedPath
        New-Item -ItemType Directory -Force -Path $stagedParent | Out-Null
        Copy-Item -LiteralPath $releaseFile.FullName -Destination $stagedPath -Force
        $stagedHash = (Get-FileHash -LiteralPath $stagedPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($stagedHash -ne $expectedHash) {
            throw "Staged release snapshot checksum mismatch: $normalizedRelativePath"
        }
        $stagedCopyCount += 1
    }
    if ($stagedCopyCount -ne $releaseFiles.Count) {
        throw "The copied MSIX staging payload file count does not match the verified release."
    }
    $snapshotFiles = @(Get-ChildItem -LiteralPath $payloadStagingRoot -File -Recurse)
    $releasePayloadBytes = [long](($snapshotFiles | Measure-Object -Property Length -Sum).Sum)
    [System.IO.File]::WriteAllText(
        $distributionMarkerPath,
        $distributionMarkerValue + "`n",
        $utf8
    )
    Invoke-Checked -FilePath $winAppExe -Arguments @(
        "package", $payloadStagingRoot,
        "--manifest", $manifestPath,
        "--executable", "Rayluno.exe",
        "--output", $stagedPackagePath,
        "--quiet"
    )

    if (-not (Test-Path -LiteralPath $stagedPackagePath -PathType Leaf)) {
        throw "WinApp CLI did not create the expected staged MSIX package: $stagedPackagePath"
    }

    $packageEntries = @(Get-ZipEntries -Path $stagedPackagePath)
    $entrySet = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $packageEntries) {
        if (-not $entrySet.Add($entry)) {
            throw "MSIX contains a duplicate entry: $entry"
        }
    }
    foreach ($requiredEntry in @(
        "Rayluno.exe",
        "RaylunoCLI.exe",
        "release-build.json",
        "THIRD_PARTY_NOTICES.md",
        "THIRD_PARTY_LICENSES/license-manifest.json",
        "THIRD_PARTY_LICENSES/sbom.cdx.json",
        "voice-model-files.sha256",
        $distributionMarkerName,
        "Assets/StoreLogo.png",
        "Assets/MedTile.png",
        "Assets/AppList.png",
        "Assets/WideTile.png",
        "AppxManifest.xml",
        "AppxBlockMap.xml",
        "[Content_Types].xml"
    )) {
        if (-not $entrySet.Contains($requiredEntry)) {
            throw "MSIX package omitted a required entry: $requiredEntry"
        }
    }
    if ($entrySet.Contains("AppxSignature.p7x")) {
        throw "Store submission package was unexpectedly signed. This build path must remain unsigned for Microsoft Store re-signing."
    }

    foreach ($releaseFile in $releaseFiles) {
        $relativePath = $releaseFile.FullName.Substring($ReleaseDir.Length + 1).Replace("\", "/")
        if (-not $entrySet.Contains($relativePath)) {
            throw "MSIX package omitted a release payload file: $relativePath"
        }
    }
    $releaseEntryNames = @(
        $releaseFiles | ForEach-Object {
            $_.FullName.Substring($ReleaseDir.Length + 1).Replace("\", "/")
        }
    )
    $packagedReleaseHashes = Get-ZipEntryHashes -Path $stagedPackagePath -EntryNames $releaseEntryNames
    foreach ($relativePath in $releaseEntryNames) {
        $expectedHash = ""
        if ($relativePath -ieq "release-files.sha256") {
            $expectedHash = $releaseHashManifestHash
        }
        elseif (-not $releaseHashMap.TryGetValue($relativePath, [ref]$expectedHash)) {
            throw "No authenticated release hash exists for packaged entry: $relativePath"
        }
        if ($packagedReleaseHashes[$relativePath] -ne $expectedHash) {
            throw "MSIX release payload checksum mismatch: $relativePath"
        }
    }
    $packagedDistributionMarker = Read-ZipText -Path $stagedPackagePath -EntryName $distributionMarkerName
    if ($packagedDistributionMarker -ne ($distributionMarkerValue + "`n")) {
        throw "MSIX package contains an invalid distribution marker."
    }

    [xml]$packagedManifest = Read-ZipText -Path $stagedPackagePath -EntryName "AppxManifest.xml"
    $namespaceManager = New-Object System.Xml.XmlNamespaceManager($packagedManifest.NameTable)
    $namespaceManager.AddNamespace("f", "http://schemas.microsoft.com/appx/manifest/foundation/windows10")
    $namespaceManager.AddNamespace("uap", "http://schemas.microsoft.com/appx/manifest/uap/windows10")
    $namespaceManager.AddNamespace("rescap", "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities")
    $identityNode = $packagedManifest.SelectSingleNode("/f:Package/f:Identity", $namespaceManager)
    if ($null -eq $identityNode -or
        $identityNode.Name -ne $IdentityName -or
        $identityNode.Publisher -ne $Publisher -or
        $identityNode.Version -ne $Version -or
        $identityNode.ProcessorArchitecture -ne "x64") {
        throw "Packaged MSIX identity does not match the requested Partner Center identity."
    }
    if ($null -eq $packagedManifest.SelectSingleNode(
            "/f:Package/f:Capabilities/rescap:Capability[@Name='runFullTrust']",
            $namespaceManager
        )) {
        throw "Packaged MSIX is missing the required runFullTrust capability."
    }
    if ($null -eq $packagedManifest.SelectSingleNode(
            "/f:Package/f:Capabilities/f:DeviceCapability[@Name='microphone']",
            $namespaceManager
        )) {
        throw "Packaged MSIX is missing the declared microphone capability."
    }

    $applicationNodes = @($packagedManifest.SelectNodes("/f:Package/f:Applications/f:Application", $namespaceManager))
    if ($applicationNodes.Count -ne 1) {
        throw "Packaged MSIX must contain exactly one application entry."
    }
    $applicationNode = $applicationNodes[0]
    if ($applicationNode.GetAttribute("Id") -ne "App" -or
        $applicationNode.GetAttribute("Executable") -ne "Rayluno.exe" -or
        $applicationNode.GetAttribute("EntryPoint") -ne "Windows.FullTrustApplication") {
        throw "Packaged MSIX application executable or full-trust entry point is invalid."
    }

    $targetFamilyNodes = @($packagedManifest.SelectNodes("/f:Package/f:Dependencies/f:TargetDeviceFamily", $namespaceManager))
    if ($targetFamilyNodes.Count -ne 1) {
        throw "Packaged MSIX must declare exactly one TargetDeviceFamily."
    }
    $targetFamilyNode = $targetFamilyNodes[0]
    if ($targetFamilyNode.GetAttribute("Name") -ne "Windows.Desktop" -or
        $targetFamilyNode.GetAttribute("MinVersion") -ne "10.0.18362.0" -or
        $targetFamilyNode.GetAttribute("MaxVersionTested") -ne "10.0.26200.0") {
        throw "Packaged MSIX TargetDeviceFamily does not match the tested Windows Desktop range."
    }

    $resourceLanguages = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($resourceNode in @($packagedManifest.SelectNodes("/f:Package/f:Resources/f:Resource", $namespaceManager))) {
        [void]$resourceLanguages.Add($resourceNode.GetAttribute("Language"))
    }
    foreach ($requiredLanguage in @("ar", "en-US")) {
        if (-not $resourceLanguages.Contains($requiredLanguage)) {
            throw "Packaged MSIX is missing required resource language: $requiredLanguage"
        }
    }

    $propertiesDisplayNameNode = $packagedManifest.SelectSingleNode(
        "/f:Package/f:Properties/f:DisplayName",
        $namespaceManager
    )
    $propertiesPublisherNode = $packagedManifest.SelectSingleNode(
        "/f:Package/f:Properties/f:PublisherDisplayName",
        $namespaceManager
    )
    $propertiesDescriptionNode = $packagedManifest.SelectSingleNode(
        "/f:Package/f:Properties/f:Description",
        $namespaceManager
    )
    $propertiesLogoNode = $packagedManifest.SelectSingleNode("/f:Package/f:Properties/f:Logo", $namespaceManager)
    $visualNode = $packagedManifest.SelectSingleNode(
        "/f:Package/f:Applications/f:Application/uap:VisualElements",
        $namespaceManager
    )
    $defaultTileNode = $packagedManifest.SelectSingleNode(
        "/f:Package/f:Applications/f:Application/uap:VisualElements/uap:DefaultTile",
        $namespaceManager
    )
    if ($null -eq $propertiesDisplayNameNode -or $propertiesDisplayNameNode.InnerText -ne $DisplayName -or
        $null -eq $propertiesPublisherNode -or $propertiesPublisherNode.InnerText -ne $PublisherDisplayName -or
        $null -eq $propertiesDescriptionNode -or $propertiesDescriptionNode.InnerText -ne $Description -or
        $null -eq $propertiesLogoNode -or $propertiesLogoNode.InnerText -ne "Assets\StoreLogo.png" -or
        $null -eq $visualNode -or
        $visualNode.GetAttribute("DisplayName") -ne $DisplayName -or
        $visualNode.GetAttribute("Description") -ne $Description -or
        $visualNode.GetAttribute("Square150x150Logo") -ne "Assets\MedTile.png" -or
        $visualNode.GetAttribute("Square44x44Logo") -ne "Assets\AppList.png" -or
        $null -eq $defaultTileNode -or
        $defaultTileNode.GetAttribute("Wide310x150Logo") -ne "Assets\WideTile.png") {
        throw "Packaged MSIX manifest contains invalid brand properties or visual asset references."
    }

    $packageItem = Get-Item -LiteralPath $stagedPackagePath
    $packageHash = (Get-FileHash -LiteralPath $stagedPackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $logoHash = (Get-FileHash -LiteralPath $LogoSource -Algorithm SHA256).Hash.ToLowerInvariant()
    $releaseBuildHash = $releaseHashMap["release-build.json"]

    $uploadPath = $null
    $uploadHash = $null
    $uploadSize = $null
    if (-not $SkipUploadPackage) {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $uploadPath = $expectedUploadPath
        $uploadArchive = [System.IO.Compression.ZipFile]::Open(
            $stagedUploadPath,
            [System.IO.Compression.ZipArchiveMode]::Create
        )
        try {
            [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $uploadArchive,
                $stagedPackagePath,
                $packageItem.Name,
                [System.IO.Compression.CompressionLevel]::NoCompression
            )
        }
        finally {
            $uploadArchive.Dispose()
        }
        $uploadItem = Get-Item -LiteralPath $stagedUploadPath
        $uploadHash = (Get-FileHash -LiteralPath $stagedUploadPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $uploadSize = $uploadItem.Length
    }

    $buildManifest = [ordered]@{
        product = $DisplayName
        package_version = $Version
        architecture = "x64"
        identity_name = $IdentityName
        publisher = $Publisher
        publisher_display_name = $PublisherDisplayName
        builder = "Microsoft WinApp CLI"
        builder_version = $winAppVersionText
        unsigned_store_submission = (-not $DevelopmentIdentity)
        distribution_marker = $distributionMarkerName
        distribution_channel = $distributionMarkerValue
        package = $packageItem.Name
        package_size_bytes = $packageItem.Length
        package_sha256 = $packageHash
        upload_package = if ($null -eq $uploadPath) { $null } else { Split-Path -Leaf $uploadPath }
        upload_package_size_bytes = $uploadSize
        upload_package_sha256 = $uploadHash
        source_release_version = [string]$releaseMetadata.version
        source_release_profile = [string]$releaseMetadata.profile
        source_release_file_count = $releaseFiles.Count
        source_release_size_bytes = $releasePayloadBytes
        source_release_build_sha256 = $releaseBuildHash
        source_release_hash_manifest_sha256 = $releaseHashManifestHash
        staged_copy_count = $stagedCopyCount
        generated_manifest_sha256 = $manifestHash
        logo_source_sha256 = $logoHash
        package_entry_count = $packageEntries.Count
        built_utc = [DateTime]::UtcNow.ToString("o")
    }
    $buildManifestJson = $buildManifest | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText(
        $stagedBuildManifestPath,
        $buildManifestJson + [Environment]::NewLine,
        $utf8
    )
    $buildManifestHash = (Get-FileHash -LiteralPath $stagedBuildManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $outputMappings = @(
        [pscustomobject]@{
            StagedPath = $stagedPackagePath
            FinalPath = $packagePath
            ExpectedHash = $packageHash
        },
        [pscustomobject]@{
            StagedPath = $stagedBuildManifestPath
            FinalPath = $buildManifestPath
            ExpectedHash = $buildManifestHash
        }
    )
    if ($null -ne $uploadPath) {
        $outputMappings += [pscustomobject]@{
            StagedPath = $stagedUploadPath
            FinalPath = $expectedUploadPath
            ExpectedHash = $uploadHash
        }
    }
    else {
        $outputMappings += [pscustomobject]@{
            StagedPath = $null
            FinalPath = $expectedUploadPath
            ExpectedHash = $null
        }
    }
    Promote-OutputFiles -Mappings $outputMappings -BackupRoot $outputBackupRoot

    Write-Host "MSIX: $packagePath"
    Write-Host "Size: $($packageItem.Length) bytes"
    Write-Host "SHA256: $packageHash"
    if ($DevelopmentIdentity) {
        Write-Host "Signature: unsigned development inspection artifact"
    }
    else {
        Write-Host "Signature: unsigned (Microsoft Store submission only)"
    }
    if ($null -ne $uploadPath) {
        Write-Host "MSIX upload: $uploadPath"
        Write-Host "MSIX upload SHA256: $uploadHash"
    }
    Write-Host "Build manifest: $buildManifestPath"
    if ($DevelopmentIdentity) {
        Write-Warning "This package uses a development identity and must not be submitted to Microsoft Store."
    }
}
finally {
    [Environment]::SetEnvironmentVariable("WINAPP_CLI_TELEMETRY_OPTOUT", $previousTelemetry, "Process")
}
}
finally {
    foreach ($temporaryDirectory in @($outputStagingRoot, $runRoot)) {
        if (-not [string]::IsNullOrWhiteSpace($temporaryDirectory) -and
            (Test-Path -LiteralPath $temporaryDirectory)) {
            Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    if ($null -ne $buildLock) {
        $buildLock.Dispose()
    }
}
