"""Meta Marketing API bilan ishlash: akkaunt ma'lumoti va insights."""
import time
import requests

GRAPH = "https://graph.facebook.com"


class MetaError(Exception):
    pass


class MetaClient:
    def __init__(self, token: str, api_version: str = "v25.0"):
        self.token = token
        self.base = f"{GRAPH}/{api_version}"

    def _get(self, url, params=None, retries=4):
        params = dict(params or {})
        if not url.startswith("http"):
            url = f"{self.base}/{url}"
            params["access_token"] = self.token
        for attempt in range(retries):
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            try:
                err = r.json().get("error", {})
            except ValueError:
                err = {"message": r.text[:300]}
            code = err.get("code")
            # 4, 17, 32, 613, 80000-80014: rate limit — kutib qayta urinish
            if code in (4, 17, 32, 613) or (isinstance(code, int) and 80000 <= code <= 80014) or r.status_code >= 500:
                time.sleep(30 * (attempt + 1))
                continue
            raise MetaError(f"[{code}] {err.get('message')}")
        raise MetaError("Meta API javob bermadi (rate limit / server xatosi)")

    def _paged(self, path, params):
        data = self._get(path, params)
        rows = list(data.get("data", []))
        nxt = data.get("paging", {}).get("next")
        while nxt:
            data = self._get(nxt)
            rows.extend(data.get("data", []))
            nxt = data.get("paging", {}).get("next")
        return rows

    def account(self, act_id):
        return self._get(act_id, {"fields": "name,currency,timezone_name,account_status"})

    def ad_statuses(self, act_id):
        rows = self._paged(f"{act_id}/ads", {
            "fields": "id,effective_status",
            "limit": 500,
        })
        return {r["id"]: r.get("effective_status") for r in rows}

    def problem_ads(self, act_id):
        """Siz yoqib qo'ygan, lekin Meta ishlatmayotgan reklamalar (rad etilgan, muammoli, tekshiruvda)."""
        rows = self._paged(f"{act_id}/ads", {"fields": "id,name,campaign{name},effective_status,configured_status",
                                            "limit": 500})
        bad = {"DISAPPROVED", "WITH_ISSUES", "PENDING_REVIEW", "IN_PROCESS", "PENDING_BILLING_INFO"}
        return [{"ad_id": r["id"], "ad_name": r.get("name", ""), "campaign_name": (r.get("campaign") or {}).get("name", ""),
                 "status": r["effective_status"]}
                for r in rows if r.get("configured_status") == "ACTIVE" and r.get("effective_status") in bad]

    def daily_ad_insights(self, act_id, since, until):
        """Har bir reklama x har bir kun. Sarf, natija, CTR trendi uchun."""
        return self._paged(f"{act_id}/insights", {
            "level": "ad",
            "time_increment": 1,
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "fields": ",".join([
                "campaign_name", "objective", "adset_name", "ad_id", "ad_name",
                "spend", "impressions", "clicks", "inline_link_clicks", "actions", "results",
            ]),
            "limit": 500,
        })

    def ad_reach_frequency(self, act_id, since, until):
        """Reach/frequency kunlar bo'yicha qo'shilmaydi — alohida so'rov."""
        rows = self._paged(f"{act_id}/insights", {
            "level": "ad",
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "fields": "ad_id,reach,frequency",
            "limit": 500,
        })
        return {r["ad_id"]: (float(r.get("reach") or 0), float(r.get("frequency") or 0)) for r in rows}

    def placements(self, act_id, since, until):
        """Qayerda yaxshi ishlayapti: Facebook/Instagram, lenta/stories/reels."""
        return self._paged(f"{act_id}/insights", {
            "level": "ad",
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "breakdowns": "publisher_platform,platform_position",
            "fields": "ad_id,campaign_name,adset_name,ad_name,spend,impressions,inline_link_clicks,actions,results",
            "limit": 500,
        })

    def action_types(self, act_id, since, until):
        rows = self._paged(f"{act_id}/insights", {
            "level": "account",
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "fields": "actions",
        })
        out = {}
        for r in rows:
            for a in r.get("actions") or []:
                out[a["action_type"]] = out.get(a["action_type"], 0) + float(a["value"])
        return out
