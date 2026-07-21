[CmdletBinding()]
param(
    [string]$VideoPath,
    [string]$VoicePath,
    [string]$OutputPath = "$env:USERPROFILE\Desktop\Rayluno_Final_YouTube.mp4"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Resolve-RecentMedia {
    param(
        [string[]]$Patterns
    )

    $roots = @(
        (Get-Location).Path,
        "$env:USERPROFILE\Downloads",
        "$env:USERPROFILE\Desktop",
        "$env:USERPROFILE\Documents"
    ) | Where-Object { Test-Path $_ } | Select-Object -Unique

    $matches = foreach ($root in $roots) {
        foreach ($pattern in $Patterns) {
            Get-ChildItem -LiteralPath $root -File -Filter $pattern -ErrorAction SilentlyContinue
        }
    }

    return $matches | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Resolve-Executable([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $wingetLinks = "$env:LOCALAPPDATA\Microsoft\WinGet\Links"
    $candidate = Join-Path $wingetLinks "$Name.exe"
    if (Test-Path $candidate) {
        return $candidate
    }

    return $null
}

function Get-DurationSeconds {
    param(
        [string]$Probe,
        [string]$Path
    )

    $raw = & $Probe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 -- $Path
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
        throw "Could not read media duration: $Path"
    }
    return [double]::Parse($raw.Trim(), [Globalization.CultureInfo]::InvariantCulture)
}

Write-Step "Locating the final Rayluno video and the new narration"

if ([string]::IsNullOrWhiteSpace($VideoPath)) {
    $video = Resolve-RecentMedia -Patterns @(
        "Rayluno_Final_Hackathon_Demo*.mp4",
        "*Rayluno*Hackathon*Demo*.mp4"
    )
    if ($null -eq $video) {
        throw "Video not found. Put Rayluno_Final_Hackathon_Demo.mp4 in Downloads or Desktop, or pass -VideoPath."
    }
    $VideoPath = $video.FullName
}

if ([string]::IsNullOrWhiteSpace($VoicePath)) {
    $voice = Resolve-RecentMedia -Patterns @(
        "Video Project*.m4a",
        "*Rayluno*voice*.m4a",
        "*.m4a"
    )
    if ($null -eq $voice) {
        throw "Narration not found. Put Video Project.m4a in Downloads or Desktop, or pass -VoicePath."
    }
    $VoicePath = $voice.FullName
}

$VideoPath = (Resolve-Path -LiteralPath $VideoPath).Path
$VoicePath = (Resolve-Path -LiteralPath $VoicePath).Path
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
$OutputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

Write-Host "Video : $VideoPath"
Write-Host "Voice : $VoicePath"
Write-Host "Output: $OutputPath"

$ffmpeg = Resolve-Executable "ffmpeg"
$ffprobe = Resolve-Executable "ffprobe"

if ([string]::IsNullOrWhiteSpace($ffmpeg) -or [string]::IsNullOrWhiteSpace($ffprobe)) {
    Write-Step "Installing FFmpeg with WinGet"
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($null -eq $winget) {
        throw "FFmpeg is missing and WinGet is unavailable. Install FFmpeg, then run this script again."
    }

    & winget install --exact --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw "FFmpeg installation failed."
    }

    $env:Path = "$env:LOCALAPPDATA\Microsoft\WinGet\Links;$env:Path"
    $ffmpeg = Resolve-Executable "ffmpeg"
    $ffprobe = Resolve-Executable "ffprobe"
}

if ([string]::IsNullOrWhiteSpace($ffmpeg) -or [string]::IsNullOrWhiteSpace($ffprobe)) {
    throw "FFmpeg was installed but is not available in the current PowerShell session. Close PowerShell, reopen it, and run the script again."
}

Write-Step "Analyzing media"
$videoDuration = Get-DurationSeconds -Probe $ffprobe -Path $VideoPath
$voiceDuration = Get-DurationSeconds -Probe $ffprobe -Path $VoicePath

if ($videoDuration -lt 30) {
    throw "The source video is unexpectedly short: $([math]::Round($videoDuration, 2)) seconds."
}
if ($voiceDuration -lt 30) {
    throw "The narration is unexpectedly short: $([math]::Round($voiceDuration, 2)) seconds."
}

# Keep the submission safely below the three-minute rule.
$targetDuration = [math]::Min($voiceDuration, 178.0)
$voiceTempo = $voiceDuration / $targetDuration
$videoFactor = $targetDuration / $videoDuration
$fadeOutStart = [math]::Max(0.0, $targetDuration - 0.8)

$invariant = [Globalization.CultureInfo]::InvariantCulture
$targetText = $targetDuration.ToString("0.000", $invariant)
$tempoText = $voiceTempo.ToString("0.000000", $invariant)
$factorText = $videoFactor.ToString("0.000000", $invariant)
$fadeText = $fadeOutStart.ToString("0.000", $invariant)

Write-Host "Source video : $([math]::Round($videoDuration, 2)) s"
Write-Host "New narration: $([math]::Round($voiceDuration, 2)) s"
Write-Host "Final target : $([math]::Round($targetDuration, 2)) s"

Write-Step "Replacing the old narration and mastering the final video"

$filter = @"
[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x050911,fps=30,setpts=${factorText}*PTS,trim=duration=${targetText},fade=t=in:st=0:d=0.35,fade=t=out:st=${fadeText}:d=0.8[v];
[1:a]aresample=48000,atempo=${tempoText},highpass=f=85,lowpass=f=12000,acompressor=threshold=-18dB:ratio=3:attack=8:release=100,loudnorm=I=-16:LRA=7:TP=-1.5,afade=t=in:st=0:d=0.25,afade=t=out:st=${fadeText}:d=0.8[voice];
[2:a]volume=0.018,lowpass=f=420[pad1];
[3:a]volume=0.012,lowpass=f=620[pad2];
[voice][pad1][pad2]amix=inputs=3:duration=first:dropout_transition=0[a]
"@ -replace "`r?`n", ""

$arguments = @(
    "-y",
    "-i", $VideoPath,
    "-i", $VoicePath,
    "-f", "lavfi", "-t", $targetText, "-i", "sine=frequency=55:sample_rate=48000",
    "-f", "lavfi", "-t", $targetText, "-i", "sine=frequency=82.5:sample_rate=48000",
    "-filter_complex", $filter,
    "-map", "[v]",
    "-map", "[a]",
    "-t", $targetText,
    "-c:v", "libx264",
    "-preset", "medium",
    "-crf", "18",
    "-profile:v", "high",
    "-level", "4.1",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "192k",
    "-ar", "48000",
    "-movflags", "+faststart",
    $OutputPath
)

& $ffmpeg @arguments
if ($LASTEXITCODE -ne 0) {
    throw "FFmpeg failed to create the final video."
}

Write-Step "Verifying the result"
$finalDuration = Get-DurationSeconds -Probe $ffprobe -Path $OutputPath
if ($finalDuration -ge 180.0) {
    Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue
    throw "The generated video exceeds the three-minute rule."
}

$sizeMb = [math]::Round((Get-Item -LiteralPath $OutputPath).Length / 1MB, 1)
Write-Host ""
Write-Host "FINAL VIDEO READY" -ForegroundColor Green
Write-Host "Duration: $([math]::Round($finalDuration, 2)) seconds"
Write-Host "Size    : $sizeMb MB"
Write-Host "File    : $OutputPath"

Start-Process explorer.exe -ArgumentList "/select,`"$OutputPath`""
