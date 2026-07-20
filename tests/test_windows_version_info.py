from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).parents[1] / "tools" / "render_windows_version_info.py"
SPEC = importlib.util.spec_from_file_location("render_windows_version_info", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_version_resource_is_derived_from_package_version() -> None:
    rendered = MODULE.render(
        version="1.2.3",
        description="Desktop",
        internal_name="Assistant",
        original_filename="Assistant.exe",
    )

    assert "filevers=(1, 2, 3, 0)" in rendered
    assert "StringStruct(u'FileVersion', u'1.2.3.0')" in rendered
    assert "StringStruct(u'ProductVersion', u'1.2.3.0')" in rendered
    assert "Assistant.exe" in rendered
    assert "StringStruct(u'CompanyName', u'Rayluno')" in rendered
    assert "StringStruct(u'ProductName', u'Rayluno')" in rendered


@pytest.mark.parametrize("value", ["1.2", "1.2.x", "70000.0.0"])
def test_version_resource_rejects_invalid_windows_versions(value: str) -> None:
    with pytest.raises(ValueError):
        MODULE.numeric_version(value)
