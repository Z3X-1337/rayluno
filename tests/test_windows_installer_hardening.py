from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_RELEASE = ROOT / "scripts" / "build-release.ps1"
SMOKE_RELEASE = ROOT / "scripts" / "smoke-release.ps1"
BUILD_INSTALLER = ROOT / "scripts" / "build-installer.ps1"
NSIS = ROOT / "packaging" / "future_assistant.nsi"
INSTALLER_DOCS = ROOT / "packaging" / "INSTALLER.md"
PYINSTALLER_SPEC = ROOT / "packaging" / "future_assistant.spec"
WINDOWS_LAUNCHER = ROOT / "packaging" / "windows_launcher.py"


def test_release_archive_is_staged_hashed_and_rollback_published() -> None:
    script = BUILD_RELEASE.read_text(encoding="utf-8")

    assert "function Publish-ArchiveArtifacts" in script
    assert "$candidateArchive = Join-Path $stagingRoot $archiveName" in script
    assert '$candidateChecksum = $candidateArchive + ".sha256"' in script
    assert "Get-FileHash -LiteralPath $candidateArchive -Algorithm SHA256" in script
    assert "Publish-ArchiveArtifacts `" in script
    assert "Remove-Item -LiteralPath $archive -Force" not in script
    assert "'^\\d+\\.\\d+\\.\\d+$'" in script


def test_release_smoke_is_hermetic_and_rechecks_integrity_after_runtime() -> None:
    script = SMOKE_RELEASE.read_text(encoding="utf-8")

    assert "[switch]$IntegrityOnly" in script
    assert "if ($IntegrityOnly) {" in script
    assert "$env:LOCALAPPDATA = $smokeLocalAppData" in script
    assert "$env:APPDATA = $smokeAppData" in script
    assert '$_.Name -like "RAYLUNO_*"' in script
    assert '$env:RAYLUNO_OLLAMA_ENDPOINT = "http://127.0.0.1:9"' in script
    assert "Remove-Item -LiteralPath $smokeUserRoot -Recurse -Force" in script
    assert script.count("-ManifestPath $releaseFilesManifestPath `") == 2
    clear_environment = script.index(
        '$_.Name -like "FUTURE_ASSISTANT_*" -or $_.Name -like "RAYLUNO_*"',
        script.index("try {", script.index("$savedEnvironment")),
    )
    gui_launch = script.index("$process = Start-Process -FilePath $guiExe -PassThru")
    restore_environment = script.index("foreach ($name in $savedEnvironment.Keys)", gui_launch)
    post_runtime_hash = script.rindex("-ManifestPath $releaseFilesManifestPath `")
    assert clear_environment < gui_launch < restore_environment < post_runtime_hash


def test_release_excludes_upstream_examples_and_command_line_tools() -> None:
    spec = PYINSTALLER_SPEC.read_text(encoding="utf-8")
    smoke = SMOKE_RELEASE.read_text(encoding="utf-8")

    assert '("pywhispercpp.examples", "vosk.transcriber")' in spec
    assert '("pywhispercpp/examples", "vosk/transcriber")' in spec
    assert 'destination.replace("\\\\", "/").startswith(' in spec
    assert 'excludes += ["pywhispercpp.examples", "vosk.transcriber"]' in spec
    assert '"pywhispercpp\\examples"' in smoke
    assert '"vosk\\transcriber"' in smoke
    assert '"win32com\\test"' in smoke


def test_installer_uses_an_immutable_true_copy_and_checks_it_twice() -> None:
    script = BUILD_INSTALLER.read_text(encoding="utf-8")

    assert "function Copy-ReleaseSnapshot" in script
    assert "Copy-Item -LiteralPath $file.FullName -Destination $destinationPath -Force" in script
    assert "ItemType HardLink" not in script
    assert '"/DSOURCE_DIR=$payloadSnapshotDir"' in script
    assert script.count('"-IntegrityOnly"') == 2
    invocation = script.index("    Copy-ReleaseSnapshot `")
    compile_call = script.index("Invoke-Checked -FilePath $makensisExe", invocation)
    first_integrity = script.index('"-IntegrityOnly"', invocation)
    second_integrity = script.index('"-IntegrityOnly"', compile_call)
    assert invocation < first_integrity < compile_call < second_integrity
    assert 'snapshot = "true-copy"' in script


