# Target hisobot — Meta Ads → Telegram

Meta Ads kabinetlaridan ma'lumot olib, "umrbek hisobot" Telegram guruhiga hisobot va PDF yuboradi.

## Nima qiladi
- **Har kuni ~18:05 (Toshkent)**: faqat hozir ishlab turgan reklamalar bo'yicha hisobot + PDF.
- **Guruhdagi buyruqlar** (har 5 daqiqada tekshiriladi, javob ~5–10 daqiqada):
  - `/hisobot` — hozirgi holat
  - `/hisobot 26.09.2026` — o'sha kungi hisobot (o'sha kuni pul sarflagan reklamalar)
  - `/hisobot kecha`
  - `/yordam`

## Metrikalar
| | |
|---|---|
| Natija | Ads Manager'dagi **Results** ustuni (Meta'ning o'z hisobi) |
| Natija narxi | sarf / natija |
| Qo'ng'iroqlar | qo'ng'iroq qildi · 20s+ gaplashdi · 60s+ gaplashdi va narxlari (call kampaniyalarda) |
| Link click, CTR, CPC, CPM | Ads Manager'dagi link ko'rsatkichlari |
| Konversiya | natija / link click |
| Chastota | 7 kunlik |
| Hook rate | 3 soniyalik video ko'rish / ko'rsatish (faqat video) |

«7 kun» = kechagacha 7 to'liq kun (Ads Manager'dagi *Last 7 days* bilan bir xil). Tarixiy hisobotda — tanlangan kun bilan tugaydigan 7 kun.

Signal chegaralari `config.yaml` → `rules` bo'limida. Ular **boshlang'ich gipoteza**, o'z natijalaringizga qarab moslang.

## Sozlash (bir marta)
Repo → **Settings → Secrets and variables → Actions → New repository secret**:
- `META_ACCESS_TOKEN` — System user token (`ads_read`, muddatsiz)
- `TELEGRAM_BOT_TOKEN` — @BotFather'dan
- `TELEGRAM_CHAT_ID` — guruh ID'si (`-100...` yoki `-...`)

Tokenlar faqat Secrets'da turadi — kodda ham, config'da ham yo'q.

## Loyiha qo'shish
`config.yaml` → `projects` ga yangi blok. Bir loyiha bir nechta kabinetdan yig'ilishi mumkin (`sources`), kampaniya nomidagi so'z bo'yicha ajratiladi (`campaign_contains` / `exclude_contains`).

## Qo'lda ishga tushirish
**Actions → Kunlik target hisobot → Run workflow** (sana maydoni bo'sh = hozirgi holat).

## Cheklovlar
- GitHub rejalashtirilgan ishlarni ba'zan kechiktiradi — aniq daqiqa kafolatlanmaydi.
- Public repo'da 60 kun commit bo'lmasa GitHub jadvalni o'chiradi; kunlik ish 45 kunda bir marta `keepalive` commit qiladi.
- Hisobot hech narsani o'chirmaydi yoki o'zgartirmaydi — token faqat o'qiy oladi.
