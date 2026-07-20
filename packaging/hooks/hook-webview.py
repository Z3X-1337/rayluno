"""PyInstaller hook for pywebview's dynamic Windows backend."""

from pathlib import Path

from PyInstaller.compat import is_win
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("webview", subdir="js")
binaries = []
hiddenimports = []


def _is_x64_windows_payload(entry: tuple[str, str]) -> bool:
    source, destination = entry
    source_name = Path(source).name.casefold()
    package_path = f"{destination}/{source_name}".replace("\\", "/").casefold()
    if source_name in {"pywebview-android.jar", "webbrowserinterop.x86.dll"}:
        return False
    return not any(
        component in package_path for component in ("/runtimes/win-arm64/", "/runtimes/win-x86/")
    )


if is_win:
    # This product deliberately ships only an x64 Windows payload. Keeping the
    # Android jar or x86/ARM64 native loaders can trigger Store architecture
    # validation warnings and adds code that can never execute in this build.
    datas += [
        entry
        for entry in collect_data_files("webview", subdir="lib")
        if _is_x64_windows_payload(entry)
    ]
    binaries += [
        entry for entry in collect_dynamic_libs("webview") if _is_x64_windows_payload(entry)
    ]
    hiddenimports += [
        "webview.platforms.edgechromium",
        "webview.platforms.mshtml",
        "webview.platforms.winforms",
    ]
