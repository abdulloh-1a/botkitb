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

## Render'ga joylash (tavsiya etiladi)

Loyihada `render.yaml` (Blueprint) tayyor. U botni **Background Worker** sifatida
ishga tushuradi va `/data` papkasiga **doimiy disk** ulaydi, shuning uchun arizalar
va FSM holatlari redeploy/restart'larda yo'qolmaydi.

1. Yuqoridagidek kodni GitHub'ga yuklang.
2. [render.com](https://dashboard.render.com) → **New → Blueprint** → repositoriyani tanlang → **Apply**.
3. Yaratilgan xizmatning **Environment** bo'limida ikkita maxfiy o'zgaruvchini to'ldiring:
   - `BOT_TOKEN` — @BotFather dan olingan token
   - `SUPER_ADMIN_ID` — masalan `8328359338`
4. **Logs** bo'limida `Bot ishga tushdi` degan xabarni ko'ring.
5. Telegramda botga yozib sinab ko'ring.

> ⚠️ Render'da bot ishga tushganda **mahalliy botni to'xtating** (`pkill -f "python bot.py"`),
> aks holda bir token bilan ikki jarayon polling qilib, xatolik beradi.

### Logdagi tez-tez uchraydigan xabarlar

- `TelegramForbiddenError: Forbidden: bot was blocked by the user` — **biror foydalanuvchi
  botni bloklagan**. Bot unga xabar yubora olmaydi, lekin ishlashda davom etadi (xato endi
  `WARNING` sifatida yoziladi, traceback chiqmaydi). Hal qilish: Telegram'da bot bilan chatni
  ochib, **Unblock / Blokdan chiqarish** tugmasini bosing va `/start` yuboring.
  Super admin bloklagan bo'lsa, unga ariza bildirishnomalari ham kelmaydi.
- `No open ports detected ... create a background worker instead` — xizmat **Web Service**
  sifatida yaratilgan. Bot HTTP port ochmaydi, shuning uchun Render port qidiraveradi.
  To'g'risi: **Background Worker** (Start Command yana `python bot.py`). Bot ishledi, lekin
  port skanerlash ogohlantirishlari chiqavermasligi uchun xizmat turini almashtiring.
- `PLACEHOLDER rejimi` — Render'da `BOT_TOKEN` yoki `SUPER_ADMIN_ID` to'ldirilmagan.
  **Environment** bo'limida kiriting.

> ❌ **Har 5 daqiqada qayta deploy qilish kerak emas.** Background Worker doimiy ishlaydi,
> jarayon o'chib qolsa Render o'zi qayta ishga tushuradi. Bepul Web Service'ni uxlamaslik
> uchun ping qilish ham SQLite ni saqlab qolmaydi — fayl tizimi vaqtinchalik. Faqat yuqoridagi
> doimiy disk (`/data`) ma'lumotni saqlaydi. Har 5 daqiqadagi deploy esa botni qisqa vaqtga
> to'xtatadi va pipeline daqiqalarini behuda sarflaydi.

**Muhim:** Render'ning bepul rejimida Background Worker va doimiy disk yo'q; bepul
Web Service 15 daqiqa harakatsizlikdan keyin uxlaydi va mahalliy fayllari (SQLite)
o'chadi. Shuning uchun ishchi bot uchun eng kam **0.5c-512mb** rejasi + 1 GB disk
kerak (taxminan $7/oy). Kod boshqa hostingga ham mos: faqat `DATABASE_PATH` ni
doimiy papkaga yo'naltiring.

Bot yaratuvchisi: **Xudoberdiyev Abdulloh**.
