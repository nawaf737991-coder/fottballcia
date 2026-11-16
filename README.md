# Fottballcia — موقع كرة القدم

موقع ثابت (HTML/CSS/JS) يعمل على GitHub Pages، وبوت بايثون يحدّث بياناته تلقائيًا عبر GitHub Actions.

## هيكل المشروع

```
index.html, config.js        الموقع وإعداداته
assets/                      التصميم والسكربت
data/*.json                  البيانات (يكتبها البوت)
site_bot.py                  بوت تحديث البيانات
sports_bot.py                دوال مشتركة (وإعداد السيرفر المستمر)
.github/workflows/site.yml   الجدولة
```

## التشغيل خطوة بخطوة

1. أنشئ مستودعًا **عامًا (Public)** على GitHub، وارفع كل الملفات مع الحفاظ على المجلدات.
   (المفاتيح تُحفظ في Secrets ولا تظهر للعامة. Pages للمستودعات الخاصة تحتاج خطة مدفوعة.)
2. من **Settings ← Secrets and variables ← Actions** أضف:
   - `API_FOOTBALL_KEY`
   - `ANTHROPIC_API_KEY`
3. من **Settings ← Actions ← General ← Workflow permissions** اختر **Read and write permissions**.
4. من **Settings ← Pages**: Source = *Deploy from a branch*، والفرع `main` والمجلد `/ (root)`.
5. من تبويب **Actions** شغّل `site-data` يدويًا (Run workflow) وانتظر دقيقة ثم افتح رابط الموقع.

## الدومين

من **Settings ← Pages ← Custom domain** أضف دومينك واتبع تعليمات الـ DNS.

## مراجعة الأخبار قبل النشر

الأخبار تُنشر مباشرة افتراضيًا. للمراجعة أولًا: **Settings ← Secrets and variables ← Actions ← Variables**
وأضف `REVIEW_NEWS` = `1`. ستُحفظ الأخبار في `data/news_pending.json`؛ انسخ ما يعجبك إلى `data/news.json`.

## التحديث اللحظي (أقل من دقيقة)

GitHub Actions يحدّث المباشر كل ~10 دقايق تقريبًا. للتحديث كل 15-30 ثانية:
1. شغّل `python3 sports_bot.py loop` على سيرفر (VPS) خلف HTTPS.
2. ضع رابطه في `config.js` ← `liveEndpoint`.

## ملاحظات

- حد طلبات API-Football: الخطة المجانية 100 طلب يوميًا ولا تكفي؛ الإعداد الحالي يحتاج خطة مدفوعة.
- محتوى الصفحات يُحمَّل بجافاسكربت، فظهوره في جوجل أضعف من المواقع المولّدة مسبقًا.
- الأخبار تُكتب بالذكاء الاصطناعي من عناوين RSS وأوصافها فقط؛ راجعها دوريًا وتأكد من حقوق المصادر.
