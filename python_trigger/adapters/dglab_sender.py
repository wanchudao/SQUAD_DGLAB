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
#
# ============================================================
# v0.2 改造说明（自动归零）
# ============================================================
# 旧版本只做了"开门动作"：
#   1. 设置通道强度（type:3）
#   2. 发送波形（clientMsg）
#   就返回 success=True，duration 到期后什么都不做。
#
# 这意味着真实设备会一直停留在 strength=10/20/40，
# 必须依赖用户在 APP 里手动调或下一次新动作覆盖才能归零。
# 这不安全。
#
# 这一版加了"关门动作"：
#   1. clientMsg 发送成功后，启动一个 threading.Timer
#   2. duration 秒后，timer 触发 _stop_channel：
#      - 先 clear 队列（type:4, clear-N）
#      - 等 80ms（按官方文档建议）
#      - 再把强度归零（type:3, strength:0）
#
# 但事件可能重叠（bleeding 的 1 秒 cooldown < 2 秒 duration），
# 直接用 Timer 会出现"旧 timer 把新动作误归零"的问题。
# 所以引入 per-channel token 机制：
#   - 每次 send_action 成功发出 clientMsg 时，对应通道的 token++
#   - Timer 创建时记下当时的 token（my_token）
#   - Timer 到期时检查通道当前 token 是否还等于 my_token
#     等于 → 自己仍是最新动作，安全归零
#     不等 → 后面已有新动作，跳过归零，避免误伤
#
# 还增加了 pulse 发送失败的兜底：
#   如果 strength 已设但 pulse 没发出去，立刻调用 _stop_channel
#   把强度归零，避免"开了门没合上"的悬挂状态。
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
# 安全停止参数
# ------------------------------------------------------------
# clear 和 strength=0 两条消息之间等待的时间。
# 官方文档原文："建议清空指令下发后稍等片刻再发送新波形数据，
#               避免网络延迟导致数据丢失"
# 80ms 在人感知阈值（约 100ms）以下，肉眼基本看不出延迟，
# 同时也足够让两条消息按顺序到达 APP。
STOP_CLEAR_TO_ZERO_DELAY = 0.08  # 单位：秒


# ------------------------------------------------------------
# 历史记录（与 mock_sender 对齐）
# ------------------------------------------------------------
SEND_HISTORY: deque = deque(maxlen=100)
_history_lock = threading.Lock()


# ------------------------------------------------------------
# Per-channel token 状态
#
# 用途：防止旧 timer 把新动作误归零。
#
# 工作原理：
#   每次 send_action 成功发出 clientMsg 时，对应通道的 token++。
#   每个 Timer 创建时记下当时的 token（my_token）。
#   Timer 到期回调里检查通道当前 token 是否还等于 my_token：
#     等于 → 自己仍是最新动作，可以安全归零
#     不等 → 已经有新动作覆盖，跳过归零
#
# 为什么是 per-channel 而不是 per-action：
#   bleeding 和 incap 都用 A 通道。如果 bleeding 触发后 1 秒，
#   incap 又来了，那么 incap 重新设置 A 通道 strength。这时
#   bleeding 那个 timer（duration=2s）必须能识别"我已经过期了"
#   而不是去归零 A 通道——否则会打断 incap 的 strong_pulse。
# ------------------------------------------------------------
_channel_tokens = {"A": 0, "B": 0}
_token_lock = threading.Lock()


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
# 底层发送函数（v0.2 新增）
# ------------------------------------------------------------
def _send_strength(channel_num: int, strength: int) -> bool:
    """
    发送 type:3 设置通道强度。

    既用于设置非零强度（开门），也用于归零（关门）。
    strength 范围按官方文档 0~200。

    返回 send_json 的返回值（True = 已发出，False = 未发出）。
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

    注意：clear 只清波形队列，不归零强度。
    强度归零必须靠 _send_strength(channel_num, 0)。

    官方协议示例：
        type:4 不带 channel 字段，通道写在 message 里（"clear-1" / "clear-2"）。
    """
    msg = {
        "type": 4,
        "message": f"clear-{channel_num}",
    }
    return _client.send_json(msg)


