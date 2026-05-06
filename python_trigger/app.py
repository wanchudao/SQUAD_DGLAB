import os

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

from event_mapper import map_event_to_action
from state import can_trigger


# ============================================================
# 根据环境变量切换发送器
# ============================================================
USE_REAL_DGLAB = os.getenv("DGLAB_REAL") == "1"

if USE_REAL_DGLAB:
    from adapters.dglab_sender import send_action
    print("[APP] 当前模式：真实 DG-LAB 发送器 adapters.dglab_sender")
else:
    from adapters.mock_sender import send_action
    print("[APP] 当前模式：MOCK 假发送器 adapters.mock_sender")


# ============================================================
# 冷却时间配置（秒）
# ============================================================
COOLDOWN = {
    "bleeding": 1.0,   # 流血持续触发，1秒一次
    "incap":    5.0,   # 濒死只触发一次，冷却长一点
    "death":    5.0,   # 死亡只触发一次
}


app = FastAPI(title="SQUAD DG-LAB Trigger API")


# ============================================================
# 请求体格式
# ============================================================
class TriggerEvent(BaseModel):
    event: str
    source: Optional[str] = "unknown"
    level: Optional[str] = None


# ============================================================
# 根路径：确认服务是否运行
# ============================================================
@app.get("/")
def root():
    return {
        "service": "python_trigger",
        "status": "running",
        "step": "step-2-assembled",
        "mode": "real_dglab" if USE_REAL_DGLAB else "mock",
        "dglab_real": USE_REAL_DGLAB,
    }


# ============================================================
# DG-LAB 状态页：确认当前是否启用真实发送器
# ============================================================
@app.get("/dglab/status")
def dglab_status():
    return {
        "service": "python_trigger",
        "mode": "real_dglab" if USE_REAL_DGLAB else "mock",
        "dglab_real": USE_REAL_DGLAB,
        "message": "当前已启用真实发送器" if USE_REAL_DGLAB else "当前仍在使用 MOCK 假发送器",
    }


# ============================================================
# 触发接口：vision 或测试脚本会调用这里
# ============================================================
@app.post("/trigger")
def trigger(body: TriggerEvent):

    event_name = body.event.strip().lower()

    # 第一步：检查冷却时间
    cooldown = COOLDOWN.get(event_name, 0.5)
    if not can_trigger(event_name, cooldown):
        return {
            "success": False,
            "event": event_name,
            "action": "blocked",
            "message": f"冷却中，{cooldown}秒内只触发一次"
        }

    # 第二步：把事件翻译成动作
    action = map_event_to_action(event_name)
    if action == "unknown_action":
        return {
            "success": False,
            "event": event_name,
            "action": "unknown_action",
            "message": f"不认识的事件：{event_name}"
        }

    # 第三步：调用发送器
    result = send_action(action, payload={
        "source": body.source,
        "level": body.level,
    })

    return {
        "success": result.get("success", False),
        "event": event_name,
        "action": action,
        "sender_result": result,
        "message": "触发成功" if result.get("success", False) else "触发失败"
    }
