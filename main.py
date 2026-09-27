"""Target hisobot — ishga tushirish nuqtasi.

  python main.py              — hisobot tuzib Telegram'ga yuboradi
  python main.py --dry-run    — yubormaydi, matnni ekranga chiqaradi, dashboard.html saqlaydi
  python main.py --actions    — har bir akkauntdagi natija turlarini ko'rsatadi (result_action tanlash uchun)
"""
import argparse
import os
import sys
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yaml

from src.meta import MetaClient, MetaError
from src.analyze import analyze, periods, name_filter
from src.telegram_report import build_messages, Telegram, WEEKDAYS, dfmt
from src.pdf_report import build_pdf


def load_config(path="config.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def project_sources(project):
    """Loyiha bir nechta kabinetdan yig'ilishi mumkin:
       sources: [{account: act_.., campaign_contains: [..], exclude_contains: [..]}, ...]
    Eski format (ad_account_id + campaign_contains) ham ishlaydi."""
    if project.get("sources"):
        return project["sources"]
    return [{"account": project["ad_account_id"],
             "campaign_contains": project.get("campaign_contains"),
             "exclude_contains": project.get("exclude_contains")}]


def collect(client, project, rules, report_date=None):
    """report_date berilsa — tarixiy hisobot: o'sha kuni pul sarflagan reklamalar."""
    rows, rf, statuses, placements, accounts, problems = [], {}, {}, [], [], []
    historical = report_date is not None
    today = report_date
    for src in project_sources(project):
        act = src["account"]
        account = client.account(act)
        accounts.append(account)
        if today is None:
            today = datetime.now(ZoneInfo(account.get("timezone_name") or "Asia/Tashkent")).date()
        P = periods(today, historical)
        since = min(P["fetch_since"], today - timedelta(days=29))
        w0, w1 = P["week"]
        keep = name_filter(src)
        rows += [r for r in client.daily_ad_insights(act, since.isoformat(), today.isoformat()) if keep(r)]
        placements += [r for r in client.placements(act, w0.isoformat(), w1.isoformat()) if keep(r)]
        rf.update(client.ad_reach_frequency(act, w0.isoformat(), w1.isoformat()))
        if not historical:
            statuses.update(client.ad_statuses(act))
            problems += [x for x in client.problem_ads(act) if keep(x)]

    if historical:
        # o'sha kuni sarf bo'lgan reklama = «ishlagan»; hozirgi holati ahamiyatsiz
        ran = {r["ad_id"] for r in rows if r["date_start"] == today.isoformat() and float(r.get("spend") or 0) > 0}
        statuses = {r["ad_id"]: ("ACTIVE" if r["ad_id"] in ran else "NOT_RUNNING") for r in rows}

    if project.get("only_active", True):
        # Faqat hozir ishlab turgan reklamalar (kampaniya/ad set to'xtatilgan bo'lsa ham chiqariladi)
        rows = [r for r in rows if statuses.get(r.get("ad_id")) == "ACTIVE"]
        placements = [r for r in placements if statuses.get(r.get("ad_id")) == "ACTIVE"]

    currencies = {a.get("currency") for a in accounts}
    merged = {
        "name": " + ".join(a.get("name", "") for a in accounts),
        "currency": accounts[0].get("currency", "") if len(currencies) == 1 else "MIXED",
        # eng yomon holat ko'rsatiladi (1 = aktiv)
        "account_status": next((a.get("account_status") for a in accounts if a.get("account_status") != 1), 1),
    }
    proj = {k: v for k, v in project.items() if k not in ("campaign_contains", "exclude_contains")}
    rep = analyze(proj, merged, rows, rf, statuses, placements, today, rules, historical)
    names = {"DISAPPROVED": "RAD ETILDI", "WITH_ISSUES": "MUAMMO BOR", "PENDING_REVIEW": "TEKSHIRUVDA",
             "IN_PROCESS": "TEKSHIRUVDA", "PENDING_BILLING_INFO": "TO'LOV MA'LUMOTI KERAK"}
    for x in problems:
        rep.signals.insert(0, ("red" if x["status"] in ("DISAPPROVED", "WITH_ISSUES") else "yellow",
                               f"REKLAMA {names[x['status']]}: «{x['ad_name']}» ({x['campaign_name']}) — "
                               f"yoqilgan, lekin ishlamayapti. Ads Manager'da sababini ko'ring"))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--actions", action="store_true")
    ap.add_argument("--date", help="tarixiy hisobot: 26.09.2026")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        sys.exit("META_ACCESS_TOKEN topilmadi")
    client = MetaClient(token, cfg.get("api_version", "v25.0"))

    if args.actions:
        for p in cfg["projects"]:
            end = datetime.now(ZoneInfo(cfg.get("report_timezone", "Asia/Tashkent"))).date()
            for src in project_sources(p):
                types = client.action_types(src["account"], (end - timedelta(days=30)).isoformat(), end.isoformat())
                print(f"\n== {p['name']} ({src['account']}) — oxirgi 30 kun ==")
                for k, v in sorted(types.items(), key=lambda x: -x[1]):
                    print(f"  {v:>10.0f}  {k}")
        return

    report_date = parse_date(args.date) if args.date else None
    if args.dry_run:
        msgs, pdf, _ = build_report(cfg, client, report_date)
        for m in msgs:
            print(m, "\n" + "-" * 40)
        print("PDF:", pdf)
        return
    tg = Telegram(os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"])
    ok = send_report(cfg, client, tg, report_date)
    if not ok:
        sys.exit(1)  # GitHub Actions'da qizil bo'lib ko'rinsin


def parse_date(s):
    s = s.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Sana tushunilmadi: {s}. Format: 26.09.2026")


def build_report(cfg, client, report_date=None):
    reports, failures = [], []
    for p in cfg["projects"]:
        try:
            reports.append(collect(client, p, cfg["rules"], report_date))
        except MetaError as e:
            failures.append((p["name"], str(e)))
        except Exception as e:  # bitta loyiha xatosi boshqalarini to'xtatmasin
            traceback.print_exc()
            failures.append((p["name"], f"{type(e).__name__}: {e}"))
    now = datetime.now(ZoneInfo(cfg.get("report_timezone", "Asia/Tashkent")))
    day = report_date or now.date()
    msgs = build_messages(reports, day, failures, cfg["rules"]["min_results_for_winner"], historical=bool(report_date))
    if report_date:
        label = f"{WEEKDAYS[day.weekday()]}, {dfmt(day)} {day.year} · tarixiy hisobot (o'sha kuni ishlagan reklamalar)"
    else:
        label = f"{WEEKDAYS[day.weekday()]}, {dfmt(day)} {day.year} · {now:%H:%M} holatiga · faqat hozir ishlab turgan reklamalar"
    pdf = build_pdf(reports, label, f"target_hisobot_{day.isoformat()}.pdf")
    return msgs, pdf, failures


def send_report(cfg, client, tg, report_date=None):
    msgs, pdf, failures = build_report(cfg, client, report_date)
    for m in msgs:
        tg.send(m)
    tg.send_file(pdf, caption="📎 To'liq hisobot (PDF)")
    return not (failures and len(failures) == len(cfg["projects"]))

if __name__ == "__main__":
    main()
