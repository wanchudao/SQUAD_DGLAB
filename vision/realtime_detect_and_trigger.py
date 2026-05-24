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

from suppression import get_detector


# =========================
# Path config
# =========================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "model" / "best.pt"

TRIGGER_URL = "http://127.0.0.1:18000/trigger"


# =========================
# Detection config
# =========================

CONF_THRESHOLD = 0.6
FRAME_INTERVAL = 0.50

# YOLO inference input size
IMG_SIZE = 640


# =========================
# GPU inference config
# =========================

DEVICE = 0 if torch.cuda.is_available() else "cpu"

# Keep half off in the first pass, stability first.
USE_HALF = False


# =========================
# ROI detection region
# =========================
# Important:
# Keep full-screen detection.
# Do not crop to lower half, incap can fail.
# =========================

DETECT_Y_START_RATIO = 0.00
DETECT_X_START_RATIO = 0.00
DETECT_X_END_RATIO = 1.00


# Whether to actually POST to Trigger
# True  = print only, do not POST
# False = POST to Trigger
DRY_RUN = False

# Whether to show OpenCV preview window
SHOW_PREVIEW = True


# =========================
# Suppression config
# =========================
#
# Suppression is loaded via vision/suppression/ factory function.
# Mode is controlled by env var SQUAD_SUPPRESSION_MODE:
#
#   off       default, no suppression detection
#   blur      v1 detector, vanilla SQUAD, may false-trigger in modded server
#   vignette  v2 detector, modded SQUAD, will NOT detect vanilla suppression
#
# Both detectors are EXPERIMENTAL, default off.
# To enable, set the env var before starting, e.g.
#   set SQUAD_SUPPRESSION_MODE=vignette
#
# Gating rules (suppression detector is SKIPPED when):
#   1. incap_cycle_active is True   -> avoid v2 false-trigger on incap UI
#   2. black_ratio > 0.50           -> avoid v2 false-trigger on near-black
#                                      frames (death blackout, big map, etc)
# When gated, the detector is reset() so it does not resume from a stuck
# state machine value after the gate lifts.
# =========================

ENABLE_SUPPRESSION = True

# Threshold above which suppression detection is gated by black-ratio.
SUPP_GATE_BLACK_RATIO = 0.50


# =========================
# Vision local cooldown config
# =========================
# Notes:
# 1. This is the vision-layer local cooldown, reduces duplicate POSTs.
# 2. python_trigger/app.py also has cooldown, second line of defense.
# 3. Two-layer cooldown is safer.
# =========================

LOCAL_COOLDOWN = {
    "bleeding": 1.0,
    "incap": 5.0,
    "death": 5.0,
    "suppression_light": 1.5,
    "suppression_heavy": 2.5,
}

last_send_time = {}


# =========================
# Death logic config
# =========================
# Rule:
# If within 250 seconds after an incap, the screen becomes 90% black,
# trigger a death event.
# =========================

DEATH_WINDOW_SECONDS = 250.0
BLACK_SCREEN_RATIO_THRESHOLD = 0.90
BLACK_PIXEL_BRIGHTNESS_THRESHOLD = 25
RECOVERY_BLACK_RATIO_THRESHOLD = 0.50
RECOVERY_FRAMES_REQUIRED = 3

last_incap_time = None
incap_cycle_active = False
death_fired_this_cycle = False
recovery_frame_count = 0


# =========================
# Run control
# =========================

stop_event = threading.Event()


def input_listener():
    """
    Console stop thread:
    type stop / q / quit / exit then Enter to stop the program.
    """
    while not stop_event.is_set():
        try:
            text = input().strip().lower()
            if text in ("stop", "q", "quit", "exit"):
                print("[STOP] console stop")
                stop_event.set()
                break
        except EOFError:
            break
        except KeyboardInterrupt:
            stop_event.set()
            break


