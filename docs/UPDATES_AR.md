# نظام تحديثات Rayluno Assistant الآمن على Windows

هذه الطبقة تتحقق من وجود إصدار جديد وتنزّل المثبّت إلى مسار مرحلي فقط. لا تشغّل
المثبّت، ولا تمنحه صلاحيات Administrator، ولا تستبدل ملفات التطبيق العامل. الفصل
مقصود: قرار التثبيت وعرض موافقة المستخدم والتحقق من توقيع Windows Authenticode
تظل مسؤولية طبقة تثبيت مستقلة.

في تطبيق 1.0.0 تُفعّل القناة فقط عند ضبط
`RAYLUNO_UPDATE_MANIFEST_URL` على عنوان HTTPS لبيان موقّع. إذا تُرك المتغير
فارغًا تظهر القناة «غير مهيأة» ولا يجري اتصال خلفي. لم يُبنَ بعد مثبّت Rayluno
1.0.0؛ المثبّت غير الموقّع للإصدار 0.1.0 محفوظ تحت `dist/legacy/installer` كسجل
اختبار فقط، ولا يجوز نشره على أنه إصدار Rayluno عام موثوق.

يبقى `FUTURE_ASSISTANT_UPDATE_MANIFEST_URL` alias توافقًا لبيئات البيتا القديمة؛
الإعدادات والأمثلة الجديدة تستخدم اسم `RAYLUNO_*`.

## نموذج الثقة

- التطبيق يحتوي مفاتيح Ed25519 عامة موثوقة فقط، مفهرسة بواسطة `key_id`.
- مفتاح الإصدار الخاص يبقى خارج المستودع وجهاز البناء وحزمة المنتج قدر الإمكان.
- التوقيع يغطي تمثيل JSON قانونيًا ثابتًا يضم `key_id` وكامل كائن `manifest`.
- عنوان البيان وعنوان المثبّت يجب أن يكونا HTTPS. ويُفحص العنوان النهائي بعد أي
  redirect أيضًا، لذلك لا يُقبل الرجوع إلى HTTP.
- لا يُستخدم اسم الملف أو حجم الاستجابة من الخادم كمرجع ثقة؛ الحجم وSHA-256 آتيان
  من البيان الموقّع.
- الرجوع إلى إصدار أقدم محظور افتراضيًا، والقناة والمنتج وإصدار Windows مثبتة في
  سياسة محلية لا يستطيع الخادم تغييرها.

## صيغة البيان

ملف الإدخال غير الموقّع لأداة الإصدار:

```json
{
  "schema_version": 1,
  "product": "future-assistant",
  "channel": "stable",
  "version": "1.2.0",
  "url": "https://updates.example.com/stable/Rayluno-Setup-1.2.0.exe",
  "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "size": 73400320,
  "min_os": "10.0.19041"
}
```

`version` يتبع Semantic Versioning الصارم، و`size` هو عدد البايتات الدقيق، و`min_os`
رقم Windows من ثلاثة أو أربعة مقاطع. القناة `stable` لا تقبل إصدارًا تمهيديًا مثل
`1.2.0-rc.1`. لا تُقبل حقول مجهولة أو مكررة ولا قيم JSON غير قياسية.

تبقى قيمة `product` الداخلية `future-assistant` في schema الحالي مع سياق توقيعها
بوصفها معرّف بروتوكول ثابتًا للتوافق مع البيتا السابقة، وليست العلامة المعروضة.
تغييرها داخل قناة قائمة سيجعل العملاء يرفضون البيانات الموقّعة. كذلك تبقى وحدة
Python `future_assistant` alias تقنيًا؛ اسم المنتج وملفات التنزيل الجديدة Rayluno.

الناتج الموقّع غلاف يحوي `key_id` و`manifest` و`signature` بترميز Base64. البايتات
الموقّعة هي UTF-8 للناتج التالي مع ترتيب المفاتيح، ومن دون مسافات، ومن دون تحويل
Unicode إلى escapes:

```text
{"key_id":"release-2026","manifest":{...}}
```

يجب استخدام دوال `canonical_signed_payload` و`build_signed_envelope` بدل إعادة
تنفيذ هذه القاعدة في خدمة أخرى.

## إصدار بيان موقّع

ثبّت اعتماد أداة الإصدار في بيئة المشغّل:

```powershell
python -m pip install -r tools/requirements-updates.txt
```

أنشئ مفتاح Ed25519 خارج المستودع واحفظه في مخزن أسرار أو جهاز إصدار منفصل. الأداة
ترفض مسار مفتاح داخل مجلد المشروع، ولا تنشئ المفتاح ولا تبحث عنه؛ المسار إلزامي. للمفتاح المشفّر، ضع كلمة السر
في متغير بيئة مخصص ولا تمررها في command line:

