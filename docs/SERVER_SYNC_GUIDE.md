# Server Sync Guide

این راهنما برای جلوگیری از اختلاف بین نسخه عملیاتی سرور، کانتینر Docker و نسخه public-safe داخل GitHub نوشته شده است.

در این پروژه معمولاً سه محل متفاوت وجود دارد:

```text
1. نسخه live داخل کانتینر: /app
2. نسخه فایل‌های پروژه روی سرور: /opt/pelak-khan/IranPlate-Vision
3. نسخه public-safe در GitHub: bahram-khakbaz/ai-license-plate-access-platform
```

نسخه live سرور و کانتینر می‌تواند شامل دیتابیس، مدل، cache، عکس پلاک، لاگ، بکاپ و تنظیمات عملیاتی باشد. نسخه GitHub باید فقط شامل کد، قالب‌ها، فایل‌های static عمومی، مستندات و ساختار امن پروژه باشد.

---

## اصل مرجع

برای توسعه عملیاتی، مرجع واقعی سامانه معمولاً نسخه live داخل کانتینر است:

```text
iranplate-vision:/app
```

اما برای GitHub نباید کل محتوای کانتینر یا سرور بدون بررسی منتقل شود. فقط فایل‌های source و public-safe باید وارد repository شوند.

---

## فایل‌هایی که مجاز است از سرور/کانتینر به GitHub منتقل شوند

این فایل‌ها معمولاً source code یا UI هستند و در صورت نبود اطلاعات حساس می‌توانند sync شوند:

```text
app.py
dx_multi_site.py
camera_manager.py
db.py
storage.py
config.py
import_tools.py
plate_engine.py
requirements.txt
Dockerfile
Dockerfile.vm-cpu
docker-compose.yml
compose.vm.yml
Makefile
README.md
CONTRIBUTING.md
LICENSE
.gitignore
.env.example
```

پوشه‌های مجاز:

```text
templates/
static/
docs/
scripts/
.github/
```

قبل از انتقال `static/` باید مطمئن شد تصویرهای پلاک، captureها، فایل‌های خروجی، لوگ‌های مرورگر یا فایل‌های آپلودی داخل آن نباشند.

---

## فایل‌هایی که نباید وارد GitHub شوند

این موارد runtime، حساس یا مخصوص محیط عملیاتی هستند و نباید commit شوند:

```text
traffic.db
*.db
*.sqlite
*.sqlite3
.env
.env.*
.env.ldap
*.pem
*.key
*.crt
best.pt
docker-cache/
models-cache/
hezar-cache/
.cache/
data/
uploads/
exports/
logs/
captures/
backups/
app/backups/
static/captures/
__pycache__/
*.pyc
*.log
*.pid
```

فایل‌های backup روی سرور هم نباید وارد GitHub شوند:

```text
app.py.bak-*
camera_manager.py.bak-*
db.py.bak-*
dx_multi_site.py.bak-*
templates/*.bak-*
```

مدل‌های حجیم و فایل‌های وزن AI/OCR نیز نباید داخل GitHub عمومی قرار بگیرند، مگر اینکه عمداً و با مجوز، از طریق release asset یا storage جداگانه مدیریت شوند.

---

## اطلاعاتی که باید قبل از Sync پاک یا sanitize شوند

قبل از هر انتقال از سرور به GitHub، این موارد را بررسی و حذف کنید:

```text
آدرس RTSP دوربین‌ها
IP داخلی سرورها
نام کاربری و رمز عبور
توکن‌ها و کلیدها
نام واقعی افراد در داده‌های تستی
شماره پلاک واقعی در fixture یا screenshot
تصاویر خودرو و پلاک واقعی
مسیرهای داخلی حساس
اطلاعات اتصال LDAP / AD / VPN / Firewall
```

---

## روش پیشنهادی برای مقایسه سرور و کانتینر

اگر روی سرور دسترسی دارید، اول نسخه live داخل کانتینر را با نسخه پروژه روی هاست مقایسه کنید:

```bash
cd /opt/pelak-khan/IranPlate-Vision
mkdir -p /tmp/iranplate-live-check

docker cp iranplate-vision:/app/app.py /tmp/iranplate-live-check/app.py
docker cp iranplate-vision:/app/dx_multi_site.py /tmp/iranplate-live-check/dx_multi_site.py
docker cp iranplate-vision:/app/templates /tmp/iranplate-live-check/templates
docker cp iranplate-vision:/app/static /tmp/iranplate-live-check/static

diff -u app.py /tmp/iranplate-live-check/app.py | head -120 || true
diff -u dx_multi_site.py /tmp/iranplate-live-check/dx_multi_site.py | head -120 || true
diff -qr templates /tmp/iranplate-live-check/templates | head -120 || true
diff -qr static /tmp/iranplate-live-check/static | head -120 || true
```

اگر اختلاف وجود داشت و کانتینر نسخه درست عملیاتی است، فقط فایل‌های source را از کانتینر به پروژه روی هاست منتقل کنید.

