# Rayluno Assistant 1.0.0 — مرشح إطلاق Windows / Windows launch candidate

**Rayluno Assistant — مساعد رايلونو** هو مساعد شخصي عربي/إنجليزي يعمل محليًا على
Windows وينفّذ مجموعة محددة من الأوامر الآمنة بالصوت أو الكتابة. اجتاز اسم
`Rayluno / رايلونو` فحص توافر أوليًا، لكنه يظل مرشح الهوية التجارية إلى أن يكتمل
البحث القانوني الرسمي وحجز النطاق وهوية Microsoft Partner Center. لا نستخدم
**JARVIS** اسمًا أو كلمة استيقاظ، ولا نقلّد صوتًا أو واجهة من فيلم.

Rayluno Assistant is an Arabic/English, local-first Windows assistant for a defined,
allowlisted set of voice and text commands. The Rayluno brand passed a preliminary
availability screen but remains subject to formal trademark review, domain acquisition,
and Microsoft Partner Center identity approval. This project is not affiliated with
Marvel or Iron Man.

> حالة الإصدار: بُنيت حزمة Rayluno 1.0.0 الكاملة لـWindows x64 وأرشيف ZIP الخاص بها
> وتحقّق منهما داخليًا، واكتمل مثبّت NSIS غير الموقّع. اكتملت كذلك حزمة MSIX
> تطويرية غير موقّعة للفحص والتحميل الجانبي؛ ليست حزمة قابلة للرفع إلى Microsoft
> Store. نُشرت النسخة 4 من موقع الإطلاق بصورة خاصة فقط، ومن دون أسرار تشغيل
> (`env_set_revision=0`)؛ لذلك لم يُفعّل الدفع أو التفعيل الإنتاجي. بقيت مخرجات
> 0.1.0 القديمة محفوظة تحت `dist/legacy` ولا تصلح للبيع أو النشر باسم Rayluno.
>
> Release status: the full Rayluno 1.0.0 x64 bundle and ZIP have been built and
> internally verified, and the unsigned NSIS installer is complete. An unsigned
> development MSIX is also complete for inspection and sideload testing; it cannot be
> uploaded to Microsoft Store. Sites version 4 is deployed privately with no runtime secrets
> (`env_set_revision=0`), so production checkout and activation remain disabled. The
> old 0.1.0 artifacts are archived under `dist/legacy` and are not public release assets.

## ما يعمل حاليًا / What works now

- واجهة وتهيئة أولى وإعدادات وأوامر بالعربية والإنجليزية.
- استيقاظ محلي عبر Vosk بعبارتي `يا رايلونو` و`Hey Rayluno` قابلتين للتغيير.
- تحويل الكلام محليًا عبر `whisper.cpp`، ونطق عبر أصوات Windows المثبتة. لا تُكتب
  تسجيلات الميكروفون إلى القرص.
- فتح مواقع وتطبيقات Windows المسموحة، بحث Google/YouTube، معرفة الوقت، والتحكم
  بالصوت، وأوامر تشغيل أغنية أو فيديو في مشغّل YouTube الرسمي.
- تكامل اختياري مع YouTube Data API بمفتاح المستخدم: يفتح أول فيديو مطابق، ويعود
  بأمان إلى صفحة نتائج YouTube عند غياب المفتاح أو فشل الطلب.
- ذكاء محلي اختياري عبر Ollama. الأوامر المباشرة السريعة لا تحتاج نموذجًا لغويًا.
- قائمة أفعال وتطبيقات ونطاقات مسموحة؛ لا يستطيع النموذج تشغيل `shell` أو PowerShell.
- Free/Pro بتراخيص Ed25519 موقّعة، وتفعيل اختياري بمفتاح شراء، وتجديد آمن دون إظهار
  رمز التجديد للواجهة.
- فحص تحديثات موقّعة وتنزيلها إلى مجلد مرحلي بعد التحقق من الحجم وSHA-256؛ التطبيق
  لا يشغّل المثبّت تلقائيًا.
- سجل تدقيق محلي يخزن تجزئة الأمر وملخص الفعل، لا نص الأمر أو استعلام البحث.

The same features are available in both UI languages. Wake detection, speech-to-text,
text-to-speech, command routing, and optional Ollama reasoning run locally. Network use
occurs only for an action that inherently opens a web service, optional YouTube lookup,
purchase activation/refresh, or an explicitly configured update check.

## حدود Free وPro / Free and Pro boundary

| الفئة / Edition | الاستحقاقات الحالية / Current entitlements |
|---|---|
| Free | أوامر مكتوبة أساسية وفتح تطبيقات/مواقع وبحث، مع خط الخصوصية المحلي (`commands.basic`, `privacy.local`) |
| Pro | صوت عربي/إنجليزي كامل، ذكاء Ollama محلي، تشغيل وسائط مباشر وتحديثات موقعة (`ai.local`, `voice.local`, `automation.pro`, `updates.pro`) |

