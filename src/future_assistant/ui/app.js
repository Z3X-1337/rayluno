const LANGUAGE_STORAGE_KEY = "future-assistant.ui-language";
const SUPPORTED_LANGUAGE_PREFERENCES = new Set(["ar", "en", "auto"]);

const translations = Object.freeze({
  ar: Object.freeze({
    documentTitle: "Rayluno — مساعدك الشخصي",
    assistantName: "رايلونو",
    brandSubtitle: "مساعد ذكي محلي بالعربية والإنجليزية",
    privacyBadge: "محلي وخاص",
    languagePickerLabel: "لغة الواجهة",
    languageArabicShort: "AR",
    languageArabicLabel: "العربية",
    languageAutoShort: "تلقائي",
    languageAutoLabel: "تلقائي",
    languageAutoHint: "اتّباع لغة النظام",
    languageEnglishShort: "EN",
    languageEnglishLabel: "الإنجليزية",
    settingsLabel: "الإعدادات",
    recentActivityLabel: "آخر النشاطات",
    historyEyebrow: "السجل",
    recentActivityTitle: "آخر النشاطات",
    clearHistory: "مسح",
    emptyHistoryTitle: "لا توجد أوامر بعد",
    emptyHistoryDescription: "ستظهر العمليات الآمنة هنا",
    localEngineTitle: "المحرك المحلي",
    engineChecking: "جارٍ التحقق…",
    assistantControlsLabel: "التحكم بالمساعد",
    modeIdle: "وضع الاستعداد",
    modeListening: "أستمع إليك",
    modeThinking: "جارٍ الفهم والتنفيذ",
    modeError: "تعذّر التنفيذ",
    orbIdle: "اضغط للتحدث",
    orbListening: "تحدث الآن",
    orbThinking: "لحظة واحدة",
    orbError: "حاول مجددًا",
    startListeningLabel: "بدء الاستماع",
    stopListeningLabel: "إيقاف الاستماع",
    readyForCommand: "جاهز لأمرك",
    commandExample: "جرّب: «افتح يوتيوب وابحث عن موسيقى هادئة»",
    commandInputLabel: "اكتب أمرًا",
    commandPlaceholder: "أو اكتب ما تريد تنفيذه…",
    sendCommandLabel: "إرسال الأمر",
    quickActionsLabel: "أوامر سريعة",
    quickYoutubeLabel: "يوتيوب",
    quickYoutubeCommand: "افتح يوتيوب",
    quickCalculatorLabel: "الحاسبة",
    quickCalculatorCommand: "افتح الحاسبة",
    quickTimeLabel: "الوقت",
    quickTimeCommand: "كم الساعة الآن",
    quickSearchLabel: "بحث سريع",
    quickSearchCommand: "ابحث في جوجل عن أخبار التقنية",
    privacyNotice: "لا يُرسل الميكروفون أو سجل الأوامر إلى خادم خارجي",
    versionPreview: "Rayluno 1.0",
    versionLabel: "الإصدار {version}",
    enginePreview: "وضع معاينة الواجهة",
    engineUnavailable: "غير متاح",
    engineLocalReady: "الأوامر المحلية جاهزة",
    engineListeningActive: "الاستماع المحلي نشط",
    historyDefaultCommand: "أمر",
    historySucceeded: "تم التنفيذ",
    historyFailed: "تعذّر التنفيذ",
    requestLabel: "طلبك",
    doneLabel: "تم",
    alertLabel: "تنبيه",
    noEngineResponse: "لم يصل رد من المحرك",
    requestProcessed: "تمت معالجة الأمر",
    executeFailed: "تعذّر تنفيذ الأمر",
    previewCommandError: "الواجهة تعمل في وضع المعاينة؛ شغّل تطبيق سطح المكتب لتنفيذ الأوامر.",
    voicePreviewError: "يتصل زر الصوت بالميكروفون عند تشغيل تطبيق سطح المكتب.",
    settingsEyebrow: "إعداد محلي",
    settingsTitle: "إعدادات المساعد",
    closeSettingsLabel: "إغلاق الإعدادات",
    welcomeTitle: "مرحبًا بك في رايلونو",
    welcomeDescription: "اختر تفضيلاتك؛ تبقى هذه البيانات على جهازك.",
    identitySection: "الهوية واللغة",
    identityDescription: "يمكن تغيير الاسم وعبارات الاستيقاظ في أي وقت.",
    assistantNameField: "اسم المساعد",
    productLanguageField: "لغة التشغيل",
    languageAutoOption: "تلقائي — العربية والإنجليزية",
    languageArabicOption: "العربية",
    languageEnglishOption: "English",
    arabicWakeField: "عبارة الاستيقاظ العربية",
    englishWakeField: "عبارة الاستيقاظ الإنجليزية",
    ttsVoiceField: "الصوت المفضّل",
    ttsAutomaticOption: "تلقائي حسب لغة الرد",
    voiceNaayfOption: "Microsoft Naayf",
    voiceHodaOption: "Microsoft Hoda",
    voiceMarkOption: "Microsoft Mark",
    voiceZiraOption: "Microsoft Zira",
    advancedSettings: "إعدادات المحركات المتقدمة",
    speechEngineField: "محرك فهم الصوت",
    whisperCppOption: "whisper.cpp",
    fasterWhisperOption: "faster-whisper",
    speechModelField: "نموذج فهم الصوت",
    aiModelField: "نموذج الذكاء المحلي",
    licenseSection: "الترخيص",
    licenseFreeStatus: "Free — المزايا الأساسية نشطة",
    licenseProStatus: "Pro — الترخيص نشط",
    licenseExpiredStatus: "انتهى ترخيص Pro — عادت مزايا Free",
    licenseInvalidStatus: "رمز غير صالح — وضع Free آمن",
    licenseUnavailableStatus: "خدمة الترخيص غير متاحة — وضع Free",
    licenseTokenField: "مفتاح الشراء أو رمز التفعيل اليدوي",
    licenseTokenPlaceholder: "الصق مفتاح الشراء الذي وصلك في الإيصال…",
    buyPro: "شراء Pro",
    activateLicense: "تفعيل Pro",
    refreshLicense: "تجديد Pro",
    removeLicense: "إزالة Pro",
    licenseUnavailable: "التحقق من الترخيص غير متاح في هذه النسخة.",
    licenseInvalid: "رمز الترخيص غير صالح.",
    licenseVerificationFailed: "تعذّر التحقق من رمز الترخيص.",
    licenseActivated: "تم تفعيل الترخيص بنجاح.",
    licenseRemoved: "تمت إزالة الترخيص المدفوع.",
    noPaidLicense: "لا يوجد ترخيص مدفوع.",
    licenseRemovalFailed: "تعذّر إزالة الترخيص.",
    purchaseOpened: "فُتحت صفحة Pro في المتصفح.",
    purchaseOpenFailed: "تعذّر فتح صفحة Pro في المتصفح.",
    reportAiResponse: "إبلاغ عن هذا الرد",
    reportOpened: "نُسخ الرد وفُتح نموذج الإبلاغ. راجع المحتوى قبل إرساله.",
    reportOpenFailed: "تعذّر فتح نموذج الإبلاغ.",
    voiceProRequired: "يتطلب الصوت المحلي الكامل ترخيص Pro نشطًا.",
    enterLicenseToken: "الصق مفتاح الشراء أو رمز التفعيل أولًا.",
    activationNotConfigured: "خدمة التفعيل عبر الإنترنت غير مهيأة بعد.",
    invalidPurchaseKey: "مفتاح الشراء غير صالح.",
    purchaseKeyRejected: "مفتاح الشراء غير صالح أو لا يخص هذا المنتج.",
    purchaseKeyExpired: "انتهت صلاحية مفتاح الشراء أو تم تعطيله.",
    activationSecureFailed: "تعذّر الاتصال بخدمة التفعيل بأمان.",
    activationReceivedInvalid: "تعذّر التحقق من الترخيص المستلم.",
    activationSuccess: "تم تفعيل Pro وربطه بهذا التثبيت بنجاح.",
    refreshNotConfigured: "خدمة تجديد الترخيص غير مهيأة بعد.",
    noActivationData: "لا توجد بيانات تفعيل محفوظة للتجديد.",
    refreshedLicenseExpired: "انتهت صلاحية الترخيص أو تم تعطيله.",
    refreshCurrentFailed: "تعذّر تجديد الترخيص من بيانات التفعيل الحالية.",
    refreshSecureFailed: "تعذّر الاتصال بخدمة التجديد بأمان.",
    refreshedLicenseInvalid: "تعذّر التحقق من الترخيص المجدد.",
    refreshSuccess: "تم تجديد ترخيص Pro والتحقق منه.",
    updateSection: "التحديثات الآمنة",
    updateNotChecked: "لم يتم الفحص بعد",
    updateUnavailableStatus: "قناة التحديث غير مهيأة",
    updateManagedByStoreStatus: "يدير Microsoft Store التحديثات تلقائيًا",
    updateCurrentStatus: "لديك أحدث إصدار",
    updateAvailableStatus: "يتوفر الإصدار {version}",
    updateStagedStatus: "تم تنزيل الإصدار {version} والتحقق منه",
    updateDescription: "لا يُقبل أي تحديث قبل التحقق من توقيعه وحجمه وبصمته.",
    checkUpdates: "فحص التحديثات",
    downloadUpdate: "تنزيل والتحقق",
    updateChannelMissing: "قناة التحديث غير مهيأة بعد.",
    updateManagedByStoreMessage: "يدير Microsoft Store التحديثات تلقائيًا.",
    updateCheckFailed: "تعذّر التحقق من التحديث بأمان.",
    updateStageFailed: "تعذّر تجهيز التحديث.",
    updateAvailableMessage: "يتوفر تحديث جديد.",
    updateCurrentMessage: "لديك أحدث إصدار.",
    updateStagedMessage: "تم تنزيل التحديث والتحقق منه. لن يُشغّل دون موافقتك.",
    restartSettingsNote: "تُطبّق تغييرات الصوت والذكاء بعد إعادة تشغيل التطبيق.",
    resetSettings: "استعادة الافتراضي",
    cancelSettings: "إلغاء",
    saveSettings: "حفظ الإعدادات",
    savingSettings: "جارٍ الحفظ…",
    settingsInvalid: "إعدادات غير صالحة.",
    settingsSaved: "حُفظت الإعدادات. أعد تشغيل التطبيق لتطبيق إعدادات الصوت والذكاء.",
    settingsReset: "أُعيدت الإعدادات الافتراضية.",
    settingsPreviewSaved: "تم تحديث المعاينة؛ يتطلب الحفظ تشغيل تطبيق سطح المكتب.",
    settingsLoadFailed: "تعذّر تحميل الإعدادات المحلية.",
    resetSettingsConfirm: "هل تريد استعادة جميع إعدادات المساعد الافتراضية؟",
    heardYouLabel: "سمعتك تقول",
    voiceConnectionFailed: "تعذّر الاتصال بالمحرك المحلي.",
    languageChanged: "لغة الواجهة: {language}.",
    listeningStopped: "توقف الاستماع",
    waitingWakeWord: "بانتظار كلمة الاستيقاظ",
    speakNow: "تحدث الآن",
    awakenedLabel: "تم الاستيقاظ",
    listeningPrompt: "أنا أستمع إليك…",
    resultLabel: "النتيجة",
    voiceFailedLabel: "تعذر تشغيل الصوت",
    enterCommandFirst: "اكتب أمرًا أولًا.",
    commandTooLong: "الأمر أطول من الحد المسموح.",
    voiceNotConfigured: "طبقة الصوت غير مهيأة بعد. شغّل فحص الجاهزية لمعرفة المطلوب.",
    microphoneStopped: "تم إيقاف الميكروفون.",
    listeningAlreadyActive: "الاستماع نشط بالفعل.",
    voiceListeningSay: "الاستماع نشط. قل: {phrase}",
  }),
  en: Object.freeze({
    documentTitle: "Rayluno — Your personal assistant",
    assistantName: "Rayluno",
    brandSubtitle: "Local intelligence in Arabic and English",
    privacyBadge: "Local & private",
    languagePickerLabel: "Interface language",
    languageArabicShort: "AR",
    languageArabicLabel: "Arabic",
    languageAutoShort: "Auto",
    languageAutoLabel: "Automatic",
    languageAutoHint: "Follow the system language",
    languageEnglishShort: "EN",
    languageEnglishLabel: "English",
    settingsLabel: "Settings",
    recentActivityLabel: "Recent activity",
    historyEyebrow: "History",
    recentActivityTitle: "Recent activity",
    clearHistory: "Clear",
    emptyHistoryTitle: "No commands yet",
    emptyHistoryDescription: "Your safe actions will appear here",
    localEngineTitle: "Local engine",
    engineChecking: "Checking…",
    assistantControlsLabel: "Assistant controls",
    modeIdle: "Standby mode",
    modeListening: "I'm listening",
    modeThinking: "Understanding and executing",
    modeError: "Execution failed",
    orbIdle: "Press to speak",
    orbListening: "Speak now",
    orbThinking: "One moment",
    orbError: "Try again",
    startListeningLabel: "Start listening",
    stopListeningLabel: "Stop listening",
    readyForCommand: "Ready for your command",
    commandExample: "Try: “Open YouTube and search for relaxing music”",
    commandInputLabel: "Type a command",
    commandPlaceholder: "Or type what you want me to do…",
    sendCommandLabel: "Send command",
    quickActionsLabel: "Quick commands",
    quickYoutubeLabel: "YouTube",
    quickYoutubeCommand: "Open YouTube",
    quickCalculatorLabel: "Calculator",
    quickCalculatorCommand: "Open Calculator",
    quickTimeLabel: "Time",
    quickTimeCommand: "What time is it",
    quickSearchLabel: "Quick search",
    quickSearchCommand: "Search Google for technology news",
    privacyNotice: "Microphone audio and command history are never sent to an external server",
    versionPreview: "Rayluno 1.0",
    versionLabel: "Version {version}",
    enginePreview: "Interface preview mode",
    engineUnavailable: "Unavailable",
    engineLocalReady: "Local commands are ready",
    engineListeningActive: "Local listening is active",
    historyDefaultCommand: "Command",
    historySucceeded: "Completed",
    historyFailed: "Execution failed",
    requestLabel: "Your request",
    doneLabel: "Done",
    alertLabel: "Notice",
    noEngineResponse: "The engine did not respond",
    requestProcessed: "The command was processed",
    executeFailed: "The command could not be completed",
    previewCommandError: "The interface is in preview mode. Start the desktop app to execute commands.",
    voicePreviewError: "The voice button connects to your microphone when the desktop app is running.",
    settingsEyebrow: "Local setup",
    settingsTitle: "Assistant settings",
    closeSettingsLabel: "Close settings",
    welcomeTitle: "Welcome to Rayluno",
    welcomeDescription: "Choose your preferences; this data stays on your device.",
    identitySection: "Identity and language",
    identityDescription: "You can change the name and wake phrases at any time.",
    assistantNameField: "Assistant name",
    productLanguageField: "Operating language",
    languageAutoOption: "Automatic — Arabic and English",
    languageArabicOption: "Arabic",
    languageEnglishOption: "English",
    arabicWakeField: "Arabic wake phrase",
    englishWakeField: "English wake phrase",
    ttsVoiceField: "Preferred voice",
    ttsAutomaticOption: "Automatic based on response language",
    voiceNaayfOption: "Microsoft Naayf",
    voiceHodaOption: "Microsoft Hoda",
    voiceMarkOption: "Microsoft Mark",
    voiceZiraOption: "Microsoft Zira",
    advancedSettings: "Advanced engine settings",
    speechEngineField: "Speech recognition engine",
    whisperCppOption: "whisper.cpp",
    fasterWhisperOption: "faster-whisper",
    speechModelField: "Speech recognition model",
    aiModelField: "Local AI model",
    licenseSection: "License",
    licenseFreeStatus: "Free — core features active",
    licenseProStatus: "Pro — license active",
    licenseExpiredStatus: "Pro expired — Free features restored",
    licenseInvalidStatus: "Invalid token — safe Free mode",
    licenseUnavailableStatus: "Licensing unavailable — Free mode",
    licenseTokenField: "Purchase key or manual activation token",
    licenseTokenPlaceholder: "Paste the purchase key from your receipt…",
    buyPro: "Buy Pro",
    activateLicense: "Activate Pro",
    refreshLicense: "Renew Pro",
    removeLicense: "Remove Pro",
    licenseUnavailable: "License verification is unavailable in this build.",
    licenseInvalid: "The license token is invalid.",
    licenseVerificationFailed: "The license token could not be verified.",
    licenseActivated: "The license was activated successfully.",
    licenseRemoved: "The paid license was removed.",
    noPaidLicense: "No paid license is installed.",
    licenseRemovalFailed: "The license could not be removed.",
    purchaseOpened: "The Pro page opened in your browser.",
    purchaseOpenFailed: "The Pro page could not be opened in your browser.",
    reportAiResponse: "Report this response",
    reportOpened: "The response was copied and the report form opened. Review it before sending.",
    reportOpenFailed: "The report form could not be opened.",
    voiceProRequired: "Full local voice requires an active Pro license.",
    enterLicenseToken: "Paste a purchase key or activation token first.",
    activationNotConfigured: "Online activation is not configured yet.",
    invalidPurchaseKey: "The purchase key is invalid.",
    purchaseKeyRejected: "The purchase key is invalid or belongs to another product.",
    purchaseKeyExpired: "The purchase key has expired or was disabled.",
    activationSecureFailed: "Could not reach the activation service securely.",
    activationReceivedInvalid: "The received license could not be verified.",
    activationSuccess: "Pro was activated and linked to this installation.",
    refreshNotConfigured: "License renewal is not configured yet.",
    noActivationData: "No saved activation data is available for renewal.",
    refreshedLicenseExpired: "The license has expired or was disabled.",
    refreshCurrentFailed: "The current activation data could not renew the license.",
    refreshSecureFailed: "Could not reach the renewal service securely.",
    refreshedLicenseInvalid: "The renewed license could not be verified.",
    refreshSuccess: "The Pro license was renewed and verified.",
    updateSection: "Secure updates",
    updateNotChecked: "Not checked yet",
    updateUnavailableStatus: "Update channel not configured",
    updateManagedByStoreStatus: "Updates are managed automatically by Microsoft Store",
    updateCurrentStatus: "You have the latest version",
    updateAvailableStatus: "Version {version} is available",
    updateStagedStatus: "Version {version} downloaded and verified",
    updateDescription: "Updates are accepted only after signature, size, and hash verification.",
    checkUpdates: "Check for updates",
    downloadUpdate: "Download and verify",
    updateChannelMissing: "The update channel is not configured yet.",
    updateManagedByStoreMessage: "Updates are managed automatically by Microsoft Store.",
    updateCheckFailed: "The update could not be checked securely.",
    updateStageFailed: "The update could not be prepared.",
    updateAvailableMessage: "A new update is available.",
    updateCurrentMessage: "You have the latest version.",
    updateStagedMessage: "The update was downloaded and verified. It will not run without your approval.",
    restartSettingsNote: "Voice and AI changes apply after restarting the app.",
    resetSettings: "Restore defaults",
    cancelSettings: "Cancel",
    saveSettings: "Save settings",
    savingSettings: "Saving…",
    settingsInvalid: "The settings are invalid.",
    settingsSaved: "Settings saved. Restart the app to apply voice and AI changes.",
    settingsReset: "Default settings were restored.",
    settingsPreviewSaved: "The preview was updated; saving requires the desktop app.",
    settingsLoadFailed: "Local settings could not be loaded.",
    resetSettingsConfirm: "Restore all assistant settings to their defaults?",
    heardYouLabel: "I heard you say",
    voiceConnectionFailed: "Could not connect to the local engine.",
    languageChanged: "Interface language: {language}.",
    listeningStopped: "Listening stopped",
    waitingWakeWord: "Waiting for the wake phrase",
    speakNow: "Speak now",
    awakenedLabel: "Wake phrase detected",
    listeningPrompt: "I'm listening…",
    resultLabel: "Result",
    voiceFailedLabel: "Voice could not start",
    enterCommandFirst: "Enter a command first.",
    commandTooLong: "The command exceeds the allowed length.",
    voiceNotConfigured: "Voice is not configured yet. Run the readiness check for setup details.",
    microphoneStopped: "The microphone was stopped.",
    listeningAlreadyActive: "Listening is already active.",
    voiceListeningSay: "Listening is active. Say: {phrase}",
  }),
});

