# GASL — نقشه راه اجرایی و معیارهای پذیرش

**نسخه:** 1.0.0
**تاریخ تثبیت:** 2026-11-20
**مرجع:** پرونده تحویل `GLOBAL_AI_SKILLS_PROJECT_HANDOFF_2026-11-20.md` و وضعیت واقعی پوشه محلی.

این سند مرجع فعلی برنامه اجراست. فایل `ROADMAP.md` ریشه فقط به این سند اشاره می‌کند؛ نسخه قبلی در `docs/archive/` حفظ شده است.

## هدف نهایی

ساخت کتابخانه‌ای مستقل و قابل توسعه برای کشف، دریافت، نگهداری، اعتبارسنجی امنیتی، ارزیابی عملی، جست‌وجو و نصب انتخابی AI Agent Skills؛ با منشأ قابل ردیابی، نسخه Pin‌شده، مجوز روشن و انتخاب متناسب با وظیفه و Agent.

## اصول غیرقابل‌مذاکره

1. چهار منبع `EN-675`، `FA-234`، `AUX-FA-750PLUS` و `AUX-FA-438` مستقل می‌مانند.
2. هیچ رکورد خامی حذف، ترجمه، ادغام یا بازنویسی نمی‌شود. Cross-reference مخازن، مجوز ادغام Skill records نیست.
3. ۶۷۵ و ۲۳۴، ادعاهای گزارش‌های تحقیقاتی هستند؛ فایل‌های اصلی CSV/JSON/XLSX هنوز بازیابی نشده‌اند و نباید بازسازی شوند.
4. اعداد ۷۵۰+ و ۴۳۸ نیز جایگزین دیتابیس کامل یا تعداد فایل‌های CSV نیستند.
5. Download ≠ Trust ≠ Security Approval ≠ Install ≠ Execution.
6. هر دریافت باید به Commit SHA، فایل‌های کامل و Hashهای SHA-256 متصل باشد.
7. هر Skill کشف‌شده، مستقل از نوع مجوز، در کاتالوگ عمومی با منشأ و انتساب ثبت شود. دریافت انتخابی مستقیم از منبع، بدون فیلتر نوع مجوز و با رعایت شرایط دسترسی انجام می‌شود؛ آرشیو خصوصی دائمی لازم نیست. Gate بازتوزیع عمومی جداگانه است.
8. اجرای کد دانلودشده روی Host ممنوع است. Dynamic validation فقط با Sandbox واقعاً enforce‌شده مجاز است؛ در غیر این صورت `needs_validation` ثبت می‌شود.
9. نصب سراسری یا بارگذاری همه Skillها در Context ممنوع؛ فعال‌سازی باید انتخابی و Progressive Disclosure باشد.
10. تمام پیشرفت‌ها، تغییرات، تست‌ها و تصمیم‌ها زیر `docs/reports/` مستند می‌شوند.

## وضعیت پایه تأییدشده

| شاخص | مقدار / وضعیت |
|---|---|
| منابع مستقل | ۴ |
| آرشیو محلی گزارش‌ها | ۴ از ۴؛ Hash تأییدشده |
| اشاره‌های Repository در چهار Manifest | ۸۷ |
| مراجع متمایز | ۵۶ |
| Canonical GitHub repositories در Snapshot تاریخی | ۵۵ |
| Targetهای Refresh فعلی | ۵۷ (۵۵ تاریخی + ۲ منبع جدید) |
| مسیرهای مشاهده‌شده SKILL.md | ۴٬۴۷۸ |
| مسیرهای معتبر وارد Source Catalog | ۴٬۴۰۵ |
| Source Catalog | ۴٬۴۰۵ رکورد، همگی Commit-pinned |
| Public Catalog | ۹ بسته، ۱۱۹ فایل، ۶۶۴٬۴۶۶ بایت |
| بسته‌های Pilot محلی | ۶۳ |
| رکوردهای Manifest دانلود | ۷۱ |
| فایل‌های Pilot محلی | ۶۴۰ |
| کل فایل‌های Manifest | ۷۵۷ |
| حجم Pilot محلی | ۱۳٬۵۸۳٬۸۸۹ بایت |
| حجم Manifest | ۱۴٬۲۲۹٬۸۸۳ بایت |
| طبقه‌بندی Registry | ۵۹ Skill candidate + ۴ test fixture |
| بسته‌های نیازمند بررسی دستی | ۱۰؛ شامل ۹ candidate و ۱ fixture |
| High-confidence static signals | ۲؛ بررسی دستی باز |
| تأیید نصب / نصب / اجرای کد | صفر / صفر / صفر |
| تست پروژه | ۱۴۳ PASS + ۶ زیرتست |

این اعداد به Snapshot محلی مورخ 2026-11-20 تعلق دارند؛ تعداد Skillهای یکتای جهانی را اثبات نمی‌کنند.

## فازها و معیارهای پذیرش

### فاز 0 — Read-only Baseline Audit

**وضعیت: تکمیل‌شده.** مسیر محلی، ساختار، منابع، گزارش‌ها، Collection، وضعیت امنیت و نبود Git metadata ثبت شد. سپس URL مخزن GitHub بررسی شد: مخزن Public، شاخه پیش‌فرض `main` و بدون Commit/Branch بود.

**معیار پذیرش:** Baseline قابل بازتولید، بدون حذف یا تغییر داده‌های اصلی. گزارش: `docs/reports/PHASE-0-BASELINE-2026-11-20.md`.

### فاز 1 — Source Manifest و قفل منشأ

**وضعیت: آرشیو و Manifest تأیید شده‌اند؛ بازیابی دیتابیس‌های اصلی همچنان باز است.**

- حفظ چهار Source ID مستقل و ثبت نام، اندازه، SHA-256، آمار ادعایی و وضعیت Artifactها.
- آرشیو چهار گزارش اصلی به‌صورت Byte-for-byte در پوشه خصوصی محلی.
- حفظ فایل‌های خام Read-only؛ ثبت Duplicate فایل گزارش به‌عنوان Duplicate فایل، نه Duplicate Dataset.
- تکمیل Cross-reference مخازن بدون اتصال Skill records به یکدیگر.
- حذف شناسه‌های داخلی Library از نسخه عمومی Manifest؛ نگهداری آن‌ها در فایل محلی Private.

**معیار پذیرش:** هر چهار منبع با Hash معتبر و مسیر بازیابی محلی؛ Manifest عمومی بدون شناسه‌های حساب‌محور؛ هیچ Dataset ادغام یا بازنویسی نشده باشد.

### فاز 2 — ممیزی Cloudflare Security Audit

**وضعیت: بازبینی ایستای دستی انجام شده؛ Gate نهایی باز است.**

- Commit دقیق `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` و License نوع MIT ثبت شده است.
- ۲۰ فایل با مجموع ۳۱۴٬۶۷۰ بایت و Hashهای SHA-256 تطبیق داده شده‌اند.
- ۱۲ هشدار Static Scanner بررسی اولیه شده‌اند؛ همگی `spawnSync` در دو فایل Test Harness هستند.
- کد اصلی Validatorها از نظر مسیر ورودی، محدودیت اندازه، فایل عادی، No-follow و نبود شبکه/Secret access بازبینی ایستا شده است.
- هیچ فایل تست یا اسکریپت اجرا نشده است. محیط Sandbox منطبق با الزامات Skill هنوز فراهم/تأیید نشده است.

**معیار پذیرش:** گزارش قابل بازتولید، بررسی دستی همه هشدارها، تصمیم مجزا درباره نصب و اجرا؛ بدون اجرای ناخواسته. گزارش: `docs/reports/PHASE-2-CLOUDFLARE-SECURITY-REVIEW-2026-11-20.md`.

### فاز 3 — Crosswalk و Source Reconciliation

**وضعیت:** Crosswalk در سطح Repository و مسیرهای Snapshot ساخته شد: ۸۷ ارجاع، ۵۵ مخزن canonical، ۴٬۲۱۴ مسیر و ۶۳ بسته محلی. تطبیق دقیق رکوردهای تحقیقاتی به‌دلیل نبود دیتابیس‌های اصلی، و اثبات Fork/Mirror و تطبیق کامل بسته‌ها هنوز باز است. گزارش: `docs/reports/PHASE-3-CROSSWALK-2026-11-20.md`.

- تطبیق Source Recordها با Repository، Path و Publisher در سطحی که شواهد منبع اجازه می‌دهد.
- ساخت `CROSS_REFERENCE` و `DUPLICATE_CANDIDATES`.
- مقایسه محتوای نرمال‌شده برای Duplicate واقعی؛ تفکیک Fork، Mirror، نسخه و Skill هم‌نام متفاوت.
- ثبت تناقض‌ها و اختلاف آمار؛ عدم حذف Source Records.

