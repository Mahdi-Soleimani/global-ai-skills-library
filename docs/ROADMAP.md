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
7. هر مسیر کشف‌شده، مستقل از مجوز، در Source Catalog با لینک و انتساب شخص ثالث ثبت می‌شود. محتوای عمومی فقط پس از عبور از Gate مجوز و شواهد License/Notice بازنشر می‌شود؛ انتساب به‌تنهایی مجوز بازنشر نیست.
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
| مسیرهای تاریخی مشاهده‌شده SKILL.md | ۴٬۲۱۴ |
| Source Catalog | ۴٬۲۷۷ رکورد (۴٬۲۱۴ مسیر تاریخی + ۶۳ نسخه دانلودشده) |
| بسته‌های دریافت‌شده محلی | ۶۳ |
| فایل‌های Manifest دریافت | ۶۴۰ |
| حجم ثبت‌شده | ۱۳٬۵۸۳٬۸۸۹ بایت |
| طبقه‌بندی Registry | ۵۹ Skill candidate + ۴ test fixture |
| بسته‌های نیازمند بررسی دستی | ۱۰؛ شامل ۹ candidate و ۱ fixture |
| High-confidence static signals | ۲؛ بررسی دستی باز |
| تأیید نصب / نصب / اجرای کد | صفر / صفر / صفر |
| تست پروژه | ۵۷ PASS |

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

**وضعیت:** اولین اجرای واقعی GitHub Actions هر ۵۷ مخزن را با صفر خطای Repository تأیید کرد و ۴٬۴۷۸ مسیر SKILL.md مشاهده شد؛ ۴٬۴۰۵ مسیر در صف Package Planning قرار گرفتند. Source Catalog ثبت‌شده در main هنوز ۴٬۲۷۷ رکورد تاریخی/نسخه‌ای دارد؛ Snapshot جدید پس از موفقیت کامل مرحله Ingestion به main Commit خواهد شد. گزارش Batch اولیه: docs/reports/PHASE-4-DISCOVERY-BATCH-01-2026-11-20.md.

ادامه Checkpointهای مستقل: EN-675 (awesome-copilot، NVIDIA، Microsoft، Anthropic verticals)؛ FA-234 (Microsoft، skills.sh، SkillsMP، Database Vendors و منابع غیرانگلیسی)؛ SUP-750 (AWS HCLS، phuryn، NVIDIA H-Z، Adobe، Google DeepMind، Agriculture/Manufacturing/Logistics، Tencent/Japan)؛ SUP-438 (Databricks، Salesforce، NVIDIA، Microsoft SDKها، phuryn و حوزه‌های کم‌پوشش).

**معیار پذیرش:** هر مورد جدید Source، Path، Commit یا Snapshot، تاریخ و وضعیت Extraction داشته باشد؛ موارد قبلی دوباره‌کاری نشوند.

### فاز 5 — Downloader و Ingestion Pipeline

**وضعیت:** Downloader به Commit/Tree/Blob pin متصل است؛ Pilot سه مخزن با ۱۷ فایل و ۶۵٬۰۹۲ بایت موفق شد. License/COPYING/NOTICEهای مرتبط از مسیرهای والد و داخل بسته نیز همراه بسته جمع‌آوری می‌شوند. Resume، Hash و Quarantine تست شده‌اند. دانلود عمومی فقط برای SPDXهای allowlist‌شده همراه License evidence انجام می‌شود؛ تمام موارد دیگر همچنان در Source Catalog حضور دارند. گزارش: docs/reports/PHASE-5-QUEUE-INGEST-BATCH-01-2026-11-20.md.

- Batch کوچک، Commit pinning، دریافت پوشه کامل Skill و فایل‌های وابسته.
- Checkpoint، Resume، Retry، Rate-limit handling، محدودیت حجم و گزارش فایل‌های Skipped.
- SHA-256 و Git blob SHA؛ جداسازی Quarantine از Catalog.
- حذف Test Fixtures از مجموعه Skillهای فعال به‌صورت پیش‌فرض؛ حفظ امکان دریافت عمدی آن‌ها برای آزمون امنیتی.

