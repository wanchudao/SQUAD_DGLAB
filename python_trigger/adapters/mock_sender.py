# ============================================================
# 文件：adapters/mock_sender.py
# 作用：高保真假发送器，用于设备到货前的完整链路验证
#
# ⚠️ 重要：所有 success=True 仅代表 API 链路通，不代表设备真的响应了
#         真实设备链路必须切换到 adapters/dglab_sender.py
#
# 设计原则：
#   1. 函数签名、返回字段与 dglab_sender 严格对齐
#      → 切换时只需改 app.py 里一行 import，其他代码零改动
#   2. 默认行为与旧版兼容（永远成功），打开开关后才模拟故障
#      → 日常 mock 测试不受影响，专项测试时打开开关
#   3. 模拟绑定状态机，提前暴露"未绑定就发送"这类真实场景 bug
#   4. 内存保留最近 100 次发送历史，方便调试 BUG 列表里的误触发
# ============================================================

import random
import time
import threading
from datetime import datetime
from collections import deque
from typing import Optional


# ------------------------------------------------------------
# 动作参数表
# 必须与 dglab_sender.py 的 ACTION_PROFILES 保持一致
# 这样 mock 阶段就能验证"动作名是否合法"，不会到设备阶段才发现笔误
# ------------------------------------------------------------
ACTION_PROFILES = {
    "weak_pulse":   {"channel": "A", "strength": 30, "duration": 2, "description": "流血反馈"},
    "strong_pulse": {"channel": "A", "strength": 60, "duration": 4, "description": "濒死反馈"},
    "death_pulse":  {"channel": "A", "strength": 80, "duration": 5, "description": "死亡反馈"},
}


# ------------------------------------------------------------
# 故障注入开关（默认全关，对外行为与旧版一致）
#
# 使用场景：
#   - 跑专项测试时：打开 SIMULATE_FAILURES 验证 trigger 层失败分支
#   - 验证 death 锁：打开 SIMULATE_DEVICE_OFFLINE 看 vision 层会不会误锁
#   - 验证主循环节奏：打开 SIMULATE_LATENCY_MS 看 vision FPS 会不会被拖垮
# ------------------------------------------------------------
SIMULATE_FAILURES = False         # 是否随机失败
FAILURE_RATE = 0.10               # 随机失败概率（0.0 ~ 1.0）

SIMULATE_DEVICE_OFFLINE = False   # 强制模拟设备离线
SIMULATE_NOT_BOUND = False        # 强制模拟未绑定（覆盖 _is_bound 状态）

SIMULATE_LATENCY_MS = 0           # 模拟发送延迟（毫秒）。0 = 不延迟


# ------------------------------------------------------------
# 错误码枚举
# 必须与 dglab_sender.py 未来定义的错误码保持一致
# 调用方根据 error_code 做不同决策（重试 / 重连 / 重置 death 周期）
# ------------------------------------------------------------
ERR_NOT_BOUND = "not_bound"             # 还没扫码绑定
ERR_DEVICE_OFFLINE = "device_offline"   # APP 在但设备没连
ERR_TARGET_OFFLINE = "target_offline"   # APP 离线
ERR_QUEUE_FULL = "queue_full"           # 波形队列满
ERR_TIMEOUT = "timeout"                 # 等响应超时
ERR_WS_DISCONNECTED = "ws_disconnected" # WebSocket 断了
ERR_UNKNOWN_ACTION = "unknown_action"   # 不在 ACTION_PROFILES 里
ERR_RANDOM_FAILURE = "random_failure"   # 故障注入：随机失败


# ------------------------------------------------------------
# 绑定状态机
# 模拟 "APP 扫码绑定 → 拿到 targetId" 的真实流程
# mock 默认已绑定，方便日常测试；专项测试时调 unbind() 模拟未绑定
# ------------------------------------------------------------
_is_bound = True
_target_id = "mock-target-001"
_client_id = "mock-client-001"
_state_lock = threading.Lock()


def bind(target_id: str, client_id: Optional[str] = None) -> dict:
    """
    模拟 APP 扫码绑定。
    dglab_sender 未来会有同名函数，参数和返回字段保持一致。
    """
    global _is_bound, _target_id, _client_id
    with _state_lock:
        _is_bound = True
        _target_id = target_id
        if client_id is not None:
            _client_id = client_id

    print(f"[MOCK BIND] target_id={target_id}, client_id={_client_id}")
    return {
        "success": True,
        "target_id": _target_id,
        "client_id": _client_id,
        "mode": "mock",
    }


def unbind() -> dict:
    """模拟设备失绑（APP 退出 SOCKET 控制）"""
    global _is_bound
    with _state_lock:
        _is_bound = False
    print("[MOCK UNBIND] 设备已解绑")
    return {"success": True, "mode": "mock"}