**معیار پذیرش:** هر Canonical Candidate به تمام Source Recordهای پشتیبان ارجاع دهد و هیچ داده اصلی حذف نشود.

### فاز 4 — Source Discovery و Repository Expansion

**وضعیت:** تکمیل شد. اجرای موفق GitHub Actions هر ۵۷ مخزن را با صفر خطا Refresh کرد؛ ۴٬۴۷۸ مسیر مشاهده و ۴٬۴۰۵ رکورد commit-pinned وارد Source Catalog شد. ۹ بسته واجد شرایط با ۱۱۹ فایل و ۶۶۴٬۴۶۶ بایت به Public Catalog اضافه و به main Commit شدند. Commit نهایی: 83c1031. اجرای روزانه، دستی و trigger بر اساس تغییر کد/تنظیمات فعال است.

ادامه Checkpointهای مستقل: EN-675 (awesome-copilot، NVIDIA، Microsoft، Anthropic verticals)؛ FA-234 (Microsoft، skills.sh، SkillsMP، Database Vendors و منابع غیرانگلیسی)؛ SUP-750 (AWS HCLS، phuryn، NVIDIA H-Z، Adobe، Google DeepMind، Agriculture/Manufacturing/Logistics، Tencent/Japan)؛ SUP-438 (Databricks، Salesforce، NVIDIA، Microsoft SDKها، phuryn و حوزه‌های کم‌پوشش).

**معیار پذیرش:** هر مورد جدید Source، Path، Commit یا Snapshot، تاریخ و وضعیت Extraction داشته باشد؛ موارد قبلی دوباره‌کاری نشوند.

### فاز 5 — Downloader و Ingestion Pipeline

**وضعیت:** Pilot محلی ۶۳ بسته و ۹ بسته عمومی قبلی حفظ شده‌اند. Downloader با Commit/Tree/Blob pin و Resume/Hash/Quarantine کار می‌کند. معماری جدید دریافت انتخابی را با gasl get (SKILL.md) و gasl download (طرح/دریافت بسته کامل محلی) ارائه می‌کند؛ هیچ مخزن خصوصی اجباری نیست. دریافت کامل روی Windows و پشتیبانی از ساختارهای استثنایی هنوز باز است.

- دریافت بسته منتخب از منبع اصلی با Commit ثابت، بدون فیلتر نوع مجوز.
- محدودیت حجم، مسیر ایمن، Hash و نگهداری License/COPYING/NOTICE.
- کش و Manifest محلی اختیاری، خارج از Git.
- عدم نصب یا اجرای خودکار.

**معیار پذیرش:** Pilot سه مخزن قبلاً موفق؛ تست‌های مسیر دریافت انتخابی، Resume و عدم تغییر Manifest عمومی اضافه شده‌اند. گزارش اصلاح معماری: docs/reports/PHASE-5-7-ON-DEMAND-ARCHITECTURE-2026-11-20.md.

### فاز 6 — Validator و Security Pipeline

**فاز ۴۶ — تفکیک شواهد محلی از اصالت منبع و مقایسه نسخه‌های Codex:** فرمان provenance-compare با selected-root و skill-name گزارشی کاملاً فقط‌خواندنی از نسخه فعال و Backupهای تأییدشده تولید می‌کند؛ دو نسخه دلخواه را نیز با left و right (شناسه ۳۲ کاراکتری Backup یا active) از نظر اثرانگشت SHA-256 فهرست فایل‌ها، تعداد فایل‌های افزوده/حذف/تغییریافته و یکسان‌بودن شناسه Plan ثبت‌شده مقایسه می‌کند. اطلاعات از Receipt/Manifest محلی و بازبینی فاز ۴۵ استخراج می‌شود؛ تأیید محلی هش، به معنای احراز مالکیت تاریخی، اصالت مخزن و Commit اصلی، مجوز نرم‌افزار یا ایمنی دستورهای Skill نیست. تمام بررسی‌های Upstream صریحاً not_checked گزارش می‌شوند؛ هیچ درخواست شبکه یا اجرای Skill انجام نمی‌شود. هشدار مالکیت تأییدشده به‌صورت دستی، حتی پس از چند Restore/Reinstall، با بازخوانی امن زنجیره Backupها باقی می‌ماند. خروجی پیش‌فرض متنی و خروجی JSON پشتیبانی می‌شوند و مسیر واقعی پروژه یا محتوای فایل‌ها افشا نمی‌شوند. CI Linux و نتیجه نهایی تست‌ها پس از انتشار در گزارش جداگانه ثبت خواهد شد. گزارش: docs/reports/PHASE-46-OFFLINE-CODEX-PROVENANCE-COMPARISON-2026-11-23.md.

**فاز ۴۵ — UX یکپارچه بازبینی و بازیابی Backup در Codex:** فرمان جدید backup-review با selected-root و skill-name سه حالت Skill نصب‌شده با Receipt، Skill حذف‌شده با Ownership Marker و Backup قدیمی بدون Marker را به‌صورت فقط‌خواندنی شناسایی و فهرست می‌کند. خروجی انسانی پیش‌فرض، وضعیت، شناسه دقیق نسخه، تعداد فایل، منشأ ثبت‌شده (نه ادعای تأیید دوباره Upstream)، اعتبار هش فایل، شواهد مالکیت، خطرات و اثر بازیابی را نشان می‌دهد؛ format=json خروجی ساختاریافته می‌دهد. با backup-id فقط Preview همان نسخه و فرمان درست موجود را با Binding دقیق می‌دهد؛ هیچ فرمان جدید نصب یا حذف ایجاد نشده و تأیید تعاملی TTY فازهای قبل همچنان الزامی است. برای Backupهای قدیمی مالکیت تاریخی همچنان غیرقابل‌اثبات گزارش می‌شود؛ در صورت نصب قبلی با اقرار دستی، این هشدار باقی می‌ماند. حالت‌های خطادار و تراکنش نیمه‌تمام بدون حدس‌زدن نسخه یا اجرای Recovery اعلام می‌شوند. مسیر کامل محلی پروژه در خروجی افشا نمی‌شود و هیچ پروفایل یا پروژه واقعی برای تست تغییر نکرد. ۲۳ تست اختصاصی، ۵۷۲ تست محلی و ۲۳۶ زیرتست موفق بودند؛ آزمون واقعی Codex در Linux (Run 45205397207)، ایمنی ZIP/Installer (Run 45205396762) و اجرای کامل ۵۷۸ تست در Refresh کاتالوگ (Run 45205396708) همگی موفق‌اند؛ ۵۷ مخزن و ۴۴۳۱ رکورد تأیید شدند. گزارش: docs/reports/PHASE-45-UNIFIED-CODEX-BACKUP-REVIEW-UX-2026-11-23.md.

**فاز ۴۴ — بازیابی کنترل‌شده Backupهای قدیمی بدون Ownership Marker:** ابزارهای audit-legacy-backups، preview-legacy-reinstall و reinstall-legacy-backup اضافه شدند. ابزار به‌صورت فقط‌خواندنی پوشه‌های Backup، هش SHA-256 همه فایل‌ها، Manifestها، نام ایستای SKILL.md و زنجیره تاریخی نسخه‌ها را ارزیابی می‌کند؛ اتصال Backup به پروژه اصلی قبل از فاز ۴۳ به‌صورت رمزنگاری‌شده قابل اثبات نیست و **تأیید مالکیت تاریخی ادعا نمی‌شود**. نصب مجدد فقط در Git Project صریح با مسیر خالی، تأیید تعاملی TTY و عبارت دقیق اقرار کاربر به مالکیت امکان دارد. رسید جدید از نوع unmanaged با شناسه محلی مصنوعی و پرچم historical_project_ownership_verified=false ثبت می‌شود. Journal و Recovery تغییرات ناتمام را فقط با تطبیق کامل فایل‌ها بازیابی می‌کنند. Backupها مصرف یا حذف نمی‌شوند؛ Uninstall بعدی مالکیت را در قالب Marker فاز ۴۳ ثبت می‌کند. وجود تاریخچه قدیمی حل‌نشده مانع نصب تازه یا جایگزینی معمولی است. ۱۲۳ تست متمرکز و ۵۴۹ تست کلی + ۲۳۶ زیرتست محلی موفق‌اند؛ Codex واقعی روی پروژه موقت macOS نیز بازیابی تأییدشده دستی را شناسایی کرد. CI واقعی Codex در Linux (Run 45201198006)، ایمنی ZIP (Run 45201197796) و اجرای کامل ۵۵۵ تست در Refresh کاتالوگ (Run 45201197849) موفق شدند؛ ۵۷ مخزن و ۴۴۳۱ رکورد تأیید شدند. گزارش: docs/reports/PHASE-44-ATTESTED-LEGACY-CODEX-BACKUP-RECOVERY-2026-11-23.md.

