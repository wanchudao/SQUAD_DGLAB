# ============================================================
# 文件:python_trigger/config_loader.py
# 作用:从项目根目录的 config.ini 读取强度和时长配置
#
# 设计原则:
#   1. 找不到 config.ini 不报错,fallback 到默认值
#   2. config.ini 里某些字段缺失,只 fallback 缺失的字段
#   3. 数值非法 (非数字 / 越界) 不崩溃,fallback 单项默认值并打 warning
#   4. mock_sender 和 dglab_sender 共用同一份默认值,保证两边一致
# ============================================================

import configparser
from pathlib import Path
from typing import Tuple, Dict


# ------------------------------------------------------------
# v1.0.0 真机验证后的保守默认值
# 跟 config.ini 里的注释保持一致
# ------------------------------------------------------------
DEFAULT_STRENGTH: Dict[str, int] = {
    "weak_pulse": 10,
    "strong_pulse": 20,
    "death_pulse": 40,
    "suppression_light_pulse": 8,
    "suppression_heavy_pulse": 14,
}

DEFAULT_DURATION: Dict[str, float] = {
    "weak_pulse": 2.0,
    "strong_pulse": 4.0,
    "death_pulse": 5.0,
    "suppression_light_pulse": 1.5,
    "suppression_heavy_pulse": 2.0,
}


# ------------------------------------------------------------
# 安全边界
# ------------------------------------------------------------
STRENGTH_MIN = 0
STRENGTH_MAX = 200      # DG-LAB 协议上限
DURATION_MIN = 0.1
DURATION_MAX = 30.0


def _project_root() -> Path:
    """
    返回项目根目录路径。

    本文件位于 python_trigger/config_loader.py
    所以根目录是 parents[1]
    """
    return Path(__file__).resolve().parents[1]


def _clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _clamp_float(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def load_action_config(verbose: bool = True) -> Tuple[Dict[str, int], Dict[str, float]]:
    """
    读取 config.ini 里的强度和时长配置。

    返回:
        (strength_dict, duration_dict)

    永远返回完整的字典,缺失字段自动用默认值补齐。
    """
    strength = dict(DEFAULT_STRENGTH)
    duration = dict(DEFAULT_DURATION)

    config_path = _project_root() / "config.ini"

    if not config_path.exists():
        if verbose:
            print("[CONFIG] config.ini 不存在,使用默认强度配置")
            print("         路径: " + str(config_path))
        return strength, duration

    cp = configparser.ConfigParser()

    try:
        cp.read(config_path, encoding="utf-8")
    except Exception as e:
        if verbose:
            print("[CONFIG] config.ini 读取失败,使用默认值: " + str(e))
        return strength, duration

    # ---- 读 strength ----
    if cp.has_section("strength"):
        for key in DEFAULT_STRENGTH:
            if cp.has_option("strength", key):
                raw = cp.get("strength", key).strip()
                try:
                    val = int(raw)
                    val = _clamp_int(val, STRENGTH_MIN, STRENGTH_MAX)
                    strength[key] = val
                except ValueError:
                    if verbose:
                        print("[CONFIG] strength." + key
                              + " = '" + raw + "' 非法,使用默认值 "
                              + str(DEFAULT_STRENGTH[key]))

    # ---- 读 duration ----
    if cp.has_section("duration"):
        for key in DEFAULT_DURATION:
            if cp.has_option("duration", key):
                raw = cp.get("duration", key).strip()
                try:
                    val = float(raw)
                    val = _clamp_float(val, DURATION_MIN, DURATION_MAX)
                    duration[key] = val
                except ValueError:
                    if verbose:
                        print("[CONFIG] duration." + key
                              + " = '" + raw + "' 非法,使用默认值 "
                              + str(DEFAULT_DURATION[key]))

    if verbose:
        print("[CONFIG] 已从 " + str(config_path) + " 加载强度配置")
        print("         strength = " + str(strength))
        print("         duration = " + str(duration))

    return strength, duration


# ------------------------------------------------------------
# 模块级缓存:第一次调用时读一次,后续 sender 直接用
# ------------------------------------------------------------
_cached_strength = None
_cached_duration = None


def get_action_config() -> Tuple[Dict[str, int], Dict[str, float]]:
    """
    带缓存的配置获取。

    sender 模块级 import 时会触发一次读取,后续都用缓存。
    """
    global _cached_strength, _cached_duration

    if _cached_strength is None:
        _cached_strength, _cached_duration = load_action_config(verbose=True)

    return _cached_strength, _cached_duration
