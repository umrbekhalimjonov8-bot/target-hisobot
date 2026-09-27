"""Tahlil: davrlar bo'yicha sarf, reklamalar reytingi, signallar.

Barcha raqamlar faqat Meta'dan kelgan qatorlardan hisoblanadi.
Mezon CPL: config'dagi target_cpl, bo'lmasa loyihaning o'z 7 kunlik CPL'i.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta


def _f(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


TRAFFIC_OBJECTIVES = {"LINK_CLICKS", "OUTCOME_TRAFFIC", "OUTCOME_AWARENESS", "REACH", "BRAND_AWARENESS",
                      "OUTCOME_ENGAGEMENT", "POST_ENGAGEMENT", "VIDEO_VIEWS"}


RESULT_NAMES = {
    "click_to_call_native_call_placed": "qo'ng'iroq qilindi",
    "lead": "lead", "onsite_conversion.lead_grouped": "lead (forma)",
    "offsite_conversion.fb_pixel_lead": "lead (sayt)",
    "onsite_conversion.messaging_conversation_started_7d": "yozishma",
    "link_click": "link click", "landing_page_view": "sahifa ko'rildi",
    "offsite_lead_add_20_s_calls": "20s+ qo'ng'iroq",
}


def result_type_of(row, action):
    """1) Meta'ning o'z "Results" maydoni — Ads Manager'dagi Results ustuni bilan bir xil.
    2) Bo'lmasa: config'dagi ustuvorlik ro'yxatidan birinchi mavjud tur (turlar qo'shilmaydi)."""
    for r in row.get("results") or []:
        ind = (r.get("indicator") or "").split(":", 1)[-1]
        vals = r.get("values") or []
        if ind and vals:
            return ind, _f(vals[0].get("value"))
    acts = {a.get("action_type"): _f(a.get("value")) for a in row.get("actions") or []}
    for t in ([action] if isinstance(action, str) else action):
        if t in acts:
            return t, acts[t]
    return None, 0.0


def results_of(row, action):
    return result_type_of(row, action)[1]


@dataclass
class Agg:
    spend: float = 0.0
    impressions: float = 0.0
    link_clicks: float = 0.0
    results: float = 0.0
    video3s: float = 0.0
    calls: float = 0.0       # qo'ng'iroq tugmasi bosilib, qo'ng'iroq qilindi
    calls20: float = 0.0     # 20+ soniya gaplashdi
    calls60: float = 0.0     # 60+ soniya gaplashdi

    def add(self, row, action):
        for a in row.get("actions") or []:
            t, v = a.get("action_type"), _f(a.get("value"))
            if t == "video_view":  # Meta: 3 soniyalik video ko'rishlar
                self.video3s += v
            elif t == "click_to_call_native_call_placed":
                self.calls += v
            elif t == "click_to_call_native_20s_call_connect":
                self.calls20 += v
            elif t == "click_to_call_native_60s_call_connect":
                self.calls60 += v
        self.spend += _f(row.get("spend"))
        self.impressions += _f(row.get("impressions"))
        self.link_clicks += _f(row.get("inline_link_clicks"))
        self.results += results_of(row, action)

    @property
    def cpl(self):
        return self.spend / self.results if self.results else None

    @property
    def ctr(self):
        return self.link_clicks / self.impressions * 100 if self.impressions else None

    @property
    def conv(self):
        """Konversiya: natija / link click, %"""
        return self.results / self.link_clicks * 100 if self.link_clicks else None

    @property
    def hook(self):
        """Hook rate: 3s video ko'rish / ko'rsatish, %. Video bo'lmasa None."""
        return self.video3s / self.impressions * 100 if self.impressions and self.video3s else None

    @property
    def cpm(self):
        return self.spend / self.impressions * 1000 if self.impressions else None

    @property
    def cpc(self):
        return self.spend / self.link_clicks if self.link_clicks else None

    def as_dict(self):
        return {"spend": self.spend, "impressions": self.impressions, "link_clicks": self.link_clicks,
                "results": self.results, "cpl": self.cpl, "conv": self.conv, "hook": self.hook,
                "calls": self.calls, "calls20": self.calls20, "calls60": self.calls60,
                "cost_call20": self.spend / self.calls20 if self.calls20 else None,
                "cost_call60": self.spend / self.calls60 if self.calls60 else None, "ctr": self.ctr, "cpm": self.cpm, "cpc": self.cpc}


