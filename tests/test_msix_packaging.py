from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-msix.ps1"
TEMPLATE = ROOT / "packaging" / "msix" / "Package.appxmanifest.template"
DOCS = ROOT / "packaging" / "MSIX.md"

FOUNDATION = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
UAP = "http://schemas.microsoft.com/appx/manifest/uap/windows10"
RESCAP = "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"


def _render_manifest() -> ElementTree.Element:
    text = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "@@IDENTITY_NAME@@": "Example.Assistant",
        "@@PUBLISHER@@": "CN=Example",
        "@@VERSION@@": "1.0.0.0",
        "@@DISPLAY_NAME@@": "Example Assistant",
        "@@PUBLISHER_DISPLAY_NAME@@": "Example Publisher",
        "@@DESCRIPTION@@": "Example bilingual assistant.",
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return ElementTree.fromstring(text.encode("utf-8"))


def test_msix_manifest_declares_verified_desktop_contract() -> None:
    package = _render_manifest()
    ns = {"f": FOUNDATION, "uap": UAP, "rescap": RESCAP}

    family = package.find("f:Dependencies/f:TargetDeviceFamily", ns)
    assert family is not None
    assert family.attrib == {
        "Name": "Windows.Desktop",
        "MinVersion": "10.0.18362.0",
        "MaxVersionTested": "10.0.26200.0",
    }

    languages = {node.attrib["Language"] for node in package.findall("f:Resources/f:Resource", ns)}
    assert languages == {"ar", "en-US"}

    application = package.find("f:Applications/f:Application", ns)
    assert application is not None
    assert application.attrib["Executable"] == "$targetnametoken$.exe"
    assert application.attrib["EntryPoint"] == "Windows.FullTrustApplication"

    assert package.find("f:Capabilities/f:DeviceCapability[@Name='microphone']", ns) is not None
    assert package.find("f:Capabilities/rescap:Capability[@Name='runFullTrust']", ns) is not None
    capabilities = package.find("f:Capabilities", ns)
    assert capabilities is not None
    assert [node.tag for node in capabilities] == [
        f"{{{RESCAP}}}Capability",
        f"{{{FOUNDATION}}}DeviceCapability",
    ]

    visual = package.find("f:Applications/f:Application/uap:VisualElements", ns)
    assert visual is not None
    assert visual.attrib["Square150x150Logo"] == r"Assets\MedTile.png"
    assert visual.attrib["Square44x44Logo"] == r"Assets\AppList.png"
    tile = visual.find("uap:DefaultTile", ns)
    assert tile is not None
    assert tile.attrib["Wide310x150Logo"] == r"Assets\WideTile.png"


def test_msix_builder_contains_prepack_and_postpack_guards() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    required_fragments = (
        "Assert-ReleaseHashManifest -ReleaseRoot $ReleaseDir",
        "release-files.sha256 must include and authenticate release-build.json",
        '"-ExpectVoice"',
        "Assert-ProductionLogo -Path $LogoSource",
        "Production MSIX version must match the packaged application version",
        "Packaged MSIX is missing the declared microphone capability",
        'GetAttribute("Executable") -ne "Rayluno.exe"',
        'GetAttribute("EntryPoint") -ne "Windows.FullTrustApplication"',
        "Packaged MSIX TargetDeviceFamily does not match",
        'foreach ($requiredLanguage in @("ar", "en-US"))',
        "Copy-Item -LiteralPath $releaseFile.FullName -Destination $stagedPath -Force",
        "ConvertFrom-MsixEntryName -Name $_.FullName",
        "encoded path separator or NUL byte",
        "Get-ZipEntryHashes -Path $stagedPackagePath",
        "Promote-OutputFiles -Mappings $outputMappings",
        '"package", $payloadStagingRoot',
    )
    for fragment in required_fragments:
        assert fragment in script

    manifest_only = script.index("if ($ManifestOnly)")
    smoke = script.index('$smokeScript = Join-Path $PSScriptRoot "smoke-release.ps1"')
    package = script.index('"package", $payloadStagingRoot')
    assert manifest_only < smoke < package
    assert script.index("Assert-ReleaseHashManifest -ReleaseRoot $ReleaseDir") < smoke
    assert "ItemType HardLink" not in script


def test_distribution_marker_contract_is_consistent() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    docs = DOCS.read_text(encoding="utf-8")

    assert '$distributionMarkerName = ".future-assistant-distribution"' in script
    assert '{ "msix-sideload" } else { "microsoft-store" }' in script
    assert '$runId = [Guid]::NewGuid().ToString("N")' in script
    assert "Staged release snapshot checksum mismatch" in script
    assert "$distributionMarkerPath = Join-Path $payloadStagingRoot" in script
    assert "Development identity forces -SkipUploadPackage" in script
    assert ".future-assistant-distribution" in docs
    assert "`microsoft-store\\n`" in docs
    assert "`msix-sideload\\n`" in docs


def test_msix_uses_rayluno_development_identity_and_production_guards() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert '$IdentityName = "Rayluno.Development"' in script
    assert '$Publisher = "CN=Rayluno Development"' in script
    assert '$PublisherDisplayName = "Rayluno Development"' in script
    assert '$DisplayName = "Rayluno (Development)"' in script
    assert 'website\\public\\og-rayluno.png' in script
    assert '"--executable", "Rayluno.exe"' in script
    assert 'if ([string]$releaseMetadata.product -ne "Rayluno")' in script
    assert "Development identity values cannot be used" in script
    assert "Copy the exact production identity from Partner Center" in script