**فاز ۴۳ — بازیابی Skill پس از Uninstall کامل در Codex:** عملیات list-uninstalled-backups، preview-reinstall و reinstall-backup اضافه شد. Uninstall از این پس نسخه فعال را نیز با Rename اتمیک در Backup محلی پروژه نگه می‌دارد و یک Ownership Marker وابسته به هش مسیر پروژه، رسید نصب قبلی و زنجیره کامل Backupها ثبت می‌کند؛ از دید Codex پوشه Skill حذف شده و دیگر شناسایی نمی‌شود. در بازیابی، فهرست Backupها و Preview فقط خواندنی‌اند؛ مقصد باید خالی باشد، همه هش‌ها و Manifestها دوباره بررسی شوند و تأیید تعاملی مستقل در TTY ثبت شود. Skill از Backup انتخابی بدون اجرای کد و بدون مصرف نسخه تاریخی در Stage جدید کپی می‌شود، بعد Receipt مدیریت‌شده و تاریخچه قبلی بازسازی می‌شوند. Journal جدید قطع عملیات Uninstall یا Reinstall را با Rollback یا تکمیل Commit معتبر بازیابی می‌کند و در حالت مبهم یا فایل دستکاری‌شده از حذف داده ناشناخته خودداری می‌کند. Backupهای باقی‌مانده از Uninstallهای قبل از این فاز که Marker ندارند، بدون بازبینی و تأیید مالکیت قابل بازیابی خودکار نیستند. تست‌های متمرکز ۱۰۳ مورد و کل مجموعه محلی ۵۲۹ تست + ۲۳۶ زیرتست موفق؛ آزمون واقعی Codex روی macOS و Linux CI (Run 45195556931)، ایمنی ZIP (Run 45195556905) و اجرای کامل ۵۳۵ تست Python همراه با Refresh کاتالوگ (Run 45195556925) همگی موفق بودند. هیچ Skill شخص ثالث اجرا و هیچ پروفایل واقعی کاربر تغییر نکرد. گزارش: docs/reports/PHASE-43-CODEX-UNINSTALLED-SKILL-REINSTALL-2026-11-23.md.

**فاز ۴۲ — بازگردانی تعاملی Backup پس از ارتقای موفق:** سه عملیات list-backups، preview-restore و restore-backup برای Host نوع Codex با Scope پروژه اضافه شد. فهرست و Preview فقط خواندنی‌اند و شناسه Backup، منشأ نسخه و Binding وابسته به مسیر پروژه، Receipt فعال، هش فایل‌ها و Manifestهای همه نسخه‌های قبلی را نمایش می‌دهند. بازگردانی فقط با تأیید مستقیم و عبارت دقیق در TTY اجرا می‌شود. فایل‌های Backup انتخابی در Stage مستقل کپی و هش‌ها دوباره تأیید می‌شوند؛ نسخه فعال با Rename اتمیک در Backup جدید ذخیره می‌شود و بعد از فعال شدن نسخه بازیابی‌شده، Receipt جدید Commit می‌شود. همه نسخه‌های تاریخی و Backup تازه حفظ می‌شوند. Recovery تراکنش قطع‌شده را تا قبل از Commit به نسخه فعال قبل برمی‌گرداند یا Commit کامل‌شده را تأیید می‌کند، بدون حذف فایل دستکاری‌شده یا اطلاعات ناشناخته. Backupهای قدیمی بدون منشأ GASL نیز قابل بازگردانی هستند اما با شناسه محلی مصنوعی و برچسب «unmanaged» ثبت می‌شوند، نه با ادعای Source Pin‌شده. آزمون‌های محلی و Codex واقعی روی پروژه Git موقت macOS موفق‌اند؛ اجرای CI Linux پس از Push باید در گزارش ثبت شود. هیچ Skill دانلودشده اجرا نشد و HOME واقعی یا پروژه‌های کاربران تغییر نکرد. گزارش: docs/reports/PHASE-42-CODEX-COMMITTED-BACKUP-RESTORE-2026-11-23.md.

**فاز ۴۱ — جایگزینی Skill موجود با Backup کامل و Recovery تراکنش:** عملیات preview-replace و replace به codex-project-install اضافه شد. مقصد و نسخه Pin‌شده پیش از تأیید دوباره بررسی می‌شوند؛ نسخه قبلی با Rename اتمیک در .gasl-managed/backups/<skill>/<backup-id> نگهداری می‌شود، Inventory هش‌شده و Receipt قبلی آن در Manifest ثبت می‌شود و Receipt نسخه جدید تنها پس از فعال‌سازی موفق به‌صورت اتمیک جایگزین می‌شود. Journal قطع عملیات را در نقاط قبل از Backup، بعد از انتقال نسخه قبلی، بعد از فعال‌سازی نسخه جدید و بعد از Commit پوشش می‌دهد؛ Recovery فقط در صورت تطابق کامل فایل‌ها، نسخه قبلی را برمی‌گرداند یا Commit معتبر را نهایی می‌کند و در حالت مبهم هیچ فایل ناشناخته‌ای را حذف نمی‌کند. Backupهای قبلی در ارتقاهای بعدی و Uninstall حفظ و دوباره اعتبارسنجی می‌شوند. ۲۹ تست اختصاصی محلی و آزمون Codex واقعی روی macOS برای جایگزینی، نگهداری Backup، قطع عمدی، بازیابی نسخه قبلی، ارتقای مجدد و حذف موفق‌اند. هیچ پروژه واقعی کاربر یا User HOME تغییر نکرد. CI جدید Linux پس از Push باید اجرا و نتیجه در گزارش ثبت شود. نصب User Scope و فرمان Restore دستی Backup بعد از Upgrade موفق هنوز خارج از محدوده است. گزارش: docs/reports/PHASE-41-CODEX-PROJECT-REPLACEMENT-BACKUP-RECOVERY-2026-11-23.md.

**فاز ۴۰ — نصب انتخابی واقعی Skill در پروژه Codex با تأیید تعاملی:** فرمان `codex-project-install` برای Preview بدون تغییر، نصب واقعی **فقط در مقصد خالی**، حذف نسخه مدیریت‌شده و بازیابی تراکنش قطع‌شده اضافه شد؛ همه عملیات روی پروژه Git با مسیر صریح انجام می‌شوند و برای نصب/حذف، تأیید متنی در TTY لازم است. وضعیت مقصد و ZIP/Source Pin‌شده دوباره کنترل می‌شود، فایل‌ها بیرون از مسیر کشف Codex Stage می‌شوند و Journal/Receipt محلی ذخیره می‌شود. آزمون نصب/شناسایی/حذف با Codex واقعی در پروژه موقت هم روی macOS و هم Ubuntu CI (Run `45181942150`) موفق شد؛ CI کامل ۴۷۹ تست (Run `45181942126`) و Workflow ایمنی ZIP (Run `45181941968`) نیز موفق بودند. در پروژه شخصی کاربر نصب نشده است. جایگزینی نسخه قبلی و Backup آن در فاز ۴۱ اضافه شد؛ نصب واقعی User HOME هنوز پیاده‌سازی نشده است. گزارش: `docs/reports/PHASE-40-OPT-IN-CODEX-PROJECT-INSTALL-2026-11-23.md`.

**فاز ۳۹ — آزمون End-to-End بسته کامل و Pin‌شده با Codex واقعی:** فرمان `codex-pinned-bundle-e2e` تمام زنجیره بررسی Source/ZIP/Format، Preflight بدون تغییر، بررسی Binding مقصد، تراکنش قفل‌دار نصب موقت فایل‌های ZIP و Rollback را در یک HOME تازه و کاملاً موقت به `skills/list` Codex واقعی متصل کرد. بسته اصلی سه‌فایلی `python-mcp-server-generator` روی مک با Codex `0.167.0` شناسایی و پس از Rollback حذف آن تأیید شد؛ نسخه ساختگی دو‌فایلی نیز موفق بود. تست‌های محلی: ۴۵۹ تست و ۲۳۶ زیرتست موفق؛ CI واقعی Linux برای بسته کامل آزمایشی در Run `45172898331` موفق و اجرای کامل ۴۶۵ تست در Run `45172898207` نیز موفق شد. هیچ کد Skill اجرا و هیچ فایل Agent واقعی تغییر نکرد. نصب Production همچنان غیرفعال است. گزارش: `docs/reports/PHASE-39-PINNED-FULL-BUNDLE-CODEX-E2E-2026-11-23.md`.