**وضعیت:** Pilot محلی ۶۳ بسته انجام شده؛ Dry-run جدید روی مک در اتصال به `api.github.com` با خطای TLS (`LibreSSL SSL_ERROR_SYSCALL`) متوقف شد و هیچ دانلودی در آن تلاش انجام نشد.

**معیار پذیرش:** حداقل سه Repository آزمایشی با Hash، ساختار کامل، Resume و طبقه‌بندی Skill/Fixture صحیح.

### فاز 6 — Validator و Security Pipeline

- اعتبارسنجی Frontmatter و ساختار پوشه.
- اسکن Prompt Injection، Script، Dependency، Network، Secret، Permission و Obfuscation.
- ثبت گزارش و وضعیت Lifecycle برای هر بسته.
- تفکیک یافته قطعی، هشدار heuristic، False Positive و `needs_validation`.
- Dynamic validation فقط در Sandbox محدود با محیط خالی و بدون Network پیش‌فرض.

**معیار پذیرش:** هر بسته گزارش امنیتی، Hash، License status، تصمیم دستی و وضعیت قابل ردیابی داشته باشد.

### فاز 7 — Attribution و GitHub Actions Automation

**وضعیت:** اولین اجرای GitHub Actions تست‌ها و Discovery را با موفقیت گذراند (۵۷/۵۷ Repository، صفر خطا، ۴٬۴۷۸ مسیر). مرحله Ingestion پس از دریافت هشت بسته در Runner موقت، به‌دلیل اختلاف Inventory در Manifest قدیمی متوقف شد. اصلاح Manifest انجام شده و اجرای بعدی برای تأیید end-to-end لازم است.

- تمام مسیرهای تاریخی و نسخه‌های دانلودشده در Source Catalog با منبع، مسیر، مالک مخزن، مجوز، وضعیت Pin و وضعیت محتوا ثبت می‌شوند.
- original_author فقط در صورت وجود شواهد ثبت می‌شود؛ repository_owner به‌عنوان نویسنده فردی فرض نمی‌شود.
- هر رکورد ownership=third_party و gasl_claims_exclusive_ownership=false دارد.
- اسکیل‌های دارای مجوز نامشخص، اختصاصی یا خارج از Allowlist از Source Catalog حذف نمی‌شوند؛ فقط محتوای آن‌ها به‌صورت خودکار در مخزن عمومی Mirror نمی‌شود.
- محتوای واجد شرایط پس از دریافت License/NOTICE، اعتبارسنجی Hash و Static Scan در public-catalog/ با ATTRIBUTION.md و ATTRIBUTION.json قرار می‌گیرد.
- Workflow روزانه تمام ۵۷ مخزن را Refresh می‌کند، Batch محدود دریافت می‌کند، Registry را به‌روزرسانی می‌کند و تغییرات را به main Commit/Push می‌کند. روشن بودن مک لازم نیست.
- Runnerهای Actions موقت‌اند؛ فقط Source Catalog و Public Catalog در Git باقی می‌مانند. ذخیره‌سازی خصوصی دائمی خارج از دامنه این Workflow است.

**معیار پذیرش:** اجرای مجدد Actions با Refresh موفق، حفظ رکوردهای تاریخی، افزودن بسته‌های واجد شرایط یا ثبت شفاف صفر مورد واجد شرایط، و Commit خودکار به main.


### فاز 8 — Registry و Search

- Schema نسخه‌بندی‌شده و Source Recordهای مستقل.
- Canonical Index با رابطه‌های `same_as`، `fork_of`، `mirror_of`، `supersedes` و `conflicts_with`.
- SQLite/FTS5 برای جست‌وجوی محلی؛ نام، حوزه، وظیفه، Publisher، سازگاری، امنیت و شواهد.

**وضعیت:** Registry فعلی JSON/CSV/summary ساخته می‌شود؛ FTS5 و Canonical Skill index هنوز تکمیل نشده‌اند.

