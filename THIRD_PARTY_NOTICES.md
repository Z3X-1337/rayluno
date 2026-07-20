# Third-party inventory / جرد مكونات الطرف الثالث

This is the reviewed engineering inventory for the **Rayluno Assistant 1.0.0 Windows
launch candidate**. Every clean release now generates `THIRD_PARTY_LICENSES/license-manifest.json`,
a CycloneDX SBOM, copied package license files, supplemental upstream notices, and a
deterministic per-file model hash manifest. This engineering inventory is not legal
advice; merchant policies and the final distribution should still receive legal review.

هذه قائمة هندسية لمرشح Rayluno Assistant 1.0.0. ينشئ كل بناء نظيف الآن SBOM بصيغة CycloneDX
وبيان تراخيص دقيقًا ونسخًا من نصوص التراخيص وإشعارات المصادر وبصمات كل ملفات نماذج
الصوت. هذه مراجعة هندسية وليست استشارة قانونية، لذا يلزم تدقيق قانوني قبل البيع العام.

## Components in the current full Windows voice bundle

| Component | Version/artifact | Purpose | License/status |
|---|---|---|---|
| CPython runtime | 3.11 | Packaged application runtime | PSF License; include Python notices |
| PyInstaller bootloader | 6.21.0 | Produces the two Windows executables | GPL-2.0-or-later with PyInstaller's exception for distributing non-free applications; include its notices |
| pywebview | 6.2.1 | Native desktop UI container | BSD-3-Clause |
| pythonnet / clr-loader | 3.1.0 / 0.3.1 | .NET bridge used by the Windows UI | Review and include their exact MIT notices from the release environment |
| cryptography | 49.0.0 | Ed25519 license and update verification | Apache-2.0 OR BSD-3-Clause |
| NumPy | 2.4.6 | Audio buffers used by local speech | Compound distribution: BSD-3-Clause plus bundled 0BSD/MIT/Zlib/CC0 notices; copy the wheel's license directory |
| pywhispercpp | 1.3.1 | In-memory `whisper.cpp` binding | MIT |
| whisper.cpp | bundled through pywhispercpp | Local speech-to-text runtime | MIT; record the exact upstream revision carried by the wheel before public release |
| Whisper model weights | `ggml-base.bin`, 147,951,465 bytes | Multilingual local speech-to-text | MIT per the Whisper project; SHA-256 `60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe` |
| sounddevice | 0.5.5 | Microphone PCM capture | MIT |
| PortAudio | standard x64 binary supplied with sounddevice on Windows | Audio I/O runtime | PortAudio license (MIT-style); the unused ASIO-enabled binary is deliberately excluded |
| Vosk API | 0.3.45 | Offline Arabic/English wake-phrase recognition | Apache-2.0 upstream; the installed wheel metadata says `UNKNOWN`, so retain the upstream license text explicitly |
| Arabic Vosk model | `vosk-model-ar-mgb2-0.4`, 698,195,675 bytes in this bundle | Arabic wake phrase | Apache-2.0 as listed in the official Vosk model index |
| English Vosk model | `vosk-model-small-en-us-0.15`, 70,898,967 bytes in this bundle | English wake phrase | Apache-2.0 as listed in the official Vosk model index |
| pywin32 | 312 | Windows integration | PSF License |
| Python/WinRT projections | 3.2.1 (`winrt-runtime`, Foundation, Collections, SpeechSynthesis, Storage.Streams) | Invoke installed Windows speech voices | MIT |
| bottle / proxy_tools | 0.13.4 / 0.1.0 | pywebview transitive runtime | MIT |
| NSIS | 3.12 | Builds the per-user installer | zlib/libpng license; see `packaging/NSIS_NOTICE.txt` |

The generated manifest also records exact versions and copied license files for the
runtime closure, including cffi, pycparser, Requests, certifi, charset-normalizer,
idna, urllib3, srt, tqdm, websockets, packaging, platformdirs, typing-extensions,
PyInstaller support packages, and the Windows bridge dependencies. The generated
`voice-model-files.sha256` covers every file under the two Vosk models and Whisper.

## Optional or user-supplied components

| Component/service | Current use | Distribution decision |
|---|---|---|
| Ollama | Optional local model server | Not bundled and never installed silently; user opt-in. Review the exact Ollama and model licenses separately. |
| `faster-whisper` / CTranslate2 | Optional development STT backend for modern CPUs | Not included in the supported full 1.0.0 voice bundle. Review its wheel and model card if distributed later. |
| YouTube Data API | Optional BYOK lookup of the first matching video | No Google client library is bundled. Use is subject to Google's API/service terms. The key remains user supplied. |
| Microsoft Edge WebView2 and Windows speech voices | System runtimes invoked by the app | Do not redistribute voice files. Follow Microsoft terms for any WebView2 runtime redistributed later. |

## Explicit exclusions and media policy

- `openWakeWord` bundled models are **not included**. Their CC BY-NC-SA 4.0 terms
  are unsuitable for a paid bundle without a separate commercial permission review.
- `llama.cpp`, Playwright, and pywinauto are roadmap candidates, not claims about the
  current 1.0.0 bundle.
- Media actions open content in the service's official player. The assistant does not
  download, extract, re-stream, or bypass advertising for YouTube/Spotify content.
- Rayluno Assistant does not include or claim rights to Marvel, Iron Man, or JARVIS
  names, characters, voices, sounds, or interface artwork.

The build fails if a release dependency has neither a copied license file nor an
explicit reviewed supplemental notice. Rebuild the Windows bundle after changing this
inventory so the installed notice, SBOM, and exact packaged versions remain aligned.