def _pct_change(new, old):
    if new is None or old in (None, 0):
        return None
    return (new - old) / old * 100


def periods(today: date, historical: bool = False):
    """Jonli rejim: «7 kun» = kechagacha 7 to'liq kun (Ads Manager'ning Last 7 days bilan bir xil).
    Tarixiy rejim (/hisobot SANA): «7 kun» = tanlangan kun bilan tugaydigan 7 kun."""
    y = today - timedelta(days=1)
    w_end = today if historical else y
    w_start = w_end - timedelta(days=6)
    pw_end, pw_start = w_start - timedelta(days=1), w_start - timedelta(days=7)
    m_start = today.replace(day=1)
    pm_end_full = m_start - timedelta(days=1)
    pm_start = pm_end_full.replace(day=1)
    pm_same_end = min(pm_start + timedelta(days=today.day - 1), pm_end_full)
    return {
        "today": (today, today),
        "yesterday": (y, y),
        "week": (w_start, w_end),
        "prev_week": (pw_start, pw_end),
        "mtd": (m_start, today),
        "prev_mtd": (pm_start, pm_same_end),
        "prev_month": (pm_start, pm_end_full),
        "fetch_since": pm_start,
    }


@dataclass
class ProjectReport:
    name: str
    account_name: str
    currency: str
    result_action: str
    today: date
    totals: dict = field(default_factory=dict)       # davr -> Agg dict
    changes: dict = field(default_factory=dict)
    benchmark_cpl: float = None
    benchmark_source: str = ""
    ads: list = field(default_factory=list)
    adsets: list = field(default_factory=list)
    placements: list = field(default_factory=list)
    signals: list = field(default_factory=list)       # (level, text)
    winners: list = field(default_factory=list)
    daily: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    idle: bool = False
    historical: bool = False
    week_range: tuple = None


def _note(item, rep, lvl, text, short):
    rep.signals.append((lvl, text))
    item["notes"].append((lvl, short))


def name_filter(project):
    """campaign_contains: ["ziyo", ...] — kampaniya/ad set/reklama nomida shu so'z bo'lsa loyihaga tegishli.
    exclude_contains — aksincha. Bo'sh bo'lsa akkauntdagi hammasi olinadi."""
    inc = [w.lower() for w in project.get("campaign_contains") or []]
    exc = [w.lower() for w in project.get("exclude_contains") or []]

    def ok(r):
        text = " ".join(str(r.get(k, "")) for k in ("campaign_name", "adset_name", "ad_name")).lower()
        if exc and any(w in text for w in exc):
            return False
        return not inc or any(w in text for w in inc)
    return ok


