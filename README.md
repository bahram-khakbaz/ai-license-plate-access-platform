# DigiExpress AI License Plate Access Platform

سامانه پلاک‌خوان دیجی‌اکسپرس یک پلتفرم داخلی و قابل توسعه برای مدیریت هوشمند تردد خودروها، تشخیص پلاک با OCR/AI، ثبت ورود و خروج، مدیریت خودروها و رانندگان، اتصال دوربین‌های RTSP، مدیریت Siteها و گزارش‌گیری عملیاتی است.

این Repository نسخه public-safe پروژه است؛ یعنی ساختار، کدها، مستندات و مسیرهای اصلی سامانه را نگهداری می‌کند، اما دیتابیس عملیاتی، تصاویر پلاک، لاگ‌ها، آدرس دوربین‌ها، فایل‌های بکاپ، مدل‌های حجیم و اطلاعات حساس سازمانی عمداً وارد GitHub نمی‌شوند.

---

## وضعیت همگام‌سازی

این نسخه برای نزدیک شدن به وضعیت عملیاتی سرور و کانتینر به‌روزرسانی شده است:

- صفحه ورود با برند DigiExpress و تم فارسی/RTL تنظیم شد.
- مسیرهای Role-Based Access Control برای `admin`، `security` و `viewer` تعریف شدند.
- Logout سخت‌گیرانه برای پاک‌سازی session اضافه شده است.
- داشبورد زنده، گزارش ورود و خروج، مدیریت Siteها، دوربین‌ها، خودروها و ثبت دستی در ساختار GitHub نگهداری می‌شوند.
- ماژول سازگاری `dx_multi_site.py` اضافه شد تا Deployهایی که هنوز این فایل را import می‌کنند fail نشوند.
- Runtime data مثل `traffic.db`، `captures`، `uploads`، `logs`، `backups` و secrets از Git خارج هستند.

---

## قابلیت‌های اصلی

### 1. تشخیص پلاک با OCR / AI

- پردازش تصویر پلاک و خودرو.
- پشتیبانی از اسکن دستی تصویر.
- ثبت خروجی OCR و confidence.
- نگهداری مسیر تصویر کامل و crop پلاک در runtime.
- پشتیبانی از تشخیص و ثبت رنگ پلاک در رویدادهای تردد.

### 2. داشبورد زنده تردد

- نمایش آمار لحظه‌ای ورود، خروج، ثبت دستی و تعداد خودروها.
- انتخاب Site برای مشاهده داده‌های همان موقعیت.
- نمایش آخرین ترددها.
- نمایش موارد نیازمند بررسی.
- API زنده از مسیر `/dx/api/live-data`.

### 3. گزارش ورود و خروج

- مشاهده سوابق تردد.
- فیلتر بر اساس Site.
- نمایش شماره پلاک، نوع تردد، منبع ثبت، وضعیت خودرو، رنگ پلاک و زمان ثبت.
- API گزارش Site-Based از مسیر `/dx/api/logs`.

### 4. ثبت تردد دستی

- ثبت رسمی ورود/خروج توسط اپراتور.
- انتخاب Site.
- ثبت نام اپراتور و توضیحات.
- استفاده برای مواقعی که دوربین یا OCR در دسترس نیست.

### 5. اسکن دستی پلاک

- آپلود تصویر خودرو یا پلاک.
- پردازش با AI/OCR.
- ثبت نتیجه در گزارش تردد.
- امکان ثبت رنگ پلاک.

### 6. مدیریت خودروها و رانندگان

- ثبت پلاک.
- نام راننده، تلفن، کد پرسنلی، واحد، شرکت، مدل خودرو، رنگ خودرو و وضعیت مجوز.
- پشتیبانی از Import از فایل Excel/CSV.

### 7. مدیریت دوربین‌های RTSP

- تعریف دوربین ورود/خروج.
- نگهداری role دوربین مثل entry/exit.
- اتصال دوربین‌ها به Site.
- آماده برای اتصال به پردازش‌های RTSP در محیط عملیاتی.

### 8. مدیریت Siteها

مسیرهای مرتبط:

```text
/settings/sites
/dx/sites
/site-admin
```

قابلیت‌ها:

- ساخت Site جدید.
- ویرایش نام، کد، توضیح و وضعیت فعال/غیرفعال.
- مشاهده تعداد دوربین‌ها و ترددهای هر Site.
- اتصال دوربین‌ها به Site در همان صفحه.

---

## نقش‌ها و سطح دسترسی

### Admin

دسترسی کامل به همه بخش‌ها، تنظیمات، import، وضعیت مدل و APIهای مدیریتی.

### Security / Harasat

دسترسی عملیاتی:

