import sys
import time
import threading
from pathlib import Path

import cv2
import numpy as np
import requests
from mss import MSS
from ultralytics import YOLO


# =========================
# 路径配置
# =========================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "model" / "best.pt"

TRIGGER_URL = "http://127.0.0.1:18000/trigger"


# =========================
# 识别配置
# =========================

CONF_THRESHOLD = 0.60
FRAME_INTERVAL = 0.50

# 是否真的发送到 Trigger
# True  = 只打印，不发送
# False = 发送到 Trigger
DRY_RUN = False

# 是否显示 OpenCV 预览窗口
SHOW_PREVIEW = True


# =========================
# vision 本地冷却配置
# =========================
# 说明：
# 1. 这里是 vision 层本地冷却，用来减少重复 POST 和刷屏
# 2. python_trigger/app.py 里的 cooldown 仍然保留，作为第二道保险
# 3. 两层冷却都存在更安全
# =========================

LOCAL_COOLDOWN = {
    "bleeding": 1.0,
    "incap": 5.0,
    "death": 5.0,
}

last_send_time = {}


# =========================
# 运行控制
# =========================

stop_event = threading.Event()


def input_listener():
    """
    命令行停止线程：
    输入 stop / q / quit / exit 后停止程序。
    """
    while not stop_event.is_set():
        try:
            text = input().strip().lower()
            if text in ("stop", "q", "quit", "exit"):
                print("[STOP] 收到命令行停止指令")
                stop_event.set()
                break
        except EOFError:
            break
        except KeyboardInterrupt:
            stop_event.set()
            break


def can_send_locally(event_name: str) -> bool:
    """
    vision 层本地冷却判断。

    返回 True：
        允许向 Trigger 发送事件。

    返回 False：
        本地冷却中，不发送 POST。
    """
    now = time.time()
    cooldown = LOCAL_COOLDOWN.get(event_name, 0.5)
    last_time = last_send_time.get(event_name, 0)

    elapsed = now - last_time

    if elapsed < cooldown:
        remain = cooldown - elapsed
        print(f"[LOCAL BLOCK] {event_name} 本地冷却中，剩余 {remain:.2f}s，不发送 POST")
        return False

    last_send_time[event_name] = now
    return True


def send_trigger(event_name: str, conf: float):
    """
    向 python_trigger 发送事件。
    """
    payload = {
        "event": event_name,
        "source": "realtime_detect_and_trigger",
        "level": f"conf={conf:.3f}"
    }

    if DRY_RUN:
        print(f"[DRY_RUN] 不发送 Trigger：{payload}")
        return

    try:
        print("=" * 50)
        print("[VISION -> TRIGGER] 准备发送事件")
        print(f"[EVENT ] {event_name}")
        print("[SOURCE] realtime_detect_and_trigger")
        print(f"[LEVEL ] conf={conf:.3f}")
        print(f"[POST  ] {TRIGGER_URL}")

        response = requests.post(TRIGGER_URL, json=payload, timeout=2.0)

        print(f"[HTTP STATUS] {response.status_code}")

        try:
            print(f"[TRIGGER RESPONSE] {response.json()}")
        except Exception:
            print(f"[TRIGGER RESPONSE TEXT] {response.text}")

        print("=" * 50)

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 发送 Trigger 失败：{e}")


def draw_detection(frame, label, conf, box):
    """
    在预览画面上画框。
    """
    x1, y1, x2, y2 = map(int, box)

    if label == "bleeding":
        color = (0, 0, 255)
    elif label == "incap":
        color = (0, 165, 255)
    else:
        color = (255, 255, 255)

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    text = f"{label} {conf:.3f}"
    cv2.putText(
        frame,
        text,
        (x1, max(y1 - 10, 20)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2
    )


def main():
    print("=" * 50)
    print("[VISION] 实时截图识别 + Trigger 测试")
    print("=" * 50)
    print(f"[MODEL] {MODEL_PATH}")
    print(f"[CONF] {CONF_THRESHOLD}")
    print(f"[FRAME_INTERVAL] {FRAME_INTERVAL}s")
    print(f"[TRIGGER_URL] {TRIGGER_URL}")
    print(f"[DRY_RUN] {DRY_RUN}")
    print(f"[LOCAL_COOLDOWN] {LOCAL_COOLDOWN}")
    print()
    print("[STOP] 停止方式：")
    print("       1. 预览窗口按 q")
    print("       2. 预览窗口按 Esc")
    print("       3. 命令行输入 stop 后回车")
    print("       4. Ctrl+C")
    print("=" * 50)

    if not MODEL_PATH.exists():
        print(f"[ERROR] 模型不存在：{MODEL_PATH}")
        return

    model = YOLO(str(MODEL_PATH))
    print(f"[MODEL NAMES] {model.names}")

    listener = threading.Thread(target=input_listener, daemon=True)
    listener.start()

    frame_id = 0

    try:
        with MSS() as sct:
            monitor = sct.monitors[1]
            print(f"[MONITOR] {monitor}")
            print("=" * 50)

            while not stop_event.is_set():
                frame_id += 1

                start_time = time.time()

                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)

                # MSS 默认 BGRA，转成 BGR 给 OpenCV / YOLO 用
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                results = model.predict(
                    source=frame,
                    conf=CONF_THRESHOLD,
                    verbose=False
                )

                infer_time = time.time() - start_time

                detections = []

                for result in results:
                    boxes = result.boxes
                    if boxes is None:
                        continue

                    for box in boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        label = model.names.get(cls_id, str(cls_id))

                        xyxy = box.xyxy[0].tolist()

                        detections.append({
                            "label": label,
                            "conf": conf,
                            "box": xyxy
                        })

                if not detections:
                    print(f"[FRAME {frame_id}] no detections | infer={infer_time:.3f}s")
                else:
                    # 如果同一帧出现多个框，优先取置信度最高的那个
                    detections.sort(key=lambda x: x["conf"], reverse=True)
                    best = detections[0]

                    label = best["label"]
                    conf = best["conf"]
                    box = best["box"]

                    print(
                        f"[FRAME {frame_id}] "
                        f"class={label}, conf={conf:.3f}, "
                        f"box={[round(v, 1) for v in box]}, "
                        f"infer={infer_time:.3f}s"
                    )

                    if label in ("bleeding", "incap", "death"):
                        if can_send_locally(label):
                            send_trigger(label, conf)
                    else:
                        print(f"[ACTION] 未知类别，不发送：{label}")

                    if SHOW_PREVIEW:
                        for det in detections:
                            draw_detection(
                                frame,
                                det["label"],
                                det["conf"],
                                det["box"]
                            )

                if SHOW_PREVIEW:
                    cv2.imshow("Realtime Detect + Trigger Preview", frame)
                    key = cv2.waitKey(1) & 0xFF

                    if key == ord("q") or key == 27:
                        print("[STOP] 收到窗口停止指令")
                        stop_event.set()
                        break

                time.sleep(FRAME_INTERVAL)

    except KeyboardInterrupt:
        print()
        print("[STOP] 收到 Ctrl+C")
        stop_event.set()

    finally:
        cv2.destroyAllWindows()
        print("=" * 50)
        print("[DONE] 实时识别 + Trigger 测试结束")
        print("=" * 50)


if __name__ == "__main__":
    main()