**فاز ۳۸ — بازبینی ایستای فرمت Skill برای Hostهای مختلف:** فرمان `host-format-review` روی ZIP خصوصی Pin‌شده، بدون استخراج فایل یا اجرای کد، یکپارچگی ZIP، Git Blob و Source Catalog را دوباره بررسی می‌کند و ساختار پایه Frontmatter را برای Codex، Cursor و Claude Code ارزیابی می‌کند. گزارش در هر سه Host برای نمونه `python-mcp-server-generator` موفق بوده؛ این نتیجه به‌معنای تأیید Discovery واقعی Cursor/Claude Code نیست. نصب دائمی و اجرای Skill همچنان غیرفعال است؛ ۴۵۰ تست و ۲۳۲ زیرتست مستقل از وابستگی اختیاری MCP موفق‌اند. گزارش: `docs/reports/PHASE-38-CROSS-HOST-STATIC-FORMAT-REVIEW-2026-11-23.md`.

**فاز ۳۷ — تأیید واقعی Skill شخص ثالث در Codex روی macOS و Linux:** فایل `SKILL.md` مهارت `python-mcp-server-generator` با Git Blob و ZIP Hash ثابت کنترل شد. Codex CLI واقعی نسخه `0.167.0` روی مک و نسخه `0.162.1` در Ubuntu CI فایل را در HOME موقت به‌عنوان Skill فعال شناخت؛ پس از Rollback، نبود Skill و حذف پروفایل موقت تأیید شد. Workflow دستی GitHub Actions با Run `45166176466` و نتیجه `success` کامل شد. هیچ Model Turn، دستور Skill، نصب Dependency یا تغییر پروفایل اصلی انجام نشد. نصب دائمی و اجرا همچنان غیرفعال‌اند. گزارش: `docs/reports/PHASE-37-REAL-THIRD-PARTY-CODEX-DISCOVERY-2026-11-23.md`.

**فاز ۳۶ — آزمون Discovery واقعی Skill شخص ثالث در Codex با HOME موقت:** اسکریپت `tools/codex_third_party_discovery.py` و Workflow دستی و approval-gated اضافه شد. پس از تأیید صریح، فقط `SKILL.md` دقیق و Blob-Pinned در `HOME/.agents/skills` موقت کپی می‌شود؛ Codex فقط `initialize` و `skills/list` را قبل/بعد/پس از Rollback دریافت می‌کند. فایل حذف و HOME موقت پاک می‌شود. هیچ Model Turn، اجرای دستور Skill، نصب Dependency، Credential، پروفایل واقعی یا نصب دائمی وجود ندارد. تست Fake Host: ۸ تست و ۳ زیرتست موفق؛ کل تست‌ها ۴۴۵ و ۲۲۶ زیرتست موفق. در زمان نگارش گزارش فاز ۳۶، Workflow هنوز اجرا نشده بود؛ اجرای موفق بعدی در گزارش فاز ۳۷ ثبت شده است. گزارش تاریخی: `docs/reports/PHASE-36-THIRD-PARTY-CODEX-DISCOVERY-ONLY-2026-11-22.md`.

**فاز ۳۵ — تشخیص Package Runnerهای بدون نسخه و انتخاب Python MCP Skill:** قاعده `UNPINNED_REMOTE_PACKAGE_EXECUTION` برای `npx`، `pnpm dlx`، `bunx`، `yarn dlx`، `npm exec` و `npm create` اضافه شد؛ نسخه دقیق SemVer و مسیر محلی مستثنا هستند. سه هشدار در `typescript-mcp-server-generator` یافت و ZIP قدیمی آن حذف شد. Candidate مناسب‌تر `python-mcp-server-generator` از `github/awesome-copilot` با Commit/Blob دقیق، مجوز MIT، سه فایل سالم و اسکن صفر یافته انتخاب و در ZIP خصوصی با SHA-256 `8870d46717fe6a44589020556432f3c79c10cbb07364c4de48d0fe21c1f05367` آماده شد. `uv`، Python و Node محلی تأیید شدند. نصب/اجرا انجام نشده؛ آزمون Codex فقط `initialize` و `skills/list` در HOME موقت و Rollback، منوط به تأیید صریح کاربر است. گزارش: `docs/reports/PHASE-35-UNPINNED-PACKAGE-EXECUTION-AND-PYTHON-MCP-CANDIDATE-2026-11-22.md`.

**فاز ۳۴ — تشخیص ریسک‌های Code Generation و سرورهای توسعه:** سه قاعده جدید اسکن برای درج مستقیم `description` در کد تولیدی، CORS با مبدأ `*` و Bind ناخواسته Node بدون Host اضافه شدند؛ فایل‌های TypeScript/JSX نیز اسکن می‌شوند. اسکن بدون تغییر فایل در `mcp-server-builder` دو سیگنال و `chatgpt-apps` سه سیگنال یافت. هر دو اکنون `manual_review_required` هستند و `install-plan` و ساخت ZIP جدید را مسدود می‌کنند. ZIP خصوصی قدیمی فقط از نظر تمامیت قابل تأیید است، نه امنیت یا نصب. گزارش: `docs/reports/PHASE-34-STATIC-CODEGEN-CORS-NETWORK-BIND-2026-11-22.md`.

**فاز ۳۳ — انتخاب و آماده‌سازی اولین Skill کاربردی MCP:** `mcp-server-builder` از `alirezarezvani/claude-skills` با MIT، Commit/Blobهای Pinشده و ۱۰ فایل سالم بررسی شد؛ اسکن اولیه ۰ یافته داشت اما فاز ۳۴ دو ریسک تولید کد یافت و نصب این Candidate را مسدود کرد. دو اسکریپت فقط OpenAPI را در مسیر خروجی انتخابی به اسکفولد تبدیل می‌کنند و Manifest محلی را اعتبارسنجی می‌کنند؛ شبکه، subprocess و دسترسی به Credential ندارند. ZIP خصوصی آماده و Verify شد اما نصب نشده است. آزمون اولیه Codex پس از تأیید کاربر فقط `skills/list` خواهد بود و هیچ اسکریپتی اجرا نمی‌شود. تست‌های CI کد و Codex در Commit `1189202` موفق شدند (Runهای `45074583955` و `45074583807`). گزارش: `docs/reports/PHASE-33-MCP-SERVER-BUILDER-CANDIDATE-REVIEW-2026-11-22.md`.

**فاز ۳۲ — بررسی مجوز و امنیت اولین Skill واقعی:** بسته خصوصی `academy-guide` از مخزن `anthropics/skills` در Commit دقیق Pin شد؛ Git Blob هر دو فایل و SHA-256 بسته تأیید شدند. فایل مجوز اختصاصی، Apache-2.0 و Copyright Anthropic را مشخص می‌کند؛ اسکن آفلاین ۰ یافته دارد و بسته فقط Markdown/License است. تنها رفتار شبکه‌ای، خواندن Catalog عمومی Claude Academy در صورت مرتبط بودن است. سازگاری Codex هنوز با همین Skill آزمایش نشده و رضایت نصب کاربر دریافت نشده است؛ هیچ نصب/اجرایی انجام نشد. گزارش: `docs/reports/PHASE-32-ACADEMY-GUIDE-LICENSE-SECURITY-REVIEW-2026-11-22.md`.

**فاز ۳۱ — کشف واقعی Codex در Scope کاربری با HOME مستقل:** مسیر مستند رسمی `~/.agents/skills/` با Codex App Server واقعی آزمایش می‌شود؛ HOME و CODEX_HOME هر دو موقت، خالی و مستقل هستند. آزمون سه مشاهده پیش از نصب، پس از نصب آزمایشی و پس از Rollback را برای Scope کاربری انجام می‌دهد و رسید فاز ۳۰ را هم یک‌بار مصرف می‌کند. هیچ فایل HOME یا Skill شخصی توسعه‌دهنده خوانده/تغییر داده نمی‌شود؛ تأیید CI شبیه‌سازی است، نه رضایت انسانی. تست واقعی GitHub Actions در Run `45073141936` با Codex `0.162.1` برای هر دو Scope موفق شد؛ User Scope، مصرف رسید و Rollback واقعی تأیید شدند. گزارش: `docs/reports/PHASE-31-CODEX-ISOLATED-USER-SCOPE-2026-11-22.md`.

**فاز ۳۰ — رسید تأیید یک‌بارمصرف و زمان‌دار برای نصب آزمایشی:** ماژول `fixture_explicit_consent.py` درخواست مستقل مرتبط با Hash بسته، Plan ID، مسیر مقصد موقت، Agent، Scope و عملیات نصب/جایگزینی می‌سازد؛ عبارت تأیید دقیق، انقضای ۳۰ تا ۳۰۰ ثانیه، HMAC محلی و مصرف یک‌باره زیر قفل فاز ۲۸ اضافه شدند. `gasl consent-fixture-interactive` فقط از ترمینال واقعی و پس از تایپ عبارت تأیید، فایل‌ها را در پروفایل موقت خود GASL نصب و Rollback می‌کند. CI فقط تأیید را **شبیه‌سازی** می‌کند، نه رضایت واقعی انسان. تست روی ZIP واقعی خصوصی `academy-guide` در دو سناریوی نصب تازه/ارتقا Pass شد؛ هیچ فایل شخصی Agent یا Skill ثالثی اجرا/نصب دائمی نشد. گزارش: `docs/reports/PHASE-30-ONE-TIME-FIXTURE-CONSENT-2026-11-22.md`.

