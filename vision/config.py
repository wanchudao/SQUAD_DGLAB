# ============================================================
# 文件：vision/config.py
# 作用：vision 识别层的配置文件
# ============================================================

# 模型路径
MODEL_PATH = r"D:\SQUAD_DGLAB\model\best.pt"

# 单张图片推理时的置信度阈值
# 低于这个置信度的识别结果会被 YOLO 过滤掉
CONF_THRESHOLD = 0.65

# 输出结果图目录
OUTPUT_DIR = r"D:\SQUAD_DGLAB\samples\output"

# 类别名，仅用于代码中判断
CLASS_BLEEDING = "bleeding"
CLASS_INCAP = "incap"
