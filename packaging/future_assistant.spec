# -*- mode: python ; coding: utf-8 -*-

import importlib.util
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


packaging_dir = Path(SPECPATH).resolve()
project_root = packaging_dir.parent
source_dir = project_root / "src"
ui_dir = source_dir / "future_assistant" / "ui"
hook_dir = packaging_dir / "hooks"
assets_dir = source_dir / "future_assistant" / "assets"


def require_file(path, label):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Required {label} file is missing: {path}")
    return path


def require_directory(path, label):
    path = Path(path).expanduser().resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"Required {label} directory is missing: {path}")
    return path


gui_version_info = require_file(
    os.environ.get(
        "FUTURE_ASSISTANT_BUILD_GUI_VERSION_INFO",
        packaging_dir / "version_info_gui.txt",
    ),
    "GUI version resource",
)
cli_version_info = require_file(
    os.environ.get(
        "FUTURE_ASSISTANT_BUILD_CLI_VERSION_INFO",
        packaging_dir / "version_info_cli.txt",
    ),
    "CLI version resource",
)


def collect_required_package(package_name):
    if importlib.util.find_spec(package_name) is None:
        raise ModuleNotFoundError(
            f"Required release dependency is not installed: {package_name}"
        )
    return collect_all(package_name)

datas = [
    (str(ui_dir / filename), "future_assistant/ui")
    for filename in ("app.js", "index.html", "styles.css")
]
for public_key_name in ("license-public.pem", "updates-public.pem"):
    public_key = require_file(assets_dir / public_key_name, public_key_name)
    datas.append((str(public_key), "future_assistant/assets"))

binaries = []
hiddenimports = [
    "clr",
    "cryptography.hazmat.primitives.serialization",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "pythonnet",
    "webview.platforms.edgechromium",
    "webview.platforms.mshtml",
    "webview.platforms.winforms",
]

# Licensing and updates are part of every commercial desktop build.  Collecting
# cryptography explicitly also preserves its native Rust extension when the
# imports are reached only through a lazy product boundary.
package_datas, package_binaries, package_hiddenimports = collect_required_package(
    "cryptography"
)
datas += package_datas
binaries += package_binaries
hiddenimports += package_hiddenimports

with_voice = os.environ.get("FUTURE_ASSISTANT_BUILD_WITH_VOICE", "0") == "1"
excludes = [
    "webview.platforms.android",
    "webview.platforms.cef",
    "webview.platforms.cocoa",
    "webview.platforms.gtk",
    "webview.platforms.qt",
]

if with_voice:
    # These packages load native components or submodules dynamically. Missing
    # dependencies are release blockers instead of silently producing a package
    # whose voice controls fail on the customer's machine.
    for package_name in ("pywhispercpp", "vosk"):
        package_datas, package_binaries, package_hiddenimports = (
            collect_required_package(package_name)
        )
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_hiddenimports

    # collect_all() discovers upstream example/CLI modules that are not part of
    # the assistant runtime. Keep them out of the commercial payload.
    unsupported_tool_prefixes = ("pywhispercpp.examples", "vosk.transcriber")
    unsupported_data_destinations = ("pywhispercpp/examples", "vosk/transcriber")
    hiddenimports = [
        module_name
        for module_name in hiddenimports
        if not module_name.startswith(unsupported_tool_prefixes)
    ]
    datas = [
        (source, destination)
        for source, destination in datas
        if not destination.replace("\\", "/").startswith(
            unsupported_data_destinations
        )
    ]
    excludes += ["pywhispercpp.examples", "vosk.transcriber"]

    # Only the SAPI client is used. collect_all("win32com") would package
    # unrelated demos, tests, server modules, headers, and COM extensions.
    hiddenimports += collect_submodules("win32com.client")

    required_modules = [
        "_pywhispercpp",
        "sounddevice",
        "pythoncom",
        "pywintypes",
        "win32com.client",
        "winrt.runtime",
        "winrt.system",
        "winrt.windows.foundation",
        "winrt.windows.foundation.collections",
        "winrt.windows.media.speechsynthesis",
        "winrt.windows.storage.streams",
        "winrt._winrt",
        "winrt._winrt_windows_foundation",
        "winrt._winrt_windows_foundation_collections",
        "winrt._winrt_windows_media_speechsynthesis",
        "winrt._winrt_windows_storage_streams",
    ]
    for module_name in required_modules:
        if importlib.util.find_spec(module_name) is None:
            raise ModuleNotFoundError(
                f"Required voice release dependency is not installed: {module_name}"
            )
    hiddenimports += required_modules

    # winrt is a namespace package. Explicitly retain its native projections and
    # C++ runtime instead of relying on package-directory discovery semantics.
    winrt_runtime_spec = importlib.util.find_spec("winrt.runtime")
    winrt_root = Path(winrt_runtime_spec.origin).resolve().parents[1]
    for pattern in ("*.pyd", "*.dll"):
        for winrt_binary in sorted(winrt_root.glob(pattern)):
            binaries.append((str(winrt_binary), "winrt"))

    model_inputs = (
        (
            "FUTURE_ASSISTANT_BUILD_ARABIC_VOSK_MODEL",
            "Arabic Vosk model",
            "models/vosk-model-ar-mgb2-0.4",
            True,
        ),
        (
            "FUTURE_ASSISTANT_BUILD_ENGLISH_VOSK_MODEL",
            "English Vosk model",
            "models/vosk-model-small-en-us-0.15",
            True,
        ),
        (
            "FUTURE_ASSISTANT_BUILD_WHISPER_MODEL",
            "Whisper ggml-base model",
            "models/whisper",
            False,
        ),
    )
    for environment_name, label, destination, is_directory in model_inputs:
        configured_path = os.environ.get(environment_name, "").strip()
        if not configured_path:
            raise RuntimeError(
                f"{environment_name} must point to the required {label} before building"
            )
        source = (
            require_directory(configured_path, label)
            if is_directory
            else require_file(configured_path, label)
        )
        datas.append((str(source), destination))

    # The supported full bundle deliberately uses whisper.cpp on older x64 CPUs.
    # Do not accidentally pull the much larger faster-whisper stack from a dirty
    # build environment.
    excludes += ["ctranslate2", "faster_whisper", "huggingface_hub", "tokenizers"]
else:
    # Keep the desktop-only package small even when the build venv has voice extras.
    excludes += [
        "ctranslate2",
        "faster_whisper",
        "huggingface_hub",
        "numpy",
        "pythoncom",
        "pywhispercpp",
        "pywintypes",
        "sounddevice",
        "tokenizers",
        "vosk",
        "win32com",
    ]

a = Analysis(
    [str(packaging_dir / "windows_launcher.py")],
    pathex=[str(source_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(hook_dir)],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

desktop_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Rayluno",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory="_internal",
    version=str(gui_version_info),
    manifest=str(packaging_dir / "future_assistant.manifest"),
)

console_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RaylunoCLI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory="_internal",
    version=str(cli_version_info),
    manifest=str(packaging_dir / "future_assistant.manifest"),
)

coll = COLLECT(
    desktop_exe,
    console_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Rayluno",
)
