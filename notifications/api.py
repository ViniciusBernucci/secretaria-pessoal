import os, time
import requests

class APIError(Exception):
    def __init__(self, status=0, retry=60):
        self.status, self.retry = status, retry
        super().__init__(f"API indisponível (HTTP {status})")

class Notion:
    def request(self, method, path, payload=None):
        for attempt in range(4):
            try:
                r = requests.request(method, "https://api.notion.com/v1/" + path,
                    headers={"Authorization": "Bearer " + os.environ["NOTION_TOKEN"], "Notion-Version": "2025-09-03"}, json=payload, timeout=20)
            except requests.RequestException:
                if attempt == 3: raise APIError()
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == 3: raise APIError(r.status_code)
                time.sleep(min(30, max(1, int(r.headers.get("Retry-After", 2 ** attempt)))))
                continue
            if not r.ok: raise APIError(r.status_code)
            return r.json()
    def pages(self):
        rows, cursor = [], None
        while True:
            body = {"page_size": 100}
            if cursor: body["start_cursor"] = cursor
            data = self.request("POST", "data_sources/" + os.environ["NOTION_DATA_SOURCE_ID"] + "/query", body)
            if data.get("request_status", {}).get("incomplete_reason"):
                raise APIError()
            rows.extend(data["results"])
            if not data["has_more"]: return rows
            cursor = data["next_cursor"]
            if not cursor: raise APIError()
    def acknowledge(self, page_id, when):
        self.request("PATCH", "pages/" + page_id, {"properties": {"Última confirmação": {"date": {"start": when.isoformat()}}}})
        result = self.request("GET", "pages/" + page_id)
        value = result["properties"]["Última confirmação"]["date"]["start"]
        from datetime import datetime
        if datetime.fromisoformat(value.replace("Z", "+00:00")) != when: raise APIError()

class Telegram:
    def call(self, method, **payload):
        try:
            r = requests.post("https://api.telegram.org/bot" + os.environ["TELEGRAM_BOT_TOKEN"] + "/" + method, json=payload, timeout=25)
            data = r.json()
        except (requests.RequestException, ValueError): raise APIError()
        if not data.get("ok"):
            raise APIError(data.get("error_code", r.status_code), data.get("parameters", {}).get("retry_after", 60))
        return data["result"]
