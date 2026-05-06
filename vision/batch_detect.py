# ============================================================
# 文件：vision/batch_detect.py
# 作用：批量测试 samples/test_images 下的图片
#
# 注意：
#   这个脚本只做识别统计，不发送 Trigger。
#   目的是评估模型对多张图片的稳定性。
# ============================================================

from pathlib import Path

from ultralytics import YOLO

from config import MODEL_PATH, CONF_THRESHOLD


IMAGE_DIR = Path(r"D:/SQUAD_DGLAB/samples/test_images")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def collect_images(image_dir: Path):
    images = []

    for path in image_dir.iterdir():
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            images.append(path)

    return sorted(images)


def detect_image(model: YOLO, image_path: Path):
    results = model(str(image_path), conf=CONF_THRESHOLD, verbose=False)
    result = results[0]
    boxes = result.boxes

    detections = []

    if boxes is None or len(boxes) == 0:
        return detections

    for box in boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        name = model.names[cls_id]
        xyxy = [round(v, 1) for v in box.xyxy[0].tolist()]

        detections.append({
            "class": name,
            "conf": conf,
            "box": xyxy,
        })

    return detections


def main():
    print("==================================================")
    print("[VISION] 批量图片识别测试")
    print("==================================================")
    print(f"[MODEL] {MODEL_PATH}")
    print(f"[IMAGE_DIR] {IMAGE_DIR}")
    print(f"[CONF] {CONF_THRESHOLD}")
    print("")

    if not IMAGE_DIR.exists():
        print(f"[ERROR] 图片目录不存在：{IMAGE_DIR}")
        return

    images = collect_images(IMAGE_DIR)

    if not images:
        print(f"[ERROR] 图片目录里没有图片：{IMAGE_DIR}")
        return

    model = YOLO(MODEL_PATH)

    total = 0
    no_detection = 0
    bleeding_count = 0
    incap_count = 0
    other_count = 0

    for image_path in images:
        total += 1
        detections = detect_image(model, image_path)

        print("--------------------------------------------------")
        print(f"[IMAGE] {image_path.name}")

        if not detections:
            no_detection += 1
            print("[RESULT] no detections")
            continue

        for det in detections:
            name = det["class"]
            conf = det["conf"]
            box = det["box"]

            if name == "bleeding":
                bleeding_count += 1
            elif name == "incap":
                incap_count += 1
            else:
                other_count += 1

            print(f"[RESULT] class={name}, conf={conf:.3f}, box={box}")

    print("==================================================")
    print("[SUMMARY]")
    print(f"total_images   = {total}")
    print(f"no_detection   = {no_detection}")
    print(f"bleeding_count = {bleeding_count}")
    print(f"incap_count    = {incap_count}")
    print(f"other_count    = {other_count}")
    print("==================================================")


if __name__ == "__main__":
    main()
