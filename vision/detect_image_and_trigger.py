# ============================================================
# 文件：vision/detect_image_and_trigger.py
# 作用：对单张图片做识别，并把结果自动发送给 python_trigger
# ============================================================

import argparse
from pathlib import Path

from ultralytics import YOLO

from config import MODEL_PATH, CONF_THRESHOLD
from trigger_client import send_event


def detect_and_trigger(image_path: str):
    source = Path(image_path)

    if not source.exists():
        print(f"[ERROR] 图片不存在：{source}")
        return

    print("==================================================")
    print("[VISION] 单张图片识别 + Trigger 联调")
    print("==================================================")
    print(f"[MODEL] {MODEL_PATH}")
    print(f"[IMAGE] {source}")
    print(f"[CONF ] {CONF_THRESHOLD}")
    print("")

    model = YOLO(MODEL_PATH)
    results = model(str(source), conf=CONF_THRESHOLD)

    result = results[0]
    boxes = result.boxes

    if boxes is None or len(boxes) == 0:
        print("[RESULT] 没有识别到 bleeding / incap")
        print("[ACTION] 不发送 Trigger 事件")
        print("==================================================")
        return

    print(f"[RESULT] 共识别到 {len(boxes)} 个目标：")

    best_name = None
    best_conf = -1.0

    for i, box in enumerate(boxes, start=1):
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        name = model.names[cls_id]
        xyxy = [round(v, 1) for v in box.xyxy[0].tolist()]

        print(
            f"  #{i} class={name}, "
            f"conf={conf:.3f}, "
            f"box={xyxy}"
        )

        if conf > best_conf:
            best_conf = conf
            best_name = name

    print("")
    print(f"[BEST DETECTION] class={best_name}, conf={best_conf:.3f}")

    if best_name in ("bleeding", "incap"):
        send_event(best_name, confidence=best_conf, source="vision_image_test")
    else:
        print("[ACTION] 识别结果不是目标事件，不发送 Trigger")

    print("==================================================")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        required=True,
        help="要识别的图片路径"
    )

    args = parser.parse_args()
    detect_and_trigger(args.source)


if __name__ == "__main__":
    main()
