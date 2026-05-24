# ============================================================
# 文件：adapters/dglab_sender.py
# 作用：真实发送器 —— 把动作通过 DG-LAB SOCKET v2 协议发到设备
#
# 与 mock_sender.py 接口对齐：
#   - send_action(action, payload) -> dict
#   - bind(target_id, client_id) -> dict
#   - unbind() -> dict
#   - get_bind_status() -> dict
#   - get_send_history(limit) -> list
#
# v0.2+ 安全机制：
#   1. 动作开始：设置通道强度 + 发送波形
#   2. 动作结束：clear 波形队列 + strength=0 自动归零
#   3. per-channel token 防止旧 timer 误归零新动作
#   4. pulse 发送失败时立即兜底归零
#
# v0.3 suppression：
#   新增 suppression_light_pulse / suppression_heavy_pulse
# ============================================================

import os
import json
import threading
import time
from datetime import datetime
from collections import deque
from typing import Optional

from adapters.dglab_ws_client import get_client


# ------------------------------------------------------------
# 动作参数表
# strength 范围 0~200。
# 强度和时长从项目根目录的 config.ini 读取,缺失字段自动 fallback。
# 详见 python_trigger/config_loader.py
# ------------------------------------------------------------
from config_loader import get_action_config

_strength_cfg, _duration_cfg = get_action_config()

ACTION_PROFILES = {
    "weak_pulse": {
        "channel": "A",
        "strength": _strength_cfg["weak_pulse"],
        "duration": _duration_cfg["weak_pulse"],
        "description": "流血反馈",
    },
    "strong_pulse": {
        "channel": "A",
        "strength": _strength_cfg["strong_pulse"],
        "duration": _duration_cfg["strong_pulse"],
        "description": "濒死反馈",
    },
    "death_pulse": {
        "channel": "A",
        "strength": _strength_cfg["death_pulse"],
        "duration": _duration_cfg["death_pulse"],
        "description": "死亡反馈",
    },
    "suppression_light_pulse": {
        "channel": "A",
        "strength": _strength_cfg["suppression_light_pulse"],
        "duration": _duration_cfg["suppression_light_pulse"],
        "description": "压制轻反馈",
    },
    "suppression_heavy_pulse": {
        "channel": "A",
        "strength": _strength_cfg["suppression_heavy_pulse"],
        "duration": _duration_cfg["suppression_heavy_pulse"],
        "description": "压制强反馈",
    },
}



# ------------------------------------------------------------
# 波形数据模板
# 强度差异主要通过 ACTION_PROFILES 里的 strength 字段控制。
# suppression 第一版复用 weak / strong 的波形模板。
# ------------------------------------------------------------
PULSE_TEMPLATES = {
    "weak_pulse": [
        "0A0A0A0A00000000",
        "0A0A0A0A14141414",
        "0A0A0A0A28282828",
        "0A0A0A0A3C3C3C3C",
        "0A0A0A0A50505050",
        "0A0A0A0A64646464",
        "0A0A0A0A64646464",
        "0A0A0A0A64646464",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
    ],
    "strong_pulse": [
        "7070707064646464",
        "7070707064646464",
        "7070707064646464",
        "7070707064646464",
        "7070707064646464",
        "7070707064646464",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
        "0A0A0A0A4B4B4B4B",
        "0A0A0A0A53535353",
        "0A0A0A0A5B5B5B5B",
        "0A0A0A0A64646464",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
        "0A0A0A0A00000000",
    ],
    "death_pulse": [
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
        "BEBEBEBE64646464",
    ],
}

# suppression 第一版复用现有模板。
# list(...) 是为了复制一份，后续可以单独调 suppression 波形。
PULSE_TEMPLATES["suppression_light_pulse"] = list(PULSE_TEMPLATES["weak_pulse"])
PULSE_TEMPLATES["suppression_heavy_pulse"] = list(PULSE_TEMPLATES["strong_pulse"])


# ------------------------------------------------------------
# 错误码
# ------------------------------------------------------------
ERR_NOT_BOUND = "not_bound"
ERR_DEVICE_OFFLINE = "device_offline"
ERR_TARGET_OFFLINE = "target_offline"
ERR_QUEUE_FULL = "queue_full"
ERR_TIMEOUT = "timeout"
ERR_WS_DISCONNECTED = "ws_disconnected"
ERR_UNKNOWN_ACTION = "unknown_action"
ERR_SEND_FAILED = "send_failed"


