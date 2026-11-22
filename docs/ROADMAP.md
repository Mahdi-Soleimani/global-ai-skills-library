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
