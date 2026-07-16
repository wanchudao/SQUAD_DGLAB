# ============================================================
# SQUAD DG-LAB DGHUB Plugin — main entry
# ============================================================
# File logging is set up FIRST so even import errors are captured.
# Log file: plugin.log in the same directory as this script.
#
# Startup order (deliberate):
#   1. Light imports + file logger
#   2. Connect DGHUB WebSocket + handshake  (< 2s, beats the 10s timeout)
#   3. Receive hello_ack + config
#   4. Heavy import: vision.*  (torch CUDA init takes 5-8s)
#   5. Monkey-patch + apply config + start vision thread
#   6. Main message loop
# ============================================================

import sys
import traceback
from datetime import datetime
from pathlib import Path

# ——— resolve paths ———
_ENTRY_FILE = Path(__file__).resolve()
_PLUGIN_DIR = _ENTRY_FILE.parent
_LOG_PATH = _PLUGIN_DIR / "plugin.log"


# ——— file logger ———
def _log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = timestamp + "  " + msg
    print(line, flush=True)
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
    except Exception:
        pass


# ——— startup banner ———
_log("=" * 60)
_log("SQUAD DG-LAB plugin starting")
_log("python  = " + sys.version.split()[0])
_log("exe     = " + sys.executable)
_log("cwd     = " + str(Path.cwd()))
_log("file    = " + str(_ENTRY_FILE))
_log("log     = " + str(_LOG_PATH))


# ============================================================
# Phase 1 — Light imports only (no torch / ultralytics / cv2)
# ============================================================

_log("--- phase 1: light imports ---")

try:
    import asyncio
    _log("import asyncio OK")
except Exception as _e:
    _log("import asyncio FAILED: " + str(_e)); raise

try:
    import json
    _log("import json OK")
except Exception as _e:
    _log("import json FAILED: " + str(_e)); raise

try:
    import os
    _log("import os OK")
except Exception as _e:
    _log("import os FAILED: " + str(_e)); raise

try:
    import threading
    _log("import threading OK")
except Exception as _e:
    _log("import threading FAILED: " + str(_e)); raise

# env vars (after os is available)
for _k in ("DGHUB_HOST", "DGHUB_PORT", "DGHUB_TOKEN", "DGHUB_PLUGIN_ID",
           "SQUAD_SUPPRESSION_MODE"):
    _v = os.environ.get(_k, "")
    _d = _v if _k != "DGHUB_TOKEN" else ("***" if _v else "MISSING")
    _log("env " + _k + "=" + _d)

try:
    import websockets
    _log("import websockets OK")
except Exception as _e:
    _log("import websockets FAILED: " + str(_e)); raise

_log("phase 1 done — all light imports OK")


# ============================================================
# Runtime state
# ============================================================
_ws = None          # DGHUB WebSocket (set after connect)
_main_loop = None   # asyncio event loop reference
_vision_thread = None
_vision_mod = None  # set after heavy import in phase 4

# Runtime config — DGHUB config_schema defaults, overwritten by config push
runtime_config = {
    "channel": "both",
    "preset": "",
    "bleeding_delta_pct": 15,   "incap_delta_pct": 30,
    "death_delta_pct": 50,
    "suppression_light_delta_pct": 10,
    "suppression_heavy_delta_pct": 20,
    "bleeding_duration_s": 2.0,  "incap_duration_s": 4.0,
    "death_duration_s": 5.0,
    "suppression_light_duration_s": 1.5,
    "suppression_heavy_duration_s": 2.0,
    "suppression_mode": "off",
    "conf_threshold": 0.6,       "frame_interval": 0.50,
    "show_preview": False,
}


# ============================================================
# DGHUB trigger message builder (does not need vision module)
# ============================================================
def _make_trigger_msg(event_name, level_text):
    cfg = runtime_config
    delta_pct = cfg.get(event_name + "_delta_pct", 15)
    duration_s = cfg.get(event_name + "_duration_s", 2.0)
    channel = cfg.get("channel", "both")
    preset = cfg.get("preset", "")

    msg = {
        "op": "trigger",
        "delta_pct": delta_pct,
        "strength_mode": "rollback",
        "duration_s": duration_s,
        "channel": channel,
        "label": "SQUAD: " + event_name + " (" + level_text + ")",
    }
    if preset:
        msg["action"] = "both"
        msg["preset"] = preset
    else:
        msg["action"] = "strength"

    return msg