**معیار پذیرش:** هر نتیجه جست‌وجو منشأ، نسخه، اختلاف و وضعیت امنیت/مجوز را نمایش دهد.

### فاز 9 — CLI و Skill Router

- تکمیل دستورات واقعی برای status، sources، discover، download، validate، scan، search، info، update-check، route و export.
- انتخاب Candidate بر اساس Intent، Domain، Agent، OS، License، Security و Evidence.
- Progressive Disclosure؛ بارگذاری فقط Skillهای منتخب.

**وضعیت:** CLI فعلی شامل `summary`، `bootstrap`، `verify`، `collector download`، `static_scan` و `build_registry` است؛ Router هنوز ساخته نشده است.

**معیار پذیرش:** پرس‌وجوهای واقعی با Precision@K و نتیجه قابل تکرار؛ بدون بارگذاری Context بی‌رویه.

### فاز 10 — Adapters / MCP / Installation

- تفکیک Native، Tested، Format-Compatible Untested و Conversion Required برای Codex، Claude Code، Cursor، Copilot، Gemini CLI و دیگر Hostها.
- Dry-run، Backup، Rollback و Install Report.
- نصب فقط برای Skillهای دارای `install_approved` و فقط در Scope انتخاب‌شده.

**معیار پذیرش:** نصب و حذف آزمایشی بدون تغییر فایل‌های نامرتبط، با تست اختصاصی هر Host/OS.

### فاز 11 — Evaluation و Benchmark

- مقایسه Task با Skill و بدون Skill.
- ثبت Model، Harness، Skill Commit، ورودی/خروجی، Pass/Fail، Token، Latency و Cost.
- Regression پس از تغییر نسخه.

**معیار پذیرش:** امتیاز اثربخشی فقط از آزمون قابل بازتولید حاصل شود؛ موارد بدون Eval برابر Unrated بمانند.

### فاز 12 — GitHub Publication و Release

- انتشار کد، Schema، مستندات و Metadata مجاز؛ عدم انتشار گزارش‌های خصوصی، آرشیو اصلی و محتوای Skill شخص ثالث بدون License.
- README، SECURITY، CONTRIBUTING، Third-party notices و License policy.
- CI برای تست، Validation، Static Scan و Hash.

**وضعیت:** Baseline عمومی در GitHub منتشر و با main محلی همگام شد. اطلاعات خصوصی و محتوای بسته‌ها خارج از Git باقی مانده‌اند. License پروژه و Release نهایی هنوز انتخاب/تکمیل نشده است.

**معیار پذیرش:** فقط فایل‌های مجاز منتشر شوند؛ تست‌ها و Hashها بازتولیدپذیر باشند؛ وضعیت پوشش و محدودیت‌ها صادقانه مستند شود.

## ترتیب اجرای جاری

1. تکمیل آرشیو و Source Manifest چهار منبع — آرشیو و Hashها تأیید شده‌اند.
2. پاک‌سازی شناسه‌های حساب‌محور و ساخت Public-safe repository baseline.
3. تکمیل ممیزی دستی Cloudflare و ثبت تصمیم؛ بدون اجرای اسکریپت.
4. تکمیل Crosswalk و ثبت Duplicate Candidates بدون حذف رکورد.
5. تکمیل triage ده بسته نیازمند بررسی؛ اولویت دو High-confidence signal.
6. تکمیل اجرای واقعی GitHub Actions و ادامه Collection به‌صورت Batchهای کوچک.
7. سپس Registry/Search، Router، Adapters و Evaluation.

## گزارش‌دهی و Gate هر مرحله

هر گزارش در `docs/reports/` باید هدف، Baseline، عملیات، فایل‌های تغییرکرده، Source IDها، Commit/Hash، تست‌ها و خروجی، محدودیت‌ها، کارهای عمداً انجام‌نشده، ریسک‌ها، تصمیم‌های باز و معیار پذیرش را ثبت کند. فاز بعد فقط بعد از ثبت معیار پذیرش فاز جاری شروع می‌شود.