**فاز ۲۹ — کشف واقعی Skill پس از نصب و حذف تراکنشی در Codex:** یک آزمون end-to-end با پروفایل کاملاً موقت، ZIP بی‌ضرر تألیفی GASL و چرخه فاز ۲۸ ساخته شد. با باینری واقعی Codex App Server سه مشاهده مستقل `skills/list` انجام می‌شود: نبود Skill پیش از نصب، ظاهرشدن Skill فعال با مسیر دقیق پس از نصب Fixture، و ناپدیدشدن آن پس از Rollback. هیچ درخواست مدل، ورود به حساب، نصب در پروفایل واقعی، یا اجرای Skill ثالث وجود ندارد. Workflow اختصاصی Ubuntu Codex CLI نسخه Pin‌شده `0.162.1` را فقط در پوشه موقت Runner نصب می‌کند؛ نتیجه واقعی تنها پس از مشاهده اجرای CI تأیید می‌شود. گزارش: `docs/reports/PHASE-29-REAL-CODEX-TRANSACTION-DISCOVERY-2026-11-22.md`.

**فاز ۲۸ — تأیید آزمایشیِ مقید به وضعیت، قفل پردازه و بازیابی از پردازه مستقل:** ماژول `fixture_transaction_v2.py` و فرمان `gasl locked-bundle-fixture` روی ZIP خصوصی Pin‌شده، Target موقت و Action دقیق (`install`/`replace`) Challenge مستقل تولید می‌کند؛ مطابقت آن قبل و بعد از Staging بررسی می‌شود. قفل انحصاری POSIX `flock`، تأیید سلامت فایل‌ها، `fsync` محتوای Stage و دایرکتوری‌ها، توقف در سه Checkpoint، بازیابی از یک Process جدید و حفظ تغییرات کاربر فقط در **Fixture موقت خود GASL** اجرا شد. ۳۶ سناریو برای ۳ Host × ۲ Scope × ۲ عملیات × ۳ Checkpoint تست شدند؛ ZIP واقعی خصوصی `academy-guide` هم در شش حالت آزمون شد. این Challenge **رضایت حقیقی کاربر نیست** و روی پروفایل‌های واقعی Codex/Cursor/Claude Code نصب انجام نمی‌دهد. قفل Advisory است و تست Checkpoint اثبات قطع برق نیست؛ Windows هنوز پشتیبانی نشده است. گزارش: `docs/reports/PHASE-28-LOCKED-FIXTURE-CONSENT-AND-RECOVERY-2026-11-22.md`.

**فاز ۲۷ — پیش‌بررسی فقط‌خواندنی مقصد واقعی و قفل‌کردن وضعیت نسخه:** فرمان `gasl target-preflight` تنها با مسیر ریشه‌ای که کاربر صریحاً وارد می‌کند، مقصد مستند Codex/Cursor/Claude Code را محاسبه می‌کند؛ وجود Skill، تداخل فایل/دایرکتوری یا Symlink، اختلاف بزرگ/کوچک نام، سلامت ZIP خصوصی، نسخه/Host/Scope و Hash محتوای قبلی را بررسی می‌کند. `state_binding_id` به مقصد دقیق، SHA-256 بسته و فهرست Hash فایل‌های موجود متصل است و بررسی دوباره، هر تغییر را قبل از نصب آینده تشخیص می‌دهد. مسیر واقعی یا نام و محتوای فایل‌های کاربر در JSON خروجی ثبت نمی‌شود؛ بررسی روی ریشه واقعی کاربر خودکار اجرا نشده و در Mac فقط با ZIP واقعی و ریشه موقت آزمایش شده است. **این شناسه مجوز نصب یا رسید رضایت کاربر نیست؛ نصب و اجرای Skill شخص ثالث غیرفعال است.** گزارش: `docs/reports/PHASE-27-READ-ONLY-TARGET-PREFLIGHT-2026-11-22.md`.

**فاز ۲۶ — نصب واقعی فایل‌ها در پروفایل موقت با Backup و Rollback:** فرمان `gasl bundle-fixture` فایل‌های ZIP خصوصی فاز ۲۵ را تنها در `TemporaryDirectory` خود GASL برای Codex/Cursor/Claude Code استخراج می‌کند؛ هیچ Host اجرا یا پروفایل شخصی خوانده نمی‌شود. اعتبارسنجی دقیق ZIP شامل SHA-256، Git Blob فایل اصلی، محافظت از Zip Slip، Symlink، فایل تکراری، فایل رمزگذاری‌شده، اندازه و Agent/Scope دقیق است. جایگزینی نسخه، ساخت Backup، تشخیص تداخل، سه Checkpoint قطع و بازگردانی با حفظ ویرایش‌های تازه و حتی پوشه‌های خالی در پروفایل آزمایشی تست شده است. ماتریس ۳۶ حالت برای سه Host و دو Scope و دو نوع نصب و سه Checkpoint PASS شد و ZIP واقعی خصوصی `academy-guide` هم سه سناریوی Fresh/Upgrade/Conflict را گذراند. **نصب در مسیر واقعی کاربر و اجرای Skill ثالث همچنان غیرفعال است.** گزارش: `docs/reports/PHASE-26-PRIVATE-BUNDLE-FIXTURE-INSTALL-ROLLBACK-2026-11-22.md`.

**فاز ۲۵ — تهیه ZIP خصوصی برای بررسی پیش از نصب:** دستور `gasl install-bundle` فقط بسته Download‌شده و Commit/Blob Pin‌شده را با کنترل مجدد SHA-256، Git Blob اصلی، تعداد و مسیر فایل‌ها، اسکن ایستا و `Plan ID` تأییدشده به ZIP محلی تبدیل می‌کند؛ ZIP همراه Manifest دارای هش و هشدارهای License/سازگاری در `private/install-bundles/` خارج از Git ذخیره می‌شود. روی بسته واقعی کاتالوگ (`academy-guide`) یک ZIP خصوصی شامل `SKILL.md` و `LICENSE.txt` ساخته و بازخوانی شد؛ هشدار License نامعلوم و فقدان Git Blob قدیمی فایل‌های فرعی حفظ شد. این مرحله فقط آماده‌سازی و بررسی است و نه نصب، اجرا یا انتشار ZIP روی GitHub. گزارش: `docs/reports/PHASE-25-PRIVATE-SKILL-BUNDLE-PREPARATION-2026-11-22.md`.

**فاز ۲۴ — سنجش آمادگی واقعی Cursor و Claude Code:** پروب `other_host_protocol_probe.py` فقط `initialize` در Cursor ACP و `--version` برای Claude Code را با باینری واقعی داخل Home و XDG موقت می‌سنجد. برخلاف فاز ۲۳، هیچ مسیر رسمی مستقل برای `skills/list` بدون احراز هویت در این دو Host تأیید نشده و **آمادگی CLI به‌معنای کشف Skill نیست**. هر دو Job در GitHub Actions Run `45057489934` موفق شدند: ACP `initialize` واقعی در Cursor و `claude --version` نسخه `2.1.330`، با `skill_discovery_verified=false` برای هر دو. هیچ Login، درخواست مدل یا نصب Skill واقعی انجام نشد. گزارش: `docs/reports/PHASE-24-OTHER-HOST-READINESS-2026-11-22.md`.

**فاز ۲۳ — کشف Skill توسط Codex واقعی در محیط موقت:** پروب `codex_discovery_probe.py` بر اساس پروتکل رسمی `codex app-server`، فقط `initialize` و `skills/list` را در پروفایل جدید و بدون Token/Prompt اجرا می‌کند. CI جداگانه یک نسخه Pin‌شده از Codex CLI را صرفاً در فضای موقت Ubuntu نصب و Skill بی‌ضرر GASL را به Host معرفی می‌کند؛ در Run واقعی `45055665888` نتیجه `verified_isolated_codex_discovery` با Codex CLI نسخه `0.162.1` ثبت و تمام مراحل Workflow موفق شد. مسیرهای واقعی Mac و Agent تغییر نمی‌کنند، اجرای Skill ثالث فعال نیست و تشخیص Cursor/Claude Code واقعی هنوز باقی است. گزارش: `docs/reports/PHASE-23-REAL-CODEX-DISCOVERY-2026-11-22.md`.

