# ============================================================
# 文件：vision/trigger_client.py
# 作用：把 vision 层识别到的事件发送给 python_trigger
# ============================================================

import requests

TRIGGER_URL = "http://127.0.0.1:18000/trigger"


def send_event(event_name: str, confidence: float | None = None, source: str = "vision") -> dict:
    """
    把识别到的事件发送给 Trigger API。
    """

    payload = {
        "event": event_name,
        "source": source,
        "level": None,
    }

    if confidence is not None:
        payload["level"] = f"conf={confidence:.3f}"

    print("==================================================")
    print("[VISION -> TRIGGER] 准备发送事件")
    print(f"[EVENT ] {event_name}")
    print(f"[SOURCE] {source}")
    print(f"[LEVEL ] {payload['level']}")
    print(f"[POST  ] {TRIGGER_URL}")
    print("")

    try:
        response = requests.post(TRIGGER_URL, json=payload, timeout=5)
        print(f"[HTTP STATUS] {response.status_code}")

        data = response.json()
        print(f"[TRIGGER RESPONSE] {data}")
        print("==================================================")
        return data

    except requests.RequestException as e:
        print(f"[ERROR] 请求 Trigger API 失败：{e}")
        print("==================================================")
        return {
            "success": False,
            "error": str(e),
        }