const BACKEND_MESSAGE_KEYS = Object.freeze([
  "engineLocalReady",
  "engineListeningActive",
  "listeningStopped",
  "waitingWakeWord",
  "speakNow",
  "awakenedLabel",
  "listeningPrompt",
  "heardYouLabel",
  "resultLabel",
  "voiceFailedLabel",
  "enterCommandFirst",
  "commandTooLong",
  "voiceNotConfigured",
  "microphoneStopped",
  "listeningAlreadyActive",
  "settingsInvalid",
  "settingsSaved",
  "settingsReset",
  "licenseUnavailable",
  "licenseInvalid",
  "licenseVerificationFailed",
  "licenseActivated",
  "licenseRemoved",
  "noPaidLicense",
  "licenseRemovalFailed",
  "purchaseOpened",
  "purchaseOpenFailed",
  "voiceProRequired",
  "activationNotConfigured",
  "invalidPurchaseKey",
  "purchaseKeyRejected",
  "purchaseKeyExpired",
  "activationSecureFailed",
  "activationReceivedInvalid",
  "activationSuccess",
  "refreshNotConfigured",
  "noActivationData",
  "refreshedLicenseExpired",
  "refreshCurrentFailed",
  "refreshSecureFailed",
  "refreshedLicenseInvalid",
  "refreshSuccess",
  "updateChannelMissing",
  "updateManagedByStoreMessage",
  "updateCheckFailed",
  "updateStageFailed",
  "updateAvailableMessage",
  "updateCurrentMessage",
  "updateStagedMessage",
]);