# ============================================================
# WebSocket helpers (light, no vision dependency)
# ============================================================
async def _ws_send(msg):
    global _ws
    if _ws is not None:
        try:
            await _ws.send(json.dumps(msg))
        except Exception as e:
            _log("[ws] send failed: " + str(e))


async def _connect_ws(host, port, token):
    """Connect with retries using websockets library."""
    url = "ws://" + host + ":" + port + "/ws/plugin?token=" + token
    for i in range(1, 10):
        try:
            _log("[ws] connecting  attempt=" + str(i) + "/9")
            ws = await websockets.connect(url, max_size=None)
            _log("[ws] connected on attempt " + str(i))
            return ws
        except asyncio.TimeoutError:
            _log("[ws] attempt " + str(i) + " timed out")
        except Exception as e:
            _log("[ws] attempt " + str(i) + " failed: "
                 + type(e).__name__ + " " + str(e))
        if i < 9:
            await asyncio.sleep(1.0)
    return None


# ============================================================
# Phase 2 — Connect + Handshake (light, fast)
# ============================================================

async def _wait_for_messages(ws, stop_after_config):
    """
    Receive messages until config is received (or stop is requested).

    Before vision is imported, we only handle:
      hello_ack, config, stop, ping
    Other ops (device_info, etc.) are logged and ignored.
    """
    while True:
        raw = await ws.recv()
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            _log("[ws] invalid JSON: " + str(raw[:100]))
            continue

        op = msg.get("op", "")
        _log("[ws] <- " + op)

        if op == "hello_ack":
            if msg.get("accepted"):
                _log("[ws] handshake ACCEPTED  sdk="
                     + str(msg.get("sdk_version", "?")))
                await _ws_send({
                    "op": "status",
                    "fields": {"display_status": "初始化中..."},
                })
            else:
                _log("[ws] handshake REJECTED: "
                     + str(msg.get("reason", "?")))
                return False  # signal to exit

        elif op == "config":
            data = msg.get("data", {})
            for k, v in data.items():
                if k in runtime_config:
                    runtime_config[k] = v
            _log("[ws] config received  fields=" + str(len(data)))
            if stop_after_config:
                return True  # signal to continue to phase 4

        elif op == "stop":
            _log("[ws] stop requested  reason="
                 + str(msg.get("reason", "?")))
            return False

        elif op == "ping":
            await _ws_send({"op": "pong", "t": msg.get("t", 0)})

        elif op == "device_info":
            _log("[ws] device_info  connected="
                 + str(msg.get("connected"))
                 + "  type=" + str(msg.get("device_type", "")))

        else:
            _log("[ws] unhandled (phase2): " + op)


# ============================================================
# Phase 4 — Heavy vision import (after WS is connected!)
# ============================================================
# This is the key fix: torch + CUDA init takes 5-8s, and
# ultralytics takes 1-3s. We do this AFTER the WebSocket is
# connected so DGHUB doesn't time out (10s limit).

def _setup_vision():
    """Import vision module, monkey-patch, apply config, return module."""
    global _vision_mod

    _log("--- phase 4: heavy imports (torch / ultralytics / cv2) ---")

    # The suppression import inside vision/ needs vision/ on sys.path
    sys.path.insert(0, str(_PLUGIN_DIR / "vision"))
    _log("sys.path[0] = " + str(sys.path[0]))

    try:
        import vision.realtime_detect_and_trigger as vmod
        _log("import vision.realtime_detect_and_trigger OK")
    except Exception as e:
        _log("import vision FAILED: " + str(e))
        _log(traceback.format_exc())
        raise

    # --- monkey-patch ---
    def _dghub_send_trigger(event_name, level_text):
        msg = _make_trigger_msg(event_name, level_text)
        if vmod.DRY_RUN:
            _log("[DRY_RUN] skip: " + str(msg))
            return True
        if _main_loop is not None and _main_loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    _ws_send(msg), _main_loop)
            except RuntimeError as e:
                _log("[plugin] schedule failed: " + str(e))
        else:
            _log("[plugin] loop unavailable, dropped: " + event_name)
        return True

    vmod.send_trigger = _dghub_send_trigger
    vmod.DRY_RUN = False

    # --- apply stored config to vision globals ---
    vmod.CONF_THRESHOLD = runtime_config["conf_threshold"]
    vmod.FRAME_INTERVAL = runtime_config["frame_interval"]
    vmod.SHOW_PREVIEW = runtime_config["show_preview"]
    os.environ["SQUAD_SUPPRESSION_MODE"] = runtime_config["suppression_mode"]

    _vision_mod = vmod
    _log("phase 4 done — vision module ready")
    return vmod


