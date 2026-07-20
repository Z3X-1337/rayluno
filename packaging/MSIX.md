# Microsoft Store MSIX

هذا المسار يبني حزمة Windows x64 غير موقّعة ومخصّصة للرفع إلى Microsoft Store.
المتجر يعيد توقيع MSIX بعد اجتياز الاعتماد، لذلك لا توزّع ناتج هذا السكربت مباشرةً
للتثبيت الجانبي أو للتنزيل العام.

This path creates an unsigned Windows x64 package for Microsoft Store submission.
The Store re-signs an accepted MSIX. Do not distribute this unsigned output for
direct sideloading or public download.

## المتطلبات

1. ثبّت Microsoft WinApp CLI 0.4.0 أو أحدث:

   ```powershell
   winget install --id Microsoft.WinAppCli --version 0.4.0 --source winget
   ```

2. ابنِ حمولة الصوت التجارية وتحقق منها:

   ```powershell
   .\scripts\build-release.ps1 -WithVoice
   .\scripts\smoke-release.ps1 -ExpectVoice -LaunchGui
   ```

   يعيد `build-msix.ps1` تشغيل `smoke-release.ps1 -ExpectVoice` بلا واجهة مباشرة قبل
   كل عملية تغليف فعلية. ملف `release-files.sha256` إلزامي حتى في وضع فحص القالب،
   ويتحقق السكربت من تغطيته الكاملة قبل إنشاء snapshot مستقل للحمولة.

3. أنشئ حساب مطور فردي من `storedeveloper.microsoft.com`، احجز الاسم النهائي، ثم
   انسخ القيم التالية حرفيًا من **Product management → Product identity**:

   - `Package/Identity/Name`
   - `Package/Identity/Publisher`
   - `Package/Properties/PublisherDisplayName`

لا تخترع قيم الهوية، ولا تستخدم هوية التطوير `Rayluno.Development` أو الاسم القديم
`Future Assistant` في أي حقل إنتاجي. انسخ هوية الإنتاج حرفيًا من Partner Center.

## فحص القالب بهوية تطوير

```powershell
.\scripts\build-msix.ps1 -DevelopmentIdentity -ManifestOnly
```

ينشئ الأمر Manifest وأصولًا تجريبية فقط تحت `build/msix/generated`. لا يحق رفعها إلى
المتجر. إصدار Rayluno الحالي `1.0.0` يطابق حزمة `1.0.0.0`، لكن هوية التطوير لا تصبح
هوية متجر صالحة مهما كان رقم الإصدار.

## بناء حزمة المتجر النهائية

```powershell
.\scripts\build-msix.ps1 `
  -IdentityName "<exact Package/Identity/Name>" `
  -Publisher "<exact Package/Identity/Publisher>" `
  -PublisherDisplayName "<exact publisher display name>" `
  -DisplayName "<reserved and cleared product name>" `
  -Description "<reviewed final English package description>" `
  -LogoSource "C:\path\to\final-square-logo.png" `
  -Version "1.0.0.0"