const DEFAULT_PRODUCT_SETTINGS = Object.freeze({
  name: "رايلونو",
  language: "auto",
  wake_phrase: "يا رايلونو",
  english_wake_phrase: "Hey Rayluno",
  stt_backend: "whispercpp",
  stt_model: "base",
  ollama_model: "qwen3.5:4b",
  tts_voice: "",
  telemetry_opt_in: false,
});

const state = {
  mode: "idle",
  modeDetail: "",
  history: [],
  voiceEnabled: false,
  toastTimer: null,
  languagePreference: readLanguagePreference(),
  language: "ar",
  snapshotName: "",
  version: "",
  engine: { kind: "key", value: "engineChecking" },
  productSettings: { ...DEFAULT_PRODUCT_SETTINGS },
  license: {
    state: "free",
    edition: "free",
    pro_active: false,
    features: [],
    activation_configured: false,
    refresh_available: false,
  },
  updates: {
    configured: false,
    managed_by_store: false,
    available: false,
    staged: false,
    version: null,
  },
  updatesChecked: false,
  updateCheckPending: false,
  updateStagePending: false,
};

const elements = {
  assistantName: document.querySelector("#assistant-name"),
  engineState: document.querySelector("#engine-state"),
  modeLabel: document.querySelector("#mode-label"),
  orb: document.querySelector("#voice-button"),
  orbLabel: document.querySelector("#orb-label"),
  transcriptLabel: document.querySelector("#transcript-label"),
  transcriptText: document.querySelector("#transcript-text"),
  commandForm: document.querySelector("#command-form"),
  commandInput: document.querySelector("#command-input"),
  sendButton: document.querySelector("#send-button"),
  activityList: document.querySelector("#activity-list"),
  clearHistory: document.querySelector("#clear-history"),
  settingsButton: document.querySelector("#settings-button"),
  settingsDialog: document.querySelector("#settings-dialog"),
  settingsForm: document.querySelector("#settings-form"),
  settingsClose: document.querySelector("#settings-close"),
  settingsCancel: document.querySelector("#settings-cancel"),
  settingsReset: document.querySelector("#settings-reset"),
  settingsSave: document.querySelector("#settings-save"),
  firstRunCard: document.querySelector("#first-run-card"),
  licenseStatus: document.querySelector("#license-status"),
  licenseToken: document.querySelector("#license-token"),
  licenseBuy: document.querySelector("#license-buy"),
  licenseActivate: document.querySelector("#license-activate"),
  licenseRefresh: document.querySelector("#license-refresh"),
  licenseRemove: document.querySelector("#license-remove"),
  updateStatus: document.querySelector("#update-status"),
  updateCheck: document.querySelector("#update-check"),
  updateDownload: document.querySelector("#update-download"),
  languageButtons: Array.from(document.querySelectorAll("[data-language]")),
  quickActions: Array.from(document.querySelectorAll("[data-command-key]")),
  toast: document.querySelector("#toast"),
  versionLabel: document.querySelector("#version-label"),
};