الميزات الفعلية تأتي من الرمز الموقّع، لذلك لا يعني ظهور كلمة Pro وعدًا بكل ميزة
مستقبلية. عند غياب الترخيص أو انتهاء صلاحيته أو فشل التحقق، يعود التطبيق إلى Free
بصورة آمنة.

Signed claims determine the exact Pro features. Missing, expired, or invalid licenses
fail closed to the safe Free mode.

## تشغيل بيئة التطوير / Development setup

يتطلب Python 3.11 أو أحدث على Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev,desktop,commercial]"
rayluno --once "يا رايلونو كم الساعة" --dry-run --no-audit
rayluno --ui
```

أو استخدم سكربت الإعداد:

```powershell
.\scripts\setup.ps1
```

يفحص الأمر التالي الاعتمادات والإعدادات ولا ينزّل شيئًا ولا يغيّر الجهاز:

```powershell
rayluno --doctor
```

## الصوت المحلي / Local voice

للتطوير من المصدر:

```powershell
python -m pip install -e ".[voice]"
.\scripts\install-arabic-wake-model.ps1 -SetUserEnvironment
```

عند استخدام اللغة `auto` يلزم نموذجا Vosk العربي والإنجليزي. الحزمة الصوتية الكاملة
تضم حاليًا:

- `vosk-model-ar-mgb2-0.4` للعربية.
- `vosk-model-small-en-us-0.15` للإنجليزية.
- `ggml-base.bin` لـ Whisper متعدد اللغات.

الافتراضي `whispercpp` مناسب لمعالجات x64 الأقدم. يبقى `faster-whisper` خيار تطوير
للأجهزة الحديثة عبر `RAYLUNO_STT_BACKEND=faster-whisper` وتثبيت
`.[voice-fast]`، ولا يدخل الحزمة الصوتية الحالية.

ثبّت صوت Windows عربيًا/إنجليزيًا مناسبًا للنطق؛ التطبيق يستدعي الأصوات الموجودة
ولا يعيد توزيع ملفات Microsoft الصوتية.

## الذكاء المحلي / Optional local AI

ثبّت Ollama باختيارك، ثم نزّل نموذجًا يناسب جهازك:

```powershell
ollama pull qwen3.5:4b
rayluno --ui --ollama
```

Ollama والنموذج غير مثبتين تلقائيًا ولا يدخلان المثبّت. مسار Ollama محمي بميزة
`ai.local` ولا يعمل في Free حتى لو كان الخادم المحلي موجودًا. راجع ترخيص أي نموذج
قبل استخدامه تجاريًا. يمكن تغيير الاسم عبر `RAYLUNO_OLLAMA_MODEL`.

## تشغيل أغنية أو فيديو / YouTube media commands

بحث YouTube العادي متاح في Free. أما طلب تشغيل أغنية/فيديو مباشرة فيتطلب
`automation.pro`؛ ومن دون مفتاح API يفتح نتائج YouTube الرسمية. لإجراء بحث رسمي وفتح
أول فيديو مطابق، ضع مفتاح YouTube Data API الخاص بك في
`RAYLUNO_YOUTUBE_API_KEY`. يرسل المفتاح في ترويسة إلى أصل Google API الثابت،
ويرفض التحويلات، ولا يضعه في عنوان URL.

The integration never downloads, re-streams, or extracts media, and does not bypass ads.
Any API error safely falls back to the official YouTube search page.

## التفعيل التجاري / Commercial activation

- قناة التوزيع المقترحة هي Microsoft Store، والشراء الخارجي المقترح لنسخة
  **Founders Pro** بسعر اختبار `29 USD` مرة واحدة هو Lemon Squeezy بوصفه
  Merchant of Record. **لم تُفعّل بعد** حسابات Store وLemon Squeezy أو المنتج أو
  الدفع الحقيقي؛ يلزم Partner Center وKYC ومراجعة المتجر واختبار شراء فعلي قبل البيع.
- يعرض Lemon Squeezy بحسب البلد والجهاز والمتصفح بطاقات الدفع وPayPal وApple Pay
  وGoogle Pay، وقد يعرض وسائل إضافية حيث تتوفر. لا يعني ذلك قبول كل شخص أو بلد،
  ولا ندّعي دعمًا أصليًا لـMada أوKNET أوBenefit.
- عنوان التفعيل الإنتاجي مثبت داخل حزمة العميل على أصل Sites المحدد، لذلك يعمل مفتاح
  الشراء بلا إعداد يدوي بعد فتح الموقع للعامة وربطه بمزود الدفع.
- لا تقبل حزمة Windows المجمدة تحويل العنوان عبر متغير بيئة. يمكن لنسخة المصدر فقط
  استخدام `RAYLUNO_ACTIVATION_URL` عند تفعيل
  `RAYLUNO_ALLOW_ACTIVATION_OVERRIDE=true` صراحةً للاختبار المرحلي.
- ينشئ التطبيق UUID عشوائيًا للتثبيت؛ لا يبني بصمة عتاد خفية.
- يُرسل مفتاح الشراء إلى خدمة التفعيل عند التفعيل، ثم يخزن رمز التجديد المعتم فقط
  محميًا بـ Windows DPAPI لحساب المستخدم الحالي.
- لا توجد مفاتيح دفع أو مفاتيح توقيع خاصة داخل تطبيق العميل. المفاتيح العامة فقط
  هي المضمّنة للتحقق.

The activation endpoint must be a plain HTTPS URL. The desktop verifies every returned
license locally before enabling Pro. See [بنية الترخيص](docs/LICENSING_AR.md).

## التحديثات / Secure updates

`RAYLUNO_UPDATE_MANIFEST_URL` يحدد بيان تحديث HTTPS موقّعًا. يفحص التطبيق
المنتج والقناة والإصدار الأدنى لـWindows والتوقيع والحجم والبصمة قبل تجهيز الملف.
التجهيز لا يعني التشغيل أو التثبيت. راجع [نظام التحديثات](docs/UPDATES_AR.md).

توقيع بيان Ed25519 لا يحل محل Authenticode: الأول يحمي قناة التحديث، والثاني يثبت
هوية ناشر برنامج Windows ويساعد سمعة SmartScreen. المثبّت التجريبي الحالي **غير
موقّع بـ Authenticode**.

## الخصوصية والإعدادات / Privacy and configuration

- الصوت وSTT وكلمة الاستيقاظ محلية، ولا تُحفظ عينات الصوت.
- لا توجد تحليلات استخدام مفعلة افتراضيًا؛ خيار telemetry محفوظ محليًا لكنه لا
  يفعّل إرسالًا خفيًا.
- فتح بحث ويب يرسل الاستعلام إلى الخدمة التي اختارها المستخدم كما يفعل المتصفح.
- يمكن تعطيل سجل التدقيق بوضع `RAYLUNO_AUDIT_PATH` فارغًا.
- ملف [`.env.example`](.env.example) مرجع فقط؛ PowerShell والتطبيق لا يحملانه تلقائيًا.
  اضبط القيم في بيئة العملية/المستخدم أو من إعدادات التطبيق حيث تتوفر.

أمثلة المستخدم الجديدة تستعمل أمر `rayluno` ومتغيرات `RAYLUNO_*`. تبقى أسماء
`FUTURE_ASSISTANT_*` ومسار `%LOCALAPPDATA%\FutureAssistant` ومعرّفات
`future-assistant` المستخدمة في التحديث والتوقيع aliases/معرّفات بروتوكول ثابتة
للتوافق مع النسخ التجريبية السابقة؛ ظهورها داخليًا لا يعني بقاء اسم المنتج القديم.

تفاصيل البيانات والحدود في [الأمان والخصوصية](docs/SECURITY_PRIVACY_AR.md).

## بناء الحزمة واختبارها / Build and verification

```powershell
.\scripts\build-release.ps1 -WithVoice
.\scripts\smoke-release.ps1 -ExpectVoice -LaunchGui
.\scripts\build-installer.ps1 -TestInstall
.\scripts\build-msix.ps1 -DevelopmentIdentity
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

