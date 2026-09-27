"""Telegram'ga o'zbekcha hisobot — har bir faol reklama alohida, har qatorda bitta metrika."""
import html
import re
import requests

MONTHS = ["yan", "fev", "mar", "apr", "may", "iyun", "iyul", "avg", "sen", "okt", "noy", "dek"]
WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
SEP = "━━━━━━━━━━━━━━"
ICON = {"red": "🔴", "orange": "🟠", "yellow": "🟡"}


def money(v, cur):
    if v is None:
        return "—"
    if cur == "USD":
        return f"{v:,.2f}$"
    if cur == "EUR":
        return f"{v:,.2f}€"
    return f"{v:,.0f} {cur}".replace(",", " ")


def num(v):
    return "—" if v is None else f"{v:,.0f}".replace(",", " ")


def pct(v):
    return "—" if v is None else f"{v:.2f}%"


def _fill_money(text, cur):
    return re.sub(r"\{m:([-\d.eE+]+)\}", lambda m: money(float(m.group(1)), cur), text)


def dfmt(d):
    return f"{d.day}-{MONTHS[d.month - 1]}"


def e(s):
    return html.escape(str(s), quote=False)


def ad_icon(x):
    if x["notes"]:
        return ICON[min(x["notes"], key=lambda n: ["red", "orange", "yellow"].index(n[0]))[0]]
    return "🟢" if "winner" in x["flags"] else "⚪"


def ad_verdicts(x):
    if x["notes"]:
        return [(ICON[lvl], t) for lvl, t in x["notes"]]
    if "winner" in x["flags"]:
        return [("✅", "Eng yaxshi ishlayotganlardan — byudjetni oshirishni ko'rib chiqing")]
    if "traffic" in x["flags"]:
        return [("ℹ️", "Trafik kampaniya — natija emas, link click muhim")]
    return [("✅", "Normal ishlayapti")]


def ad_block(x, c, day="Bugun", wk="Oxirgi 7 kun"):
    freq = "—" if not x["frequency"] else f"{x['frequency']:.2f}"
    L = [f"{ad_icon(x)} <b>{e(x['ad_name'])}</b>",
         f"<i>{e(x['campaign_name'])}</i>",
         "",
         f"{day} sarf: <b>{money(x['today_spend'], c)}</b>",
         f"{day} natija: {num(x['today_results'])}",
         "",
         f"<u>{wk}</u>",
         f"Sarf: <b>{money(x['w_spend'], c)}</b>",
         f"Natija ({e(x['result_type'])}): <b>{num(x['w_results'])}</b>",
         f"Natija narxi: <b>{money(x['w_cpl'], c)}</b>",
         ""]
    if x["w_calls"]:
        L += ["📞 <u>Qo'ng'iroqlar (7 kun)</u>",
              f"Qo'ng'iroq qildi: <b>{num(x['w_calls'])}</b>",
              f"20s+ gaplashdi: <b>{num(x['w_calls20'])}</b>",
              f"20s+ qo'ng'iroq narxi: <b>{money(x['w_cost_call20'], c)}</b>",
              f"60s+ gaplashdi: {num(x['w_calls60'])}",
              f"60s+ qo'ng'iroq narxi: {money(x['w_cost_call60'], c)}",
              ""]
    L += [
         f"Link click: {num(x['w_link_clicks'])}",
         f"CTR: {pct(x['w_ctr'])}",
         f"Konversiya: {pct(x['w_conv'])}",
         f"CPC: {money(x['w_cpc'], c)}",
         f"CPM: {money(x['w_cpm'], c)}",
         "",
         f"Chastota: {freq}"]
    if x.get("w_hook") is not None:
        L.append(f"Hook rate: {pct(x['w_hook'])}")
    L.append("")
    L += [f"{i} {e(_fill_money(t, c))}" for i, t in ad_verdicts(x)]
    return "\n".join(L)


