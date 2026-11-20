# نقشه راه اجرایی Global AI Skills Library (GASL)

نسخه 0.1.0 — 2026-11-19

## هدف
ساخت یک کتابخانه مرکزی و مستقل برای کشف، دریافت، نگهداری، اعتبارسنجی امنیتی، ارزیابی عملی، جست‌وجو و نصب انتخابی AI Agent Skills در چند Agent و چند سیستم‌عامل.

## فاز 0 — تثبیت ورودی‌ها و حفاظت از داده
وضعیت: انجام‌شده در محیط کاری اولیه.
- حفظ مستقل DR-01 و DR-02.
- ثبت SHA-256 و اندازه فایل گزارش‌ها.
- استخراج ردیف‌های CSV تعبیه‌شده بدون حذف یا بازنویسی.
- استخراج URLهای صریح GitHub به دو Source Manifest مستقل.
- ساخت Cross-reference مخازن مشترک؛ بدون ادغام رکوردها.

معیار پذیرش: هش ورودی‌ها معتبر باشد؛ نمونه‌های 45 و 40 ردیفی مستقل بمانند.

## فاز 1 — راستی‌آزمایی منابع زنده
- بررسی وجود واقعی Repositoryها، مالک، visibility، archived، default branch، updated_at، حجم و license.
- بررسی درخت Git و شمارش واقعی SKILL.mdها.
- استخراج مسیر دقیق هر Skill و منابع وابسته.
- تفکیک «رسمی ادعاشده در گزارش» از «رسمی تأییدشده».
- ثبت missing / inaccessible / archived / fork / mirror / renamed.

معیار پذیرش: هر Repository وضعیت قابل استناد و هر Skill مسیر واقعی و commit مشخص داشته باشد.

## فاز 2 — Downloader قابل‌اعتماد
- دریافت پوشه کامل هر Skill، نه فقط SKILL.md.
- دریافت scripts/references/assets و فایل‌های وابسته.
- دانلود بدون تاریخچه کامل Git مگر برای ممیزی لازم باشد.
- پین Commit SHA و ثبت SHA-256 فایل‌ها.
- Resume، retry، rate-limit handling و Checkpoint.
- محدودیت حجم و گزارش فایل‌های skipped.
- عدم اجرای کد.

معیار پذیرش: 3 مخزن آزمایشی با تطابق هش، ساختار کامل و Resume موفق.

## فاز 3 — امنیت و مجوز
- اسکن ایستای SKILL.md و فایل‌های اجرایی.
- بررسی shell/network/filesystem/secrets/hooks/dependencies/obfuscation/prompt injection.
- ثبت مجوز در سطح مخزن و Skill.
- وضعیت‌های approved / review / blocked / unknown.
- قرنطینه موارد پرخطر؛ هیچ اجرای خودکار.

معیار پذیرش: هیچ Skill بدون وضعیت امنیتی و مجوز روشن وارد Active Catalog نشود.

## فاز 4 — Central Registry و تطبیق
- مدل داده واحد با source_report_id و source_record_id.
- حفظ نسخه‌ها، Forkها و Mirrorها با رابطه‌های صریح.
- same_as / fork_of / mirror_of / supersedes / conflicts_with.
- SQLite برای جست‌وجوی محلی؛ JSON/CSV برای تبادل.
- تکراری‌ها حذف نمی‌شوند؛ فقط cross-reference می‌شوند.

معیار پذیرش: هر رکورد تا گزارش، مخزن، مسیر و Commit قابل ردیابی باشد.

## فاز 5 — نصب چندعاملی و چندسیستمی
- Adapterهای مستقل برای Codex، Claude Code، Cursor، Copilot، Gemini CLI، OpenCode و غیره.
- مسیرها و محدودیت‌های هر Agent جداگانه مدیریت شود.
- پیاده‌سازی اختصاصی macOS، Windows و Linux؛ از یکسان‌سازی کد سیستم‌عامل‌ها پرهیز شود.
- Dry-run، backup، rollback و install report.

معیار پذیرش: نصب/حذف آزمایشی بدون تغییر فایل‌های نامرتبط و با تست جداگانه هر پلتفرم.

