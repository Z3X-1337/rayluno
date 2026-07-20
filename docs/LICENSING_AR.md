# بنية الترخيص التجاري لـ Rayluno Assistant

تعتمد طبقة الترخيص على توقيع **Ed25519** غير متماثل. يحتوي تطبيق Windows على
المفتاح العام فقط، ولذلك يستطيع التحقق من الرمز لكنه لا يستطيع إنشاء ترخيص Pro
جديد أو تعديل خصائص ترخيص موجود.

توجد في 1.0.0 طريقتان للتفعيل: تثبيت رمز Ed25519 موقّع يدويًا، أو تبادل مفتاح شراء
قصير مع خدمة HTTPS المثبت عنوانها داخل العميل. المسار التجاري المخطط لنسخة
**Founders Pro بسعر 29 دولارًا مرة واحدة** هو Lemon Squeezy بوصفه Merchant of
Record، مع Microsoft Store قناة توزيع Windows. الموقع لا يزال خاصًا، ولم يُعتمد
حسابا Store وLemon Squeezy ولم يكتمل إعداد المنتج أو KYC؛ لذلك لا يوجد checkout
عام أو ترخيص
شراء حقيقي حتى الآن.

## صيغة الرمز

الرمز ملف JSON صغير وموقّع، وتوجد داخله كل الحقول التالية:

- `license_id`: معرّف فريد للترخيص.
- `edition`: إما `free` أو `pro`.
- `customer_hash`: SHA-256 صغير الأحرف لمرجع عميل ثابت، لا بريد العميل أو اسمه.
- `issued_at` و`expires_at`: ثواني Unix بتوقيت UTC.
- `device_limit`: الحد الذي يجب على خدمة التفعيل فرضه.
- `features`: قائمة مرتبة من صلاحيات المنتج، مثل `voice.premium`.

توقّع الخوارزمية والإصدار والـclaims معًا بعد تحويلها إلى JSON حتمي. يرفض المتحقق
الحقول المجهولة والمفقودة، المفاتيح المتكررة، الخوارزمية المختلفة، التوقيع المعدّل،
الترخيص المنتهي، تاريخ إصدار مستقبليًا بصورة غير منطقية، وإرجاع ساعة الجهاز إلى ما
قبل آخر وقت محلي موثوق (مع سماح افتراضي بخمس دقائق).

## فصل المفتاح الخاص

لا يوضع المفتاح الخاص في `src`، أو المثبت، أو Git، أو متغيرات بيئة جهاز العميل.
احتفظ به في مخزن أسرار/جهاز إصدار منفصل، وأنشئ المفتاح صراحةً؛ لا ينشئ المشروع
مفتاحًا افتراضيًا. مثال تنفيذي خارج عملية البناء:

```powershell
openssl genpkey -algorithm ED25519 -out C:\secure\license-private.pem
openssl pkey -in C:\secure\license-private.pem -pubout -out license-public.pem
```

يُضمّن `license-public.pem` أو بايتاته العامة فقط في تطبيق العميل. لإصدار رمز، ثبّت
إضافة الترخيص في بيئة المشغّل ثم مرّر مسار المفتاح الخاص صراحةً:

```powershell
python -m pip install -e ".[licensing]"
python tools\issue_license.py `
  --private-key C:\secure\license-private.pem `
  --license-id lic_2026_000001 `
  --edition pro `
  --customer-hash 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef `
  --expires-at 2027-07-01T00:00:00Z `
  --device-limit 2 `
  --feature automation.pro `
  --feature voice.local `
  --output .\issued\lic_2026_000001.json