- داشبورد زنده تردد
- اسکن دستی پلاک
- دوربین‌های ورود و خروج
- مدیریت Siteها
- خودروها و رانندگان
- ثبت تردد دستی
- گزارش ورود و خروج

بدون دسترسی به مدیریت کاربران، تنظیمات مدیریتی، shortcutهای API گزارش، import مدیریتی و ثبت موبایلی.

### Viewer

فقط مشاهده:

- داشبورد زنده تردد
- گزارش ورود و خروج

---

## تکنولوژی‌های استفاده‌شده

```text
Python
Flask
SQLite
Docker
HTML / CSS / JavaScript
RTSP Stream
OCR / AI Model
Multi-Site Architecture
CSV / Excel Import & Export
```

---

## مسیرهای اصلی

```text
/                         داشبورد زنده
/login                    ورود
/logout                   خروج و پاک‌سازی session
/dx/logout                alias خروج
/force-logout             alias خروج
/scan                     اسکن دستی پلاک
/manual-entry             ثبت تردد دستی
/mobile-entry             ثبت موبایلی برای admin
/vehicles                 خودروها و رانندگان
/vehicles/import          ورود گروهی Excel/CSV
/cameras                  دوربین‌ها
/logs                     گزارش ورود و خروج
/settings/sites           مدیریت Siteها
/dx/sites                 alias مدیریت Siteها
/site-admin               alias مدیریت Siteها
/status                   وضعیت سرویس AI/OCR
/dx/whoami                مشاهده کاربر و role فعلی
```

---

## APIهای اصلی

```text
GET /dx/whoami
GET /dx/api/live-data
GET /dx/api/logs
GET /dx/api/sites
GET /api/dashboard-stats
GET /api/sites
GET /api/vehicles
GET /api/log
GET /dx/vehicle-import-template.csv
```

---

## دیتابیس

مسیر پیش‌فرض دیتابیس در نسخه template:

```text
data/traffic.db
```

در سرور عملیاتی ممکن است مسیر runtime داخل کانتینر مثل `/app/traffic.db` باشد. دیتابیس عملیاتی نباید در Git commit شود.

جدول‌های اصلی در این نسخه public-safe:

```text
users
sites / dx_sites در Deploy عملیاتی
vehicles
cameras
events / access_log در Deploy عملیاتی
```

Roleهای معتبر:

```text
admin
security
viewer
```

---

## راه‌اندازی محلی

```bash
git clone https://github.com/bahram-khakbaz/ai-license-plate-access-platform.git
cd ai-license-plate-access-platform
cp .env.example .env
docker compose up -d --build
```

سپس:

```text
http://localhost
```

---

## تست‌های ضروری بعد از Deploy

### سلامت سرویس

```bash
curl -I http://localhost/status
```

### بررسی Role کاربر

بعد از Login:

```text
/dx/whoami
```

نمونه خروجی:

```json
{
  "logged_in": true,
  "username": "user@example.com",
  "db_role": "security",
  "normalized_role": "security"
}
```

### تست Logout

```bash
curl -I http://localhost/logout
```

خروجی درست:

```text
HTTP/1.1 302 FOUND
Location: /login
Set-Cookie: session=; Expires=Thu, 01 Jan 1970...
```

### تست Site Management

```bash
curl -I http://localhost/dx/sites
curl -I http://localhost/site-admin
```

---

## Runtime Data که نباید وارد Git شود

```text
traffic.db
*.db
*.sqlite
*.sqlite3
data/
uploads/
exports/
logs/
captures/
backups/
.env
.env.*
*.pem
*.key
*.crt
```

همچنین فایل‌هایی مثل مدل‌ها، cache، تصویر پلاک، آدرس RTSP واقعی، لاگ عملیاتی و بکاپ‌ها نباید داخل GitHub قرار بگیرند.

---

## Sync درست بین سرور، کانتینر و GitHub

در محیط عملیاتی معمولاً سه سطح وجود دارد:

```text
1. کد Live داخل کانتینر: /app
2. کد روی سرور/هاست: /opt/pelak-khan/IranPlate-Vision
3. نسخه public-safe در GitHub
```

GitHub باید شامل کد، template، static، مستندات و ساختار قابل Deploy باشد؛ اما runtime data نباید وارد آن شود.

---

## Changelog کوتاه

### 2026-07-13

- RBAC نهایی برای admin/security/viewer.
- خواندن Role از دیتابیس users.
- اضافه شدن `/dx/whoami`.
- اصلاح Logout برای همه Roleها.
- یکپارچه‌سازی مدیریت Site و اتصال دوربین.
- اضافه شدن پشتیبانی CSV Import.
- بهبود UI فارسی و Role-aware.
- اضافه شدن branding صفحه Login.
- اضافه شدن ماژول سازگاری `dx_multi_site.py`.

---

## Designed & Developed by

DigiExpress Infrastructure