def can_send_locally(event_name):
    """
    Vision-layer local cooldown check.

    Returns True:
        allowed to POST the event to Trigger.

    Returns False:
        in local cooldown, do not POST.
    """
    now = time.time()
    cooldown = LOCAL_COOLDOWN.get(event_name, 0.5)
    last_time = last_send_time.get(event_name, 0)

    elapsed = now - last_time

    if elapsed < cooldown:
        remain = cooldown - elapsed
        print("[LOCAL BLOCK] " + event_name + " local cooldown, remain " + "{:.2f}".format(remain) + "s, skip POST")
        return False

    last_send_time[event_name] = now
    return True


def get_black_screen_ratio(frame):
    """
    Compute the ratio of near-black pixels in the current frame.

    Return:
        0.0 = no black pixels
        1.0 = entire frame is black
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    black_pixels = gray < BLACK_PIXEL_BRIGHTNESS_THRESHOLD
    black_ratio = black_pixels.sum() / black_pixels.size

    return float(black_ratio)


def reset_death_cycle():
    """
    Reset the current incap -> death cycle.
    """
    global last_incap_time
    global incap_cycle_active
    global death_fired_this_cycle
    global recovery_frame_count

    last_incap_time = None
    incap_cycle_active = False
    death_fired_this_cycle = False
    recovery_frame_count = 0

    print("[DEATH STATE] reset incap/death cycle, wait for next incap")


def should_trigger_death(now, black_ratio):
    """
    Decide whether to fire a death event.

    Conditions:
    1. currently in an incap cycle
    2. death has not fired in this cycle yet
    3. last incap was within 250 seconds
    4. current black_ratio >= 90 percent
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


def update_recovery_state(black_ratio, has_incap_detection):
    """
    Detect whether the screen has returned to a normal state.

    On recovery, reset the cycle so the next incap/death can fire again.
    """
    global recovery_frame_count

    if not incap_cycle_active:
        return

    if black_ratio < RECOVERY_BLACK_RATIO_THRESHOLD and not has_incap_detection:
        recovery_frame_count += 1

        if recovery_frame_count >= RECOVERY_FRAMES_REQUIRED:
            reset_death_cycle()
    else:
        recovery_frame_count = 0


def make_gated_supp_result(reason):
    """
    Build a placeholder suppression result when the detector is gated.

    reason: short string for logging, e.g. "gated_incap", "gated_black"
    """
    return {
        "event": None,
        "score": 0.0,
        "blur_ratio": 0.0,
        "chroma_shift": 0.0,
        "state": reason,
        "debug_text": reason,
    }


def send_trigger(event_name, level_text):
    """
    POST an event to python_trigger.

    level_text examples:
        YOLO:
            conf=0.937

        death:
            black=0.979

        suppression v1:
            score=6.80,blur=7.10,chroma=0.130,state=active_heavy

        suppression v2:
            vignette=0.95,cob=2,off=0.05,edge=0.010,state=active_heavy

    Return True:
        Trigger returned success=True, or DRY_RUN considered success.

    Return False:
        request failed, or Trigger returned success=False.
    """
    payload = {
        "event": event_name,
        "source": "realtime_detect_and_trigger",
        "level": level_text,
    }

    if DRY_RUN:
        print("[DRY_RUN] skip POST: " + str(payload))
        return True

    try:
        print("=" * 50)
        print("[VISION -> TRIGGER] sending event")
        print("[EVENT ] " + event_name)
        print("[SOURCE] realtime_detect_and_trigger")
        print("[LEVEL ] " + str(level_text))
        print("[POST  ] " + TRIGGER_URL)

        response = requests.post(TRIGGER_URL, json=payload, timeout=2.0)

        print("[HTTP STATUS] " + str(response.status_code))

        try:
            data = response.json()
            print("[TRIGGER RESPONSE] " + str(data))
            print("=" * 50)

            return bool(data.get("success", False))

        except Exception:
            print("[TRIGGER RESPONSE TEXT] " + response.text)
            print("=" * 50)

            return 200 <= response.status_code < 300

    except requests.exceptions.RequestException as e:
        print("[ERROR] send trigger failed: " + str(e))
        return False