def analyze(project, account, rows, reach_freq, statuses, placement_rows, today, rules, historical=False):
    keep = name_filter(project)
    rows = [r for r in rows if keep(r)]
    placement_rows = [r for r in placement_rows if keep(r)]
    action = project.get("result_action", "lead")
    nice = {"lead": "lead", "offsite_lead_add_20_s_calls": "20s+ qo'ng'iroq",
            "onsite_conversion.messaging_conversation_started_7d": "yozishma"}
    action_label = " / ".join(nice.get(a, a) for a in ([action] if isinstance(action, str) else action))
    P = periods(today, historical)
    rep = ProjectReport(
        name=project["name"], account_name=account.get("name", ""),
        currency=account.get("currency", ""), result_action=action_label, today=today,
    )

    def in_range(d, key):
        a, b = P[key]
        return a <= d <= b

    # --- Davrlar bo'yicha jami ---
    keys = ["today", "yesterday", "week", "prev_week", "mtd", "prev_mtd", "prev_month"]
    tot = {k: Agg() for k in keys}
    by_day = {}
    ads = {}
    for r in rows:
        d = date.fromisoformat(r["date_start"])
        for k in keys:
            if in_range(d, k):
                tot[k].add(r, action)
        by_day.setdefault(d, Agg()).add(r, action)

        aid = r.get("ad_id")
        ad = ads.setdefault(aid, {
            "ad_id": aid, "ad_name": r.get("ad_name", ""), "adset_name": r.get("adset_name", ""),
            "campaign_name": r.get("campaign_name", ""), "week": Agg(), "today": Agg(),
            "last3": Agg(), "prev4": Agg(), "objective": r.get("objective", ""), "rtypes": set(),
        })
        rt, _ = result_type_of(r, action)
        if rt:
            ad["rtypes"].add(rt)
        if in_range(d, "week"):
            ad["week"].add(r, action)
            if d >= P["week"][1] - timedelta(days=2):
                ad["last3"].add(r, action)
            else:
                ad["prev4"].add(r, action)
        if d == today:
            ad["today"].add(r, action)

    rep.totals = {k: v.as_dict() for k, v in tot.items()}
    rep.changes = {
        "week_spend": _pct_change(tot["week"].spend, tot["prev_week"].spend),
        "week_results": _pct_change(tot["week"].results, tot["prev_week"].results),
        "week_cpl": _pct_change(tot["week"].cpl, tot["prev_week"].cpl),
        "mtd_spend": _pct_change(tot["mtd"].spend, tot["prev_mtd"].spend),
        "mtd_cpl": _pct_change(tot["mtd"].cpl, tot["prev_mtd"].cpl),
    }

    start = today - timedelta(days=29)
    rep.daily = [{"date": (start + timedelta(days=i)).isoformat(),
                  **by_day.get(start + timedelta(days=i), Agg()).as_dict()} for i in range(30)]

    # --- Mezon CPL ---
    if project.get("target_cpl"):
        rep.benchmark_cpl = float(project["target_cpl"])
        rep.benchmark_source = "maqsad (config)"
    elif tot["week"].cpl:
        rep.benchmark_cpl = tot["week"].cpl
        rep.benchmark_source = "loyihaning 7 kunlik o'rtachasi"
    bench = rep.benchmark_cpl

    # --- Reklamalar ---
    ad_list = []
    for a in ads.values():
        w = a["week"]
        if w.spend <= 0 and a["today"].spend <= 0:
            continue
        reach, freq = reach_freq.get(a["ad_id"], (None, None))
        item = {
            "ad_id": a["ad_id"], "ad_name": a["ad_name"], "adset_name": a["adset_name"],
            "campaign_name": a["campaign_name"], "status": statuses.get(a["ad_id"], "?"),
            **{f"w_{k}": v for k, v in w.as_dict().items()},
            "today_spend": a["today"].spend, "today_results": a["today"].results, "notes": [], "frequency": freq, "reach": reach,
            "ctr_last3": a["last3"].ctr, "ctr_prev4": a["prev4"].ctr, "flags": [],
            "objective": a["objective"],
            "result_type": ", ".join(RESULT_NAMES.get(t, t) for t in sorted(a["rtypes"])) or "—",
        }
        is_traffic = a["objective"] in TRAFFIC_OBJECTIVES and not a["rtypes"]
        if is_traffic:
            item["flags"].append("traffic")
        is_active = item["status"] == "ACTIVE"
        label = f"«{a['ad_name']}» ({a['adset_name']})"

        # 1) Natijasiz sarf
        if is_traffic:
            pass  # trafik kampaniya: natija (lead) kutilmaydi — o'chirish tavsiya qilinmaydi
        elif bench and w.results == 0 and w.spend >= rules["no_result_spend_multiplier"] * bench:
            item["flags"].append("off")
            if is_active:
                _note(item, rep, "red",
                      f"O'CHIRISH: {label} — 7 kunda {{m:{w.spend}}} sarfladi, 0 natija "
                      f"(mezon CPL {{m:{bench}}} ning {w.spend / bench:.1f}x)",
                      f"O'chirish kerak: 7 kunda {{m:{w.spend}}} sarf, 0 natija")
        # 2) Qimmat CPL
        elif bench and w.results > 0 and w.cpl >= rules["expensive_cpl_multiplier"] * bench \
                and w.spend >= rules["no_result_spend_multiplier"] * bench:
            item["flags"].append("expensive")
            if is_active:
                _note(item, rep, "orange",
                      f"QIMMAT: {label} — CPL {{m:{w.cpl}}}, mezondan {w.cpl / bench:.1f}x. "
                      f"Auditoriya/kreativni tekshiring yoki o'chiring",
                      f"CPL qimmat: o'rtachadan {w.cpl / bench:.1f} barobar. Kreativ/auditoriyani almashtiring")
        # 3) Chastota
        if freq and freq > rules["max_frequency"] and is_active:
            item["flags"].append("freq")
            _note(item, rep, "yellow",
                  f"CHASTOTA {freq:.1f}: {label} — auditoriya charchagan, kreativni yangilang",
                  f"Chastota {freq:.1f}: auditoriya charchagan, kreativni yangilang")
        # 4) CTR pasayishi
        mi = rules["min_impressions_for_ctr"]
        if a["last3"].impressions >= mi and a["prev4"].impressions >= mi and is_active:
            ch = _pct_change(a["last3"].ctr, a["prev4"].ctr)
            if ch is not None and ch <= -rules["ctr_drop_pct"]:
                item["flags"].append("ctr_drop")
                _note(item, rep, "yellow",
                      f"CTR TUSHDI {ch:.0f}%: {label} — {a['prev4'].ctr:.2f}% → {a['last3'].ctr:.2f}%",
                      f"CTR tushdi: {a['prev4'].ctr:.2f}% → {a['last3'].ctr:.2f}%")
        ad_list.append(item)

    # 5) G'oliblar
    min_r = rules["min_results_for_winner"]
    cand = [x for x in ad_list if x["w_results"] >= min_r and x["w_cpl"] is not None]
    cand.sort(key=lambda x: x["w_cpl"])
    for x in cand[:3]:
        if bench is None or x["w_cpl"] <= bench:
            x["flags"].append("winner")
            rep.winners.append(x)

    ad_list.sort(key=lambda x: -x["w_spend"])
    rep.ads = ad_list

    # --- Ad setlar (qaysi auditoriya yaxshi) ---
    sets = {}
    for x in ad_list:
        s = sets.setdefault((x["campaign_name"], x["adset_name"]), Agg())
        s.spend += x["w_spend"]; s.impressions += x["w_impressions"]
        s.link_clicks += x["w_link_clicks"]; s.results += x["w_results"]
    rep.adsets = sorted(
        [{"campaign_name": c, "adset_name": n, **v.as_dict()} for (c, n), v in sets.items()],
        key=lambda s: (s["cpl"] is None, s["cpl"] or 0))

    # --- Joylashuvlar (qayerda yaxshi) ---
    plg = {}
    for r in placement_rows:
        plg.setdefault((r.get("publisher_platform", ""), r.get("platform_position", "")), Agg()).add(r, action)
    pl = [{"platform": k[0], "position": k[1], **g.as_dict()} for k, g in plg.items() if g.spend > 0]
    pl.sort(key=lambda s: -s["spend"])
    rep.placements = pl

    order = {"red": 0, "orange": 1, "yellow": 2}
    rep.signals.sort(key=lambda s: order[s[0]])
    rep.historical = historical
    rep.week_range = P["week"]
    rep.idle = tot["week"].spend == 0 and tot["today"].spend == 0
    if rep.idle:
        rep.signals.insert(0, ("yellow", "Oxirgi 7 kun va bugun sarf yo'q — reklama ishlamayapti (to'xtatilgan yoki byudjet tugagan)"))
    elif bench is None:
        rep.signals.insert(0, ("orange", "Oxirgi 7 kunda natija (" + action_label + ") yo'q — mezon CPL aniqlanmadi. "
                                         "result_action to'g'riligini tekshiring: python main.py --actions"))
    st = account.get("account_status")
    if st not in (None, 1):
        names = {2: "O'CHIRILGAN (disabled)", 3: "TO'LOV QARZI (unsettled)", 7: "RISK TEKSHIRUVIDA",
                 8: "TO'LOV KUTILMOQDA", 9: "GRACE PERIOD", 100: "YOPILISH ARAFASIDA", 101: "YOPILGAN"}
        rep.signals.insert(0, ("red", f"AKKAUNT HOLATI: {names.get(st, st)} — reklama to'xtashi mumkin, to'lov/holatni tekshiring"))
    return rep
