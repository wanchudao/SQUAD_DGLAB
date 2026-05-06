import sys
import time
import threading
from pathlib import Path

import cv2
import numpy as np
import requests
import torch
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

CONF_THRESHOLD = 0.6
FRAME_INTERVAL = 0.50

# YOLO 推理输入尺寸
# 第一版先用 640，保证识别效果。
# 如果后续性能仍然不够，再考虑改成 512 或 416。
IMG_SIZE = 640


# =========================
# GPU 推理配置
# =========================
# 当前系统 Python 已确认：
# torch: 2.11.0+cu126
# cuda available: True
# GPU: NVIDIA GeForce RTX 3070 Ti
#
# DEVICE = 0 表示使用第 0 张 NVIDIA 显卡。
# 如果 CUDA 不可用，则自动回退到 CPU。
# =========================

DEVICE = 0 if torch.cuda.is_available() else "cpu"

# 第一轮先不开 half，先保证稳定。
# 如果后续确认 GPU 推理稳定，可以改成 True 测试半精度加速。
USE_HALF = False


# =========================
# ROI 检测区域配置
# =========================
# 观察 SQUAD UI 后发现：
# bleeding / incap 相关 UI 基本集中在屏幕下半部分。
#
# 因此 YOLO 不再检测整张图，而是只检测屏幕下半部分。
# 这样可以减少上半屏天空、建筑、水印、服务器文字等干扰，
# 也可以减轻模型推理负担。
#
# DETECT_Y_START_RATIO = 0.70
# 表示从画面高度 70% 开始检测，也就是只看下半屏。
#!!!!!千万不要改，保持0.00，否则incap会失效
# =========================

DETECT_Y_START_RATIO = 0.00
DETECT_X_START_RATIO = 0.00
DETECT_X_END_RATIO = 1.00


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
# death 逻辑判断配置
# =========================
# 你的规则：
# 检测到 incap 后 250 秒内，如果屏幕 90% 以上是黑的，就触发 death。
#
# 设计目标：
# 1. incap：濒死期间每 5 秒触发一次 strong_pulse
# 2. death：本轮 incap 后，如果黑屏死亡，只触发一次 death_pulse
# 3. 复活/恢复正常画面后，重置状态，允许下一轮 death 再次触发
# =========================

# 检测到 incap 后，多少秒内允许通过黑屏判断 death
DEATH_WINDOW_SECONDS = 250.0

# 黑屏比例阈值：屏幕 90% 以上接近黑色，就认为是死亡黑屏
BLACK_SCREEN_RATIO_THRESHOLD = 0.90

# 单个像素亮度低于这个值，就认为这个像素是黑的
# 0 是纯黑，255 是纯白。25 是比较保守的黑色阈值。
BLACK_PIXEL_BRIGHTNESS_THRESHOLD = 25

# 恢复判断：黑屏比例低于这个值，认为画面可能已经恢复正常
RECOVERY_BLACK_RATIO_THRESHOLD = 0.50

# 连续多少帧恢复正常后，才真正重置 death 周期
RECOVERY_FRAMES_REQUIRED = 3

# 上一次检测到 incap 的时间
last_incap_time = None

# 当前是否处于一轮 incap → death 判断周期里
incap_cycle_active = False

# 当前这一轮 incap 后，death 是否已经触发过
death_fired_this_cycle = False

# 恢复正常画面的连续帧计数
recovery_frame_count = 0


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