function normalizeLanguagePreference(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return SUPPORTED_LANGUAGE_PREFERENCES.has(normalized) ? normalized : "auto";
}

function readLanguagePreference() {
  try {
    return normalizeLanguagePreference(window.localStorage.getItem(LANGUAGE_STORAGE_KEY));
  } catch (_error) {
    return "auto";
  }
}

function saveLanguagePreference(preference) {
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, preference);
  } catch (_error) {
    // The private desktop webview may disable storage. The in-memory choice still works.
  }
}

function systemLanguage() {
  const preferred = navigator.languages?.[0] || navigator.language || "en";
  return String(preferred).toLowerCase().startsWith("ar") ? "ar" : "en";
}

function resolveInterfaceLanguage(preference) {
  return preference === "auto" ? systemLanguage() : preference;
}

function t(key, replacements = {}) {
  const catalog = translations[state.language] || translations.en;
  const template = catalog[key] ?? translations.en[key] ?? key;
  return Object.entries(replacements).reduce(
    (message, [name, value]) => message.replaceAll(`{${name}}`, String(value)),
    template,
  );
}

function knownBackendKey(value) {
  if (typeof value !== "string") return null;
  return BACKEND_MESSAGE_KEYS.find(
    (key) => translations.ar[key] === value || translations.en[key] === value,
  ) || null;
}

