# DasLab — Boshlang'ich qo'llanma (eng oddiy tilda)

> Bu qo'llanma **hech narsa bilmagan odam uchun**. Har bir qadam ketma-ket
> yozilgan. Yuqoridan pastga qarab, birma-bir bajaring — o'tkazib yubormang.
>
> Tajribali operator uchun to'liq qo'llanma: [`USER-GUIDE.md`](USER-GUIDE.md).
> Bu yerdagi barcha buyruqlar 2026-08-02 kuni haqiqiy mashinada tekshirilgan.

---

## 0. DasLab nima? (1 daqiqalik tushuntirish)

Tasavvur qiling, sizda **32 kishilik dasturchilar kompaniyasi** bor: direktor,
menejerlar, dasturchilar, dizaynerlar, testerlar, marketologlar.

DasLab — o'sha kompaniyaning o'zi, faqat odamlar o'rniga **32 ta AI agent**.
Ular birgalikda haqiqiy dastur yozadi: rejalashtiradi, kod yozadi, tekshiradi,
xatolarni topadi va ishga tushiradi.

Uchta muhim narsani boshidanoq biling:

| Narsa | Ma'nosi |
|---|---|
| **Server yo'q** | Hech qanday sayt, tugma yoki panel yo'q. Hammasi terminal (qora oyna) ichida. |
| **O'zi ishlamaydi** | Siz buyruq bermasangiz, kompaniya **uxlab yotadi**. Tungi taymer yo'q. |
| **Kalit sizda** | Pul, ruxsat va "ishga tushiramizmi?" degan qarorlar **faqat sizniki**. AI o'zi hal qilmaydi. |

**Vazifalar oddiy fayllarda saqlanadi.** `board/tickets/` papkasidagi har bir
`.md` fayl — bitta vazifa. Baza ham, dastur ham emas — shunchaki fayl. Uni
xohlagan paytda ochib o'qishingiz mumkin.

---

## 1. Kerakli narsalar (bir marta o'rnatiladi)

Uchta narsa **shart**:

