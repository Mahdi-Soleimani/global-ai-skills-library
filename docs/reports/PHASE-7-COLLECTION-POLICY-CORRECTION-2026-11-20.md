# اصلاح سیاست Collection مستقل از مجوز — GASL

تاریخ: 2026-11-20
مخزن کاری: `Mahdi-Soleimani/global-ai-skills-library`

## تصمیم قطعی

تمام Skillهای کشف‌شده باید صرف‌نظر از نوع مجوز برای Collection خصوصی دریافت شوند. مجوز MIT، Apache، GPL، CC، تجاری/اختصاصی، `NOASSERTION`، مجوز ناشناخته یا نبود فایل LICENSE نباید مانع استخراج و نگهداری خصوصی شود.

اطلاعات منشأ و حقوق شخص ثالث برای هر بسته حفظ می‌شود: نام Skill، مخزن، مسیر، URL، Commit/Tree/Blob، شناسه SPDX در صورت وجود، License/COPYING/NOTICEهای قابل بازیابی، وضعیت شواهد، انتساب و عدم ادعای مالکیت انحصاری.

Gate مجوز فقط برای انتشار عمومی محتواست؛ Collection خصوصی و Public Mirror دو مرحله مستقل هستند.

## علت مغایرت قبلی

- Workflow گزینه `--public-redistributable-only` را به `queue_ingest.py` می‌داد.
- Downloader هم در انتخاب Repository و هم در انتخاب Skill، موارد خارج از Allowlist یا فاقد مسیر License evidence را قبل از دانلود حذف می‌کرد.
- این منطق اشتباهاً شرط انتشار عمومی را به شرط اصل Collection تبدیل کرده بود.

## تغییرات اعمال‌شده

1. حذف کامل گزینه `--public-redistributable-only` از CLI و حذف فیلتر مجوز از انتخاب Repository و Skill.
2. تمام رکوردهای Queue که از نظر صحت منبع و محدودیت‌های فنی معتبرند، بدون توجه به مجوز وارد برنامه دانلود می‌شوند. محدودیت‌های امنیتی فایل همچنان برقرارند: Commit pinning، Hash، اندازه، مسیر امن، فایل عادی، عدم دنبال‌کردن Symlink، Resume و Quarantine.
3. تفکیک وضعیت‌ها در `source.json`:
   - `collection_status`: وضعیت دریافت
   - `collection_scope`: محل Collection خصوصی
   - `content_status`: وجود محتوای دریافت‌شده و Hash‌شده
   - `license_status`: وضعیت شناسایی و شواهد مجوز
   - `public_mirror_status`: صلاحیت جداگانه برای انتشار عمومی
4. `build_registry.py` و `build_source_catalog.py` این وضعیت‌ها را بدون ادغام با هم در Registry حفظ می‌کنند.
5. `config/policy.json` صریحاً `collection_requires_license_allowlist=false` را ثبت می‌کند.
6. Workflow فرمان دانلود بدون فیلتر مجوز را دارد، اما اجرای آن تا آماده‌شدن Writer آرشیو خصوصی با متغیر `GASL_PRIVATE_ARCHIVE_WRITER_READY` غیرفعال است. این Guard به‌دلیل موقتی‌بودن Runner است، نه محدودیت مجوز.
7. Metadata بسته‌های محلی موجود به مدل وضعیت جدید منتقل شد؛ محتوای اصلی Skillها دست‌نخورده ماند.

## وضعیت فعلی و اعتبارسنجی

- ۴٬۴۰۵ رکورد منبع در Queue فعلی وجود دارد؛ این اصلاح به معنی دانلودشدن همه آن‌ها نیست.
- ۶۳ بسته محلی موجود از نظر Metadata مهاجرت شدند؛ Registry مشتق‌شده ۶۲ بسته خصوصی محلی و ۹ بسته Public Mirror را گزارش می‌کند.
- بسته‌های خارج از Allowlist و بدون شواهد همچنان در Collection خصوصی باقی می‌مانند؛ فقط `public-catalog/` آن‌ها را منتشر نمی‌کند.
- تست کامل: **۱۴۰ passed، ۶ subtests passed**.
- تست‌های هدفمند Collection، Public Catalog، Registry و Source Catalog: **۲۷ passed**.
- `py_compile` برای Downloader و Builderها موفق؛ `git diff --check` موفق؛ JSON سیاست معتبر.
- جست‌وجوی کد تأیید کرد هیچ ارجاعی به `--public-redistributable-only` یا `public_redistributable_only` باقی نمانده است.
- هیچ Skill نصب یا اجرا نشد.
- هیچ Commit یا Push انجام نشد.

## مانع باقی‌مانده: ذخیره‌سازی پایدار خصوصی

مخزن فعلی `global-ai-skills-library` عمومی است و `catalog/` در `.gitignore` قرار دارد. GitHub Actions Runner موقت است؛ بنابراین دانلود تمام محتوا در Runner و پایان Workflow، آن محتوا را به‌صورت پایدار نگه نمی‌دارد. انتشار مستقیم همه محتوا در مخزن عمومی نیز صرفاً با درج نام/لینک مجاز نمی‌شود؛ انتساب، جایگزین مجوز بازتوزیع نیست.

در حساب Cloudflare متصل، درخواست R2 با خطای `10042` برگشت داده شد: R2 باید ابتدا از Dashboard فعال شود. در نتیجه هیچ Bucket فعالی برای آرشیو خصوصی در دسترس نیست.

**راه‌حل پیشنهادی:** مخزن عمومی فعلی برای کد، Source Catalog و Public Mirror واجد شرایط باقی بماند؛ آرشیو کامل همه Skillها در یک مقصد خصوصی جداگانه ذخیره شود. گزینه پیشنهادی برای ادامه، یک GitHub repository خصوصی مستقل است؛ پس از آماده‌شدن آن، Writer در GitHub Actions با Secret محدود به همان مخزن اضافه می‌شود. تا آن زمان Downloader محلی تمام مجوزها را می‌پذیرد، اما اجرای دائمی خودکار در Runner فعال نمی‌شود.

## معیار پذیرش نهایی این اصلاح

- هیچ نوع مجوزی باعث رد Collection خصوصی نشود.
- همه بسته‌ها با Source URL، Commit pin، Hash و Attribution ثبت شوند.
- انتشار عمومی فقط در Gate مستقل خودش بررسی شود.
- محتوا در مقصد خصوصی پایدار بماند و به عمر Runner وابسته نباشد.
- هیچ فایل محتوایی غیرمجاز به مخزن عمومی منتقل نشود.

## تصمیم جدید

طبق تصمیم کاربر، ایجاد آرشیو خصوصی مستقل لغو شد. معماری دریافت انتخابی از منبع اصلی و Refresh صرفاً Metadata جایگزین الزامات ذخیره‌سازی دائمی شده است. گزارش مرحله بعد: PHASE-5-7-ON-DEMAND-ARCHITECTURE-2026-11-20.md.
