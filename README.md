# 10-maktab kitobxonlik musobaqasi boti

Aiogram 3 + SQLite (aiosqlite) asosida yozilgan to'liq Telegram bot.
Faqat Farg'ona viloyati, Toshloq tumani, 10-umumiy o'rta ta'lim maktabining
6–11-sinf o'quvchilari ariza topshirishi mumkin.

## Ishga tushirish (Ubuntu)

```bash
cd ~/Music/book_competition_bot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
nano .env          # BOT_TOKEN va SUPER_ADMIN_ID ni to'ldiring

python bot.py
```

Avtomatik qayta ishga tushurish uchun:
```bash
./start_bot.sh
```
yoki systemd xizmati (`book-competition-bot.service`) dan foydalaning.

Token @BotFather dan, Telegram ID @userinfobot dan olinadi.
Baza birinchi ishga tushirishda `data/bot.db` yo'lida avtomatik yaratiladi.
Eski bazada `user_id UNIQUE` bo'lsa, ishga tushirishda avtomatik yangi sxemaga o'tkaziladi
(ma'lumotlar yo'qotilmaydi).

## Buyruqlar

- `/start` — asosiy menyu
- `/apply` — ariza topshirish
- `/admin` — admin paneli (faqat adminlar)
- `/competition` — musobaqa sanasi/vaqti/joyi
- `/help` — yordam

## Xavfsizlik

- Super admin ID faqat `.env` da saqlanadi va paneldan o'chirib bo'lmaydi.
- Oddiy admin admin qo'sha/ololmaydi, Excel eksporti va bot statistikasini ko'rmaydi.
- Ariza faqat bir marta tasdiqlanadi (`WHERE status='pending'`).
- Bitta Telegram profilidan **5 tagacha** ariza topshirish mumkin (6-chi rad etiladi).
- Telefon bosqichida oxirgi ishlatilgan raqam avtomatik taklif qilinadi: uni nusxalab yoki
  «✅ Shu raqamni ishlatish» tugmasi bilan qabul qilish mumkin. «🎲 Yangi raqam taklif qilish»
  har bir o'quvchi uchun yangi, takrorlanmaydigan raqam yaratadi. «✏️ Boshqa raqam yuborish»
  bilan o'zingiznikini ham kiritishingiz mumkin.
- Har bir arizaning telefon raqamini «👤 Mening arizam» → ariza → «📱 Telefon raqamini
  o'zgartirish» orqali keyinroq ham o'zgartirish mumkin.
- Rad etilgan arizani qayta topshirishda yangi qator yaratilmay, eskisi yangilanadi.
- Sinf (`6`–`11`) va jins (`1` — o'g'il, `2` — qiz) ham tugma, ham matn bilan qabul qilinadi.
- FSM holati `data/bot.db` da saqlanadi — server qayta ishlaganda ariza yo'qolmaydi.
- Barcha xatoliklar `bot.log` fayliga yoziladi.

## GitHub'ga joylash

`.env` fayli `.gitignore` da — token va admin ID hech qachon GitHub'ga yuborilmaydi.
Faqat `.env.example` namuna sifatida saqlanadi.

```bash
cd ~/Music/book_competition_bot
git init
git add .
git commit -m "10-maktab kitobxonlik musobaqasi boti"
git remote add origin https://github.com/<USERNAME>/<REPO>.git
git branch -M main
git push -u origin main
```

## Render'ga joylash — BEPUL rejim (to'liq ishlaydigan tartib)