```

قيود الإنتاج المقصودة:

- الوصف إلزامي ولا يقبل النص التجريبي الافتراضي.
- الاسم والناشر واسم العرض والوصف وبيانات `release-build.json` لا تقبل العلامة المؤقتة.
- الشعار يجب أن يكون صورة raster صالحة، مربعة، وأبعادها `400x400` بكسل على الأقل.
- أول ثلاثة أجزاء من إصدار MSIX يجب أن تساوي إصدار التطبيق داخل `release-build.json`،
  والجزء الرابع يساوي صفرًا. الإصدار الحالي `1.0.0` يحقق بوابة الرقم بعد إعادة بناء
  حمولة Rayluno؛ وتبقى هوية Partner Center والتوقيع والاعتماد متطلبات مستقلة.
- الحمولة يجب أن تكون `commercial-local-voice` و`x64` وتنجح في smoke test المجمد.

الناتج في `dist/msix`:

- ملف `.msix` غير موقع يقبله Partner Center.
- ملف `.msixupload` موصى به للرفع ويحتوي MSIX نفسه دون رموز تصحيح.
- `msix-build-manifest.json` وفيه الحجم وSHA-256 وهوية الحزمة وبصمات حمولة المصدر.

يفحص السكربت بعد التغليف الهوية، `runFullTrust`، الميكروفون، اللغتين `ar` و`en-US`،
ملف التنفيذ و`EntryPoint`، نطاق Windows Desktop المختبر، وكل مراجع أصول المتجر والبلاطات.
كما يثبت أن كل ملف من حمولة الإصدار دخل الحزمة وأنها ما زالت غير موقعة. عند استخدام
`-SkipUploadPackage` يحذف أي `.msixupload` قديم مطابق للاسم والإصدار حتى لا يُرفع أثر قديم.

## علامة قناة التوزيع

يضيف السكربت أثناء التغليف فقط ملفًا في جذر الحزمة اسمه:

```text
.future-assistant-distribution
```

محتواه الدقيق `microsoft-store\n` في حزمة الإنتاج و`msix-sideload\n` مع
`-DevelopmentIdentity`. لا يكتب السكربت العلامة داخل `ReleaseDir` مطلقًا: ينشئ مجلد
تشغيل فريدًا تحت `build/msix`، وينسخ إليه كل ملفات الإصدار ويتحقق من SHA-256 لكل نسخة.
بعد التغليف يعيد حساب بصمة كل ملف إصدار من داخل MSIX ويقارنها بالـmanifest الموثق.
تُنشأ MSIX وMSIXUPLOAD وbuild manifest داخل output staging فريد، ولا تُرقّى إلى أسمائها
النهائية إلا بعد نجاح جميع الفحوص، مع backup وrollback عند فشل الترقية. يحذف `finally`
snapshot وoutput staging سواء نجح التغليف أم فشل.
يجب أن يعتبر التطبيق التحديثات مُدارة بواسطة Store فقط عندما يكون داخل MSIX وتكون
قيمة العلامة `microsoft-store`؛ حزمة التطوير الجانبية ليست إصدار متجر.
يفرض `-DevelopmentIdentity` عدم إنشاء `.msixupload` ويضع
`unsigned_store_submission=false` في build manifest.

## تبرير runFullTrust للاعتماد

عدّل اسم المنتج فقط في النص التالي، ولا توسّع الادعاءات من دون تغيير فعلي ومختبر في المنتج:

> The product is a user-controlled packaged Win32 personal assistant. Full trust is
> required to open only configured allowlisted desktop application identifiers and
> allowlisted HTTP/HTTPS domains on standard ports in response to user commands; access
> the local microphone and Windows speech components for opt-in voice control;
> communicate with a user-configured Ollama HTTP/HTTPS endpoint (loopback by default); and maintain per-user settings
> and signed license data. It runs only as the interactive user. It does not elevate,
> install drivers or services, execute arbitrary shell commands, change security settings,
> or bypass Windows controls. The current packaged command path exposes only reviewed,
> allowlisted actions and does not expose an arbitrary automation executor. Privacy-preserving local
> audit logging is enabled by default and can be disabled; when enabled, it stores command
> hashes and minimized action metadata rather than raw commands or URL query values.

هذه الصياغة تطابق دعم `http` و`https` الفعلي ضمن قائمة النطاقات والمنافذ المسموحة،
وتوضح أن سجل التدقيق يعمل **عندما يكون مفعّلًا** بدل الادعاء بأنه لا يمكن تعطيله.

## ما يبقى قبل الرفع

- الاسم والشعار والوصف النهائيون بعد فحص العلامة التجارية.
- هوية Partner Center الفعلية ورفع إصدار التطبيق إلى `1.0.0` أو أحدث.
- تشغيل Windows App Certification Kit واختبار الحزمة الموقعة من Store على Windows 10
  وWindows 11، خصوصًا WebView2 والميكروفون وTTS وDPAPI وOllama وفتح البرامج.
- اختبار التثبيت والترقية على جهاز أو VM نظيف.
- إعداد الدفع والسياسات والدعم قبل جعل الموقع عامًا.
