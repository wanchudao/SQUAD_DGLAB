# ============================================================
# 文件：event_mapper.py
# 作用：把“游戏事件”翻译成“设备动作”
#
# 游戏事件：
#   bleeding
#   incap
#   death
#   suppression_light
#   suppression_heavy
#
# 设备动作：
#   weak_pulse
#   strong_pulse
#   death_pulse
#   suppression_light_pulse
#   suppression_heavy_pulse
# ============================================================


EVENT_ACTION_MAP = {
    "bleeding": "weak_pulse",
    "incap": "strong_pulse",
    "death": "death_pulse",
    "suppression_light": "suppression_light_pulse",
    "suppression_heavy": "suppression_heavy_pulse",
}


def map_event_to_action(event_name: str) -> str:
    """
    把一个事件名翻译成对应的动作名。

    返回：
        找到事件：返回动作名
        未知事件：返回 unknown_action
    """
    key = event_name.strip().lower()
    return EVENT_ACTION_MAP.get(key, "unknown_action")
