Unicode true
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"
!include "x64.nsh"

!ifndef APP_VERSION
  !define APP_VERSION "1.0.0"
!endif
!ifndef APP_FILE_VERSION
  !define APP_FILE_VERSION "1.0.0.0"
!endif
!ifndef SOURCE_DIR
  !define SOURCE_DIR "..\dist\Rayluno"
!endif
!ifndef OUTPUT_FILE
  !define OUTPUT_FILE "..\dist\installer\Rayluno-Setup-${APP_VERSION}-win-x64.exe"
!endif
!ifndef UNINSTALL_INCLUDE
  !error "UNINSTALL_INCLUDE must point to the generated safe-uninstall include."
!endif

!define APP_NAME "Rayluno"
!define APP_EXE "Rayluno.exe"
!define APP_REG_KEY "Software\Rayluno\Installer"
!define APP_UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Rayluno"
!define INSTALL_MARKER ".rayluno-install"
!define INSTALL_IDENTITY "rayluno-per-user-v1"

!ifdef SIGN_COMMAND
  ; SIGN_COMMAND is assembled only from a validated SignTool path, certificate
  ; thumbprint, and HTTPS timestamp URL by build-installer.ps1.
  !uninstfinalize '${SIGN_COMMAND}' = 0
  !finalize '${SIGN_COMMAND}' = 0
!endif

Var IsUpgradeUninstall
Var UninstallDeleteFailed

Name "${APP_NAME} ${APP_VERSION}"
OutFile "${OUTPUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\Rayluno"
InstallDirRegKey HKCU "${APP_REG_KEY}" "InstallDir"
RequestExecutionLevel user
BrandingText "Rayluno"
ShowInstDetails show
ShowUninstDetails show

VIProductVersion "${APP_FILE_VERSION}"
VIFileVersion "${APP_FILE_VERSION}"
VIAddVersionKey /LANG=1033 "ProductName" "${APP_NAME}"
VIAddVersionKey /LANG=1033 "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1033 "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1033 "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey /LANG=1033 "CompanyName" "Rayluno"
VIAddVersionKey /LANG=1033 "LegalCopyright" "Copyright (C) 2026 Rayluno"

!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_LANGDLL_REGISTRY_ROOT HKCU
!define MUI_LANGDLL_REGISTRY_KEY "${APP_REG_KEY}"
!define MUI_LANGDLL_REGISTRY_VALUENAME "InstallerLanguage"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Arabic"

LangString CoreSection ${LANG_ENGLISH} "Rayluno (required)"
LangString CoreSection ${LANG_ARABIC} "رايلونو (مطلوب)"
LangString DesktopSection ${LANG_ENGLISH} "Desktop shortcut"
LangString DesktopSection ${LANG_ARABIC} "اختصار سطح المكتب"
LangString CoreDescription ${LANG_ENGLISH} "Install the application and its local runtime."
LangString CoreDescription ${LANG_ARABIC} "تثبيت التطبيق وبيئة التشغيل المحلية."
LangString DesktopDescription ${LANG_ENGLISH} "Create a shortcut on the current user's desktop."
LangString DesktopDescription ${LANG_ARABIC} "إنشاء اختصار على سطح مكتب المستخدم الحالي."
LangString UnsupportedWindows ${LANG_ENGLISH} "Rayluno requires 64-bit Windows 10 or Windows 11."
LangString UnsupportedWindows ${LANG_ARABIC} "يتطلب رايلونو نظام Windows 10 أو Windows 11 بمعمارية 64 بت."