def draw_detection(frame, label, conf, box):
    """
    Draw a detection box on the preview frame.
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

    text = label + " " + "{:.3f}".format(conf)
    cv2.putText(
        frame,
        text,
        (x1, max(y1 - 10, 20)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
    )


def draw_roi(frame, roi_x1, roi_y1, roi_x2, roi_y2):
    """
    Draw the YOLO ROI on the preview frame.
    Currently full-screen.
    """
    cv2.rectangle(
        frame,
        (roi_x1, roi_y1),
        (roi_x2, roi_y2),
        (0, 255, 255),
        2,
    )

    cv2.putText(
        frame,
        "YOLO ROI",
        (roi_x1 + 10, max(roi_y1 + 25, 25)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
    )


def draw_suppression_status(frame, supp_result):
    """
    Draw suppression status in the upper-left of the preview.
    """
    if not supp_result:
        return

    event = supp_result.get("event")
    state = supp_result.get("state", "unknown")
    debug_text = supp_result.get("debug_text", "")

    if event == "suppression_heavy":
        color = (0, 0, 255)
    elif event == "suppression_light":
        color = (0, 165, 255)
    elif state in ("off", "disabled"):
        color = (120, 120, 120)
    elif state in ("gated_incap", "gated_black"):
        color = (200, 200, 80)
    else:
        color = (180, 180, 180)

    lines = [
        "SUPP: " + str(state),
        debug_text,
    ]

    x = 15
    y = 35

    for line in lines:
        cv2.putText(
            frame,
            line,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
        )
        y += 28


def main():
    global last_incap_time
    global incap_cycle_active
    global death_fired_this_cycle
    global recovery_frame_count

    print("=" * 50)
    print("[VISION] realtime detect + trigger")
    print("=" * 50)
    print("[MODEL] " + str(MODEL_PATH))
    print("[CONF] " + str(CONF_THRESHOLD))
    print("[FRAME_INTERVAL] " + str(FRAME_INTERVAL) + "s")
    print("[IMG_SIZE] " + str(IMG_SIZE))
    print("[ROI] x=" + "{:.2f}".format(DETECT_X_START_RATIO) + "~" + "{:.2f}".format(DETECT_X_END_RATIO)
          + ", y=" + "{:.2f}".format(DETECT_Y_START_RATIO) + "~1.00")
    print("[TRIGGER_URL] " + TRIGGER_URL)
    print("[DRY_RUN] " + str(DRY_RUN))
    print("[LOCAL_COOLDOWN] " + str(LOCAL_COOLDOWN))
    print()
    print("[DEVICE CONFIG]")
    print("       torch version = " + str(torch.__version__))
    print("       cuda available = " + str(torch.cuda.is_available()))
    print("       device = " + str(DEVICE))
    print("       use_half = " + str(USE_HALF))
    if torch.cuda.is_available():
        print("       gpu = " + str(torch.cuda.get_device_name(0)))
    print()
    print("[DEATH CONFIG]")
    print("       DEATH_WINDOW_SECONDS = " + str(DEATH_WINDOW_SECONDS))
    print("       BLACK_SCREEN_RATIO_THRESHOLD = " + str(BLACK_SCREEN_RATIO_THRESHOLD))
    print("       BLACK_PIXEL_BRIGHTNESS_THRESHOLD = " + str(BLACK_PIXEL_BRIGHTNESS_THRESHOLD))
    print("       RECOVERY_BLACK_RATIO_THRESHOLD = " + str(RECOVERY_BLACK_RATIO_THRESHOLD))
    print("       RECOVERY_FRAMES_REQUIRED = " + str(RECOVERY_FRAMES_REQUIRED))
    print()
    print("[SUPPRESSION CONFIG]")
    print("       ENABLE_SUPPRESSION = " + str(ENABLE_SUPPRESSION))
    print("       mode is controlled by env SQUAD_SUPPRESSION_MODE")
    print("       valid: off / blur / vignette (default off)")
    print("       gated when incap_cycle_active or black_ratio > "
          + "{:.2f}".format(SUPP_GATE_BLACK_RATIO))
    print("       priority = death > incap > bleeding > suppression_heavy > suppression_light")
    print()
    print("[STOP] stop options:")
    print("       1. preview window: press q")
    print("       2. preview window: press Esc")
    print("       3. console: type stop and Enter")
    print("       4. Ctrl+C")
    print("=" * 50)

    if not MODEL_PATH.exists():
        print("[ERROR] model not found: " + str(MODEL_PATH))
        return

    model = YOLO(str(MODEL_PATH))

    if DEVICE != "cpu":
        model.to("cuda:" + str(DEVICE))
        print("[MODEL DEVICE] moved to cuda:" + str(DEVICE))
    else:
        print("[MODEL DEVICE] using CPU")

    print("[MODEL NAMES] " + str(model.names))

    suppression_detector = get_detector(verbose=True)

    # Track whether the detector was gated last frame, so we only call
    # detector.reset() on the transition into a gated state (one print
    # per transition, not every frame).
    supp_gated_prev = False

    listener = threading.Thread(target=input_listener, daemon=True)
    listener.start()

    frame_id = 0

    try:
        with MSS() as sct:
            monitor = sct.monitors[1]
            print("[MONITOR] " + str(monitor))
            print("=" * 50)

            while not stop_event.is_set():
                frame_id += 1

                start_time = time.time()

                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)

                # MSS gives BGRA, convert to BGR for OpenCV / YOLO
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                now = time.time()

                # death uses full-frame black ratio
                black_ratio = get_black_screen_ratio(frame)

                # =========================
                # Suppression gating
                #
                # Skip the suppression detector entirely when:
                #   1. we are inside an incap cycle (incap UI looks like
                #      modded vignette suppression to v2 -> false trigger)
                #   2. screen is mostly black (death blackout, big map UI)
                #
                # On entering a gated state, reset() the detector so its
                # state machine does not resume from active_light /
                # active_heavy after the gate lifts.
                # =========================
                if not ENABLE_SUPPRESSION:
                    supp_result = make_gated_supp_result("disabled")
                    supp_gated_prev = False
                else:
                    gate_incap = incap_cycle_active
                    gate_black = black_ratio > SUPP_GATE_BLACK_RATIO

                    if gate_incap or gate_black:
                        reason = "gated_incap" if gate_incap else "gated_black"

                        if not supp_gated_prev:
                            try:
                                suppression_detector.reset()
                            except Exception:
                                pass
                            print("[SUPP GATE] enter " + reason
                                  + " (incap_cycle_active=" + str(incap_cycle_active)
                                  + ", black=" + "{:.3f}".format(black_ratio) + ")")

                        supp_result = make_gated_supp_result(reason)
                        supp_gated_prev = True
                    else:
                        if supp_gated_prev:
                            print("[SUPP GATE] leave, resume detector")
                        supp_result = suppression_detector.update(frame)
                        supp_gated_prev = False

                # =========================
                # YOLO detection ROI
                # =========================
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
                    verbose=False,
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

                        # YOLO returns ROI-local coords, add back ROI offset
                        xyxy[0] += roi_x1
                        xyxy[2] += roi_x1
                        xyxy[1] += roi_y1
                        xyxy[3] += roi_y1

                        detections.append(
                            {
                                "label": label,
                                "conf": conf,
                                "box": xyxy,
                            }
                        )

                        if label == "incap":
                            has_incap_detection = True

                # =========================
                # Parse YOLO event
                # =========================
                yolo_event = None
                yolo_level = None
                yolo_label = None
                yolo_conf = None
                yolo_box = None

                incap_dets = []
                bleeding_dets = []

                if detections:
                    detections.sort(key=lambda x: x["conf"], reverse=True)

                    incap_dets = [d for d in detections if d["label"] == "incap"]
                    bleeding_dets = [d for d in detections if d["label"] == "bleeding"]

                    if incap_dets:
                        best = incap_dets[0]
                    elif bleeding_dets:
                        best = bleeding_dets[0]
                    else:
                        best = detections[0]

                    yolo_label = best["label"]
                    yolo_conf = best["conf"]
                    yolo_box = best["box"]

                    if yolo_label in ("bleeding", "incap"):
                        yolo_event = yolo_label
                        yolo_level = "conf=" + "{:.3f}".format(yolo_conf)

                    if yolo_label == "incap":
                        if not incap_cycle_active:
                            incap_cycle_active = True
                            death_fired_this_cycle = False
                            recovery_frame_count = 0
                            print("[INCAP STATE] new incap cycle, open 250s death window")

                        last_incap_time = now

                # =========================
                # Console log
                # =========================
                supp_debug = supp_result.get("debug_text", "")

                if not detections:
                    print(
                        "[FRAME " + str(frame_id) + "] no detections | "
                        + "black=" + "{:.3f}".format(black_ratio) + " | "
                        + "supp=(" + supp_debug + ") | "
                        + "infer=" + "{:.3f}".format(infer_time) + "s"
                    )
                else:
                    box_str = str([round(v, 1) for v in yolo_box])
                    print(
                        "[FRAME " + str(frame_id) + "] "
                        + "class=" + str(yolo_label) + ", conf=" + "{:.3f}".format(yolo_conf) + ", "
                        + "box=" + box_str + ", "
                        + "black=" + "{:.3f}".format(black_ratio) + ", "
                        + "supp=(" + supp_debug + "), "
                        + "infer=" + "{:.3f}".format(infer_time) + "s"
                    )

                # =========================
                # Unified event arbitration
                #
                # Priority (highest first):
                #   death
                #   incap
                #   bleeding
                #   suppression_heavy
                #   suppression_light
                #
                # Rationale:
                #   - bleeding is a direct survival signal, more important
                #     than environmental suppression feedback
                #   - suppression v2 is still EXPERIMENTAL, keeping it
                #     below bleeding limits its damage when it misfires
                # =========================
                final_event = None
                final_level = None
                final_is_death = False

                if should_trigger_death(now, black_ratio):
                    elapsed_after_incap = now - last_incap_time

                    print(
                        "[DEATH CHECK] triggered: "
                        + "incap " + "{:.1f}".format(elapsed_after_incap) + "s ago, "
                        + "black_ratio=" + "{:.3f}".format(black_ratio)
                    )

                    final_event = "death"
                    final_level = "black=" + "{:.3f}".format(black_ratio)
                    final_is_death = True

                elif yolo_event == "incap":
                    final_event = "incap"
                    final_level = yolo_level

                elif yolo_event == "bleeding":
                    final_event = "bleeding"
                    final_level = yolo_level

                elif supp_result.get("event") == "suppression_heavy":
                    final_event = "suppression_heavy"
                    final_level = supp_debug

                elif supp_result.get("event") == "suppression_light":
                    final_event = "suppression_light"
                    final_level = supp_debug

                if final_event:
                    if can_send_locally(final_event):
                        ok = send_trigger(final_event, final_level)

                        if final_is_death:
                            if ok:
                                death_fired_this_cycle = True
                                print("[DEATH STATE] death fired, lock for this cycle")
                            else:
                                print("[DEATH STATE] death send failed, not locking, can retry")
                else:
                    if detections and yolo_label not in ("bleeding", "incap"):
                        print("[ACTION] unknown class, skip: " + str(yolo_label))

                # Recovery check:
                # if the screen returns to normal and no incap is visible,
                # reset the incap/death cycle so the next round can fire.
                update_recovery_state(black_ratio, has_incap_detection)

                if SHOW_PREVIEW:
                    draw_roi(frame, roi_x1, roi_y1, roi_x2, roi_y2)

                    for det in detections:
                        draw_detection(
                            frame,
                            det["label"],
                            det["conf"],
                            det["box"],
                        )

                    draw_suppression_status(frame, supp_result)

                    cv2.imshow("Realtime Detect + Trigger Preview", frame)
                    key = cv2.waitKey(1) & 0xFF

                    if key == ord("q") or key == 27:
                        print("[STOP] window stop")
                        stop_event.set()
                        break

                time.sleep(FRAME_INTERVAL)

    except KeyboardInterrupt:
        print()
        print("[STOP] Ctrl+C")
        stop_event.set()

    finally:
        cv2.destroyAllWindows()
        print("=" * 50)
        print("[DONE] realtime detect + trigger finished")
        print("=" * 50)


if __name__ == "__main__":
    main()
