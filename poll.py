"""Guruhdagi buyruqlarni tekshiradi (GitHub Actions har 5 daqiqada ishga tushiradi).

  /hisobot              — hozirgi holat (faol reklamalar)
  /hisobot 26.09.2026   — o'sha kungi hisobot (o'sha kuni ishlagan reklamalar)
  /hisobot kecha        — kechagi kun
  /yordam               — buyruqlar ro'yxati

Faqat TELEGRAM_CHAT_ID dagi guruhdan kelgan buyruqlarga javob beriladi.
Telegram xabarlarni 24 soat saqlaydi; o'qilganlari offset bilan tasdiqlanadi.
"""
import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from main import load_config, parse_date, send_report
from src.meta import MetaClient
from src.telegram_report import Telegram

HELP = ("🤖 <b>Buyruqlar</b>\n\n"
        "/hisobot — hozirgi holat (faol reklamalar)\n"
        "/hisobot 26.09.2026 — o'sha kungi hisobot\n"
        "/hisobot kecha — kechagi kun\n\n"
        "<i>Javob ~5–10 daqiqada keladi (GitHub har 5 daqiqada tekshiradi).</i>")

CMD = re.compile(r"^/(hisobot|report|yordam|help|start)(?:@\w+)?(?:\s+(.*))?$", re.I | re.S)


def main():
    token, chat_id = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    base = f"https://api.telegram.org/bot{token}"
    upd = requests.get(f"{base}/getUpdates", params={"timeout": 0, "allowed_updates": '["message"]'}, timeout=30).json()
    updates = upd.get("result", [])
    if not updates:
        print("Yangi buyruq yo'q")
        return

    commands = []
    for u in updates:
        m = u.get("message") or {}
        if str((m.get("chat") or {}).get("id")) != str(chat_id):
            continue  # begona chatlarga javob bermaymiz
        mt = CMD.match((m.get("text") or "").strip())
        if mt:
            commands.append((mt.group(1).lower(), (mt.group(2) or "").strip(), m.get("message_id")))

    # O'qilganlarini tasdiqlaymiz — keyingi ishga tushishda qayta ishlanmasin
    requests.get(f"{base}/getUpdates", params={"offset": updates[-1]["update_id"] + 1, "timeout": 0}, timeout=30)

    if not commands:
        print("Buyruq yo'q")
        return

    cfg = load_config()
    client = MetaClient(os.environ["META_ACCESS_TOKEN"], cfg.get("api_version", "v25.0"))
    tg = Telegram(token, chat_id)
    today = datetime.now(ZoneInfo(cfg.get("report_timezone", "Asia/Tashkent"))).date()
    done = set()
    for cmd, arg, mid in commands:
        if cmd in ("yordam", "help", "start"):
            tg.send(HELP)
            continue
        try:
            if not arg or arg.lower() in ("bugun", "hozir"):
                day = None
            elif arg.lower() == "kecha":
                day = today - timedelta(days=1)
            else:
                day = parse_date(arg)
                if day > today:
                    raise ValueError("Kelajakdagi sana uchun hisobot bo'lmaydi")
                if day == today:
                    day = None
        except ValueError as e:
            tg.send(f"❗ {e}\nMisol: /hisobot 26.09.2026")
            continue
        key = day or "now"
        if key in done:
            continue  # bir xil so'rov takrorlansa bir marta yuboramiz
        done.add(key)
        send_report(cfg, client, tg, day)


if __name__ == "__main__":
    sys.exit(main())