def project_blocks(rep):
    day = dfmt(rep.today) if rep.historical else "Bugun"
    a, b = rep.week_range
    wk = f"7 kun ({a.day}–{dfmt(b)})" if a.month == b.month else f"7 kun ({dfmt(a)} – {dfmt(b)})"
    """Loyiha sarlavhasi + har bir faol reklama — alohida bloklar."""
    c, t = rep.currency, rep.totals
    head = [f"📊 <b>{e(rep.name.upper())}</b>"]
    for lvl, txt in rep.signals:
        if txt.startswith(("AKKAUNT HOLATI", "REKLAMA ")):
            head.append(f"{ICON[lvl]} {e(txt)}")
    active = [x for x in rep.ads if x["status"] == "ACTIVE"]
    if not active:
        head.append("⏸ Bu kuni ishlagan reklama yo'q" if rep.historical else "⏸ Hozir faol reklama yo'q")
        return ["\n".join(head)]
    head += [f"{'Ishlagan' if rep.historical else 'Faol'} reklamalar: {len(active)} ta",
             "",
             f"{day} sarf: <b>{money(t['today']['spend'], c)}</b>",
             f"{day} natija: {num(t['today']['results'])}",
             f"{dfmt(rep.today - __import__('datetime').timedelta(days=1)) if rep.historical else 'Kecha'} sarf: {money(t['yesterday']['spend'], c)}",
             f"7 kun sarf: {money(t['week']['spend'], c)}",
             f"Oy boshidan: {money(t['mtd']['spend'], c)}",
             "",
             f"7 kun natija: <b>{num(t['week']['results'])}</b>",
             f"7 kun natija narxi: <b>{money(t['week']['cpl'], c)}</b>"]
    if t["week"]["calls"]:
        head += [f"7 kun qo'ng'iroq qildi: {num(t['week']['calls'])}",
                 f"7 kun 20s+ gaplashdi: {num(t['week']['calls20'])} ({money(t['week']['cost_call20'], c)} dan)"]
    head += [
             f"7 kun link click: {num(t['week']['link_clicks'])}",
             f"7 kun CTR: {pct(t['week']['ctr'])}",
             f"7 kun konversiya: {pct(t['week']['conv'])}",
             f"7 kun CPM: {money(t['week']['cpm'], c)}"]
    return ["\n".join(head)] + [SEP + "\n" + ad_block(x, c, day, wk) for x in active]


def build_messages(reports, today, failures, min_results=3, historical=False):
    sub = (f"<i>Tarixiy hisobot: {dfmt(today)} kuni ishlagan reklamalar · «7 kun» = {dfmt(today)} bilan tugaydigan 7 kun</i>"
           if historical else "<i>Faqat hozir ishlab turgan reklamalar · «7 kun» = kechagacha 7 kun</i>")
    blocks = [f"🗓 <b>Target hisobot — {WEEKDAYS[today.weekday()]}, {dfmt(today)} {today.year}</b>\n{sub}"]
    for r in reports:
        blocks += project_blocks(r)
    for name, err in failures:
        blocks.append(f"❗ <b>{e(name)}</b>: ma'lumot olinmadi — {e(err)}")
    blocks.append("<i>Natija = Ads Manager'dagi Results ustuni · Natija narxi = sarf/natija · CTR = klik/ko'rsatish · Konversiya = natija/klik · "
                  "Hook rate = 3s video ko'rish/ko'rsatish</i>\n📎 To'liq jadval — PDF faylda")
    msgs, cur = [], ""
    for b in blocks:
        if cur and (b.startswith("📊") or len(cur) + len(b) + 2 > 3900):
            msgs.append(cur)
            cur = ""
        cur += ("\n\n" if cur else "") + b
    if cur:
        msgs.append(cur)
    return msgs


class Telegram:
    def __init__(self, token, chat_id):
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id

    def send(self, text):
        r = requests.post(f"{self.base}/sendMessage", data={
            "chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
            "disable_web_page_preview": "true"}, timeout=30)
        if not r.ok:
            raise RuntimeError(f"Telegram xatosi: {r.text[:300]}")

    def send_file(self, path, caption=""):
        with open(path, "rb") as f:
            r = requests.post(f"{self.base}/sendDocument", data={"chat_id": self.chat_id, "caption": caption},
                              files={"document": f}, timeout=60)
        if not r.ok:
            raise RuntimeError(f"Telegram xatosi: {r.text[:300]}")
