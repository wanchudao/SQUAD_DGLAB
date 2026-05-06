# ============================================================
# 文件：vision/detect_image.py
# 作用：用 best.pt 对单张图片做 YOLO 推理
#
# 当前阶段目标：
#   1. 确认模型能在笔记本上正常推理
#   2. 打印识别到的 bleeding / incap
#   3. 保存一张带框结果图，方便肉眼检查
# ============================================================

import argparse
from pathlib import Path

from ultralytics import YOLO

from config import MODEL_PATH, CONF_THRESHOLD, OUTPUT_DIR


def detect_one_image(image_path: str):
    """
    对单张图片进行识别。
    """

    source = Path(image_path)

    if not source.exists():
        print(f"[ERROR] 图片不存在：{source}")
        return

    print("==================================================")
    print("[VISION] 单张图片识别测试")
    print("==================================================")
    print(f"[MODEL] {MODEL_PATH}")
    print(f"[IMAGE] {source}")
    print(f"[CONF ] {CONF_THRESHOLD}")
    print("")

    # 加载模型
    model = YOLO(MODEL_PATH)

    print(f"[MODEL NAMES] {model.names}")
    print("")

    # 执行推理
    results = model(str(source), conf=CONF_THRESHOLD)

    # 单张图片只有一个 result
    result = results[0]

    boxes = result.boxes

    if boxes is None or len(boxes) == 0:
        print("[RESULT] 没有识别到 bleeding / incap")
    else:
        print(f"[RESULT] 共识别到 {len(boxes)} 个目标：")

        for i, box in enumerate(boxes, start=1):
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            name = model.names[cls_id]
            xyxy = box.xyxy[0].tolist()
            xyxy = [round(v, 1) for v in xyxy]

            print(
                f"  #{i} class={name}, "
                f"conf={conf:.3f}, "
                f"box={xyxy}"
            )

    # 保存带框结果图
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"detected_{source.name}"
    result.save(filename=str(output_path))

    print("")
    print(f"[SAVE] 带框结果图已保存到：{output_path}")
    print("==================================================")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        required=True,
        help="要识别的图片路径，例如 D:\\SQUAD_DGLAB\\samples\\test_images\\bleeding_01.jpg"
    )

    args = parser.parse_args()
    detect_one_image(args.source)


if __name__ == "__main__":
    main()
