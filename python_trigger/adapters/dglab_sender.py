# ============================================================
# 文件：adapters/dglab_sender.py
# 作用：真实发送器 —— 把动作通过 DG-LAB SOCKET v2 协议发到设备
#
# 与 mock_sender.py 接口完全对齐：
#   - send_action(action, payload) -> dict
#   - bind(target_id, client_id) -> dict
#   - unbind() -> dict
#   - get_bind_status() -> dict
#   - get_send_history(limit) -> list
#
# 切换方式（推荐用环境变量）：
#   CMD:
#     set DGLAB_REAL=1
#     set DGLAB_LAN_IP=你的局域网IP
#     uvicorn app:app --host 0.0.0.0 --port 18000
#
#   PowerShell:
#     $env:DGLAB_REAL="1"
#     $env:DGLAB_LAN_IP="你的局域网IP"
#     uvicorn app:app --host 0.0.0.0 --port 18000
# ============================================================

import os
import json
import threading
from datetime import datetime
from collections import deque
from typing import Optional

from adapters.dglab_ws_client import get_client


# ------------------------------------------------------------
# 动作参数表（与 mock_sender 严格对齐）
# strength 范围 0~200，初始值保守，体验后再调
# ------------------------------------------------------------
ACTION_PROFILES = {
    "weak_pulse": {
        "channel": "A",
        "strength": 10,
        "duration": 2,
        "description": "流血反馈",
    },
    "strong_pulse": {
        "channel": "A",
        "strength": 20,
        "duration": 4,
        "description": "濒死反馈",
    },
    "death_pulse": {
        "channel": "A",
        "strength": 40,
        "duration": 5,
        "description": "死亡反馈",
    },
}


# ------------------------------------------------------------
# 波形数据模板（来自官方 DG_WAVES_V2_V3_simple.js 的 expectedV3）
# 强度差异通过 type:3 的 strength 字段调，波形本身不变
#
# weak_pulse   -> 呼吸波形，从 0 渐进到 64 再保持，柔和
# strong_pulse -> 心跳节奏波形，双脉冲，有心跳感
# death_pulse  -> 信号灯波形，前段持续高强度，冲击感强
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


# ------------------------------------------------------------
# 错误码（与 mock_sender 对齐）
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
# 历史记录（与 mock_sender 对齐）
# ------------------------------------------------------------
SEND_HISTORY: deque = deque(maxlen=100)
_history_lock = threading.Lock()


# ------------------------------------------------------------
# 模块初始化：启动 WS 客户端
# ------------------------------------------------------------
_client = get_client()
_client.start()


# ------------------------------------------------------------
# 绑定状态接口（保持与 mock 一致的签名）
# ------------------------------------------------------------
def bind(target_id: str, client_id: Optional[str] = None) -> dict:
    """
    手动绑定。

    真实模式下通常不需要手动调用 bind：
    APP 扫描二维码后，官方 WebSocket 后端会自动完成绑定。
    这个函数保留只是为了和 mock_sender 接口对齐。
    """
    print("[DGLAB BIND] 真实模式下 bind 由 APP 扫码触发，无需手动调用")
    return get_bind_status()


def unbind() -> dict:
    """断开当前 WS 连接"""
    _client.stop()
    return {
        "success": True,
        "mode": "dglab",
    }


def get_bind_status() -> dict:
    """
    查询当前绑定状态。

    qrcode_url 使用 DGLAB_LAN_IP 环境变量生成。
    如果用户没有设置 DGLAB_LAN_IP，则使用示例地址 192.168.1.100。
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
    with _history_lock:
        records = list(SEND_HISTORY)

    records.reverse()
    return records[:limit]


def clear_send_history():
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
# 主函数：发送动作
# ------------------------------------------------------------
def send_action(action: str, payload: Optional[dict] = None) -> dict:
    """
    把动作通过 DG-LAB SOCKET v2 发到设备。

    返回字段（与 mock_sender 对齐）：
        success / action / mode / error / error_code / payload / profile
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

    # ---- 4. 第一步：设置强度（type: 3）----
    strength_msg = {
        "type": 3,
        "channel": channel_num,
        "strength": profile["strength"],
        "message": "set channel",
    }

    if not _client.send_json(strength_msg):
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

    # ---- 5. 第二步：发送波形（type: clientMsg）----
    pulse_msg = {
        "type": "clientMsg",
        "channel": channel_letter,
        "time": profile["duration"],
        "message": f"{channel_letter}:{json.dumps(pulse_data)}",
    }

    if not _client.send_json(pulse_msg):
        result = _make_result(
            success=False,
            action=action,
            payload=payload,
            profile=profile,
            error="send pulse failed",
            error_code=ERR_SEND_FAILED,
        )
        _record_history(action, payload, result)
        return result

    # ---- 6. 成功 ----
    print(
        f"[{now_str}] [DGLAB SEND] action={action}, "
        f"channel={channel_letter}, strength={profile['strength']}, "
        f"duration={profile['duration']}s, payload={payload}"
    )

    result = _make_result(
        success=True,
        action=action,
        payload=payload,
        profile=profile,
    )
    _record_history(action, payload, result)
    return result