# ------------------------------------------------------------
# 安全停止参数
# ------------------------------------------------------------
STOP_CLEAR_TO_ZERO_DELAY = 0.08


# ------------------------------------------------------------
# 历史记录
# ------------------------------------------------------------
SEND_HISTORY: deque = deque(maxlen=100)
_history_lock = threading.Lock()


# ------------------------------------------------------------
# Per-channel token 状态
# 防止旧 safe stop timer 误归零新动作。
# ------------------------------------------------------------
_channel_tokens = {"A": 0, "B": 0}
_token_lock = threading.Lock()


# ------------------------------------------------------------
# 模块初始化：启动 WS 客户端
# ------------------------------------------------------------
_client = get_client()
_client.start()


# ------------------------------------------------------------
# 绑定状态接口
# ------------------------------------------------------------
def bind(target_id: str, client_id: Optional[str] = None) -> dict:
    """
    手动绑定。

    真实模式下通常不需要手动调用 bind。
    APP 扫描二维码后，官方 WebSocket 后端会自动完成绑定。
    """
    print("[DGLAB BIND] 真实模式下 bind 由 APP 扫码触发，无需手动调用")
    return get_bind_status()


def unbind() -> dict:
    """
    断开当前 WS 连接。
    """
    _client.stop()
    return {
        "success": True,
        "mode": "dglab",
    }


def get_bind_status() -> dict:
    """
    查询当前绑定状态。
    """
    lan_ip = os.getenv("DGLAB_LAN_IP", "192.168.1.100")

    return {
        "is_bound": _client.is_paired(),
        "target_id": _client.target_id,
        "client_id": _client.client_id,
        "qrcode_url": _client.get_qrcode_url(lan_ip),
        "mode": "dglab",
    }


def get_send_history(limit: int = 20) -> list:
    """
    获取最近发送历史。
    """
    with _history_lock:
        records = list(SEND_HISTORY)

    records.reverse()
    return records[:limit]


def clear_send_history():
    """
    清空发送历史。
    """
    with _history_lock:
        SEND_HISTORY.clear()


# ------------------------------------------------------------
# 内部辅助
# ------------------------------------------------------------
def _make_result(
    success: bool,
    action: str,
    payload: Optional[dict],
    profile: Optional[dict] = None,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
) -> dict:
    return {
        "success": success,
        "action": action,
        "mode": "dglab",
        "error": error,
        "error_code": error_code,
        "payload": payload or {},
        "profile": profile,
    }


def _record_history(action: str, payload: Optional[dict], result: dict):
    with _history_lock:
        SEND_HISTORY.append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "action": action,
                "payload": payload or {},
                "success": result["success"],
                "error_code": result.get("error_code"),
            }
        )


def _channel_letter_to_num(ch: str) -> int:
    return 1 if ch.upper() == "A" else 2


# ------------------------------------------------------------
# 底层发送函数
# ------------------------------------------------------------
def _send_strength(channel_num: int, strength: int) -> bool:
    """
    发送 type:3 设置通道强度。

    strength 范围 0~200。
    """
    msg = {
        "type": 3,
        "channel": channel_num,
        "strength": strength,
        "message": "set channel",
    }
    return _client.send_json(msg)


def _clear_channel(channel_num: int) -> bool:
    """
    发送 type:4 清空对应通道的波形队列。

    clear 只清波形队列，不归零强度。
    强度归零必须靠 _send_strength(channel_num, 0)。
    """
    msg = {
        "type": 4,
        "message": f"clear-{channel_num}",
    }
    return _client.send_json(msg)


def _stop_channel(channel_num: int) -> bool:
    """
    安全停止：清波形队列 + 等一下 + 强度归零。
    """
    if not _client.is_paired():
        print(
            f"[DGLAB STOP] channel={channel_num} 未配对，跳过归零"
            "（设备会通过心跳超时自动停止）"
        )
        return False

    ok_clear = _clear_channel(channel_num)
    if not ok_clear:
        print(f"[DGLAB STOP] channel={channel_num} clear 队列失败")

    time.sleep(STOP_CLEAR_TO_ZERO_DELAY)

    ok_zero = _send_strength(channel_num, 0)
    if not ok_zero:
        print(f"[DGLAB STOP] channel={channel_num} strength=0 失败")

    return ok_clear and ok_zero