LangString MarkerWriteFailure ${LANG_ENGLISH} "The installer could not create its installation identity marker."
LangString MarkerWriteFailure ${LANG_ARABIC} "تعذر على المثبت إنشاء علامة هوية التثبيت."
LangString InvalidInstallMarker ${LANG_ENGLISH} "The installation identity marker is missing or invalid. No program files were removed."
LangString InvalidInstallMarker ${LANG_ARABIC} "علامة هوية التثبيت مفقودة أو غير صالحة. لم تُحذف أي ملفات للبرنامج."
LangString ForeignInstallDirectory ${LANG_ENGLISH} "The selected folder already contains files but is not a trusted Rayluno installation. Choose an empty folder; legacy or foreign files were not changed."
LangString ForeignInstallDirectory ${LANG_ARABIC} "يحتوي المجلد المحدد على ملفات، لكنه ليس تثبيتًا موثوقًا من رايلونو. اختر مجلدًا فارغًا؛ لم تتغير الملفات القديمة أو الخارجية."
LangString PreviousUninstallFailure ${LANG_ENGLISH} "The trusted previous version could not be removed safely. Close Rayluno, restart Windows if requested, then retry. No new files were installed."
LangString PreviousUninstallFailure ${LANG_ARABIC} "تعذرت إزالة الإصدار السابق الموثوق بأمان. أغلق رايلونو وأعد تشغيل Windows عند الطلب، ثم حاول مجددًا. لم تُثبت ملفات جديدة."
LangString UninstallDeleteFailure ${LANG_ENGLISH} "Some program files are locked or could not be removed. Close Rayluno, restart Windows if requested, and run uninstall again. The uninstall registration was preserved."
LangString UninstallDeleteFailure ${LANG_ARABIC} "بعض ملفات البرنامج مقفلة أو تعذر حذفها. أغلق رايلونو وأعد تشغيل Windows عند الطلب، ثم شغّل الإزالة مجددًا. تم الاحتفاظ بسجل الإزالة."

Section "$(CoreSection)" SEC_CORE
  SectionIn RO
  SetShellVarContext current
  SetRegView 64

  ; Never adopt or modify a legacy/foreign non-empty directory. Automatic
  ; upgrade is allowed only when the Rayluno v1 marker and safe uninstaller agree.
  IfFileExists "$INSTDIR\${INSTALL_MARKER}" existingTrustedMarker checkFreshDirectory

checkFreshDirectory:
  Call IsInstallDirectoryEmpty
  Pop $0
  StrCmp $0 "1" installDirectoryReady
  MessageBox MB_ICONSTOP|MB_OK "$(ForeignInstallDirectory)" /SD IDOK
  SetErrorLevel 2
  Abort

existingTrustedMarker:
  ClearErrors
  FileOpen $0 "$INSTDIR\${INSTALL_MARKER}" r
  IfErrors unsafeExistingDirectory
  FileRead $0 $1
  FileClose $0
  StrCmp $1 "${INSTALL_IDENTITY}" trustedUpgrade unsafeExistingDirectory

trustedUpgrade:
  IfFileExists "$INSTDIR\Uninstall.exe" 0 unsafeExistingDirectory
  ExecWait '"$INSTDIR\Uninstall.exe" /S /UPGRADE=1 _?=$INSTDIR' $0
  StrCmp $0 "0" verifyTrustedUpgrade upgradeFailed

verifyTrustedUpgrade:
  ; Upgrade mode deliberately preserves the marker and old uninstaller while
  ; deleting every old owned payload file. The new installer overwrites both.
  IfFileExists "$INSTDIR\${INSTALL_MARKER}" installDirectoryReady upgradeFailed

unsafeExistingDirectory:
  MessageBox MB_ICONSTOP|MB_OK "$(ForeignInstallDirectory)" /SD IDOK
  SetErrorLevel 2
  Abort

upgradeFailed:
  MessageBox MB_ICONSTOP|MB_OK "$(PreviousUninstallFailure)" /SD IDOK
  SetErrorLevel 2
  Abort

installDirectoryReady:
  SetOutPath "$INSTDIR"
  SetOverwrite on
  File /r "${SOURCE_DIR}\*.*"
  File /oname=NSIS_NOTICE.txt "${__FILEDIR__}\NSIS_NOTICE.txt"

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ClearErrors
  FileOpen $0 "$INSTDIR\${INSTALL_MARKER}" w
  ${If} ${Errors}
    MessageBox MB_ICONSTOP|MB_OK "$(MarkerWriteFailure)"
    Abort
  ${EndIf}
  FileWrite $0 "${INSTALL_IDENTITY}"
  FileClose $0
  ${If} ${Errors}
    Delete "$INSTDIR\${INSTALL_MARKER}"
    MessageBox MB_ICONSTOP|MB_OK "$(MarkerWriteFailure)"
    Abort
  ${EndIf}

  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Rayluno CLI.lnk" "$INSTDIR\RaylunoCLI.exe" "" "$INSTDIR\RaylunoCLI.exe" 0

  WriteRegStr HKCU "${APP_REG_KEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${APP_REG_KEY}" "InstallerLanguage" "$LANGUAGE"
  WriteRegStr HKCU "${APP_UNINSTALL_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${APP_UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${APP_UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKCU "${APP_UNINSTALL_KEY}" "Publisher" "Rayluno"
  WriteRegStr HKCU "${APP_UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${APP_UNINSTALL_KEY}" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteRegStr HKCU "${APP_UNINSTALL_KEY}" "QuietUninstallString" "$\"$INSTDIR\Uninstall.exe$\" /S"
  WriteRegDWORD HKCU "${APP_UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${APP_UNINSTALL_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKCU "${APP_UNINSTALL_KEY}" "EstimatedSize" $0
