# ============================================================
# 文件：vision/screenshot_test.py
# 作用：测试能否截取当前屏幕并保存图片
# ============================================================

from pathlib import Path

import mss
import mss.tools


OUTPUT_PATH = Path("D:/SQUAD_DGLAB/samples/output/screenshot_test.png")


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with mss.mss() as sct:
        # monitor[1] 通常是主显示器
        monitor = sct.monitors[1]

        print("[SCREENSHOT TEST]")
        print(f"monitor = {monitor}")

        img = sct.grab(monitor)

        mss.tools.to_png(img.rgb, img.size, output=str(OUTPUT_PATH))

        print(f"[SAVE] 截图已保存：{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