# ============================================================
# Vision thread management (needs _vision_mod to be set)
# ============================================================

def _reset_vision_globals():
    v = _vision_mod
    v.last_incap_time = None
    v.incap_cycle_active = False
    v.death_fired_this_cycle = False
    v.recovery_frame_count = 0
    v.last_send_time.clear()


def _start_vision():
    global _vision_thread
    v = _vision_mod

    _log("[vision] starting detection thread ...")
    if not v.MODEL_PATH.exists():
        _log("[vision] ERROR: model not found at " + str(v.MODEL_PATH))
        return False

    v.stop_event.clear()
    _reset_vision_globals()

    _vision_thread = threading.Thread(
        target=v.main, daemon=True, name="VisionLoop")
    _vision_thread.start()
    _log("[vision] thread started (alive="
         + str(_vision_thread.is_alive()) + ")")
    return True


def _stop_vision():
    _log("[vision] stopping thread ...")
    if _vision_mod is not None:
        _vision_mod.stop_event.set()
    if _vision_thread is not None and _vision_thread.is_alive():
        _vision_thread.join(timeout=5.0)
    _log("[vision] thread stopped")


async def _vision_watchdog():
    while _vision_thread is not None and _vision_thread.is_alive():
        await asyncio.sleep(1.0)
    if (_vision_mod is not None
            and not _vision_mod.stop_event.is_set()):
        _log("[vision] WARNING: thread exited unexpectedly, shutting down")
        _vision_mod.stop_event.set()
    if _ws is not None:
        try:
            await _ws.close()
        except Exception:
            pass


# ============================================================
# Phase 6 — Normal message loop (vision is already running)
# ============================================================

async def _handle_message(raw):
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        _log("[ws] invalid JSON: " + str(raw[:100]))
        return

    op = msg.get("op", "")
    _log("[ws] <- " + op)

    if op == "config":
        data = msg.get("data", {})
        for k, v in data.items():
            if k in runtime_config:
                runtime_config[k] = v
        if _vision_mod is not None:
            _vision_mod.CONF_THRESHOLD = runtime_config["conf_threshold"]
            _vision_mod.FRAME_INTERVAL = runtime_config["frame_interval"]
            _vision_mod.SHOW_PREVIEW = runtime_config["show_preview"]
        _log("[ws] config loaded  fields=" + str(len(data)))

    elif op == "config_changed":
        k = msg.get("key")
        v = msg.get("value")
        if k in runtime_config:
            old = runtime_config[k]
            runtime_config[k] = v
            if _vision_mod is not None:
                _vision_mod.CONF_THRESHOLD = runtime_config["conf_threshold"]
                _vision_mod.FRAME_INTERVAL = runtime_config["frame_interval"]
                _vision_mod.SHOW_PREVIEW = runtime_config["show_preview"]
                os.environ["SQUAD_SUPPRESSION_MODE"] = \
                    runtime_config["suppression_mode"]
            _log("[ws] config_changed  " + k + "=" + str(v))
            if k == "suppression_mode" and v != old:
                _log("[ws] restarting vision for suppression_mode change ...")
                _stop_vision()
                _start_vision()

    elif op == "device_info":
        _log("[ws] device_info  connected=" + str(msg.get("connected"))
             + "  type=" + str(msg.get("device_type", "")))

    elif op == "stop":
        _log("[ws] stop requested  reason="
             + str(msg.get("reason", "?")))
        if _vision_mod is not None:
            _vision_mod.stop_event.set()

    elif op == "ping":
        await _ws_send({"op": "pong", "t": msg.get("t", 0)})

    elif op == "hello_ack":
        pass  # shouldn't happen in phase 6, ignore

    else:
        _log("[ws] unhandled op: " + op)