```powershell
$env:UPDATE_KEY_PASSWORD = "<read-from-a-secure-secret-store>"
python tools/sign_update_manifest.py release-manifest.json `
  --output release-manifest.signed.json `
  --private-key D:\offline-keys\update-ed25519.pem `
  --password-env UPDATE_KEY_PASSWORD `
  --key-id release-2026
```

الأداة ترفض استبدال ناتج موجود ما لم يضف المشغّل `--force`، وتمنع أن يكون مسار
الناتج هو ملف المفتاح الخاص. لا تطبع المفتاح أو كلمة سره.

## تسلسل نشر إصدار

1. ابن المثبّت النهائي ووقّعه بـ Windows Authenticode إن توفرت شهادة تجارية.
2. احسب SHA-256 والحجم بعد اكتمال كل توقيعات المثبّت؛ أي تعديل لاحق يغيّر البصمة.
3. أنشئ manifest بالقناة والإصدار و`min_os` الصحيحين.
4. وقّع manifest بمفتاح Ed25519 الخارجي باستخدام الأداة أعلاه.
5. انشر المثبّت والغلاف الموقّع على HTTPS. انشر الغلاف أخيرًا حتى لا يشير إلى ملف
   غير جاهز.
6. احتفظ بمفتاح الإصدار السابق في التطبيق أثناء نافذة تدوير المفاتيح، وأضف الجديد
   في إصدار موقّع بالمفتاح القديم قبل استخدام `key_id` الجديد.

مهم: بعد توقيع Authenticode يجب إعادة إنشاء manifest؛ بصمة المثبّت غير الموقّع لا
تطابق الملف بعد التوقيع. لا تنشر manifest تجريبيًا يشير إلى مسار محلي أو URL غير
نهائي.

## استخدام الطبقة برمجيًا

```python
from future_assistant.updates import (
    Ed25519ManifestVerifier,
    ManifestPolicy,
    SecureUpdateClient,
)
from future_assistant.product_updates import default_update_directory

verifier = Ed25519ManifestVerifier({"release-2026": PUBLIC_KEY_RAW_32_BYTES})
policy = ManifestPolicy(
    expected_product="future-assistant",
    channel="stable",
    current_version="1.1.0",
    os_version="10.0.22631",
)
client = SecureUpdateClient(
    manifest_url="https://updates.example.com/stable/manifest.json",
    verifier=verifier,
    policy=policy,
)
check = client.check()
if check.update_available:
    destination = default_update_directory() / "Rayluno-Setup-1.2.0.exe"
    staged = client.download(check, destination)
    # staged.path موثّق بالبصمة لكنه لم يُشغّل.
```

التنزيل streaming وبحد أقصى محلي، ويجب أن يساوي الحجم الموقّع بالضبط. يُكتب إلى
ملف `.part` في مجلد الوجهة، ثم تُفحص SHA-256 بمقارنة ثابتة الزمن، ثم ينفذ
`os.replace` الذري. عند أي فشل يبقى الملف المرحلي السابق دون تغيير ويُحذف الجزء
غير المكتمل.

## ضوابط التشغيل التجاري

- لا تُضمّن المفتاح الخاص في الكود أو CI logs أو المثبّت أو دعم العملاء.
- لا تجعل `allow_downgrade=True` إعدادًا يستطيع المستخدم أو الخادم تغييره؛ استخدمه
  فقط في أداة استرداد إدارية منفصلة إن لزم.
- استخدم manifest مستقلًا لكل قناة، وثبّت القناة محليًا. لا تنقل مستخدم stable إلى
  beta برسالة من الخادم.
- حدّث قائمة المفاتيح العامة بعملية تدوير معلنة، ويمكن حذف المفتاح المسروق في إصدار
  عاجل موقّع بمفتاح احتياطي محفوظ منفصلًا.
- Ed25519 يثبت أن metadata صادرة عنك وSHA-256 يثبت سلامة البايتات. Authenticode
  يضيف هوية ناشر Windows وسمعة SmartScreen؛ الآليتان متكاملتان وليستا بديلتين.

## English summary

Set `RAYLUNO_UPDATE_MANIFEST_URL` only to the production HTTPS URL of a signed
stable-channel manifest. The client verifies Ed25519 metadata, product/channel policy,
version, Windows minimum version, exact size, and SHA-256 before staging an installer.
It never executes the staged file automatically. A new Rayluno 1.0.0 installer has not
been built yet; the unsigned 0.1.0 candidate under `dist/legacy/installer` is retained
for historical verification only and must not be published as a Rayluno release.