function translateBackendMessage(value) {
  if (typeof value !== "string") return "";
  const exactKey = knownBackendKey(value);
  if (exactKey) return t(exactKey);

  const listeningPrefixes = ["الاستماع نشط. قل:", "Listening is active. Say:"];
  const prefix = listeningPrefixes.find((candidate) => value.startsWith(candidate));
  if (prefix) {
    const phrase = value.slice(prefix.length).trim();
    return t("voiceListeningSay", { phrase });
  }
  return value;
}

function setLocalizedText(element, key) {
  if (!element) return;
  element.dataset.i18n = key;
  delete element.dataset.backendText;
  element.textContent = t(key);
}

function setRawText(element, value) {
  if (!element) return;
  delete element.dataset.i18n;
  delete element.dataset.backendText;
  element.textContent = String(value ?? "");
}

function setBackendText(element, value, fallbackKey = null) {
  if (!element) return;
  if (!value && fallbackKey) {
    setLocalizedText(element, fallbackKey);
    return;
  }
  delete element.dataset.i18n;
  element.dataset.backendText = String(value ?? "");
  element.textContent = translateBackendMessage(String(value ?? ""));
}

function renderAssistantName() {
  const genericNames = new Set([
    "",
    translations.ar.assistantName,
    translations.en.assistantName,
    "المساعد",
    "Assistant",
  ]);
  if (genericNames.has(state.snapshotName)) {
    setLocalizedText(elements.assistantName, "assistantName");
  } else {
    setRawText(elements.assistantName, state.snapshotName);
  }
}

function renderVersion() {
  if (state.version) {
    delete elements.versionLabel.dataset.i18n;
    elements.versionLabel.textContent = t("versionLabel", { version: state.version });
  } else {
    setLocalizedText(elements.versionLabel, "versionPreview");
  }
}

function renderEngineState() {
  if (state.engine.kind === "key") {
    setLocalizedText(elements.engineState, state.engine.value);
  } else {
    setBackendText(elements.engineState, state.engine.value, "engineUnavailable");
  }
}

function renderLicenseStatus() {
  const license = state.license || {};
  const keys = {
    active: license.pro_active ? "licenseProStatus" : "licenseFreeStatus",
    expired: "licenseExpiredStatus",
    invalid: "licenseInvalidStatus",
    unavailable: "licenseUnavailableStatus",
    free: "licenseFreeStatus",
  };
  setLocalizedText(elements.licenseStatus, keys[license.state] || "licenseFreeStatus");
  elements.licenseStatus.classList.toggle("pro", Boolean(license.pro_active));
  elements.licenseBuy.hidden = Boolean(license.pro_active);
  elements.licenseRemove.hidden = !license.pro_active;
  elements.licenseRefresh.hidden = !license.refresh_available;
  renderUpdateStatus();
}

function renderUpdateStatus() {
  const updates = state.updates || {};
  const storeManaged = updates.managed_by_store === true;
  if (storeManaged) {
    setLocalizedText(elements.updateStatus, "updateManagedByStoreStatus");
  } else if (!updates.configured) {
    setLocalizedText(elements.updateStatus, "updateUnavailableStatus");
  } else if (updates.staged) {
    setRawText(elements.updateStatus, t("updateStagedStatus", { version: updates.version || "" }));
  } else if (updates.available) {
    setRawText(elements.updateStatus, t("updateAvailableStatus", { version: updates.version || "" }));
  } else if (updates.checked || state.updatesChecked) {
    setLocalizedText(elements.updateStatus, "updateCurrentStatus");
  } else {
    setLocalizedText(elements.updateStatus, "updateNotChecked");
  }
  elements.updateCheck.hidden = storeManaged;
  elements.updateDownload.hidden = storeManaged
    || !updates.available
    || updates.staged;
  elements.updateCheck.disabled = storeManaged
    || !updates.configured
    || state.updateCheckPending;
  elements.updateDownload.disabled = state.updateStagePending;
}

function renderMode() {
  const definitions = {
    idle: ["modeIdle", "orbIdle"],
    listening: ["modeListening", "orbListening"],
    thinking: ["modeThinking", "orbThinking"],
    error: ["modeError", "orbError"],
  };
  const [modeKey, orbKey] = definitions[state.mode] || definitions.idle;
  elements.orb.classList.remove("listening", "thinking", "error");
  setLocalizedText(elements.modeLabel, modeKey);
  if (state.modeDetail) {
    setBackendText(elements.orbLabel, state.modeDetail);
  } else {
    setLocalizedText(elements.orbLabel, orbKey);
  }
  if (state.mode !== "idle") elements.orb.classList.add(state.mode);
  const voiceLabelKey = state.voiceEnabled ? "stopListeningLabel" : "startListeningLabel";
  elements.orb.dataset.i18nAriaLabel = voiceLabelKey;
  elements.orb.setAttribute("aria-label", t(voiceLabelKey));
  elements.orb.setAttribute("aria-pressed", String(state.voiceEnabled));
}