الحزمة الحالية تستهدف Windows x64. لا تنشر الناتج للعامة قبل استكمال توقيع
Authenticode، البحث القانوني الرسمي للعلامة وحجز النطاق، اختبار بيتا على أجهزة
متعددة، إعداد حسابي Store وLemon Squeezy وKYC وخدمة التفعيل والتحديث الحقيقية،
واعتماد سياسات الدعم والاسترجاع.

ينشئ البناء الصوتي تلقائيًا حزمة نصوص تراخيص، وبيانًا بالإصدارات، وCycloneDX SBOM،
وملف SHA-256 حتميًا لكل ملفات النماذج. كما يستبعد PortAudio المبني مع ASIO لأنه غير
مستخدم؛ تعتمد النسخة على واجهات Windows الصوتية القياسية.

لمسار Microsoft Store المجاني التوقيع والاستضافة، يوجد بناء MSIX يطلب هوية Partner
Center الحقيقية واسم Rayluno وشعاره المعتمدين، ويرفض استخدام هوية تطويرية في حزمة
إنتاجية. راجع [دليل MSIX للمتجر](packaging/MSIX.md). الملف الحالي
`Rayluno.Development-1.0.0.0-x64.msix` حزمة تطوير غير موقّعة للفحص والتحميل الجانبي
فقط، وليست قابلة للرفع إلى المتجر أو مناسبة للتنزيل العام المباشر.

## وثائق إضافية / More documentation

- [المعمارية التقنية](docs/ARCHITECTURE_AR.md)
- [استراتيجية المنتج والربح](docs/PRODUCT_STRATEGY_AR.md)
- [الأمان والخصوصية](docs/SECURITY_PRIVACY_AR.md)
- [بنية الترخيص](docs/LICENSING_AR.md)
- [نظام التحديثات](docs/UPDATES_AR.md)
- [بناء MSIX لـ Microsoft Store](packaging/MSIX.md)
- [سجل جاهزية إصدار Rayluno 1.0.0](docs/RELEASE_READINESS_AR.md)
- [مراجعة مكونات الطرف الثالث](THIRD_PARTY_NOTICES.md)