`render.yaml` tayyor: bot **Web Service** sifatida ishlaydi, lekin ichida kichik
`/health` HTTP server ham ochadi — Render "No open ports" deb ogohlantirmaydi.
Bepul rejim 15 daqiqa harakatsizlikdan keyin uxlab qolgani uchun
`.github/workflows/keep-alive.yml` har 5 daqiqada o'sha `/health` ga so'rov yuboradi.
**Ma'lumot yo'qolmasligi uchun tashqi PostgreSQL shart** (Render bepulida fayl tizimi
vaqtinchalik, disk yo'q).

### 1. Doimiy baza — Neon.tech (bepul)

1. [neon.tech](https://neon.tech) → GitHub bilan ro'yxatdan o'ting → **New Project**.
2. **Connection Details** bo'limidan `psql` / connection string ni oling:
   ```
   postgresql://neondb_owner:PAROL@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require
   ```
3. Bu satrni Render'ga `DATABASE_URL` sifatida kiritasiz (3-qadam).
   Kod `?sslmode=require` ni o'zi `ssl=True` ga aylantiradi.

### 2. GitHub'ga yuklash

```bash
cd ~/Music/book_competition_bot
git add .
git commit -m "Render free: health server, PostgreSQL, keep-alive"
git push origin main
```

`.env` va `data/` git'ga kirmaydi — token va ma'lumot xavfsiz.

### 3. Render xizmati

**New → Blueprint** → reponi tanlang → **Apply** (tavsiya etiladi), yoki qo'lda:

| Sozlama | Qiymat |
|---|---|
| Service Type | **Web Service** |
| Runtime | Python |
| Plan | **Free** |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python bot.py` |
| Health Check Path | `/health` |

**Environment** bo'limi:

| Key | Value |
|---|---|
| `BOT_TOKEN` | @BotFather tokeni |
| `SUPER_ADMIN_ID` | `8328359338` |
| `DATABASE_URL` | 1-qadamda olingan PostgreSQL satri |
| `ENABLE_HEALTH_SERVER` | `true` |
| `ENABLE_FILE_LOG` | `false` |
| `LOG_LEVEL` | `INFO` |
| `BROADCAST_DELAY` | `0.05` |
| `PYTHONUNBUFFERED` | `1` |

Logda shuni ko'rishingiz kerak:
```
Health server ishga tushdi: 0.0.0.0:10000/health
Ma'lumotlar bazasi tayyor: PostgreSQL (DATABASE_URL)
Bot ishga tushdi...
```

### 4. GitHub Actions keep-alive (uxlab qolmasligi uchun)

GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:
- **Name:** `RENDER_URL`
- **Value:** Render bergan URL, masalan `https://book-competition-bot.onrender.com`
  (oxiriga `/health` qo'shmang — workflow o'zi qo'shadi).

Keyin **Actions** → **Render keep-alive** → **Run workflow** → natija `HTTP 200` bo'lishi kerak.
Shundan keyin har 5 daqiqada o'zi ishlaydi. **Deploy qilish shart emas.**

### 5. Tekshirish

Telegramda `/start`, keyin `/admin` yozing. Biror ariza topshiring va admin tomonidan
tasdiqlang. Render'ni qayta deploy qilib, ma'lumot saqlanganligini tekshiring.

> ⚠️ Render ishga tushganda **mahalliy botni to'xtating**:
> ```bash
> pkill -f start_bot.sh; pkill -f "python bot.py"
> ```
> Bir token bilan ikki jarayon polling qilsa, xatolik beradi.

### Logdagi tez-tez uchraydigan xabarlar

- `TelegramForbiddenError: ... bot was blocked by the user` — biror foydalanuvchi botni
  bloklagan. Endi traceback emas, oddiy `WARNING` chiqadi va bot ishlayveradi.
  Telegram'da bot chati → **Unblock / Blokdan chiqarish** → `/start`.
- `TelegramConflictError: terminated by other getUpdates request` — **bir vaqtda ikki bot
  polling qilayapti** (masalan, eski Render xizmati + yangisi, yoki mahalliy bot).
  Aiogram qayta urinadi, lekin sababni yo'q qilish kerak: Render Dashboard'da faqat **bitta**
  xizmat qoldiring, qolganini **Delete** qiling va mahalliy botni to'xtating.
  Deploy paytida bir necha soniya davom etadigan conflict odatiy hol — o'zi tiklanadi.
- `DATABASE_URL yo'q: ma'lumotlar vaqtinchalik SQLite faylida...` — `DATABASE_URL`
  kiritilmagan. Bepul Render'da arizalar restart'da yo'qoladi. 1-qadamga qayting.
- `No open ports detected` — `ENABLE_HEALTH_SERVER` yo'q yoki Health Check Path
  noto'g'ri. `true` va `/health` qiling.
- `PLACEHOLDER rejimi` — `BOT_TOKEN` yoki `SUPER_ADMIN_ID` to'ldirilmagan.

### Pullik alternativa (tashqi bazasiz)

Agar Neon ishlatishni istamasangiz: **Background Worker** + **1 GB disk**,
`DATABASE_PATH=/data/bot.db`, plan `0.5c-512mb` (~$7/oy). Bu holda `DATABASE_URL`
va keep-alive kerak emas — bot doimiy ishlaydi, baza diskda saqlanadi.

Bot yaratuvchisi: **Xudoberdiyev Abdulloh**.