```

للمفتاح المشفّر استخدم `--private-key-password-env SECRET_NAME` ولا تمرر كلمة السر
في سطر الأوامر. أداة الإصدار خارج الحزمة المنشورة، لا تبحث عن مفتاح، ولا تولّده.

## التفعيل والحدود الأمنية

1. بعد تفعيل الحساب التجاري، تتحقق الخدمة من مفتاح ترخيص Lemon Squeezy ومن حالة
   الدفع والمتجر والمنتج والـvariant المطابقين لإعداد الخادم؛ ولا تعتمد ادعاءً من
   العميل وحده.
2. ينشئ العميل UUID v4 عشوائيًا للتثبيت. لا يقرأ serial القرص أو MAC address ولا
   يبني بصمة عتاد خفية.
3. يرسل العميل مفتاح الشراء وUUID وإصدار التطبيق واللغة إلى endpoint HTTPS بلا query
   أو fragment. يرفض redirects والمنافذ غير القياسية والاستجابات الكبيرة أو JSON
   ذي الحقول المكررة.
4. تفرض الخدمة `device_limit` وتصدر lease محليًا قصير العمر موقّعًا ورمز تجديد
   معتمًا. وجود `device_limit` داخل الرمز وحده لا يستطيع منع نسخه؛ العد الفعلي يجب
   أن يبقى في الخدمة.
5. يتحقق التطبيق من رمز Ed25519 بالمفتاح العام **قبل** تمكين Pro أو حفظه ذريًا.
   الاسم العام الجديد لمجلد البيانات هو `%LOCALAPPDATA%\Rayluno`، مع التعرف على
   `%LOCALAPPDATA%\FutureAssistant` وترحيله/استخدامه كمسار توافق للبيتا السابقة كي
   لا تضيع إعدادات أو تراخيص المستخدم.
6. يخزن العميل رمز التجديد ومرجع instance محميين بـ Windows DPAPI في مجلد بيانات
   المنتج نفسه. لا يعيدهما إلى واجهة HTML/JavaScript.
7. في كل تشغيل يتحقق من التوقيع والانتهاء، ثم يرفع `last_seen_at` المخزن ولا يخفضه.
   يجدد lease في الخلفية عندما ينتهي أو يقترب من الانتهاء، ويمكن للمستخدم طلب
   التجديد يدويًا.
8. عند إزالة Pro يحذف العميل الرمز وحالة التجديد ويعود إلى استحقاقات Free.

مفتاح الشراء يُستخدم في طلب التفعيل ولا يُحفظ في إعدادات التطبيق. رمز الترخيص
الموقّع ليس سرًا، لكن مفتاح التوقيع الخاص ورمز التجديد ومفاتيح مزود الدفع أسرار.
لا يدخل أي منها—عدا رمز التجديد المحمي محليًا—إلى جهاز العميل.

أسماء `FUTURE_ASSISTANT_*` وسياقات التوقيع الداخلية التي تبدأ بـ
`future-assistant` تبقى aliases/معرّفات بروتوكول ثابتة للتوافق، وليست اسمًا معروضًا
للمنتج. الأمثلة الجديدة ودعم التشغيل العام يستخدمان `RAYLUNO_*` والأمر `rayluno`؛
لا ينبغي تغيير سياق توقيع قائم لمجرد تغيير العلامة لأن ذلك يبطل الرموز السابقة.

## Free وPro

يحتفظ التطبيق دائمًا بخط Free آمن حتى عند غياب اعتماد `cryptography` أو تلف/انتهاء
الترخيص:

- Free: `commands.basic`, `privacy.local` (أوامر مكتوبة أساسية، لا صوت دائم).
- ميزات Pro الممكنة: `ai.local`, `automation.pro`, `updates.pro`, `voice.local`.

هذه ليست أسماءً شكلية: يرفض زر الصوت `voice.local` الغائبة، لا يُستدعى Ollama بلا
`ai.local`، يتطلب التشغيل المباشر للوسائط `automation.pro`، وتتطلب قناة التحديث
`updates.pro`. إزالة الترخيص توقف الميكروفون فورًا.

الرمز الموقّع يحدد الميزات الممنوحة فعليًا؛ لا يضيف التطبيق كل ميزات Pro تلقائيًا
بسبب قيمة `edition` وحدها. هذه خاصية مهمة لإصدار خطط أو تجارب محدودة من دون تغيير
العميل.

الترخيص غير المتصل بالكامل **وسيلة ردع وليس حماية مطلقة**: مالك الجهاز يستطيع حذف
حالة الساعة، نسخ الرمز، أو تعديل البرنامج نفسه. للحماية التجارية العملية استخدم
تفعيلًا دوريًا قصيرًا عبر HTTPS، وعدّ الأجهزة في الخادم، ورموزًا محدودة العمر، مع
فترة سماح واضحة عند انقطاع الإنترنت. لا تستخدم بصمة عتاد خفية؛ اعرض للمستخدم الأجهزة
المفعّلة وسياسة الخصوصية وطريقة إلغاء جهاز قديم.

## English summary

The desktop contains only the Ed25519 public verification key. It can install a manual
signed token or exchange a purchase key with the exact production HTTPS endpoint pinned
in the frozen client. Source builds alone may opt into an explicit staging override.
The installation identifier is a random UUID, not a hardware fingerprint. The purchase
key is not persisted; the opaque refresh credential is protected with Windows DPAPI.
Every server-issued lease is verified locally before Pro is enabled, and any missing,
expired, or invalid license fails closed to typed-command Free mode.