SectionEnd

Section /o "$(DesktopSection)" SEC_DESKTOP
  SetShellVarContext current
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_CORE} "$(CoreDescription)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_DESKTOP} "$(DesktopDescription)"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
  SetShellVarContext current
  SetRegView 64

  ClearErrors
  FileOpen $0 "$INSTDIR\${INSTALL_MARKER}" r
  IfErrors uninstallMarkerInvalid
  FileRead $0 $1
  FileClose $0
  StrCmp $1 "${INSTALL_IDENTITY}" uninstallMarkerValid uninstallMarkerInvalid

uninstallMarkerInvalid:
  MessageBox MB_ICONSTOP|MB_OK "$(InvalidInstallMarker)" /SD IDOK
  Abort

uninstallMarkerValid:
  ; Program files are isolated from the legacy-compatible
  ; %LOCALAPPDATA%\FutureAssistant user-data directory.
  ; This generated include deletes only files packaged by this exact release,
  ; then removes known directories non-recursively. Foreign files survive.
  !include "${UNINSTALL_INCLUDE}"

  ; A normal uninstall deletes registration only after every owned program file
  ; was removed. Trusted upgrade keeps its recoverable marker, uninstaller,
  ; shortcuts, and registry until the new installer overwrites them.
  ${If} $IsUpgradeUninstall != "1"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Rayluno CLI.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    DeleteRegKey HKCU "${APP_UNINSTALL_KEY}"
    DeleteRegKey HKCU "${APP_REG_KEY}"
  ${EndIf}
  SetErrorLevel 0
SectionEnd

Function IsInstallDirectoryEmpty
  ClearErrors
  FindFirst $0 $1 "$INSTDIR\*.*"
  IfErrors installDirectoryIsEmpty

inspectInstallDirectoryEntry:
  StrCmp $1 "" installDirectoryIsEmptyAfterFind
  StrCmp $1 "." inspectNextInstallDirectoryEntry
  StrCmp $1 ".." inspectNextInstallDirectoryEntry
  FindClose $0
  Push "0"
  Return

inspectNextInstallDirectoryEntry:
  ClearErrors
  FindNext $0 $1
  IfErrors installDirectoryIsEmptyAfterFind
  Goto inspectInstallDirectoryEntry

installDirectoryIsEmptyAfterFind:
  FindClose $0
installDirectoryIsEmpty:
  Push "1"
FunctionEnd

Function .onInit
  SetShellVarContext current
  SetRegView 64

  ${GetParameters} $R0
  ${GetOptions} "$R0" "/LANG=" $R1
  ${If} $R1 == "Arabic"
    StrCpy $LANGUAGE ${LANG_ARABIC}
  ${ElseIf} $R1 == "English"
    StrCpy $LANGUAGE ${LANG_ENGLISH}
  ${EndIf}

  IfSilent languageReady
  !insertmacro MUI_LANGDLL_DISPLAY
languageReady:

  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP|MB_OK "$(UnsupportedWindows)"
    Abort
  ${EndIf}
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK "$(UnsupportedWindows)"
    Abort
  ${EndIf}
FunctionEnd

Function un.onInit
  SetShellVarContext current
  SetRegView 64
  StrCpy $IsUpgradeUninstall "0"
  ${GetParameters} $R0
  ${GetOptions} "$R0" "/UPGRADE=" $R1
  ${If} $R1 == "1"
    StrCpy $IsUpgradeUninstall "1"
  ${EndIf}
  !insertmacro MUI_UNGETLANGUAGE
FunctionEnd