function setMode(mode, detail = "") {
  state.mode = ["idle", "listening", "thinking", "error"].includes(mode) ? mode : "idle";
  state.modeDetail = detail || "";
  renderMode();
}

function showToast(message, isError = false) {
  window.clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", isError);
  elements.toast.classList.add("show");
  state.toastTimer = window.setTimeout(() => elements.toast.classList.remove("show"), 3200);
}

function createEmptyHistoryItem() {
  const item = document.createElement("li");
  item.className = "empty-activity";

  const icon = document.createElement("span");
  icon.className = "activity-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "✦";

  const copy = document.createElement("span");
  const title = document.createElement("b");
  const description = document.createElement("small");
  title.textContent = t("emptyHistoryTitle");
  description.textContent = t("emptyHistoryDescription");
  copy.append(title, description);
  item.append(icon, copy);
  return item;
}

function renderHistory() {
  elements.activityList.replaceChildren();
  if (!state.history.length) {
    elements.activityList.append(createEmptyHistoryItem());
    return;
  }

  state.history.slice(0, 8).forEach((entry) => {
    const item = document.createElement("li");
    if (!entry.ok) item.classList.add("failed");

    const icon = document.createElement("span");
    icon.className = "activity-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = entry.ok ? "✓" : "!";

    const copy = document.createElement("span");
    const title = document.createElement("b");
    const meta = document.createElement("small");
    title.textContent = entry.command || entry.action || t("historyDefaultCommand");
    meta.textContent = entry.message
      ? translateBackendMessage(String(entry.message))
      : t(entry.ok ? "historySucceeded" : "historyFailed");
    copy.append(title, meta);
    if (entry.ai_generated === true) {
      const report = document.createElement("button");
      report.type = "button";
      report.className = "activity-report";
      report.textContent = t("reportAiResponse");
      report.addEventListener("click", async () => {
        report.disabled = true;
        const reportText = [
          `Command: ${String(entry.command || "")}`,
          `AI response: ${String(entry.message || "")}`,
        ].join("\n");
        try {
          await navigator.clipboard.writeText(reportText);
        } catch {
          // Clipboard access can be unavailable in hardened WebView profiles;
          // the form still opens and lets the user paste or type manually.
        }
        try {
          if (!apiAvailable() || typeof window.pywebview.api.open_ai_report_page !== "function") {
            showToast(t("reportOpenFailed"), true);
            return;
          }
          const result = await window.pywebview.api.open_ai_report_page();
          showToast(t(result?.ok ? "reportOpened" : "reportOpenFailed"), !result?.ok);
        } catch {
          showToast(t("reportOpenFailed"), true);
        } finally {
          report.disabled = false;
        }
      });
      copy.append(report);
    }
    item.append(icon, copy);
    elements.activityList.append(item);
  });
}

function applyTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
  document.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.setAttribute("title", t(element.dataset.i18nTitle));
  });
  document.querySelectorAll("[data-backend-text]").forEach((element) => {
    element.textContent = translateBackendMessage(element.dataset.backendText);
  });
  elements.quickActions.forEach((button) => {
    button.dataset.command = t(button.dataset.commandKey);
  });
}

function languagePreferenceLabel(preference) {
  const keys = {
    ar: "languageArabicLabel",
    en: "languageEnglishLabel",
    auto: "languageAutoLabel",
  };
  return t(keys[preference] || keys.auto);
}

function applyLanguage(preference, { persist = false, announce = false } = {}) {
  const normalized = normalizeLanguagePreference(preference);
  state.languagePreference = normalized;
  state.language = resolveInterfaceLanguage(normalized);

  const root = document.documentElement;
  root.lang = state.language;
  root.dir = state.language === "ar" ? "rtl" : "ltr";
  root.dataset.languagePreference = normalized;

  applyTranslations();
  renderAssistantName();
  renderVersion();
  renderEngineState();
  renderHistory();
  renderMode();
  renderLicenseStatus();
  renderUpdateStatus();

  elements.languageButtons.forEach((button) => {
    const selected = button.dataset.language === normalized;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });

  if (persist) saveLanguagePreference(normalized);
  if (announce) {
    showToast(t("languageChanged", { language: languagePreferenceLabel(normalized) }));
  }

  window.dispatchEvent(new CustomEvent("assistantlanguagechange", {
    detail: { language: state.language, preference: normalized },
  }));
}

function apiAvailable() {
  return Boolean(window.pywebview?.api);
}

function normalizeProductSettings(values = {}) {
  const merged = { ...DEFAULT_PRODUCT_SETTINGS, ...(values || {}) };
  merged.tts_voice = merged.tts_voice || "";
  return merged;
}

function populateSettingsForm(values = state.productSettings) {
  const settings = normalizeProductSettings(values);
  Object.entries(settings).forEach(([name, value]) => {
    const control = elements.settingsForm.elements.namedItem(name);
    if (!control || name === "telemetry_opt_in") return;
    const genericName = name === "name"
      && [
        translations.ar.assistantName,
        translations.en.assistantName,
        "المساعد",
        "Assistant",
      ].includes(String(value));
    control.value = genericName ? t("assistantName") : String(value ?? "");
  });
}

function settingsFromForm() {
  const value = (name) => String(elements.settingsForm.elements.namedItem(name)?.value || "").trim();
  return {
    name: value("name"),
    language: normalizeLanguagePreference(value("language")),
    wake_phrase: value("wake_phrase"),
    english_wake_phrase: value("english_wake_phrase"),
    stt_backend: value("stt_backend"),
    stt_model: value("stt_model"),
    ollama_model: value("ollama_model"),
    tts_voice: value("tts_voice") || null,
    telemetry_opt_in: false,
  };
}

