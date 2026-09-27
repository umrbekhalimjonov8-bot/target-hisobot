"""PDF hisobot (telefonda ochiladi). Faqat faol reklamalar."""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart

from src.telegram_report import money, num, pct, _fill_money

FONT, BOLD = "Helvetica", "Helvetica-Bold"
_D = "/usr/share/fonts/truetype/dejavu/"
if os.path.exists(_D + "DejaVuSans.ttf") and os.path.exists(_D + "DejaVuSans-Bold.ttf"):
    pdfmetrics.registerFont(TTFont("DV", _D + "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DVB", _D + "DejaVuSans-Bold.ttf"))
    FONT, BOLD = "DV", "DVB"

INK = colors.HexColor("#15202e")
MUTE = colors.HexColor("#5f6b7a")
LINE = colors.HexColor("#dde3ea")
HEAD = colors.HexColor("#1f4fa8")
ZEBRA = colors.HexColor("#f4f7fb")
LVL = {"red": colors.HexColor("#c62828"), "orange": colors.HexColor("#d9690b"),
       "yellow": colors.HexColor("#a67c00"), "ok": colors.HexColor("#1b7f4c"), "info": MUTE}

S = {
    "h1": ParagraphStyle("h1", fontName=BOLD, fontSize=18, leading=22, textColor=INK),
    "sub": ParagraphStyle("sub", fontName=FONT, fontSize=9.5, leading=12, textColor=MUTE),
    "h2": ParagraphStyle("h2", fontName=BOLD, fontSize=14, leading=18, textColor=HEAD, spaceBefore=4),
    "cell": ParagraphStyle("cell", fontName=FONT, fontSize=8.5, leading=10.5, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName=BOLD, fontSize=8.5, leading=10.5, textColor=INK),
    "small": ParagraphStyle("small", fontName=FONT, fontSize=7.5, leading=9, textColor=MUTE),
    "note": ParagraphStyle("note", fontName=FONT, fontSize=9, leading=12, textColor=INK),
}


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _verdict(x, c):
    if x["notes"]:
        return [(lvl, _fill_money(t, c)) for lvl, t in x["notes"]]
    if "winner" in x["flags"]:
        return [("ok", "Eng yaxshi — byudjetni oshirishni ko'rib chiqing")]
    if "traffic" in x["flags"]:
        return [("info", "Trafik kampaniya — link click muhim")]
    return [("ok", "Normal")]


def _summary(rep):
    c, t = rep.currency, rep.totals
    day = "Kun" if rep.historical else "Bugun"
    rows = [[f"{day} sarf", money(t["today"]["spend"], c), "7 kun natija", num(t["week"]["results"])],
            ["Kecha sarf", money(t["yesterday"]["spend"], c), "7 kun natija narxi", money(t["week"]["cpl"], c)],
            ["7 kun sarf", money(t["week"]["spend"], c), "7 kun link click", num(t["week"]["link_clicks"])],
            ["Oy boshidan", money(t["mtd"]["spend"], c), "7 kun CTR", pct(t["week"]["ctr"])],
            ["7 kun CPM", money(t["week"]["cpm"], c), "7 kun konversiya", pct(t["week"]["conv"])]]
    if t["week"]["calls"]:
        rows.append(["Qo'ng'iroq qildi", num(t["week"]["calls"]), "20s+ gaplashdi",
                     f'{num(t["week"]["calls20"])} ({money(t["week"]["cost_call20"], c)})'])
    tb = Table(rows, colWidths=[32 * mm, 34 * mm, 34 * mm, 34 * mm])
    tb.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), FONT, 10), ("FONT", (1, 0), (1, -1), BOLD, 10), ("FONT", (3, 0), (3, -1), BOLD, 10),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTE), ("TEXTCOLOR", (2, 0), (2, -1), MUTE),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tb


def _chart(rep):
    days = rep.daily[-14:]
    d = Drawing(120 * mm, 45 * mm)
    ch = VerticalBarChart()
    ch.x, ch.y, ch.width, ch.height = 12 * mm, 8 * mm, 104 * mm, 32 * mm
    ch.data = [[x["spend"] for x in days]]
    ch.categoryAxis.categoryNames = [x["date"][8:] for x in days]
    ch.categoryAxis.labels.fontName = FONT
    ch.categoryAxis.labels.fontSize = 6.5
    ch.valueAxis.labels.fontName = FONT
    ch.valueAxis.labels.fontSize = 6.5
    ch.valueAxis.valueMin = 0
    ch.valueAxis.gridStrokeColor = LINE
    ch.valueAxis.visibleGrid = True
    ch.bars[0].fillColor = HEAD
    ch.bars[0].strokeColor = None
    d.add(ch)
    d.add(String(12 * mm, 42 * mm, f"Kunlik sarf, oxirgi 14 kun ({rep.currency})", fontName=FONT, fontSize=8, fillColor=MUTE))
    return d