def _stop_channel(channel_num: int) -> bool:
    """
    安全停止：清波形队列 + 等一下 + 强度归零。

    顺序很重要：
      1. 先 clear，让 APP 知道"不要再播之前队列里的波形了"
      2. 等 80ms（避免两条消息乱序到达）
      3. 再 strength=0，把通道彻底关掉

    边界处理：
      如果中途发现已经 not_paired（WS 断开等），不报错只打日志，
      因为这时 APP 收不到任何消息，设备会通过心跳超时自动停止。

    返回：
      True  -> 两步都成功
      False -> 任一步失败
    """
    if not _client.is_paired():
        print(f"[DGLAB STOP] channel={channel_num} 未配对，跳过归零（设备会通过心跳超时自动停止）")
        return False

    ok_clear = _clear_channel(channel_num)
    if not ok_clear:
        print(f"[DGLAB STOP] channel={channel_num} clear 队列失败")

    # 不管 clear 成不成功，都试一下 strength=0
    # 因为 strength=0 是最关键的归零动作，能发就发
    time.sleep(STOP_CLEAR_TO_ZERO_DELAY)

    ok_zero = _send_strength(channel_num, 0)
    if not ok_zero:
        print(f"[DGLAB STOP] channel={channel_num} strength=0 失败")

    return ok_clear and ok_zero


# ------------------------------------------------------------
# Safe stop timer（v0.2 新增）
# ------------------------------------------------------------
def _safe_stop_callback(channel_letter: str, channel_num: int, my_token: int):
    """
    Timer 到期回调：检查 token 是否仍是最新，决定要不要归零。

    场景说明：
      bleeding 的本地 cooldown 是 1 秒，但 weak_pulse 的 duration 是 2 秒。
      所以可能出现：
        T=0.0s  bleeding 触发，A 通道 strength=10，启动 timer1（2 秒后归零），token=1
        T=1.0s  bleeding 又触发（cooldown 过了），A 通道 strength=10，启动 timer2，token=2
        T=2.0s  timer1 到期 → 检查 token，发现当前 A token=2 ≠ my_token=1
                → 跳过归零，避免打断 timer2 那一轮
        T=3.0s  timer2 到期 → token 仍是 2，等于 my_token → 安全归零

    所以 token 自增是 per-channel，timer 只对"自己那一轮"负责。
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


def _schedule_safe_stop(channel_letter: str, channel_num: int, duration: float, my_token: int):
    """
    启动一个 Timer，duration 秒后调用 _safe_stop_callback。

    使用 daemon=True：
      程序退出时这些 timer 会被 Python 自动清理，
      不会阻塞 uvicorn / app.py 的优雅关闭流程。
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

    返回字段（与 mock_sender 对齐）：
        success / action / mode / error / error_code / payload / profile

    success=True 的语义：
        两条 WebSocket 消息（type:3 设强度 + clientMsg 发波形）都已成功发出。
        ⚠️ 不代表设备一定执行 —— 可能 APP 端处理失败、可能网络中途丢包，
            这层语义在 v0.2 仍然不变。

    v0.2 新增行为：
        clientMsg 成功发出后，会启动一个 threading.Timer，
        duration 秒后自动归零（clear 队列 + strength=0）。
        归零受 per-channel token 保护，不会误伤后续新动作。
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

    # ---- 2. 配对状态检查（必须在任何发送之前）----
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

    # ---- 5. 第二步：发送波形（type: clientMsg）----
    pulse_msg = {
        "type": "clientMsg",
        "channel": channel_letter,
        "time": profile["duration"],
        "message": f"{channel_letter}:{json.dumps(pulse_data)}",
    }

    if not _client.send_json(pulse_msg):
        # 关键：strength 已经设上去了但 pulse 没发出去。
        # 必须立刻把强度归零，避免"开了门没合上"的悬挂状态。
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
    # 必须在 pulse 成功之后才自增 token，因为只有"真正持续作用中"
    # 的动作才需要被归零保护。失败的动作没 token，自然也不会有 timer。
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
        f"channel={channel_letter}, strength={profile['strength']}, "
        f"duration={profile['duration']}s, "
        f"token={my_token}, payload={payload}"
    )

    result = _make_result(
        success=True,
        action=action,
        payload=payload,
        profile=profile,
    )
    _record_history(action, payload, result)
    return result
