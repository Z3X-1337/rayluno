# Windows installer

The zero-cost commercial installer uses NSIS 3, whose official license permits
commercial use. It consumes the one-folder PyInstaller output at
`dist/Rayluno`.

The installation is per-user and never requests administrator privileges.
Program files go to `%LOCALAPPDATA%\Programs\Rayluno`. Runtime data intentionally
continues to use the legacy technical path `%LOCALAPPDATA%\FutureAssistant` so
existing settings and downloaded voice models remain compatible. Uninstall never
deletes that data directory. The uninstaller also requires an installation
identity marker and deletes only the exact release files listed by the build.
Known directories are removed non-recursively, so an unrelated file placed in
the program directory is preserved and keeps that directory in place.

The Rayluno v1 marker (`.rayluno-install` containing `rayluno-per-user-v1`) is
also the upgrade trust boundary. An installer may run the previous safe Rayluno
uninstaller only when that exact marker and `Uninstall.exe` are both present. A
legacy FutureAssistant installation is a separate, untrusted product install:
Rayluno does not uninstall, overwrite, or claim to upgrade it. A damaged or
foreign non-empty Rayluno directory is likewise rejected without modification.
During a trusted Rayluno upgrade the old uninstaller must delete every file
owned by its release before the new payload is written. Foreign files survive.

Only an x64 `commercial-local-voice` release whose version matches the source
package can be packaged. Before NSIS starts, the build script runs
`smoke-release.ps1 -ExpectVoice`. A missing or mismatched `release-build.json`
is a hard failure.

Build the existing release:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-installer.ps1
```

Build PyInstaller first, include voice dependencies, then compile and smoke-test
the Arabic silent install/uninstall path:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-installer.ps1 -BuildRelease -WithVoice -TestInstall
```

`-BuildRelease` always selects the full local-voice profile; `-WithVoice`
remains accepted for command compatibility. `-TestInstall` compares SHA-256 for
every installed payload file, runs the installed CLI voice self-test, and
proves that both user data and a foreign file inside the installation directory
survive uninstall.

NSIS compiles into a unique staging directory from a true byte-for-byte copy of
the release, never from the live `dist/Rayluno` directory. The complete
`release-files.sha256` inventory is checked on that private snapshot before and
after `makensis` reads it. The installer and its manifest are promoted together
only after all requested checks pass; a failed copy, compile, integrity check,
signature gate, or install test leaves the previously published pair intact.
The old `-SkipCompile` mode is intentionally rejected because it could associate
a fresh manifest with a stale installer.

The Windows application version must be exactly three numeric components, such
as `1.2.3`; NSIS receives the corresponding four-part file version `1.2.3.0`.

The output is `dist/installer/Rayluno-Setup-<version>-win-x64.exe` plus
`installer-manifest.json`, which records its byte size, SHA-256 digest, builder,
real Authenticode status, payload signature statuses, and the SHA-256 of
`release-build.json`. If the release contains `release-files.sha256`, its digest
is recorded as well. An unsigned build is explicitly classified as
`unsigned-release-candidate` and is not a public-distribution artifact.

For an approved production-signing candidate, pass `-RequireAuthenticode` with
all four constrained signing inputs: the exact `signtool.exe` path, the
40-character certificate thumbprint, an absolute HTTPS RFC 3161 timestamp URL,
and the exact publisher certificate subject. Example placeholders:

```powershell
.\scripts\build-installer.ps1 `
  -RequireAuthenticode `
  -SignTool "C:\Program Files (x86)\Windows Kits\10\bin\<sdk>\x64\signtool.exe" `
  -SigningCertificateThumbprint "<40_HEX_CHARACTERS>" `
  -TimestampUrl "https://<approved-rfc3161-service>" `
  -ExpectedPublisher "CN=<exact publisher subject>"
```

The release EXEs must already be signed by that same certificate and covered by
`release-files.sha256`. NSIS then uses the constrained command to sign its
embedded uninstaller and staged installer. The build verifies trust status,
certificate thumbprint, exact publisher subject, and a timestamp before
promotion. No private key, password, or arbitrary shell command is accepted or
printed. Without this approved configuration, output remains an unsigned
release candidate.

The optional `future_assistant.iss` definition is retained only for teams that
purchase the appropriate Inno Setup commercial license. Current free Inno Setup
compilers identify themselves as non-commercial, so that path is not used by
the zero-cost product build.

The current local output is not code-signed. Windows SmartScreen can warn users
about new or uncommon unsigned installers. Never disable or bypass SmartScreen
in the product or in customer instructions.

Uninstall uses `Delete /REBOOTOK` for owned files and verifies that each path is
actually gone. If a file is locked, uninstall returns a failure, keeps its v1
marker and uninstall registry entry, and asks the user to close the application
or restart before retrying. Registry/shortcut removal happens only after the
owned payload deletion succeeds. The installer uses new Rayluno program,
registry, uninstall, and shortcut identities, so it can safely exist alongside
an older FutureAssistant installation.