1. **Claude Code** — AI ishlaydigan dastur (`claude` buyrug'i).
2. **Python 3.10 yoki yuqori** — yordamchi skriptlar shuning ustida ishlaydi.
3. **git** — kod tarixini saqlaydi.

Yana ikkitasi **shart emas**, lekin bo'lsa yaxshi (xotira uchun): **ArcRift** va
**Ollama**. Bo'lmasa ham DasLab ishlayveradi — shunchaki eslab qolmaydi.

Hozir hammasi bor-yo'qligini **o'zingiz tekshirmang** — 3-qadamdagi dastur buni
siz uchun tekshirib beradi.

---

## 2. Papkani ochish

Terminalni oching va DasLab papkasiga kiring:

```bash
cd /home/daslab/projects/daslab
```

> **Nega bu muhim?** Barcha buyruqlar **shu papka ichida** ishlaydi. Boshqa
> joyda tursangiz, "fayl topilmadi" degan xato chiqadi. Adashib qolsangiz,
> yuqoridagi buyruqni yana bir marta yozing.

Qayerda turganingizni tekshirish:

```bash
pwd
```

Ekranda `/home/daslab/projects/daslab` chiqishi kerak.

---

## 3. Birinchi tayyorgarlik (`bootstrap`)

Bu buyruq kompaniyani "uyg'otadi": kerakli papkalarni yaratadi va 32 ta agentni
qaytadan yig'adi.

```bash
python3 scripts/bootstrap.py
```

**Nima ko'rasiz** (oxirgi qatorlar):

```
→ projects/ exists
→ regenerate agent shims
  ok
→ environment preflight (doctor.py)
  ok
bootstrap complete — open `claude` at the repo root, then /daslab-plan "<goal>".
```

`bootstrap complete` so'zini ko'rsangiz — hammasi joyida. ✅

> **Qo'rqmang:** bu buyruqni **necha marta ishlatsangiz ham** hech narsa
> buzilmaydi. U hech narsani o'chirmaydi, faqat yetishmayotganini qo'shadi.

---

## 4. Sog'liqni tekshirish (`doctor`)

Bu — kompaniyaning "shifokori". Kerakli dasturlar bor-yo'qligini aytadi.

```bash
python3 scripts/doctor.py
```

**Nima ko'rasiz:**

```
| Claude Code CLI (claude on PATH)   | REQUIRED | PASS   |
| Python >= 3.10                     | REQUIRED | PASS   |
| git on PATH                        | REQUIRED | PASS   |
| Repo root resolves (LAW A)         | REQUIRED | PASS   |
| projects/ workspace exists         | REQUIRED | PASS   |
| ArcRift MCP reachable              | OPTIONAL | PASS   |
| Ollama + nomic-embed-text          | OPTIONAL | PASS   |
  REQUIRED 5/5 pass · OPTIONAL 2/2 pass
```

Buni shunday o'qing:

- **REQUIRED** = **shart**. Hammasi `PASS` bo'lishi kerak. Bittasi `FAIL` bo'lsa,
  oldinga yurmang — avval o'shani tuzating.
- **OPTIONAL** = **ixtiyoriy**. `WARN` yoki `FAIL` bo'lsa ham davom etishingiz
  mumkin. Bu faqat "uzoq muddatli xotira" ishlamasligini bildiradi.

---

## 5. Hamma narsa butunligini tekshirish (`diagnostics`)

Bu — kompaniyaning **imtihoni**. 7 ta yo'nalish bo'yicha ball qo'yadi.

```bash
python3 scripts/diagnostics.py
```

**Nima ko'rasiz** (eng oxiri):

```
[PASS] Docs           20/20
[PASS] Architecture   20/20
[PASS] Code-quality   15/15
[PASS] Consistency    15/15
[PASS] Portability    15/15
[PASS] Security       10/10
[PASS] Git-hygiene     5/5
SCORE = 100/100
```

> **Muhim qoida:** bu imtihonda **faqat 100/100 o'tgan** hisoblanadi. 99 ham
> yiqilish demakdir. Sababi oddiy: "deyarli xavfsiz" degan narsa yo'q.
> Agar 100 dan kam chiqsa — yuqorida qaysi qator `FAIL` ekanini o'qing,
> u yerda **nima buzilgani aniq yozilgan** bo'ladi.

---

## 6. Claude'ni ochish

Endi AI kompaniyani boshqaradigan oynani ochamiz:

```bash
claude
```

Endi siz Claude ichidasiz. Bundan keyingi buyruqlar terminalga emas,
**Claude oynasiga** yoziladi va ular `/` (slash) bilan boshlanadi.

> **Farqni yodda tuting:**
> `python3 ...` → terminalga yoziladi.
> `/daslab-...` → Claude oynasiga yoziladi.

---

## 7. Kompaniyaga ish berish — 3 ta asosiy buyruq

Bor-yo'g'i uchta buyruqni bilsangiz yetadi.

### 7.1 `/daslab-plan` — "Menga shu narsa kerak"

Maqsadingizni aytasiz, kompaniya uni **vazifalarga bo'lib chiqadi**.

```
/daslab-plan Kitob do'koni uchun oddiy sayt kerak
```

**Nima bo'ladi:** hech qanday kod yozilmaydi. Faqat `board/tickets/` ichida
yangi vazifa fayllari paydo bo'ladi — kim nima qilishi yozilgan holda.

> **Yangi loyiha uchun muhim to'siq bor.** Agar bu butunlay yangi loyiha bo'lsa,
> AI darrov vazifa yozmaydi. Avval sizga **kamida 10 ta savol** beradi (kimlar
> uchun? qancha pul? qachon kerak? raqobatchilar kim? ...). Keyin bozorni
> o'rganib chiqadi va natijani
> `projects/<loyiha-nomi>/APPROVED-GOAL-QUEUE.md` fayliga yozadi.
>
> Siz o'sha faylni **o'qib chiqmaguningizcha va rozilik bermaguningizcha** ish
> boshlanmaydi. Rozilik berish uchun aniq so'z yozasiz:
>
> ```
> APPROVED:
> ```
>
> yoki o'zbekcha:
>
> ```
> TASDIQLANDI:
> ```
>
> Nega bunday? Chunki AI o'zicha "menga shunday yaxshi ko'rindi" deb pulingizni
> va vaqtingizni sarflamasligi kerak. Boshlanish nuqtasi — **sizning ruxsatingiz**.

### 7.2 `/daslab-cycle` — "Bir marta ishlang"

Bu **bitta to'lqin** (wave) ishga tushiradi: taxtadagi tayyor vazifalarni oladi,
kerakli agentlarga tarqatadi, ular ishlaydi, natijani yig'ib sizga aytadi.

```
/daslab-cycle
```

Kichikroq sinov uchun raqam qo'shishingiz mumkin — masalan faqat 3 ta vazifa:

```
/daslab-cycle 3
```

> **"To'lqin" nima?** Bir marta hamma ishchilarni chaqirib, ish topshirib,
> qaytib kelishlarini kutish. Tugagach — kompaniya **yana uxlaydi**. Yana ish
> bo'lishi uchun buyruqni qayta yozasiz.

### 7.3 `/daslab-run` — "Tugagunicha ishlang"

Bu `/daslab-cycle` ni **vazifalar tugagunicha** qayta-qayta ishlatadi.

```
/daslab-run
```

> Faqat **tasdiqlangan** ro'yxatdagi ishlarni bajaradi. Yangi ish o'ylab
> topmaydi. Jiddiy muammo chiqsa — to'xtaydi va sizdan so'raydi.

---

## 8. Natijani qayerdan ko'raman?

| Nima ko'rmoqchisiz | Qayerga qarang |
|---|---|
| Vazifalar ro'yxati | `board/tickets/` papkasi — har bir `.md` fayl bitta vazifa |
| Tayyor mahsulot (kod, sayt) | `projects/<loyiha-nomi>/` papkasi |
| Kompaniya qonunlari | `governance/policies/` papkasi |
| Kim nima qiladi | [`02-ORG.md`](02-ORG.md) |

Vazifalar qay ahvolda ekanini bir qatorda ko'rish (terminalda):

```bash
grep -h "^status:" board/tickets/*.md | sort | uniq -c | sort -rn
```

Javob shunga o'xshash bo'ladi (raqamlar har to'lqindan keyin o'zgaradi —
2026-08-02 holati misol uchun keltirilgan):

```
    190 status: done
      5 status: backlog
      3 status: todo
      3 status: blocked
      1 status: in_review
```

Har bir vazifa fayli boshida shunday yozuv bor:

```
id: DAS-1645
title: ...
status: in_review
assignee: security-lead
```

Buni shunday o'qing: `status` — ish qay bosqichda; `assignee` — kim bajaryapti.

**Status so'zlari:**

| So'z | Ma'nosi |
|---|---|
| `backlog` | Ro'yxatda bor, hali navbat kelmagan |
| `todo` | Boshlashga tayyor |
| `in_progress` | Hozir bajarilyapti |
| `blocked` | To'sib qo'yilgan — boshqa ish tugashini kutyapti |
| `in_review` | Bajarildi, **tekshiruvchi** ko'rib chiqyapti |
| `done` | Tugadi ✅ |

---

## 9. Har kuni qiladigan ish (qisqacha shpargalka)

```bash
cd /home/daslab/projects/daslab
python3 scripts/doctor.py          # sog'lommi?
claude                             # oynani ochish
```

Keyin Claude ichida:

```
/daslab-cycle
```

Tamom. Kunlik ish shu.

---

## 10. Xato chiqsa nima qilaman?

| Ekranda ko'rgan narsangiz | Ma'nosi | Nima qilasiz |
|---|---|---|
| `command not found: claude` | Claude Code o'rnatilmagan | Claude Code'ni o'rnating |
| `No such file or directory` | Noto'g'ri papkadasiz | `cd /home/daslab/projects/daslab` |
| `doctor` da REQUIRED `FAIL` | Shart dastur yo'q | O'sha qatorda nima yetishmayotgani yozilgan — o'shani o'rnating |
| `SCORE = 97/100` | Nimadir buzilgan | Yuqoridagi `FAIL` qatorini o'qing — sabab o'sha yerda |
| `board_lint: ... violations` | Vazifa fayli noto'g'ri to'ldirilgan | Xabarda qaysi fayl va nima xato ekani aniq yozilgan |

**Oltin qoida:** xato xabarini **o'qing**. DasLab'dagi xabarlar "xato bo'ldi" deb
emas, **nima buzilgani va qanday tuzatish** kerakligini yozadigan qilib
tuzilgan. Javob deyarli har doim o'sha xabarning ichida.

---

## 11. Xavfsizlik — nimalarga tegmaslik kerak

1. **Parol va kalitlarni chatga yozmang.** Ular `.env` fayliga yoziladi va
   `.env` hech qachon git'ga tushmaydi. Agar tasodifan yozib yuborsangiz —
   o'sha kalitni **bekor qilib, yangisini oling**.
2. **`projects/` papkasi git'ga tushmaydi.** Har bir loyiha o'z tarixini
   o'zi yuritadi.
3. **Ishga tushirish (production) — faqat sizning qaroringiz.** AI o'zi
   "tayyor, chiqaraman" demaydi.
4. **Xavfli imkoniyatlar boshidan o'chirilgan.** Ularni yoqish alohida,
   ongli harakat talab qiladi.

---

## 12. Keyingi qadam

Bu qo'llanmani tushunib bo'lgach:

| Keyin nima o'qish | Nima haqida |
|---|---|
| [`01-OVERVIEW.md`](01-OVERVIEW.md) | DasLab umumiy tasviri |
| [`USER-GUIDE.md`](USER-GUIDE.md) | To'liq operator qo'llanmasi (inglizcha) |
| [`04-OPERATIONS.md`](04-OPERATIONS.md) | Kundalik boshqaruv |
| [`02-ORG.md`](02-ORG.md) | 32 ta agent va ularning vazifalari |
| [`05-SCRIPTS.md`](05-SCRIPTS.md) | Har bir skript nima qilishi |

---

## Eng qisqa xulosa

```bash
cd /home/daslab/projects/daslab   # 1. Papkaga kir
python3 scripts/bootstrap.py      # 2. Uyg'ot (bir marta)
python3 scripts/doctor.py         # 3. Sog'liqni tekshir
python3 scripts/diagnostics.py    # 4. 100/100 bo'lsin
claude                            # 5. Oynani och
```

Claude ichida:

```
/daslab-plan <maqsadingiz>   → vazifalar yaratiladi
/daslab-cycle                → bir marta ishlanadi
/daslab-run                  → tugagunicha ishlanadi
```

Natija: `projects/` papkasida. Vazifalar: `board/tickets/` papkasida.