def get_bind_status() -> dict:
    """查询当前绑定状态。app.py 可以暴露成 GET /bind/status"""
    with _state_lock:
        return {
            "is_bound": _is_bound,
            "target_id": _target_id if _is_bound else None,
            "client_id": _client_id if _is_bound else None,
            "mode": "mock",
        }


# ------------------------------------------------------------
# 发送历史（内存环形缓冲，最多 100 条）
# 调试 BUG 列表时非常有用：可以反查"刚刚的误触发是哪一帧、什么 payload"
# 后续可以在 app.py 里加 GET /history 接口暴露这个列表
# ------------------------------------------------------------
SEND_HISTORY: deque = deque(maxlen=100)


def get_send_history(limit: int = 20) -> list:
    """获取最近 N 条发送记录，按时间倒序"""
    records = list(SEND_HISTORY)
    records.reverse()
    return records[:limit]


def clear_send_history():
    """清空历史。测试用例之间隔离时调用"""
    SEND_HISTORY.clear()


# ------------------------------------------------------------
# 内部辅助：构造统一格式的返回值
# 所有返回都走这里，保证字段齐全、不会漏字段
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
        "mode": "mock",
        "error": error,
        "error_code": error_code,
        "payload": payload or {},
        "profile": profile,
    }


# ------------------------------------------------------------
# 主函数：发送动作
# ------------------------------------------------------------
def send_action(action: str, payload: Optional[dict] = None) -> dict:
    """
    把动作"发送"到 mock 设备。

    返回字段（与 dglab_sender 完全对齐）：
        success    : bool        发送是否成功
        action     : str         原样返回动作名
        mode       : "mock"      区分 mock / dglab
        error      : str | None  人类可读的错误描述
        error_code : str | None  机器可读的错误码（用于调用方分支判断）
        payload    : dict        原始 payload 透传
        profile    : dict | None 对应的 ACTION_PROFILES 项（若动作合法）
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---- 第一步：动作合法性检查 ----
    profile = ACTION_PROFILES.get(action)
    if profile is None:
        print(f"[{now_str}] [MOCK SEND] action={action} → 未知动作，拒绝")
        result = _make_result(
            success=False,
            action=action,
            payload=payload,
            error=f"unknown action: {action}",
            error_code=ERR_UNKNOWN_ACTION,
        )
        _record_history(action, payload, result)
        return result

    # ---- 第二步：故障注入 - 模拟未绑定 ----
    if SIMULATE_NOT_BOUND or not _is_bound:
        print(f"[{now_str}] [MOCK SEND] action={action} → 未绑定设备，拒绝")
        result = _make_result(
            success=False,
            action=action,
            payload=payload,
            profile=profile,
            error="device not bound (扫码绑定后再发送)",
            error_code=ERR_NOT_BOUND,
        )
        _record_history(action, payload, result)
        return result

    # ---- 第三步：故障注入 - 模拟设备离线 ----
    if SIMULATE_DEVICE_OFFLINE:
        print(f"[{now_str}] [MOCK SEND] action={action} → 模拟设备离线")
        result = _make_result(
            success=False,
            action=action,
            payload=payload,
            profile=profile,
            error="device offline (APP 已断开或郊狼未连接)",
            error_code=ERR_DEVICE_OFFLINE,
        )
        _record_history(action, payload, result)
        return result

    # ---- 第四步：故障注入 - 模拟延迟 ----
    if SIMULATE_LATENCY_MS > 0:
        time.sleep(SIMULATE_LATENCY_MS / 1000.0)

    # ---- 第五步：故障注入 - 模拟随机失败 ----
    if SIMULATE_FAILURES and random.random() < FAILURE_RATE:
        print(f"[{now_str}] [MOCK SEND] action={action} → 模拟随机失败")
        result = _make_result(
            success=False,
            action=action,
            payload=payload,
            profile=profile,
            error="random failure injected",
            error_code=ERR_RANDOM_FAILURE,
        )
        _record_history(action, payload, result)
        return result

    # ---- 第六步：正常路径，假装发送成功 ----
    print(
        f"[{now_str}] [MOCK SEND] action={action}, "
        f"channel={profile['channel']}, strength={profile['strength']}, "
        f"duration={profile['duration']}s, payload={payload}"
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


# ------------------------------------------------------------
# 内部辅助：记录发送历史
# ------------------------------------------------------------
def _record_history(action: str, payload: Optional[dict], result: dict):
    SEND_HISTORY.append({
        "time": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "payload": payload or {},
        "success": result["success"],
        "error_code": result.get("error_code"),
    })