function openSettings({ firstRun = false } = {}) {
  populateSettingsForm();
  elements.firstRunCard.hidden = !firstRun;
  if (!elements.settingsDialog.open) elements.settingsDialog.showModal();
}

function applySavedSettings(settings) {
  state.productSettings = normalizeProductSettings(settings);
  state.snapshotName = state.productSettings.name;
  renderAssistantName();
  populateSettingsForm();
}

async function refreshAndOpenSettings() {
  if (!apiAvailable()) {
    openSettings();
    return;
  }
  try {
    const result = await window.pywebview.api.get_product_settings();
    if (!result?.ok) throw new Error(t("settingsLoadFailed"));
    applySavedSettings(result.settings);
    openSettings({ firstRun: Boolean(result.first_run) });
  } catch (_error) {
    showToast(t("settingsLoadFailed"), true);
  }
}

function applySnapshot(snapshot = {}) {
  if (snapshot.name) state.snapshotName = String(snapshot.name);
  if (snapshot.version) state.version = String(snapshot.version);
  if (snapshot.engine) state.engine = { kind: "backend", value: String(snapshot.engine) };
  if (Array.isArray(snapshot.history)) state.history = snapshot.history;
  if (snapshot.settings) state.productSettings = normalizeProductSettings(snapshot.settings);
  if (snapshot.license) state.license = snapshot.license;
  if (snapshot.updates) state.updates = snapshot.updates;
  if (snapshot.mode) {
    state.voiceEnabled = snapshot.mode === "listening";
    state.mode = snapshot.mode;
    state.modeDetail = "";
  }
  renderAssistantName();
  renderVersion();
  renderEngineState();
  renderHistory();
  renderMode();
  renderLicenseStatus();
  renderUpdateStatus();
  populateSettingsForm();
  if (snapshot.first_run && apiAvailable()) {
    window.setTimeout(() => openSettings({ firstRun: true }), 0);
  }
}

async function submitCommand(rawCommand) {
  const command = rawCommand.trim();
  if (!command || state.mode === "thinking") return;

  elements.commandInput.value = "";
  setLocalizedText(elements.transcriptLabel, "requestLabel");
  setRawText(elements.transcriptText, command);
  setMode("thinking");
  elements.sendButton.disabled = true;

  try {
    if (!apiAvailable()) {
      await new Promise((resolve) => window.setTimeout(resolve, 550));
      throw new Error(t("previewCommandError"));
    }
    const result = await window.pywebview.api.execute_command(command);
    const normalized = result || { ok: false, message: "", action: "none" };
    state.history.unshift({ command, ...normalized });
    state.history = state.history.slice(0, 20);
    renderHistory();
    setLocalizedText(elements.transcriptLabel, normalized.ok ? "doneLabel" : "alertLabel");
    if (normalized.message) {
      setBackendText(elements.transcriptText, normalized.message);
    } else {
      setLocalizedText(elements.transcriptText, normalized.ok ? "requestProcessed" : "noEngineResponse");
    }
    setMode(normalized.ok ? "idle" : "error");
    if (!normalized.ok) {
      showToast(
        normalized.message ? translateBackendMessage(String(normalized.message)) : t("executeFailed"),
        true,
      );
    }
  } catch (error) {
    const message = error?.message || String(error);
    setLocalizedText(elements.transcriptLabel, "alertLabel");
    setRawText(elements.transcriptText, message);
    setMode("error");
    showToast(message, true);
  } finally {
    elements.sendButton.disabled = false;
    window.setTimeout(() => {
      if (state.mode === "error") setMode("idle");
    }, 2400);
  }
}

elements.commandForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitCommand(elements.commandInput.value);
});

elements.quickActions.forEach((button) => {
  button.addEventListener("click", () => submitCommand(button.dataset.command || ""));
});

elements.languageButtons.forEach((button) => {
  button.addEventListener("click", () => {
    applyLanguage(button.dataset.language, { persist: true, announce: true });
  });
});

elements.orb.addEventListener("click", async () => {
  if (!apiAvailable()) {
    showToast(t("voicePreviewError"), true);
    return;
  }
  try {
    const result = await window.pywebview.api.toggle_voice();
    state.voiceEnabled = Boolean(result?.enabled);
    setMode(state.voiceEnabled ? "listening" : "idle");
    if (result?.message) showToast(translateBackendMessage(String(result.message)), !result.ok);
  } catch (error) {
    state.voiceEnabled = false;
    setMode("error");
    showToast(error?.message || String(error), true);
  }
});

elements.clearHistory.addEventListener("click", async () => {
  if (apiAvailable()) await window.pywebview.api.clear_history();
  state.history = [];
  renderHistory();
});

elements.settingsButton.addEventListener("click", refreshAndOpenSettings);

elements.settingsClose.addEventListener("click", () => elements.settingsDialog.close());
elements.settingsCancel.addEventListener("click", () => elements.settingsDialog.close());

elements.settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!elements.settingsForm.reportValidity()) return;
  const settings = settingsFromForm();
  elements.settingsSave.disabled = true;
  elements.settingsSave.textContent = t("savingSettings");
  try {
    if (!apiAvailable()) {
      applySavedSettings(settings);
      applyLanguage(settings.language, { persist: true });
      elements.settingsDialog.close();
      showToast(t("settingsPreviewSaved"));
      return;
    }
    const result = await window.pywebview.api.save_product_settings(settings);
    if (!result?.ok) {
      showToast(translateBackendMessage(String(result?.message || t("settingsInvalid"))), true);
      return;
    }
    applySavedSettings(result.settings);
    applyLanguage(result.settings.language, { persist: true });
    elements.settingsDialog.close();
    showToast(translateBackendMessage(String(result.message || t("settingsSaved"))));
  } catch (_error) {
    showToast(t("settingsInvalid"), true);
  } finally {
    elements.settingsSave.disabled = false;
    elements.settingsSave.textContent = t("saveSettings");
  }
});

elements.settingsReset.addEventListener("click", async () => {
  if (!window.confirm(t("resetSettingsConfirm"))) return;
  try {
    const result = apiAvailable()
      ? await window.pywebview.api.reset_product_settings()
      : { ok: true, settings: DEFAULT_PRODUCT_SETTINGS, message: t("settingsReset") };
    if (!result?.ok) throw new Error(t("settingsInvalid"));
    applySavedSettings(result.settings);
    applyLanguage(result.settings.language, { persist: true });
    showToast(translateBackendMessage(String(result.message || t("settingsReset"))));
  } catch (_error) {
    showToast(t("settingsInvalid"), true);
  }
});

