"""Keep only the CLR loader matching the commercial x64 Windows target."""

from PyInstaller.utils.hooks import collect_dynamic_libs


def _is_amd64_loader(entry: tuple[str, str]) -> bool:
    source, destination = entry
    package_path = f"{destination}/{source}".replace("\\", "/").casefold()
    return "/ffi/dlls/amd64/" in f"/{package_path}"


binaries = [entry for entry in collect_dynamic_libs("clr_loader") if _is_amd64_loader(entry)]
