# ============================================================
# 文件：event_mapper.py
# 作用：把“游戏事件”翻译成“设备动作”
#
# 这个文件存在的意义：
#   游戏世界说的话      —— "hurt" / "death" / 以后可能有 "kill" / "revive"
#   设备世界听得懂的话  —— "weak_pulse" / "strong_pulse" / 以后可能有 "burst" 等
#   这两套语言不该混在主程序里，所以单独抽出来一张“翻译词典”
#
# 使用方式：
#   from event_mapper import map_event_to_action
#   action = map_event_to_action("hurt")   # 得到 "weak_pulse"
# ============================================================


# ------------------------------------------------------------
# 翻译词典本体
# ------------------------------------------------------------
# 这是一个 Python 字典（dict）：
#   - 左边（key）   ：游戏事件名
#   - 右边（value） ：对应的设备动作名
#
# 为什么用字典而不是一堆 if/elif？
#   - 字典查得快，写得短
#   - 以后加新事件，只要在表里多加一行，不用改函数逻辑
#   - 这种“数据驱动”的写法，工程上叫“配置和代码分离”
EVENT_ACTION_MAP = {
    "bleeding": "weak_pulse",
    "incap":    "strong_pulse",
    "death":    "death_pulse",
}



# ------------------------------------------------------------
# 翻译函数
# ------------------------------------------------------------
def map_event_to_action(event_name: str) -> str:
    """
    把一个事件名翻译成对应的动作名。

    参数：
        event_name : 事件名字符串，比如 "hurt"

    返回：
        动作名字符串，比如 "weak_pulse"
        如果事件名在词典里找不到，统一返回 "unknown_action"
    """

    # 第一步：清洗输入
    # .strip()  去掉首尾空格，防止别人传进来 " hurt "
    # .lower()  转小写，防止别人传进来 "Hurt" 或 "HURT"
    # 这一步看似多余，其实是“防御式编程”——
    # 你永远不知道未来识别层会传什么进来，先洗一遍最安全
    key = event_name.strip().lower()

    # 第二步：去字典里查
    # dict.get(key, default) 的好处：
    #   - 找到了，返回对应的值
    #   - 找不到，返回我们指定的 default（这里是 "unknown_action"）
    # 这样函数永远不会因为“事件名没见过”而报错崩溃，
    # 调用方拿到 "unknown_action" 自己决定怎么处理（拒绝 / 记日志 / 忽略）
    return EVENT_ACTION_MAP.get(key, "unknown_action")