**فاز ۲۲ — بررسی واقعی دسترسی Host و بازیابی تراکنش موقت:** `gasl host-probe` صرفاً حضور CLIهای Codex/Cursor/Claude Code را بدون اجرای برنامه و بدون خواندن پروفایل کاربر بررسی می‌کند؛ در مک توسعه هیچ‌یک روی PATH قابل دسترسی نبودند و بنابراین کشف Skill توسط خود Host هنوز تأیید نشده است. `gasl host-transaction-rehearsal` عملیات ساخت/Backup/بازیابی را فقط با فایل‌های بی‌ضرر GASL در مسیر Temporary Directory انجام می‌دهد. ۳۶ حالت (۳ Host × ۲ Scope × ۲ نوع نصب آزمایشی × ۳ نقطه قطع) با بازگردانی درست PASS شدند؛ محافظت از تغییرات کاربر، مخدوش‌شدن Backup، Symlink و خرابی Journal نیز تست شد. هیچ نصب/اجرای Skill یا تغییر در Agent واقعی انجام نشده است. گزارش: `docs/reports/PHASE-22-HOST-PROBE-AND-INERT-TRANSACTION-RECOVERY-2026-11-22.md`.

**فاز ۲۱ — Adapterهای Host صرفاً در Fixture:** ماتریس مستند مسیرهای Codex (`.agents/skills`)، Cursor (`.cursor/skills`) و Claude Code (`.claude/skills`) در Scope کاربر/پروژه ساخته شد. **Claude Desktop با Claude Code یکی نیست** و فقط فرآیند بارگذاری دستی ZIP در حساب Claude دارد؛ برای generic MCP نیز مسیر نصب عمومی جعل نشده است. ۴۰ اجرای آزمایشی روی ۵ Host، ۲ Scope و ۴ سناریو (نصب اولیه بی‌ضرر، ارتقا/Backup/Rollback بی‌ضرر، برخورد فایل موجود و جلوگیری از Symlink) PASS شد؛ ۱۲ بازگردانی Fixture موفق، ۶ تعارض محفوظ، ۶ Symlink مسدود و ۱۶ سناریوی بدون مسیر فایل‌سیستمی معتبر. هیچ فایل واقعی Host یا Skill شخص ثالث دست‌کاری، نصب یا اجرا نشده است. `install-plan` اکنون قالب Host را مستند می‌کند اما مجوز نصب واقعی همچنان False است. گزارش: `docs/reports/PHASE-21-HOST-ADAPTER-FIXTURE-REHEARSAL-2026-11-22.md`.

**فاز ۲۰ — نصب انتخابی فقط در حالت Plan/Simulation:** دستورهای `gasl install-plan`، `gasl install-simulate` و `gasl install-status` اضافه شدند؛ نسخه Commit و Blob دقیق، مجوز، سلامت محلی، اسکن ایستا، سازگاری ادعاشده/تأییدنشده Agent و الزامات Backup/Rollback بررسی می‌شوند. چرخه `Plan → تأیید دقیق Plan ID → Apply شبیه‌سازی‌شده → Rollback شبیه‌سازی‌شده` با رویدادهای تراکنشی و زنجیره SHA-256 در `private/install-simulation/` (خارج از Git) قابل تکرار است؛ تست واقعی روی بسته محلی انجام شد و صفر فایل Agent تغییر کرد. نصب/حذف واقعی، اخذ مجوز واقعی کاربر، اعتبارسنجی Host و اجرای Skill **همچنان غیرفعال** هستند. گزارش: `docs/reports/PHASE-20-INSTALL-LIFECYCLE-SIMULATION-2026-11-22.md`.

**مرحله ۱۹ — آزمون جداسازی با کد آزمایشی:** Runner ایزوله Docker برای **فقط یک Canary بی‌ضرر نوشته‌شده داخل خود GASL** پیاده‌سازی شد. ساخت تصویر از `FROM scratch` با Go استاتیک، بدون شبکه Build و بدون Pull؛ اجرای واقعی آن روی GitHub Actions Linux موقت انجام شد و هر ۱۸ بررسی جداسازی، محدودیت CPU/RAM/PID، فایل‌سیستم Read-only، Network none، Capabilities و متغیرهای محیطی PASS شدند (Run `45046458532`). اسکنر و نصب Skillها تغییری نکرده‌اند و اجرای کد شخص ثالث همچنان غیرفعال است. گزارش: `docs/reports/PHASE-19-EPHEMERAL-INERT-SANDBOX-CANARY-2026-11-22.md`.

**تکمیل مرحله ۱۸ (بدون اجرای کد شخص ثالث):** بررسی مجدد ۳۸ بسته Pin‌شده نشان داد ۳۱ بسته بدون هشدار ایستای قابل‌اقدام و ۷ بسته نیازمند بررسی بیشتر هستند. ۱۲ هشدار صرفاً اطلاعاتیِ فایل‌های تست در گزارش حفظ شده‌اند، ولی دیگر به اشتباه وضعیت manual_review_required ایجاد نمی‌کنند. تشخیص `gasl sandbox` اضافه شد؛ روی مک توسعه Docker CLI موجود ولی Daemon خاموش/غیرقابل دسترس است و در هر حالت بدون Canary ایزولاسیون، گیت fail-closed باقی می‌ماند. هیچ Skill نصب، تأیید یا اجرا نشده؛ Dynamic Sandbox و نصب انتخابی همچنان مراحل آینده‌اند. گزارش: `docs/reports/PHASE-18-SECURITY-TRIAGE-AND-SANDBOX-READINESS-2026-11-22.md`.

**وضعیت تا فاز ۱۷:** گیت آفلاین اسکن ایستا به `gasl download --execute` متصل شد و `gasl audit --id` اضافه شد. مسیرها، Symlink، فایل اضافه، اندازه و SHA-256 و Git Blob اصلی دوباره کنترل می‌شوند. اسکن روی ۳۸ بسته محلی با نسخه Pin‌شده مطابق کاتالوگ فعلی اجرا شد: ۳۰ بدون پرچم آشکار (اما تأییدنشده)، ۸ نیازمند بازبینی، صفر خطای Integrity یا Pin. ۱۶ Checkpoint داخلی قدیمی پس از اعتبارسنجی ساختار و تطبیق فهرست فایل‌ها شناسایی شدند. ۲۵ بسته قدیمی که با Commitهای فعلی کاتالوگ منطبق نیستند، در آمار اسکن اعتبارسنجی‌شده قرار ندارند. Dynamic Sandbox واقعی و تأیید نصب/اجرای Skill هنوز پیاده نشده است. گزارش: `docs/reports/PHASE-17-SELECTED-SKILL-OFFLINE-SECURITY-GATE-2026-11-22.md`.

- اعتبارسنجی Frontmatter و ساختار پوشه.
- اسکن Prompt Injection، Script، Dependency، Network، Secret، Permission و Obfuscation.
- ثبت گزارش و وضعیت Lifecycle برای هر بسته.
- تفکیک یافته قطعی، هشدار heuristic، False Positive و `needs_validation`.
- Dynamic validation فقط در Sandbox محدود با محیط خالی و بدون Network پیش‌فرض.

**معیار پذیرش:** هر بسته گزارش امنیتی، Hash، License status، تصمیم دستی و وضعیت قابل ردیابی داشته باشد.

### فاز 7 — Attribution و GitHub Actions Automation

**وضعیت:** اجرای تاریخی Actions با ۵۷ مخزن و ۹ بسته عمومی موفق بوده است. در معماری جدید Workflow فقط کاتالوگ منابع و شواهد Metadata را Refresh می‌کند. وابستگی به Writer آرشیو خصوصی، R2 و دانلود انبوه در Runner حذف شده است.

- تمام انواع مجوز در Source Catalog ثبت می‌شوند؛ دریافت انتخابی روی سیستم مصرف‌کننده از منبع Pin‌شده انجام می‌شود.
- بسته‌های عمومی فعلی حفظ می‌شوند و بازتوزیع جدید فرآیند مستقل بازبینی دارد.
- حالت --public-only مانع ورود Metadata بسته‌های محلی به خروجی سازنده عمومی است.
- Workflow روزانه و اجرای دستی بدون سرور اختصاصی؛ فقط فایل‌های Metadata مشخص stage می‌شوند.

**معیار پذیرش:** تست محلی و ساخت خروجی عمومی موفق پس از اصلاح؛ اجرای واقعی Workflow اصلاح‌شده روی GitHub هنوز لازم است. گزارش: docs/reports/PHASE-5-7-ON-DEMAND-ARCHITECTURE-2026-11-20.md.


### فاز 8 — Registry و Search

