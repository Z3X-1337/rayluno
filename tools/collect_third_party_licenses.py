#!/usr/bin/env python3
"""Build an exact license bundle and CycloneDX SBOM from the release environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import uuid
from collections import deque
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

BASE_DISTRIBUTIONS = (
    "cryptography",
    "PyInstaller",
    "pywebview",
)
VOICE_DISTRIBUTIONS = (
    "numpy",
    "pywhispercpp",
    "pywin32",
    "sounddevice",
    "vosk",
    "winrt-Windows.Foundation",
    "winrt-Windows.Foundation.Collections",
    "winrt-Windows.Media.SpeechSynthesis",
    "winrt-Windows.Storage.Streams",
)
LICENSE_PREFIXES = ("license", "licence", "copying", "notice", "authors", "copyright")
LICENSE_OVERRIDES = {
    "clr-loader": "MIT",
    "colorama": "BSD-3-Clause",
    "proxy-tools": "MIT",
    "pyinstaller": "GPL-2.0-or-later with PyInstaller Bootloader Exception",
    "pyinstaller-hooks-contrib": "GPL-2.0-or-later",
    "pywebview": "BSD-3-Clause",
    "vosk": "Apache-2.0",
}
SUPPLEMENTAL_COVERAGE = {
    "proxy-tools",
    "vosk",
    "winrt-runtime",
    "winrt-windows-foundation",
    "winrt-windows-foundation-collections",
    "winrt-windows-media-speechsynthesis",
    "winrt-windows-storage-streams",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _requirements(distribution: metadata.Distribution) -> tuple[str, ...]:
    dependencies: set[str] = set()
    for raw_requirement in distribution.requires or ():
        requirement = Requirement(raw_requirement)
        if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
            continue
        dependencies.add(canonicalize_name(requirement.name))
    return tuple(sorted(dependencies))


def distribution_closure(names: tuple[str, ...]) -> dict[str, metadata.Distribution]:
    """Resolve the installed, marker-aware dependency closure for release roots."""

    queue = deque(names)
    found: dict[str, metadata.Distribution] = {}
    while queue:
        requested = queue.popleft()
        canonical = canonicalize_name(requested)
        if canonical in found:
            continue
        try:
            distribution = metadata.distribution(requested)
        except metadata.PackageNotFoundError as exc:
            raise RuntimeError(
                f"required release distribution is not installed: {requested}"
            ) from exc
        found[canonical] = distribution
        queue.extend(_requirements(distribution))
    return dict(sorted(found.items()))


def _license_name(canonical: str, distribution: metadata.Distribution) -> str:
    if canonical in LICENSE_OVERRIDES:
        return LICENSE_OVERRIDES[canonical]
    expression = distribution.metadata.get("License-Expression")
    if expression and expression.strip().casefold() != "unknown":
        return expression.strip()
    declared = distribution.metadata.get("License")
    if declared and len(declared.strip()) <= 120 and declared.strip().casefold() != "unknown":
        return declared.strip()
    classifiers = distribution.metadata.get_all("Classifier") or ()
    classifier_text = " ".join(classifiers).casefold()
    for marker, identifier in (
        ("apache", "Apache-2.0"),
        ("bsd", "BSD"),
        ("mit", "MIT"),
        ("mozilla public license 2", "MPL-2.0"),
        ("python software foundation", "PSF-2.0"),
    ):
        if marker in classifier_text:
            return identifier
    raise RuntimeError(f"release distribution has no reviewed license declaration: {canonical}")


def _source_url(distribution: metadata.Distribution) -> str | None:
    project_urls = distribution.metadata.get_all("Project-URL") or ()
    parsed_urls: list[tuple[str, str]] = []
    for raw_value in project_urls:
        if "," not in raw_value:
            continue
        label, url = (part.strip() for part in raw_value.split(",", 1))
        if url.startswith(("https://", "http://")):
            parsed_urls.append((label.casefold(), url))
    for preferred in ("repository", "source", "homepage", "documentation"):
        for label, url in parsed_urls:
            if preferred in label:
                return url
    home_page = distribution.metadata.get("Home-page")
    if home_page and home_page.startswith(("https://", "http://")):
        return home_page
    return parsed_urls[0][1] if parsed_urls else None


def _license_sources(distribution: metadata.Distribution) -> tuple[tuple[PurePosixPath, Path], ...]:
    sources: list[tuple[PurePosixPath, Path]] = []
    for package_path in distribution.files or ():
        relative = PurePosixPath(str(package_path).replace("\\", "/"))
        if not relative.name.casefold().startswith(LICENSE_PREFIXES):
            continue
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"unsafe distribution license path: {relative}")
        source = Path(distribution.locate_file(package_path)).resolve()
        if source.is_file():
            sources.append((relative, source))
    return tuple(sorted(set(sources), key=lambda item: item[0].as_posix().casefold()))


def _copy_with_record(source: Path, destination: Path, relative: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return {
        "path": relative.as_posix(),
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
    }


def _copy_supplemental_directory(
    source_directory: Path, output_directory: Path
) -> list[dict[str, Any]]:
    source_directory = source_directory.resolve()
    if not source_directory.is_dir():
        raise RuntimeError(f"supplemental license directory is missing: {source_directory}")
    records: list[dict[str, Any]] = []
    for source in sorted(source_directory.rglob("*")):
        if not source.is_file():
            continue
        resolved = source.resolve()
        if source_directory not in resolved.parents:
            raise RuntimeError(f"supplemental license escapes its directory: {source}")
        relative_source = source.relative_to(source_directory)
        relative = Path("supplemental") / relative_source
        records.append(_copy_with_record(resolved, output_directory / relative, relative))
    return records


def _parse_supplemental(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("use NAME=PATH for supplemental files")
    name, raw_path = value.split("=", 1)
    if not name or Path(name).name != name or name in {".", ".."}:
        raise argparse.ArgumentTypeError("supplemental NAME must be one plain filename")
    return name, Path(raw_path)


def _component(
    canonical: str,
    distribution: metadata.Distribution,
    license_name: str,
) -> dict[str, Any]:
    name = distribution.metadata.get("Name") or canonical
    purl = f"pkg:pypi/{canonical}@{distribution.version}"
    component: dict[str, Any] = {
        "type": "library",
        "bom-ref": purl,
        "name": name,
        "version": distribution.version,
        "purl": purl,
        "licenses": [{"license": {"name": license_name}}],
    }
    source_url = _source_url(distribution)
    if source_url:
        component["externalReferences"] = [{"type": "website", "url": source_url}]
    return component


def _sbom(
    *,
    product_version: str,
    distributions: dict[str, metadata.Distribution],
    licenses: dict[str, str],
    roots: tuple[str, ...],
) -> dict[str, Any]:
    product_ref = f"pkg:generic/rayluno-assistant@{product_version}"
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    components = [
        {
            "type": "framework",
            "bom-ref": f"pkg:generic/cpython@{python_version}",
            "name": "CPython",
            "version": python_version,
            "licenses": [{"license": {"name": "PSF-2.0"}}],
        }
    ]
    components.extend(
        _component(canonical, distribution, licenses[canonical])
        for canonical, distribution in distributions.items()
    )
    dependency_nodes = [
        {
            "ref": product_ref,
            "dependsOn": [
                f"pkg:pypi/{canonicalize_name(name)}@{distributions[canonicalize_name(name)].version}"
                for name in roots
            ],
        }
    ]
    for canonical, distribution in distributions.items():
        dependencies = [
            f"pkg:pypi/{name}@{distributions[name].version}"
            for name in _requirements(distribution)
            if name in distributions
        ]
        dependency_nodes.append(
            {"ref": f"pkg:pypi/{canonical}@{distribution.version}", "dependsOn": dependencies}
        )
    identity = "|".join(
        [product_ref, *(f"{name}=={dist.version}" for name, dist in distributions.items())]
    )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, identity)}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": product_ref,
                "name": "Rayluno",
                "version": product_version,
            }
        },
        "components": components,
        "dependencies": dependency_nodes,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--product-version", required=True)
    parser.add_argument("--python-license", type=Path, required=True)
    parser.add_argument("--notice", type=Path, required=True)
    parser.add_argument("--supplemental-dir", type=Path, required=True)
    parser.add_argument("--supplemental", action="append", type=_parse_supplemental, default=[])
    parser.add_argument("--with-voice", action="store_true")
    return parser


def run(arguments: argparse.Namespace) -> Path:
    output = arguments.output.expanduser().resolve()
    if output.exists():
        raise RuntimeError(f"license bundle output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    roots = BASE_DISTRIBUTIONS + (VOICE_DISTRIBUTIONS if arguments.with_voice else ())
    distributions = distribution_closure(roots)
    licenses = {
        canonical: _license_name(canonical, distribution)
        for canonical, distribution in distributions.items()
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        packages: list[dict[str, Any]] = []
        for canonical, distribution in distributions.items():
            records: list[dict[str, Any]] = []
            package_root = Path("packages") / f"{canonical}-{distribution.version}"
            for relative_source, source in _license_sources(distribution):
                relative = package_root / Path(*relative_source.parts)
                records.append(_copy_with_record(source, temporary / relative, relative))
            if not records and canonical not in SUPPLEMENTAL_COVERAGE:
                raise RuntimeError(
                    f"no license file was found for release distribution: {canonical}"
                )
            packages.append(
                {
                    "name": distribution.metadata.get("Name") or canonical,
                    "canonical_name": canonical,
                    "version": distribution.version,
                    "license": licenses[canonical],
                    "source_url": _source_url(distribution),
                    "dependencies": [
                        name for name in _requirements(distribution) if name in distributions
                    ],
                    "license_files": records,
                }
            )

        supplemental = _copy_supplemental_directory(arguments.supplemental_dir, temporary)
        fixed_files = (
            ("CPYTHON_LICENSE.txt", arguments.python_license),
            ("THIRD_PARTY_NOTICES.md", arguments.notice),
            *arguments.supplemental,
        )
        for name, source_path in fixed_files:
            source = source_path.expanduser().resolve()
            if not source.is_file():
                raise RuntimeError(f"required supplemental notice is missing: {source}")
            relative = Path("supplemental") / name
            supplemental.append(_copy_with_record(source, temporary / relative, relative))

        apache_source = next(
            (
                source
                for relative, source in _license_sources(distributions["cryptography"])
                if relative.name.casefold() == "license.apache"
            ),
            None,
        )
        if apache_source is None:
            raise RuntimeError("cryptography did not provide the shared Apache-2.0 text")
        apache_relative = Path("supplemental") / "APACHE-2.0.txt"
        supplemental.append(
            _copy_with_record(apache_source, temporary / apache_relative, apache_relative)
        )

        manifest = {
            "schema_version": 1,
            "product": "Rayluno",
            "product_version": arguments.product_version,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "profile": "commercial-local-voice" if arguments.with_voice else "commercial-desktop",
            "packages": packages,
            "supplemental_files": sorted(supplemental, key=lambda item: item["path"]),
        }
        (temporary / "license-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (temporary / "sbom.cdx.json").write_text(
            json.dumps(
                _sbom(
                    product_version=arguments.product_version,
                    distributions=distributions,
                    licenses=licenses,
                    roots=roots,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.rename(output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return output


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        output = run(arguments)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"Third-party license bundle written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
