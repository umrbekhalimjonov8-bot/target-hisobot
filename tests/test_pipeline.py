"""Test: soxta (sintetik) Meta javoblari bilan butun zanjirni tekshiradi.
Bu raqamlar HAQIQIY EMAS — faqat kod to'g'ri ishlashini ko'rish uchun."""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml
from src.analyze import analyze, periods
from src.telegram_report import build_messages
from src.pdf_report import build_pdf

random.seed(7)
TODAY = date(2026, 9, 28)  # dushanba — haftalik blok ham tekshiriladi

ADS = [  # (ad_id, nom, adset, kunlik sarf, lead ehtimoli / 1000 ko'rsatish, ctr)
    ("1", "Video — ota-onalar fikri", "Ota-onalar 28-45", 120000, 0.9, 1.4),
    ("2", "Karusel — sinf xonalari", "Ota-onalar 28-45", 90000, 0.35, 0.9),
    ("3", "Stories — ochiq eshiklar", "Keng auditoriya", 80000, 0.0, 0.5),
    ("4", "Rasm — chegirma", "Lookalike 1%", 60000, 0.6, 1.1),
]


def fake_rows():
    rows = []
    since = periods(TODAY)["fetch_since"]
    d = since
    while d <= TODAY:
        for aid, name, adset, spend, lp, ctr in ADS:
            k = 0.45 if d == TODAY else 1.0
            sp = spend * k * random.uniform(0.8, 1.2)
            impr = sp / 25
            c = ctr * (0.5 if aid == "4" and d >= TODAY - timedelta(days=3) else 1)
            leads = round(impr / 1000 * lp * random.uniform(0.6, 1.4) * 10)
            rows.append({"date_start": d.isoformat(), "ad_id": aid, "ad_name": name, "adset_name": adset,
                         "campaign_name": "Qabul 2026", "spend": f"{sp:.0f}", "impressions": f"{impr:.0f}",
                         "inline_link_clicks": f"{impr * c / 100:.0f}",
                         "actions": [{"action_type": "lead", "value": str(leads)}] if leads else []})
        d += timedelta(days=1)
    return rows


cfg = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config.yaml", encoding="utf-8"))
project = {"name": "DEMO loyiha (soxta ma'lumot)", "result_action": "lead", "target_cpl": None}
rf = {"1": (9000, 2.1), "2": (7000, 3.6), "3": (8000, 1.8), "4": (5000, 2.4)}
st = {a[0]: "ACTIVE" for a in ADS}
pl = [
    {"publisher_platform": "instagram", "platform_position": "feed", "spend": "900000", "impressions": "36000",
     "inline_link_clicks": "400", "actions": [{"action_type": "lead", "value": "70"}]},
    {"publisher_platform": "instagram", "platform_position": "instagram_stories", "spend": "600000",
     "impressions": "30000", "inline_link_clicks": "200", "actions": [{"action_type": "lead", "value": "30"}]},
    {"publisher_platform": "facebook", "platform_position": "feed", "spend": "300000", "impressions": "12000",
     "inline_link_clicks": "90", "actions": [{"action_type": "lead", "value": "12"}]},
]
rep = analyze(project, {"name": "DEMO akkaunt", "currency": "UZS"}, fake_rows(), rf, st, pl, TODAY, cfg["rules"])

assert rep.totals["week"]["spend"] > 0
assert any("O'CHIRISH" in s[1] and "ochiq eshiklar" in s[1] for s in rep.signals), rep.signals
assert any("CHASTOTA" in s[1] for s in rep.signals)
assert any("CTR TUSHDI" in s[1] for s in rep.signals)
assert rep.winners and rep.winners[0]["ad_id"] == "1"
msgs = build_messages([rep], TODAY, [("Boshqa loyiha", "[190] Error validating access token")])
assert all(len(m) < 4096 for m in msgs)
out = str(Path(__file__).resolve().parent / "demo_hisobot.pdf")
build_pdf([rep], "DEMO — soxta ma'lumot", out)
for m in msgs:
    print(m)
print("\nOK — barcha tekshiruvlar o'tdi. Dashboard:", out)