# ============================================================
# Main
# ============================================================

async def main():
    global _ws, _main_loop

    _main_loop = asyncio.get_running_loop()
    _log("--- main loop started ---")

    host = os.environ.get("DGHUB_HOST", "127.0.0.1")
    port = os.environ.get("DGHUB_PORT", "")
    token = os.environ.get("DGHUB_TOKEN", "")

    if not port or not token:
        _log("FATAL: DGHUB_PORT or DGHUB_TOKEN not set")
        return

    # Load manifest
    manifest_path = _PLUGIN_DIR / "manifest.json"
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        _log("[init] manifest loaded  id=" + manifest["id"]
             + "  version=" + manifest["version"])
    except Exception as e:
        _log("[init] manifest load FAILED: " + str(e))
        return

    # ============================================================
    # Phase 2: Connect to DGHUB WebSocket  (fast, ~1-2s)
    # ============================================================
    _log("--- phase 2: connect WebSocket ---")
    ws = await _connect_ws(host, port, token)
    if ws is None:
        _log("FATAL: could not connect to DGHUB")
        return
    _ws = ws

    try:
        # ============================================================
        # Phase 3: Handshake + receive hello_ack + config  (fast)
        # ============================================================
        _log("--- phase 3: handshake ---")

        hello = {
            "op": "hello",
            "token": token,
            "manifest": {
                "id": manifest["id"],
                "name": manifest["name"],
                "version": manifest["version"],
                "sdk": manifest["sdk"],
            },
        }
        for f in ("author", "description", "homepage",
                  "entry", "config_schema"):
            if f in manifest:
                hello["manifest"][f] = manifest[f]

        _log("[ws] -> hello  id=" + manifest["id"]
             + "  sdk=" + manifest["sdk"])
        await ws.send(json.dumps(hello))

        # Wait for hello_ack + config
        ok = await _wait_for_messages(ws, stop_after_config=True)
        if not ok:
            _log("[ws] phase 3 failed — rejected or stopped")
            return

        # ============================================================
        # Phase 4: Heavy vision import  (slow, 5-12s)
        # ============================================================
        # DGHUB already sees us as connected, so no timeout.
        _setup_vision()

        # ============================================================
        # Phase 5: Start vision thread
        # ============================================================
        _log("--- phase 5: start vision ---")
        if not _start_vision():
            _log("[init] WARNING: vision failed to start (model missing?)")
            await _ws_send({
                "op": "log",
                "level": "warning",
                "message": "模型文件未找到，YOLO 检测未启动",
            })
        watchdog = asyncio.create_task(_vision_watchdog())

        # Notify DGHUB we're ready
        await _ws_send({
            "op": "status",
            "fields": {"display_status": "YOLO 检测就绪"},
        })
        await _ws_send({
            "op": "log",
            "level": "info",
            "message": "SQUAD DG-LAB 插件已就绪",
        })
        _log("[init] plugin ready")

        # ============================================================
        # Phase 6: Normal message loop
        # ============================================================
        _log("--- phase 6: message loop ---")
        async for raw in ws:
            await _handle_message(raw)
            if (_vision_mod is not None
                    and _vision_mod.stop_event.is_set()):
                _log("[ws] stop_event set, exiting")
                break

    except websockets.exceptions.ConnectionClosed as e:
        _log("[ws] connection closed  code=" + str(e.code))
    except Exception as e:
        _log("[ws] error: " + type(e).__name__ + " " + str(e))
        _log(traceback.format_exc())
    finally:
        _ws = None
        try:
            watchdog.cancel()
        except NameError:
            pass  # watchdog may not have been created
        _stop_vision()
        _log("--- plugin exited ---")
        _log("log file: " + str(_LOG_PATH))


if __name__ == "__main__":
    _log("--- entering asyncio.run(main()) ---")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log("stopped by KeyboardInterrupt")
    except Exception as _e:
        _log("FATAL: " + type(_e).__name__ + " " + str(_e))
        _log(traceback.format_exc())
    _log("--- process end ---")