def get_black_screen_ratio(frame) -> float:
    """
    计算当前画面中“接近黑色”的像素比例。

    返回值：
        0.0 表示完全不黑
        1.0 表示整张图都是黑的
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    black_pixels = gray < BLACK_PIXEL_BRIGHTNESS_THRESHOLD
    black_ratio = black_pixels.sum() / black_pixels.size

    return float(black_ratio)


def reset_death_cycle():
    """
    重置本轮 incap → death 周期。

    什么时候会调用：
    1. death 已经触发过；
    2. 后续画面恢复正常；
    3. 程序认为可以等待下一轮新的 incap。
    """
    global last_incap_time
    global incap_cycle_active
    global death_fired_this_cycle
    global recovery_frame_count

    last_incap_time = None
    incap_cycle_active = False
    death_fired_this_cycle = False
    recovery_frame_count = 0

    print("[DEATH STATE] 已重置 incap/death 周期，等待下一轮 incap")


def should_trigger_death(now: float, black_ratio: float) -> bool:
    """
    判断是否应该触发 death。

    death 条件：
    1. 当前处于 incap 周期；
    2. 本轮 death 还没触发过；
    3. 最近一次 incap 在 250 秒内；
    4. 当前画面黑屏比例 >= 90%。
    """
    if not incap_cycle_active:
        return False

    if death_fired_this_cycle:
        return False

    if last_incap_time is None:
        return False

    elapsed_after_incap = now - last_incap_time

    if elapsed_after_incap > DEATH_WINDOW_SECONDS:
        return False

    if black_ratio >= BLACK_SCREEN_RATIO_THRESHOLD:
        return True

    return False


def update_recovery_state(black_ratio: float, has_incap_detection: bool):
    """
    检测是否已经恢复到正常画面。

    恢复后重置本轮周期，让下一次 incap/death 可以重新触发。

    这里不只是在 death 后能重置；
    如果玩家被救起、离开 incap 状态，也能在画面恢复后重置。
    """
    global recovery_frame_count

    if not incap_cycle_active:
        return

    # 如果画面不黑，并且当前没有检测到 incap，认为可能已经恢复
    if black_ratio < RECOVERY_BLACK_RATIO_THRESHOLD and not has_incap_detection:
        recovery_frame_count += 1

        if recovery_frame_count >= RECOVERY_FRAMES_REQUIRED:
            reset_death_cycle()
    else:
        recovery_frame_count = 0


def send_trigger(event_name: str, conf: float) -> bool:
    """
    向 python_trigger 发送事件。

    返回 True：
        Trigger 返回 success=True，或者 DRY_RUN 模式下认为发送成功。

    返回 False：
        请求失败，或者 Trigger 返回 success=False。
    """
    payload = {
        "event": event_name,
        "source": "realtime_detect_and_trigger",
        "level": f"conf={conf:.3f}"
    }

    if DRY_RUN:
        print(f"[DRY_RUN] 不发送 Trigger：{payload}")
        return True

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
            data = response.json()
            print(f"[TRIGGER RESPONSE] {data}")
            print("=" * 50)

            return bool(data.get("success", False))

        except Exception:
            print(f"[TRIGGER RESPONSE TEXT] {response.text}")
            print("=" * 50)

            return 200 <= response.status_code < 300

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 发送 Trigger 失败：{e}")
        return False


def draw_detection(frame, label, conf, box):
    """
    在预览画面上画框。
    """
    x1, y1, x2, y2 = map(int, box)

    if label == "bleeding":
        color = (0, 0, 255)
    elif label == "incap":
        color = (0, 165, 255)
    elif label == "death":
        color = (255, 0, 255)
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


def draw_roi(frame, roi_x1, roi_y1, roi_x2, roi_y2):
    """
    在预览画面上画出 YOLO 实际检测区域。
    黄色框表示当前 ROI。
    """
    cv2.rectangle(
        frame,
        (roi_x1, roi_y1),
        (roi_x2, roi_y2),
        (0, 255, 255),
        2
    )

    cv2.putText(
        frame,
        "YOLO ROI",
        (roi_x1 + 10, max(roi_y1 + 25, 25)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2
    )


def main():
    global last_incap_time
    global incap_cycle_active
    global death_fired_this_cycle
    global recovery_frame_count

    print("=" * 50)
    print("[VISION] 实时截图识别 + Trigger 测试")
    print("=" * 50)
    print(f"[MODEL] {MODEL_PATH}")
    print(f"[CONF] {CONF_THRESHOLD}")
    print(f"[FRAME_INTERVAL] {FRAME_INTERVAL}s")
    print(f"[IMG_SIZE] {IMG_SIZE}")
    print(f"[ROI] x={DETECT_X_START_RATIO:.2f}~{DETECT_X_END_RATIO:.2f}, y={DETECT_Y_START_RATIO:.2f}~1.00")
    print(f"[TRIGGER_URL] {TRIGGER_URL}")
    print(f"[DRY_RUN] {DRY_RUN}")
    print(f"[LOCAL_COOLDOWN] {LOCAL_COOLDOWN}")
    print()
    print("[DEVICE CONFIG]")
    print(f"       torch version = {torch.__version__}")
    print(f"       cuda available = {torch.cuda.is_available()}")
    print(f"       device = {DEVICE}")
    print(f"       use_half = {USE_HALF}")
    if torch.cuda.is_available():
        print(f"       gpu = {torch.cuda.get_device_name(0)}")
    print()
    print("[DEATH CONFIG]")
    print(f"       DEATH_WINDOW_SECONDS = {DEATH_WINDOW_SECONDS}")
    print(f"       BLACK_SCREEN_RATIO_THRESHOLD = {BLACK_SCREEN_RATIO_THRESHOLD}")
    print(f"       BLACK_PIXEL_BRIGHTNESS_THRESHOLD = {BLACK_PIXEL_BRIGHTNESS_THRESHOLD}")
    print(f"       RECOVERY_BLACK_RATIO_THRESHOLD = {RECOVERY_BLACK_RATIO_THRESHOLD}")
    print(f"       RECOVERY_FRAMES_REQUIRED = {RECOVERY_FRAMES_REQUIRED}")
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

    # 显式把模型放到 GPU。
    # model.predict(device=DEVICE) 本身也会指定设备，
    # 这里额外 model.to 是为了启动时更明确地完成迁移。
    if DEVICE != "cpu":
        model.to(f"cuda:{DEVICE}")
        print(f"[MODEL DEVICE] 模型已移动到 cuda:{DEVICE}")
    else:
        print("[MODEL DEVICE] 当前使用 CPU 推理")

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

                now = time.time()

                # 计算当前画面的黑屏比例，用于 death 逻辑。
                # 注意：death 黑屏判断仍然使用全屏 frame，不使用 ROI。
                black_ratio = get_black_screen_ratio(frame)

                # =========================
                # 裁剪 YOLO 检测 ROI
                # =========================
                # YOLO 只看屏幕下半部分。
                # 这样可以减少上半屏无关内容对检测的干扰。
                frame_h, frame_w = frame.shape[:2]

                roi_x1 = int(frame_w * DETECT_X_START_RATIO)
                roi_x2 = int(frame_w * DETECT_X_END_RATIO)
                roi_y1 = int(frame_h * DETECT_Y_START_RATIO)
                roi_y2 = frame_h

                detect_frame = frame[roi_y1:roi_y2, roi_x1:roi_x2]

                results = model.predict(
                    source=detect_frame,
                    conf=CONF_THRESHOLD,
                    imgsz=IMG_SIZE,
                    device=DEVICE,
                    half=(USE_HALF and DEVICE != "cpu"),
                    verbose=False
                )

                infer_time = time.time() - start_time

                detections = []
                has_incap_detection = False

                for result in results:
                    boxes = result.boxes
                    if boxes is None:
                        continue

                    for box in boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        label = model.names.get(cls_id, str(cls_id))

                        xyxy = box.xyxy[0].tolist()

                        # YOLO 返回的是 ROI 内部坐标，需要加回 ROI 在原图中的偏移。
                        # 否则预览窗口里的框会画到错误位置。
                        xyxy[0] += roi_x1
                        xyxy[2] += roi_x1
                        xyxy[1] += roi_y1
                        xyxy[3] += roi_y1

                        detections.append({
                            "label": label,
                            "conf": conf,
                            "box": xyxy
                        })

                        if label == "incap":
                            has_incap_detection = True

                if not detections:
                    print(
                        f"[FRAME {frame_id}] no detections | "
                        f"black={black_ratio:.3f} | "
                        f"infer={infer_time:.3f}s"
                    )
                else:
                    # 如果同一帧出现多个框，先按置信度排序
                    detections.sort(key=lambda x: x["conf"], reverse=True)

                    # 当前阶段：
                    # 如果同一帧同时有 incap 和 bleeding，优先处理 incap
                    # 因为 incap 是更严重的状态
                    incap_dets = [d for d in detections if d["label"] == "incap"]
                    bleeding_dets = [d for d in detections if d["label"] == "bleeding"]

                    if incap_dets:
                        best = incap_dets[0]
                    elif bleeding_dets:
                        best = bleeding_dets[0]
                    else:
                        best = detections[0]

                    label = best["label"]
                    conf = best["conf"]
                    box = best["box"]

                    print(
                        f"[FRAME {frame_id}] "
                        f"class={label}, conf={conf:.3f}, "
                        f"box={[round(v, 1) for v in box]}, "
                        f"black={black_ratio:.3f}, "
                        f"infer={infer_time:.3f}s"
                    )

                    if label in ("bleeding", "incap", "death"):

                        # incap 是 death 逻辑的前置条件
                        if label == "incap":
                            # 如果之前不在 incap 周期，说明这是新一轮 incap
                            if not incap_cycle_active:
                                incap_cycle_active = True
                                death_fired_this_cycle = False
                                recovery_frame_count = 0
                                print("[INCAP STATE] 新一轮 incap 周期开始，开启 250 秒 death 判断窗口")

                            # 持续更新时间：
                            # 只要还在检测到 incap，就说明仍处于这一轮濒死状态
                            last_incap_time = now

                        # bleeding / incap 仍然按本地 cooldown 正常触发。
                        # 这保证 incap 会每 5 秒触发一次 strong_pulse。
                        if can_send_locally(label):
                            send_trigger(label, conf)

                    else:
                        print(f"[ACTION] 未知类别，不发送：{label}")

                # death 逻辑：
                # 检测到 incap 后 250 秒内，如果屏幕 90% 以上为黑，则触发一次 death
                if should_trigger_death(now, black_ratio):
                    elapsed_after_incap = now - last_incap_time

                    print(
                        f"[DEATH CHECK] 条件成立："
                        f"incap 后 {elapsed_after_incap:.1f}s 内，"
                        f"black_ratio={black_ratio:.3f}"
                    )

                    if can_send_locally("death"):
                        ok = send_trigger("death", black_ratio)

                        if ok:
                            death_fired_this_cycle = True
                            print("[DEATH STATE] death 已触发，本轮不再重复触发 death")
                        else:
                            print("[DEATH STATE] death 发送失败，本轮暂不锁定，后续可重试")

                # 恢复检测：
                # 如果画面恢复正常，并且没有 incap，重置本轮 incap/death 周期
                update_recovery_state(black_ratio, has_incap_detection)

                if SHOW_PREVIEW:
                    # 黄色框表示当前 YOLO 实际检测区域
                    draw_roi(frame, roi_x1, roi_y1, roi_x2, roi_y2)

                    for det in detections:
                        draw_detection(
                            frame,
                            det["label"],
                            det["conf"],
                            det["box"]
                        )

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