elements.licenseBuy.addEventListener("click", async () => {
  if (!apiAvailable() || typeof window.pywebview.api.open_purchase_page !== "function") {
    showToast(t("purchaseOpenFailed"), true);
    return;
  }
  try {
    const result = await window.pywebview.api.open_purchase_page();
    showToast(t(result?.ok ? "purchaseOpened" : "purchaseOpenFailed"), !result?.ok);
  } catch (_error) {
    showToast(t("purchaseOpenFailed"), true);
  }
});

elements.licenseActivate.addEventListener("click", async () => {
  const token = elements.licenseToken.value.trim();
  if (!token) {
    showToast(t("enterLicenseToken"), true);
    return;
  }
  if (!apiAvailable()) {
    showToast(t("licenseUnavailable"), true);
    return;
  }
  elements.licenseActivate.disabled = true;
  try {
    const onlineActivation = Boolean(
      state.license.activation_configured &&
      typeof window.pywebview.api.activate_purchase_key === "function",
    );
    const result = onlineActivation
      ? await window.pywebview.api.activate_purchase_key(token)
      : await window.pywebview.api.install_license(token);
    if (!result?.ok) {
      showToast(translateBackendMessage(String(result?.message || t("licenseInvalid"))), true);
      return;
    }
    state.license = result.license;
    elements.licenseToken.value = "";
    renderLicenseStatus();
    showToast(translateBackendMessage(String(result.message || t("licenseActivated"))));
  } catch (_error) {
    showToast(t("licenseVerificationFailed"), true);
  } finally {
    elements.licenseActivate.disabled = false;
  }
});

elements.licenseRefresh.addEventListener("click", async () => {
  if (!apiAvailable() || typeof window.pywebview.api.refresh_purchase_license !== "function") {
    showToast(t("refreshNotConfigured"), true);
    return;
  }
  elements.licenseRefresh.disabled = true;
  try {
    const result = await window.pywebview.api.refresh_purchase_license();
    if (!result?.ok) {
      showToast(translateBackendMessage(String(result?.message || t("refreshCurrentFailed"))), true);
      return;
    }
    state.license = result.license;
    renderLicenseStatus();
    showToast(translateBackendMessage(String(result.message || t("refreshSuccess"))));
  } catch (_error) {
    showToast(t("refreshSecureFailed"), true);
  } finally {
    elements.licenseRefresh.disabled = false;
  }
});

elements.licenseRemove.addEventListener("click", async () => {
  if (!apiAvailable()) return;
  try {
    const result = await window.pywebview.api.remove_license();
    if (!result?.ok) {
      showToast(translateBackendMessage(String(result?.message || t("licenseRemovalFailed"))), true);
      return;
    }
    state.license = result.license;
    renderLicenseStatus();
    showToast(translateBackendMessage(String(result.message || t("licenseRemoved"))));
  } catch (_error) {
    showToast(t("licenseRemovalFailed"), true);
  }
});

elements.updateCheck.addEventListener("click", async () => {
  if (!apiAvailable()) {
    showToast(t("updateChannelMissing"), true);
    return;
  }
  state.updateCheckPending = true;
  renderUpdateStatus();
  try {
    const result = await window.pywebview.api.check_for_updates();
    if (!result?.ok) {
      showToast(translateBackendMessage(String(result?.message || t("updateCheckFailed"))), true);
      return;
    }
    state.updates = result.updates;
    state.updatesChecked = true;
    renderUpdateStatus();
    showToast(translateBackendMessage(String(result.message || t("updateCurrentMessage"))));
  } catch (_error) {
    showToast(t("updateCheckFailed"), true);
  } finally {
    state.updateCheckPending = false;
    renderUpdateStatus();
  }
});

elements.updateDownload.addEventListener("click", async () => {
  if (!apiAvailable()) return;
  state.updateStagePending = true;
  renderUpdateStatus();
  try {
    const result = await window.pywebview.api.stage_update();
    if (!result?.ok) {
      showToast(translateBackendMessage(String(result?.message || t("updateStageFailed"))), true);
      return;
    }
    state.updates = result.updates;
    renderUpdateStatus();
    showToast(translateBackendMessage(String(result.message || t("updateStagedMessage"))));
  } catch (_error) {
    showToast(t("updateStageFailed"), true);
  } finally {
    state.updateStagePending = false;
    renderUpdateStatus();
  }
});

window.assistantEvent = (event = {}) => {
  if (event.license) {
    state.license = event.license;
    renderLicenseStatus();
  }
  if (event.mode) {
    if (event.mode === "listening") state.voiceEnabled = true;
    if (event.mode === "idle" || event.mode === "error") state.voiceEnabled = false;
    setMode(event.mode, event.detail || "");
  }
  if (event.transcript) {
    setBackendText(elements.transcriptLabel, event.label || "", "heardYouLabel");
    setBackendText(elements.transcriptText, event.transcript);
  }
  if (event.result) {
    state.history.unshift(event.result);
    state.history = state.history.slice(0, 20);
    renderHistory();
  }
};

window.assistantLocalization = Object.freeze({
  getLanguage: () => state.language,
  getPreference: () => state.languagePreference,
  setLanguage: (language) => applyLanguage(language, { persist: true, announce: true }),
  translate: (key) => t(key),
});

window.addEventListener("languagechange", () => {
  if (state.languagePreference === "auto") applyLanguage("auto");
});

window.addEventListener("storage", (event) => {
  if (event.key === LANGUAGE_STORAGE_KEY) applyLanguage(event.newValue || "auto");
});

window.addEventListener("pywebviewready", async () => {
  try {
    applySnapshot(await window.pywebview.api.get_snapshot());
  } catch (_error) {
    state.engine = { kind: "key", value: "engineUnavailable" };
    renderEngineState();
    showToast(t("voiceConnectionFailed"), true);
  }
});

applyLanguage(state.languagePreference);

if (!apiAvailable()) {
  state.engine = { kind: "key", value: "enginePreview" };
  renderEngineState();
  renderHistory();
}
