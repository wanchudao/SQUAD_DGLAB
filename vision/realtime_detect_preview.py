# ============================================================
# 文件：vision/realtime_detect_preview.py
# 作用：实时截图 + YOLO 识别预览
#
# 当前阶段目标：
#   1. 从屏幕实时截图
#   2. 用 best.pt 做 YOLO 推理
#   3. 打印 bleeding / incap 识别结果
#   4. 暂时不发送 Trigger，避免误触发
#
# 停止方式：
#   1. 在预览窗口按 q
#   2. 在预览窗口按 Esc
#   3. 在命令行输入 stop 后回车
#   4. Ctrl + C 强制中断
# ============================================================

import threading
import time

import cv2
import numpy as np
from mss import MSS
from ultralytics import YOLO

from config import MODEL_PATH, CONF_THRESHOLD


# 每隔多少秒识别一次
FRAME_INTERVAL = 0.5

# 是否显示预览窗口
SHOW_WINDOW = True

# 是否只截取屏幕局部区域
# 第一版先截全屏，确认能跑通后再优化成只截 UI 区域
USE_REGION = False

# 如果后面要截局部区域，可以改这里
# left/top/width/height 单位是像素
CAPTURE_REGION = {
    "left": 0,
    "top": 0,
    "width": 1280,
    "height": 720,
}


# 全局停止标志
stop_event = threading.Event()


def input_listener():
    """
    命令行停止监听线程。
    用户输入 stop / q / exit 后，通知主循环退出。
    """
    while not stop_event.is_set():
        try:
            text = input().strip().lower()
        except EOFError:
            break

        if text in ("stop", "q", "quit", "exit"):
            print("[STOP] 收到命令行停止指令")
            stop_event.set()
            break


def get_monitor(sct: MSS):
    """
    获取截图区域。
    第一版默认使用主显示器全屏。
    """
    if USE_REGION:
        return CAPTURE_REGION

    # sct.monitors[1] 通常是主显示器
    return sct.monitors[1]


def screenshot_to_bgr(sct: MSS, monitor: dict):
    """
    用 mss 截图，并转换成 OpenCV/YOLO 常用的 BGR 图像。
    """
    shot = sct.grab(monitor)

    # mss 输出是 BGRA，转成 BGR
    frame = np.array(shot)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    return frame


def get_best_detection(model: YOLO, frame):
    """
    对当前截图帧做推理，返回最高置信度目标。
    如果没有检测到，返回 None。
    """
    results = model(frame, conf=CONF_THRESHOLD, verbose=False)

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


def draw_detection(frame, detection):
    """
    在预览窗口上画识别框。
    """
    if detection is None:
        return frame

    x1, y1, x2, y2 = [int(v) for v in detection["box"]]
    name = detection["class"]
    conf = detection["conf"]

    color = (0, 255, 0)

    if name == "bleeding":
        color = (0, 0, 255)      # 红色
    elif name == "incap":
        color = (255, 0, 0)      # 蓝色

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    label = f"{name} {conf:.2f}"
    cv2.putText(
        frame,
        label,
        (x1, max(y1 - 10, 20)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
    )

    return frame


def main():
    print("==================================================")
    print("[VISION] 实时截图 + YOLO 识别预览")
    print("==================================================")
    print(f"[MODEL] {MODEL_PATH}")
    print(f"[CONF] {CONF_THRESHOLD}")
    print(f"[FRAME_INTERVAL] {FRAME_INTERVAL}s")
    print(f"[SHOW_WINDOW] {SHOW_WINDOW}")
    print("[NOTICE] 当前版本只打印识别结果，不发送 Trigger")
    print("[STOP] 停止方式：")
    print("       1. 预览窗口按 q")
    print("       2. 预览窗口按 Esc")
    print("       3. 命令行输入 stop 后回车")
    print("       4. Ctrl + C")
    print("==================================================")
    print("")

    # 启动命令行输入监听线程
    listener = threading.Thread(target=input_listener, daemon=True)
    listener.start()

    model = YOLO(MODEL_PATH)

    with MSS() as sct:
        monitor = get_monitor(sct)

        print(f"[MONITOR] {monitor}")
        print("==================================================")

        frame_index = 0

        try:
            while not stop_event.is_set():
                frame_index += 1

                frame = screenshot_to_bgr(sct, monitor)

                start = time.time()
                detection = get_best_detection(model, frame)
                elapsed = time.time() - start

                if detection is None:
                    print(f"[FRAME {frame_index}] no detections | infer={elapsed:.3f}s")
                else:
                    name = detection["class"]
                    conf = detection["conf"]
                    box = detection["box"]

                    print(
                        f"[FRAME {frame_index}] "
                        f"class={name}, conf={conf:.3f}, box={box}, "
                        f"infer={elapsed:.3f}s"
                    )

                if SHOW_WINDOW:
                    preview = frame.copy()
                    preview = draw_detection(preview, detection)

                    # 缩小窗口显示，避免太大
                    preview = cv2.resize(preview, None, fx=0.6, fy=0.6)

                    cv2.imshow("SQUAD Vision Preview - q/Esc to quit", preview)

                    key = cv2.waitKey(1) & 0xFF

                    if key == ord("q"):
                        print("[STOP] 预览窗口收到 q")
                        stop_event.set()
                        break

                    if key == 27:
                        print("[STOP] 预览窗口收到 Esc")
                        stop_event.set()
                        break

                time.sleep(FRAME_INTERVAL)

        except KeyboardInterrupt:
            print("")
            print("[STOP] 收到 Ctrl + C")
            stop_event.set()

        finally:
            cv2.destroyAllWindows()
            print("[DONE] 实时识别预览结束")


if __name__ == "__main__":
    main()