def _ads_table(ads, c):
    head = ["Reklama", "Kun", "7 kun sarf", "Natija", "Natija narxi", "20s+ qo'ng'.", "20s+ narxi",
            "Link click", "CTR", "Konv.", "CPC", "CPM", "Chas-tota", "Hook", "Xulosa"]
    data = [[Paragraph(h, S["cellb"]) for h in head]]
    styles = []
    for i, x in enumerate(ads, start=1):
        verdict = "<br/>".join(f'<font color="{LVL[l].hexval()}">● </font>{_esc(t)}' for l, t in _verdict(x, c))
        data.append([
            Paragraph(f"<b>{_esc(x['ad_name'])}</b><br/><font size=7 color='#5f6b7a'>{_esc(x['campaign_name'])}"
                      f"<br/>natija: {_esc(x['result_type'])}</font>", S["cell"]),
            money(x["today_spend"], c), money(x["w_spend"], c), num(x["w_results"]),
            Paragraph(f"<b>{money(x['w_cpl'], c)}</b>", S["cell"]),
            num(x["w_calls20"]) if x["w_calls"] else "—",
            money(x["w_cost_call20"], c) if x["w_calls"] else "—",
            num(x["w_link_clicks"]), pct(x["w_ctr"]), pct(x["w_conv"]), money(x["w_cpc"], c), money(x["w_cpm"], c),
            "—" if not x["frequency"] else f"{x['frequency']:.2f}", pct(x.get("w_hook")),
            Paragraph(verdict, S["cell"]),
        ])
        if i % 2 == 0:
            styles.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    widths = [44, 14, 17, 14, 16, 14, 16, 14, 13, 14, 14, 14, 15, 13, 49]
    tb = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    tb.setStyle(TableStyle([
        ("FONT", (0, 1), (-1, -1), FONT, 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (13, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ] + styles))
    return tb


def story_has_page_only_header(story):
    return len(story) <= 3


def build_pdf(reports, label, path):
    # faol reklamasi bor loyihalar oldin, bo'shlari oxirida — ortiqcha bo'sh sahifa bo'lmasin
    reports = sorted(reports, key=lambda r: not any(x["status"] == "ACTIVE" for x in r.ads))
    doc = SimpleDocTemplate(path, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=10 * mm, bottomMargin=10 * mm, title="Target hisobot")
    story = [Paragraph("Target hisobot", S["h1"]),
             Paragraph(f"{_esc(label)} · manba: Meta Marketing API", S["sub"]),
             Spacer(1, 6 * mm)]
    for n, rep in enumerate(reports):
        active = [x for x in rep.ads if x["status"] == "ACTIVE"]
        if n and active and not story_has_page_only_header(story):
            story.append(PageBreak())
        story.append(Paragraph(_esc(rep.name), S["h2"]))
        story.append(Paragraph(f"{_esc(rep.account_name)} · natija: {_esc(rep.result_action)}", S["small"]))
        for lvl, txt in rep.signals:
            if txt.startswith(("AKKAUNT HOLATI", "REKLAMA ")):
                story.append(Paragraph(f'<font color="{LVL[lvl].hexval()}">● {_esc(txt)}</font>', S["note"]))
        story.append(Spacer(1, 3 * mm))
        if not active:
            story.append(Paragraph("Bu kuni ishlagan reklama yo'q." if rep.historical else "Hozir faol reklama yo'q.", S["note"]))
            story.append(Spacer(1, 6 * mm))
            continue
        top = Table([[_summary(rep), _chart(rep)]], colWidths=[140 * mm, 125 * mm])
        top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story += [top, Spacer(1, 4 * mm), _ads_table(active, rep.currency), Spacer(1, 8 * mm)]
    story += [Spacer(1, 5 * mm),
              Paragraph("Natija = Ads Manager'dagi Results ustuni (Meta'ning o'z hisobi). Natija narxi = sarf / natija. CTR = link click / ko'rsatish. Konversiya = natija / link click. "
                        "Hook = 3 soniyalik video ko'rish / ko'rsatish (faqat video). Natija: har reklamada birinchi mavjud tur (lead → 20s+ qo'ng'iroq → yozishma). "
                        "Signal chegaralari config.yaml'da — boshlang'ich gipoteza.", S["small"])]
    doc.build(story)
    return path