- Schema نسخه‌بندی‌شده و Source Recordهای مستقل.
- Canonical Index با رابطه‌های same_as، fork_of، mirror_of، supersedes و conflicts_with.
- SQLite/FTS5 برای جست‌وجوی محلی؛ نام، توضیحات، حوزه، Publisher، سازگاری، امنیت و شواهد.
- جست‌وجوی فارسی/انگلیسی با نرمال‌سازی حروف عربی/فارسی، حذف واژه‌های پرتکرار و مترادف‌های حوزه‌ای.
- فیلتر License، Domain، Security status، Public-only و Content-only.
- Semantic/vector search فقط به‌صورت قابلیت اختیاری و محلی؛ بدون API پولی یا مدل اجباری.

**وضعیت:** موتور lexical مبتنی بر SQLite FTS5 برای هر ۴٬۴۰۵ رکورد Source Catalog پیاده‌سازی و تست شده است. Taxonomy نسخه‌دار ۱۰ حوزه دارد. نرمال‌سازی فارسی/عربی و گسترش مترادف‌های حوزه‌ای فعال است؛ Taxonomy نسخه ۱.۳.۰ شامل عبارت‌های دوزبانه و وزن‌دهی مفاهیم تخصصی است. توضیحات موجود از منبع عمومی و بسته‌های محلی استفاده می‌شوند. ابزار gasl enrich محتوای SKILL.md را فقط از Commit دقیق و pin‌شده دریافت می‌کند، Frontmatter/Tags/متن قابل جست‌وجو را استخراج می‌کند و Metadata را در private/skill-metadata-cache.json نگه می‌دارد؛ این فایل در Git نادیده گرفته می‌شود. Metadata harvesting برای هر ۴٬۴۰۵ رکورد انجام شده است: ۴٬۴۰۴ دریافت موفق و یک SKILL.md به‌دلیل عبور از سقف ایمنی ۲۵۶ KiB عمداً Skip شده است. ۴٬۳۷۲ رکورد Description و تمام ۴٬۴۰۵ رکورد Search Text محلی دارند. ایندکس SQLite محلی و مشتق‌شده است و با تغییر Fingerprint منابع بازسازی می‌شود. جست‌وجوی معنایی هنوز فعال نیست و هیچ مدل یا API خارجی برای اجرای عادی لازم نیست.

**معیار پذیرش:** PASS برای ۴٬۴۰۵ رکورد، منشأ/Commit/License/Security در نتیجه، فیلترها، فارسی/انگلیسی، دریافت انتخابی محتوا و بازسازی ایندکس. Canonical relationship resolution و Semantic Reranker محلی باز هستند. Benchmark اولیه ۲۶ پرسش دوزبانه با ۱۴۸ Judgment همچنان مجموعه توسعه و provisional است. بسته اصلاح‌شده V2 شامل ۲۶ Query در ۱۳ جفت فارسی/انگلیسی، ۳۸۵ Candidate pair-level، دو داوری مستقل و دو فرم Answerability در private/benchmark-review آماده است. سناریوی Android/Kotlin BroadcastReceiver برای پیامک بانکی بازگردانده شد؛ سناریوی Twilio فقط در آرشیو superseded باقی مانده است. ۱۲ Skill نزدیک بررسی محتوایی pin-verified شدند و هیچ‌کدام پیاده‌سازی مستقیم Android SMS نبودند؛ این شکاف هنوز باید توسط دو داور تأیید شود. گزارش: docs/reports/PHASE-11B-ANDROID-SMS-COVERAGE-CORRECTION-2026-11-22.md.

**پیشرفت جدید:** شاخص عمومی استاندارد واژگان Skill بدون متن اصلی به موتور افزوده شد. نخستین Batch واقعی: ۲۹۱ فایل تأیید شده از ۳۱۶ تلاش، ۲۵ خطای شبکه. Workflow روزانه حداکثر ۲۰۰ مورد ناقص را دریافت می‌کند؛ تغییر Commit با Blob SHA یکسان موجب دریافت مجدد نمی‌شود. جست‌وجوی آفلاین و بدون وابستگی تازه برقرار است. ارزیابی فعلی بهبود Precision/Recall/NDCG و افت جزئی MRR را نشان می‌دهد. در ادامه، Batch دوم و سوم ۹۹۱ رکورد جدیدِ تأییدشده افزودند (مجموع ۱٬۲۸۲ از ۴٬۴۰۵) و ۲۵ خطای شبکه Batch اول رفع شد. ذخیره checkpoint هر ۲۵ درخواست و صف تلاش مجدد بر اساس تعداد تلاش ثبت می‌شود. نمونه مستقل E5-small + RRF روی ۲۶ Query و ۴۱۷ Candidate واقعاً اجرا شد؛ NDCG@5 از ۰٫۴۲۶۱ به ۰٫۴۴۰۵ رسید و Peak RSS کل فرآیند ۷۴۰٫۹۱ MiB بود. به‌دلیل سود محدود و هزینه منابع، حالت پیش‌فرض همچنان FTS5 است. جست‌وجوی برداری در کل کاتالوگ هنوز پیاده نشده است. پوشش Feature اکنون به ۴٬۴۰۴ از ۴٬۴۰۵ رکورد Commit-pinned رسیده است (۹۹٫۹۸٪). تنها رکورد باقی‌مانده به‌دلیل عبور SKILL.md از سقف ایمنی ۲۵۶ KiB عمداً Skip و در Failure Ledger حفظ شده است. از ۴۰ شناسه ثبت‌شده در Failure Ledger، تعداد ۳۹ مورد با Retry بازیابی شدند. Benchmark پس از پوشش با مجموعه داخلی ۲۶ Query و ۱۴۸ Judgment اجرا شد، اما همچنان provisional و غیرمستقل است؛ به‌دلیل تفاوت Source Catalog و Ranking Code با Snapshot قبلی، مقایسه مستقیم انجام نمی‌شود. خطای حجم به‌صورت non-retryable ثبت می‌شود و در اجرای بعدی دوباره دریافت نمی‌شود. ارزیابی مستقل همچنان باز است. گزارش: docs/reports/PHASE-8-SEARCH-FEATURE-COVERAGE-2026-11-22.md؛ خروجی Benchmark: docs/reports/SEARCH-BENCHMARK-POST-FEATURE-COVERAGE-2026-11-22.json. گزارش پایه: docs/reports/PHASE-8-SEARCH-FEATURES-2026-11-20.md.

### فاز 9 — CLI و Skill Router

- CLI ساده برای status، sources، discover، download، validate، scan، search، info، update-check، route، enrich و export.
- انتخاب Candidate بر اساس Intent، Domain، Agent، OS، License، Security و Evidence.
- Progressive Disclosure؛ دریافت فقط محتوای Skillهای منتخب.

**وضعیت:** CLI شامل summary، bootstrap، verify، reconcile، domains، evaluate، index، search، route، enrich، mcp و serve است. Router بر اساس ارتباط وظیفه با Skill و پوشش گروه‌های مفهومی Query رتبه‌بندی می‌کند؛ Metadata completeness و Provenance فقط به‌عنوان شواهد مستقل نمایش داده می‌شوند و امتیاز ارتباط یا کیفیت Skill را دست‌کاری نمی‌کنند. Search response کپی‌های یکسان با Repo/Commit و Content Hash یکسان را فقط در لایه نمایش گروه‌بندی می‌کند و همه Source IDها/مسیرها را نگه می‌دارد؛ Source Catalog و رکوردهای مستقل تغییر یا ادغام نمی‌شوند. Fixtureها و موارد دارای شکست Integrity حذف می‌شوند؛ Manual Review، Security Not Scanned، License و سازگاری نامشخص به‌صورت Warning نمایش داده می‌شوند. Router فقط پیشنهاد می‌دهد و نصب/اجرا نمی‌کند.

**معیار پذیرش:** PASS برای خروجی Top-K قابل تکرار، فیلتر Agent در حالت strict، نمایش Warningها و صفر نصب/اجرا؛ Benchmark اولیه Search با Precision@5، Recall@5، MRR@10 و NDCG@5 فقط Regression Set است. بسته V2 اصلاح‌شده شامل ۲۶ Query، ۱۳ جفت دوزبانه، ۳۸۵ Candidate pair-level و فرم جداگانه Answerability برای ۱۳ جفت است. سناریوی Android SMS به‌عنوان آزمون احتمالی نبود پوشش ثبت شده و Twilio جایگزین آن نیست. داوری مستقل، Adjudication و Freeze هنوز انجام نشده‌اند. Runner از Schema `1.1.0` برای برچسب‌های answerable/unanswerable/uncertain و معیارهای جداگانه no-answer پشتیبانی می‌کند؛ اما Router اکنون با سیاست آزمایشی و شفاف `experimental_heuristic_not_calibrated` سه تصمیم `recommend`/`abstain`/`undetermined` را بر اساس شواهد بازیابی تولید می‌کند؛ `recommend` فقط پیشنهاد بررسی است و `abstain` اثبات نبود Skill در کاتالوگ نیست. نسخه قبلی همیشه `undetermined` می‌داد. گزارش‌ها: `docs/reports/PHASE-11B-ANDROID-SMS-COVERAGE-CORRECTION-2026-11-22.md` و `docs/reports/PHASE-13-ROUTER-ANSWERABILITY-GATE-2026-11-22.md`.