---

## روش پیشنهادی برای Sync از کانتینر به پوشه پروژه سرور

```bash
cd /opt/pelak-khan/IranPlate-Vision

docker cp iranplate-vision:/app/app.py ./app.py
docker cp iranplate-vision:/app/dx_multi_site.py ./dx_multi_site.py
docker cp iranplate-vision:/app/templates/. ./templates/
docker cp iranplate-vision:/app/static/. ./static/
```

بعد از sync، حتماً بررسی کنید فایل‌های runtime وارد Git نشده باشند:

```bash
git status --ignored | head -150
git status
```

---

## چک قبل از Commit

قبل از commit یا انتقال به GitHub، این دستورها کمک می‌کنند فایل‌های خطرناک را پیدا کنید:

```bash
find . -maxdepth 3 \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '.env*' -o -name '*.key' -o -name '*.pem' -o -name '*.crt' \)
find . -maxdepth 3 \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' -o -name '*.webp' -o -name '*.mp4' \)
find . -maxdepth 2 -name '*bak*'
```

همچنین برای پیدا کردن موارد حساس احتمالی:

```bash
grep -RIn "rtsp://\|password\|passwd\|secret\|token\|ldap\|private key\|BEGIN RSA\|BEGIN OPENSSH" . \
  --exclude-dir=.git \
  --exclude-dir=__pycache__ \
  --exclude-dir=data \
  --exclude-dir=uploads \
  --exclude-dir=exports \
  --exclude-dir=logs \
  --exclude-dir=captures \
  --exclude='*.db' \
  --exclude='*.sqlite' \
  --exclude='*.sqlite3'
```

---

## مسیر درست برای به‌روزرسانی GitHub

وقتی دسترسی مستقیم از سرور به GitHub وجود ندارد، مسیر امن این است:

```text
1. تغییرات live روی سرور بررسی شود.
2. فقط فایل‌های source و public-safe مشخص شوند.
3. محتوای حساس حذف یا عمومی‌سازی شود.
4. فایل‌های تمیز داخل GitHub آپدیت شوند.
5. README و CHANGELOG مطابق تغییرات اصلاح شوند.
```

نباید کل پوشه سرور یا خروجی `tar` مستقیم در GitHub آپلود شود.

---

## چک‌های بعد از Pull روی سرور

اگر بعداً از GitHub روی سرور pull انجام شد، قبل از restart این‌ها را تست کنید:

```bash
python -m py_compile app.py dx_multi_site.py
```

اگر پروژه داخل کانتینر اجرا می‌شود:

```bash
docker exec iranplate-vision python -m py_compile /app/app.py /app/dx_multi_site.py
```

تست‌های سریع:

```bash
curl -I http://localhost/status
curl -I http://localhost/login
curl -I http://localhost/logout
curl -I http://localhost/dx/sites
curl -I http://localhost/logs
```

انتظار برای logout:

```text
HTTP/1.1 302 FOUND
Location: /login
Set-Cookie: session=; Expires=Thu, 01 Jan 1970...
```

---

## چیزهایی که GitHub باید نشان دهد

GitHub باید نماینده ساختار و منطق پروژه باشد:

```text
کد برنامه
قالب‌های UI
فایل‌های CSS/JS عمومی
لوگوی عمومی و branding غیرحساس
مستندات
Dockerfile و compose template
.env.example
README
CHANGELOG
راهنمای sync
```

GitHub نباید mirror کامل محیط production باشد.

---

## وضعیت فعلی پروژه

وضعیت عملیاتی که باید در GitHub منعکس شود:

```text
- Login فارسی و برند DigiExpress
- RBAC برای admin / security / viewer
- Hard logout و session clear
- /dx/whoami برای بررسی نقش کاربر
- داشبورد زنده تردد
- گزارش ورود و خروج Site-Based
- ثبت تردد دستی
- اسکن دستی پلاک با OCR / AI
- ثبت و نمایش رنگ پلاک
- مدیریت خودروها و رانندگان
- مدیریت دوربین‌های RTSP
- مدیریت Siteها و اتصال دوربین به Site
- CSV Import / Export
- مستندات public-safe
```

---

## جمع‌بندی

سرور و کانتینر می‌توانند شامل همه چیز لازم برای اجرا باشند، اما GitHub باید نسخه تمیز، قابل انتشار، قابل توسعه و بدون داده حساس پروژه باشد.

هر تغییری که از production به GitHub منتقل می‌شود باید از این فیلتر عبور کند:

```text
آیا source code است؟
آیا برای توسعه لازم است؟
آیا اطلاعات حساس ندارد؟
آیا بدون دیتابیس و فایل runtime قابل فهم است؟
آیا README یا CHANGELOG نیاز به به‌روزرسانی دارد؟
```

اگر پاسخ مثبت بود، فایل می‌تواند به GitHub منتقل شود. در غیر این صورت باید در سرور، backup یا storage عملیاتی باقی بماند.