# ------------------------------------------------------------
# Safe stop timer
# ------------------------------------------------------------
def _safe_stop_callback(channel_letter: str, channel_num: int, my_token: int):
    """
    Timer 到期回调：检查 token 是否仍是最新，决定要不要归零。
    """
    with _token_lock:
        current_token = _channel_tokens[channel_letter]

    if current_token != my_token:
        print(
            f"[SAFE STOP {channel_letter}] token 已过期 "
            f"(my={my_token}, current={current_token})，跳过归零"
        )
        return

    print(f"[SAFE STOP {channel_letter}] token={my_token} 仍最新，开始归零")
    _stop_channel(channel_num)


def _schedule_safe_stop(
    channel_letter: str,
    channel_num: int,
    duration: float,
    my_token: int,
):
    """
    启动一个 Timer，duration 秒后调用 _safe_stop_callback。
    """
    timer = threading.Timer(
        duration,
        _safe_stop_callback,
        args=(channel_letter, channel_num, my_token),
    )
    timer.daemon = True
    timer.start()


# ------------------------------------------------------------
# 主函数：发送动作
# ------------------------------------------------------------
def send_action(action: str, payload: Optional[dict] = None) -> dict:
    """
    把动作通过 DG-LAB SOCKET v2 发到设备。

    返回字段：
        success
        action
        mode
        error
        error_code
        payload
        profile
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---- 1. 动作合法性检查 ----
    profile = ACTION_PROFILES.get(action)

    if profile is None:
        print(f"[{now_str}] [DGLAB SEND] action={action} → 未知动作")
        result = _make_result(
            success=False,
            action=action,
            payload=payload,
            error=f"unknown action: {action}",
            error_code=ERR_UNKNOWN_ACTION,
        )
        _record_history(action, payload, result)
        return result

    # ---- 2. 配对状态检查 ----
    if not _client.is_paired():
        print(f"[{now_str}] [DGLAB SEND] action={action} → 未配对设备")
        result = _make_result(
            success=False,
            action=action,
            payload=payload,
            profile=profile,
            error="device not bound (APP 未扫码绑定)",
            error_code=ERR_NOT_BOUND,
        )
        _record_history(action, payload, result)
        return result

    # ---- 3. 检查波形模板 ----
    pulse_data = PULSE_TEMPLATES.get(action)

    if pulse_data is None:
        result = _make_result(
            success=False,
            action=action,
            payload=payload,
            profile=profile,
            error=f"no pulse template for {action}",
            error_code=ERR_UNKNOWN_ACTION,
        )
        _record_history(action, payload, result)
        return result

    channel_num = _channel_letter_to_num(profile["channel"])
    channel_letter = profile["channel"].upper()

    # ---- 4. 设置强度 ----
    if not _send_strength(channel_num, profile["strength"]):
        result = _make_result(
            success=False,
            action=action,
            payload=payload,
            profile=profile,
            error="send strength failed",
            error_code=ERR_SEND_FAILED,
        )
        _record_history(action, payload, result)
        return result

    # ---- 5. 发送波形 ----
    pulse_msg = {
        "type": "clientMsg",
        "channel": channel_letter,
        "time": profile["duration"],
        "message": f"{channel_letter}:{json.dumps(pulse_data)}",
    }

    if not _client.send_json(pulse_msg):
        print(f"[{now_str}] [DGLAB SEND] action={action} → pulse 失败，立即归零兜底")
        _stop_channel(channel_num)

        result = _make_result(
            success=False,
            action=action,
            payload=payload,
            profile=profile,
            error="send pulse failed (strength 已自动归零)",
            error_code=ERR_SEND_FAILED,
        )
        _record_history(action, payload, result)
        return result

    # ---- 6. 成功：自增 token，启动 safe stop timer ----
    with _token_lock:
        _channel_tokens[channel_letter] += 1
        my_token = _channel_tokens[channel_letter]

    _schedule_safe_stop(
        channel_letter=channel_letter,
        channel_num=channel_num,
        duration=profile["duration"],
        my_token=my_token,
    )

    print(
        f"[{now_str}] [DGLAB SEND] action={action}, "
        f"channel={channel_letter}, "
        f"strength={profile['strength']}, "
        f"duration={profile['duration']}s, "
        f"token={my_token}, "
        f"payload={payload}"
    )

    result = _make_result(
        success=True,
        action=action,
        payload=payload,
        profile=profile,
        error=None,
        error_code=None,
    )
    _record_history(action, payload, result)
    return result