## فاز 6 — Skill Router
- جست‌وجوی واژگانی BM25 در نسخه اول.
- Embedding محلی در نسخه بعد و فقط در صورت نیاز.
- رتبه‌بندی بر اساس وظیفه، Agent، OS، مجوز، امنیت و شواهد.
- نمایش چند گزینه برتر و فعال‌سازی انتخابی؛ نه تزریق کل کتابخانه به Context.

معیار پذیرش: تست پرس‌وجوهای واقعی و گزارش Precision@K و خطاهای انتخاب.

## فاز 7 — ارزیابی اثربخشی
- ساخت Task/Eval برای حوزه‌های مختلف.
- مقایسه با Skill و بدون Skill.
- ثبت مدل، Harness، نسخه Skill، ورودی/خروجی، Pass/Fail و هزینه توکن.
- امتیاز اثربخشی بدون شواهد آزمون ساخته نمی‌شود.

معیار پذیرش: امتیازها قابل بازتولید باشند؛ فاقد آزمون‌ها Unrated بمانند.

## فاز 8 — GitHub و انتشار
- انتشار کد، Schema، مستندات و متادیتای مجاز.
- محتوای شخص ثالث فقط با مجوز بازنشر روشن.
- CI برای تست، اسکن، اعتبارسنجی و ساخت Registry.
- گزارش‌ها و آرشیوهای اصلی در صورت نیاز خصوصی بمانند.

معیار پذیرش: README، SECURITY، CONTRIBUTING، License و سیاست بازنشر روشن.

## فاز 9 — نگهداری مستمر
- پایش دوره‌ای Repositoryها و Commitها.
- تشخیص Skill جدید، حذف‌شده، تغییرکرده و تغییر مجوز.
- Snapshot، Changelog و Rollback.
- عدم به‌روزرسانی خودکار Skill فعال بدون ارزیابی مجدد.

## اصول غیرقابل‌مذاکره
1. DR-01 و DR-02 مستقل باقی می‌مانند.
2. هیچ رکورد خامی حذف یا بازنویسی نمی‌شود.
3. اعداد گزارش‌ها تا زمان استخراج و تأیید، «ادعای گزارش» هستند.
4. دانلود مساوی اعتماد، نصب یا اجازه اجرا نیست.
5. محبوبیت و نصب، اثبات کیفیت یا امنیت نیست.
6. مجوز نامعلوم یعنی عدم بازنشر عمومی.
7. هر سیستم‌عامل و هر Agent، آداپتور و تست اختصاصی خودش را دارد.

## اقدام جاری
فاز 1: راستی‌آزمایی Repositoryهای موجود در دو Source Manifest؛ ابتدا Batch کوچک و سپس اجرای کامل با Checkpoint.

---

## Current execution status — 2026-11-19

### Completed
- Corrected source mapping: EN-675 and FA-234 are the primary independent datasets; AUX-FA-750PLUS and AUX-FA-438 are separate supplemental reports.
- Recovered and locally archived the exact EN-675 and FA-234 report texts with SHA-256 checksums.
- Confirmed the original row-level CSV/JSON/XLSX database artifacts are still missing; no 675-row or 234-row replacement has been fabricated.
- Created four independent source manifests. Repository cross-references do not merge skill records.
- Live-verified all 12 repository references explicitly present in the two primary reports; current trees contain 1,291 SKILL.md paths.
- Live-verified all 56 source repository references across the four reports; one is a redirected alias, leaving 55 canonical GitHub repositories and 4,214 current SKILL.md paths (not deduplicated).
- Completed a 25-package collection pilot across OpenAI Codex Security and Cloudflare Security Audit: 100 files, 789,061 bytes, all recorded file hashes match.
- Static scan completed without executing downloaded code. Three packages remain in manual review; one has a high-confidence credential-to-HTTP-body signal.

### In progress
- Complete manual review and risk classification before any package is promoted to installable.
- Repository metadata and recursive trees are now verified for all 56 source references; maintain periodic re-verification and resolve future redirects.
- Expand collection from verified repositories with dry-run caps and package-level checkpoints.
- Build content-hash deduplication and the central registry without modifying source datasets.

### Blockers / gates
- EN-675 and FA-234 row-level databases cannot be imported or reconciled until the original CSV/JSON/XLSX artifacts are recovered or supplied.
- Unknown repository licenses remain unknown; do not redistribute or publish third-party content without license verification.
- No Skill is approved for installation solely because it is official or has no static scanner findings.
