# ============================================================
# 文件：vision/sequence_trigger_test.py
# 作用：连续帧模拟测试
#
# 用 samples/sequence_images 里的图片模拟连续游戏画面。
# 每隔一段时间识别一张图。
# 如果识别到 bleeding / incap，就发送到 python_trigger。
# ============================================================

import time
from pathlib import Path

from ultralytics import YOLO

from config import MODEL_PATH, CONF_THRESHOLD
from trigger_client import send_event


SEQUENCE_DIR = Path("D:/SQUAD_DGLAB/samples/sequence_images")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

FRAME_INTERVAL = 0.5


def collect_images():
    images = []

    if not SEQUENCE_DIR.exists():
        print(f"[ERROR] 连续帧目录不存在：{SEQUENCE_DIR}")
        return images

    for path in SEQUENCE_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            images.append(path)

    return sorted(images)


def get_best_detection(model: YOLO, image_path: Path):
    results = model(str(image_path), conf=CONF_THRESHOLD, verbose=False)
    result = results[0]
    boxes = result.boxes

    if boxes is None or len(boxes) == 0:
        return None

    best = None

    for box in boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        name = model.names[cls_id]
        xyxy = [round(v, 1) for v in box.xyxy[0].tolist()]

        if best is None or conf > best["conf"]:
            best = {
                "class": name,
                "conf": conf,
                "box": xyxy,
            }

    return best


def main():
    print("==================================================")
    print("[VISION] 连续帧模拟 + Trigger 测试")
    print("==================================================")
    print(f"[MODEL] {MODEL_PATH}")
    print(f"[SEQUENCE_DIR] {SEQUENCE_DIR}")
    print(f"[CONF] {CONF_THRESHOLD}")
    print(f"[FRAME_INTERVAL] {FRAME_INTERVAL}s")
    print("")

    images = collect_images()

    if not images:
        print("[ERROR] 没有找到连续帧图片")
        return

    model = YOLO(MODEL_PATH)

    print(f"[INFO] 共找到 {len(images)} 张图片")
    print("==================================================")

    for index, image_path in enumerate(images, start=1):
        print("")
        print("--------------------------------------------------")
        print(f"[FRAME {index}/{len(images)}] {image_path.name}")

        detection = get_best_detection(model, image_path)

        if detection is None:
            print("[DETECT] no detections")
            print("[ACTION] 不发送 Trigger")
        else:
            name = detection["class"]
            conf = detection["conf"]
            box = detection["box"]

            print(f"[DETECT] class={name}, conf={conf:.3f}, box={box}")

            if name in ("bleeding", "incap"):
                print(f"[ACTION] 发送事件到 Trigger：{name}")
                send_event(name, confidence=conf, source="vision_sequence_test")
            else:
                print("[ACTION] 非目标类别，不发送 Trigger")

        print(f"[SLEEP] 等待 {FRAME_INTERVAL}s")
        time.sleep(FRAME_INTERVAL)

    print("")
    print("==================================================")
    print("[DONE] 连续帧模拟测试结束")
    print("==================================================")


if __name__ == "__main__":
    main()