### فاز 10 — MCP / Local API / Explorer

- MCP با انتقال STDIO به‌عنوان مسیر اصلی اتصال Agentها؛ بدون Hosted Endpoint و بدون نیاز به سرور اختصاصی.
- یک Core مشترک برای CLI، MCP، REST API محلی و Explorer؛ منطق جست‌وجو و مسیریابی تکراری پیاده‌سازی نمی‌شود.
- REST API و Explorer فقط برای اجرای محلی و توسعه؛ Bind پیش‌فرض روی localhost.
- Progressive Disclosure: جست‌وجو و مشاهده Metadata ابتدا؛ دریافت SKILL.md فقط در صورت درخواست.
- نصب و اجرای Skillها خارج از دامنه Adapter فعلی باقی می‌ماند.

**وضعیت:** MCP Server با ۶ ابزار search، details، content، route، domains و health پیاده‌سازی شده است. انتقال STDIO با MCP Client واقعی Initialize، List Tools و Call Tool شده است. REST API و Explorer نیز به‌صورت Local-only پیاده‌سازی و تست شده‌اند. راه‌انداز ریشه gasl و install.sh مسیر نصب محلی را ساده می‌کنند. اجرای عادی به سرور، Docker، API Key یا سرویس پولی وابسته نیست. تست End-to-End واقعی STDIO در مجموعه تست‌ها اضافه شده است.

**معیار پذیرش:** PASS برای اتصال واقعی STDIO، فهرست و اجرای ابزارها، استفاده از Core مشترک، دریافت محتوا با Commit pin‌شده و نبود نصب/اجرای خودکار. نصب مستقل در محیط مجازی تازه macOS/Python 3.13.9 و ارتباط STDIO از همان محیط تأیید شد. آزمون Hostهای واقعی Claude Desktop، Cursor و Codex هنوز باز است؛ این برنامه‌ها در مسیرهای استاندارد نصب مک یافت نشدند.

### فاز 11 — Evaluation و Benchmark

- مقایسه Task با Skill و بدون Skill.
- ثبت Model، Harness، Skill Commit، ورودی/خروجی، Pass/Fail، Token، Latency و Cost.
- Regression پس از تغییر نسخه.

**وضعیت:** لایه مقدماتی Evidence Evaluation اضافه شد: metadata_completeness_score و provenance_score جداگانه محاسبه می‌شوند. overall_quality_score برای تمام رکوردها null است. بسته اصلاح‌شده داوری مستقل V2 آماده است (۲۶ Query، ۱۳ جفت دوزبانه، ۳۸۵ Candidate، فرم Answerability و Adjudication Template)؛ هنوز Grade انسانی وارد نشده و Behavioral Benchmark اجرا نشده است. سناریوی Android banking SMS دارای سیگنال شکاف پوشش است، اما برچسب no-answer تا داوری مستقل و بررسی کامل کاتالوگ ثبت نمی‌شود. Benchmark runner از Schema 1.1.0 و معیارهای no-answer پشتیبانی می‌کند؛ Router برای استفاده عملی از سیاست آزمایشی و بدون وابستگی انسانی استفاده می‌کند و محدودیت‌های آن را در پاسخ اعلام می‌کند. هیچ امتیاز کیفیتی از روی Metadata یا رتبه بازیابی جعل نمی‌شود. گزارش‌ها: `docs/reports/PHASE-11B-ANDROID-SMS-COVERAGE-CORRECTION-2026-11-22.md` و `docs/reports/PHASE-13-ROUTER-ANSWERABILITY-GATE-2026-11-22.md`.
بسته‌های reviewer با نسخه `INTAKE-V2` سخت‌سازی شدند: attestation مستقل انسانی با شناسه مستعار متمایز، فیلد صریح `out_of_pool_reviewed`، ثبت چند Search Formulation و Search Method، قالب جداگانه adjudication برای Answerability و اعتبارسنج خودکار Source Pin/ZIP/Blindness/Grade/Evidence آماده است. Audit کاتالوگ و ZIPها را PASS کرد؛ اختلاف Taxonomy hash با Snapshot زمان ساخت بسته به‌صورت هشدار ثبت شد و Manifest بازنویسی نشد. گزارش: `docs/reports/PHASE-14-HUMAN-REVIEW-INTAKE-2026-11-22.md`.

**معیار پذیرش:** امتیاز اثربخشی فقط از آزمون قابل بازتولید حاصل شود؛ موارد بدون Eval برابر Unrated بمانند.

### فاز 12 — GitHub Publication و Release

- انتشار کد، Schema، مستندات و Metadata مجاز؛ عدم انتشار گزارش‌های خصوصی، آرشیو اصلی و محتوای Skill شخص ثالث بدون License.
- README، SECURITY، CONTRIBUTING، Third-party notices و License policy.
- CI برای تست، Validation، Static Scan و Hash.

**وضعیت:** Baseline عمومی در GitHub منتشر و با main محلی همگام شد. اطلاعات خصوصی و محتوای بسته‌ها خارج از Git باقی مانده‌اند. README اکنون معماری Local-first و راه‌اندازی دو‌دستوری را مستند می‌کند. Workflow تست‌ها وابستگی اختیاری MCP را نیز نصب می‌کند تا تست‌های Integration در CI قابل اجرا باشند. License پروژه هنوز انتخاب نشده و تا انتخاب/افزودن فایل LICENSE، پروژه از نظر حقوقی هنوز مجوز متن‌باز مشخصی برای کد خود اعطا نکرده است.

**معیار پذیرش:** فقط فایل‌های مجاز منتشر شوند؛ تست‌ها و Hashها بازتولیدپذیر باشند؛ وضعیت پوشش و محدودیت‌ها صادقانه مستند شود.

## ترتیب اجرای جاری

1. تکمیل آرشیو و Source Manifest چهار منبع — آرشیو و Hashها تأیید شده‌اند.
2. پاک‌سازی شناسه‌های حساب‌محور و ساخت Public-safe repository baseline.
3. تکمیل ممیزی دستی Cloudflare و ثبت تصمیم؛ بدون اجرای اسکریپت.
4. تکمیل Crosswalk و ثبت Duplicate Candidates بدون حذف رکورد.
5. تکمیل triage ده بسته نیازمند بررسی؛ اولویت دو High-confidence signal.
6. اجرای واقعی Workflow جدید Metadata-only روی GitHub؛ دریافت انتخابی محلی جایگزین Collection انبوه و آرشیو خصوصی است.
7. تست نصب تازه از روی README تأیید شد؛ تکمیل ماتریس سازگاری Hostهای واقعی باقی مانده است.
8. **مسیر خودکار عملیاتی:** ارزیابی داخلی خودکار V2 روی ۳۸۵ Candidate و ۲۶ Query اجرا شد؛ دو rubric قطعی، ۳۲ اختلاف خودکار، امتیازدهی محافظه‌کارانه و گزارش هر Query ثبت شده است. Router سه تصمیم آزمایشی `recommend`/`abstain`/`undetermined` را بدون وابستگی به داور انسانی و بدون API پولی تولید می‌کند. بررسی انسانی و Gold Dataset مستقل دیگر گیت استفاده از سیستم نیستند و فقط در صورت نیاز برای انتشار ادعای دقت تأییدشده انجام خواهند شد. مقادیر Proxy نباید Gold یا Accuracy مستقل معرفی شوند. برای no-answer قطعی همچنان بررسی کامل کاتالوگ لازم است؛ `abstain` صرفاً فقدان شواهد کافی در نتایج بازیابی است. گزارش: `docs/reports/PHASE-15-AUTONOMOUS-PROXY-EVALUATION-2026-11-22.md`.
9. انتخاب مجوز کد خود پروژه و افزودن LICENSE پیش از اعلام Release متن‌باز رسمی.

## گزارش‌دهی و Gate هر مرحله

هر گزارش در `docs/reports/` باید هدف، Baseline، عملیات، فایل‌های تغییرکرده، Source IDها، Commit/Hash، تست‌ها و خروجی، محدودیت‌ها، کارهای عمداً انجام‌نشده، ریسک‌ها، تصمیم‌های باز و معیار پذیرش را ثبت کند. فاز بعد فقط بعد از ثبت معیار پذیرش فاز جاری شروع می‌شود.
