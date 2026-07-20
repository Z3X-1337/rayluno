"""Render a PyInstaller Windows version resource from the package version."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def numeric_version(value: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[.+-][0-9A-Za-z.-]+)?", value)
    if match is None:
        raise ValueError("version must contain three numeric components")
    parts = tuple(int(item) for item in match.groups()) + (0,)
    if any(item > 65535 for item in parts):
        raise ValueError("Windows version components must not exceed 65535")
    return parts


def render(
    *,
    version: str,
    description: str,
    internal_name: str,
    original_filename: str,
) -> str:
    parts = numeric_version(version)
    four_part = ".".join(str(item) for item in parts)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={parts!r},
    prodvers={parts!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName', u'Rayluno'),
          StringStruct(u'FileDescription', {description!r}),
          StringStruct(u'FileVersion', u'{four_part}'),
          StringStruct(u'InternalName', {internal_name!r}),
          StringStruct(u'LegalCopyright', u'Copyright (C) 2026 Rayluno'),
          StringStruct(u'OriginalFilename', {original_filename!r}),
          StringStruct(u'ProductName', u'Rayluno'),
          StringStruct(u'ProductVersion', u'{four_part}')
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--internal-name", required=True)
    parser.add_argument("--original-filename", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    content = render(
        version=args.version,
        description=args.description,
        internal_name=args.internal_name,
        original_filename=args.original_filename,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
