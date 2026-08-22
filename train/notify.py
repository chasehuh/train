from __future__ import annotations

from datetime import datetime

import requests


def telegram(token: str | None, chat_id: str | None, text: str) -> None:
    if not token or not chat_id:
        print(f"[{datetime.now():%H:%M:%S}] telegram skipped")
        return
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        if response.status_code != 200:
            print(
                f"[{datetime.now():%H:%M:%S}] telegram failed: "
                f"{response.status_code} {response.text[:200]}"
            )
            return
        print(f"[{datetime.now():%H:%M:%S}] telegram sent")
    except Exception as exc:  # pragma: no cover
        print(f"[{datetime.now():%H:%M:%S}] telegram error: {exc}")