def test_uninstall_and_upgrade_contract_is_fail_closed() -> None:
    builder = BUILD_INSTALLER.read_text(encoding="utf-8")
    nsis = NSIS.read_text(encoding="utf-8")

    assert 'Delete /REBOOTOK "$INSTDIR\\{0}"' in builder
    assert "$UninstallDeleteFailed" in builder
    assert 'INSTALL_IDENTITY "rayluno-per-user-v1"' in nsis
    assert "/UPGRADE=1 _?=$INSTDIR" in nsis
    assert "ForeignInstallDirectory" in nsis
    assert "PreviousUninstallFailure" in nsis
    assert "RMDir /r" not in nsis
    uninstall = nsis.index('Section "Uninstall"')
    owned_delete = nsis.index('!include "${UNINSTALL_INCLUDE}"', uninstall)
    registry_delete = nsis.index('DeleteRegKey HKCU "${APP_UNINSTALL_KEY}"', uninstall)
    assert owned_delete < registry_delete


def test_signing_gate_and_smoke_cleanup_are_explicit() -> None:
    builder = BUILD_INSTALLER.read_text(encoding="utf-8")
    nsis = NSIS.read_text(encoding="utf-8")
    docs = INSTALLER_DOCS.read_text(encoding="utf-8")

    assert "SigningCertificateThumbprint" in builder
    assert "TimestampUrl" in builder
    assert "ExpectedPublisher" in builder
    assert "unsigned-release-candidate" in builder
    assert "UNSIGNED RELEASE CANDIDATE - NOT FOR PUBLIC DISTRIBUTION" in builder
    assert "!uninstfinalize '${SIGN_COMMAND}' = 0" in nsis
    assert "!finalize '${SIGN_COMMAND}' = 0" in nsis
    assert "Refusing to reuse any existing smoke-test installation path" in builder
    assert "fallback uninstall failed" in builder
    assert "smoke-test state remains after cleanup" in builder
    assert "true byte-for-byte copy" in docs
    assert "unsigned-release-candidate" in docs


def test_rayluno_packaging_identity_is_side_by_side_safe() -> None:
    release = BUILD_RELEASE.read_text(encoding="utf-8")
    smoke = SMOKE_RELEASE.read_text(encoding="utf-8")
    builder = BUILD_INSTALLER.read_text(encoding="utf-8")
    nsis = NSIS.read_text(encoding="utf-8")
    spec = PYINSTALLER_SPEC.read_text(encoding="utf-8")
    launcher = WINDOWS_LAUNCHER.read_text(encoding="utf-8")
    docs = INSTALLER_DOCS.read_text(encoding="utf-8")

    assert '$releaseDir = Join-Path $distRoot "Rayluno"' in release
    assert 'product = "Rayluno"' in release
    assert 'if ([string]$releaseManifest.product -ne "Rayluno")' in smoke
    assert 'if ([string]$releaseMetadata.product -ne "Rayluno")' in builder
    assert 'name="Rayluno"' in spec
    assert 'name="RaylunoCLI"' in spec
    assert 'Join-Path $ReleaseDir "Rayluno.exe"' in smoke
    assert 'Join-Path $ReleaseDir "RaylunoCLI.exe"' in smoke
    assert '$installerName = "Rayluno-Setup-$version-win-x64.exe"' in builder
    assert 'payload_directory = "Rayluno"' in builder
    assert '!define APP_NAME "Rayluno"' in nsis
    assert '!define APP_REG_KEY "Software\\Rayluno\\Installer"' in nsis
    assert 'Uninstall\\Rayluno"' in nsis
    assert '!define INSTALL_MARKER ".rayluno-install"' in nsis
    assert 'InstallDir "$LOCALAPPDATA\\Programs\\Rayluno"' in nsis
    assert '"rayluno", "futureassistant"' in launcher

    # The old program installation is never adopted, while its runtime-data
    # directory remains stable for settings/model compatibility.
    assert ".future-assistant-install" not in nsis
    assert "future-assistant-per-user" not in nsis
    assert "%LOCALAPPDATA%\\FutureAssistant" in docs
    assert "does not uninstall, overwrite, or claim to upgrade it" in docs
