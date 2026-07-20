"""Collect the standard x64 PortAudio runtime without the unused ASIO build."""

from pathlib import Path

from PyInstaller.utils.hooks import get_module_file_attribute

package_root = Path(get_module_file_attribute("sounddevice")).parent
runtime_root = package_root / "_sounddevice_data" / "portaudio-binaries"
runtime = runtime_root / "libportaudio64bit.dll"
readme = runtime_root / "README.md"

if not runtime.is_file():
    raise FileNotFoundError(f"Required standard x64 PortAudio runtime is missing: {runtime}")

destination = str(runtime_root.relative_to(package_root))
binaries = [(str(runtime), destination)]
datas = [(str(readme), destination)] if readme.is_file() else []
