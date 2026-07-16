# ============================================================
# squad_dglab.zip 构建脚本
# 用法: python build_zip.py
# zip 内容 = DGHUB 插件运行所需的最小文件集
# ============================================================
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FILES = [
    "manifest.json",
    "main.py",
    "start.bat",
    "requirements.txt",
    "LICENSE",
    "vision/__init__.py",
    "vision/realtime_detect_and_trigger.py",
    "vision/suppression/__init__.py",
    "vision/suppression/detector_v1_blur.py",
    "vision/suppression/detector_v2_vignette.py",
    "model/best.pt",
]

out = ROOT / "squad_dglab.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for rel in FILES:
        src = ROOT / rel
        if not src.exists():
            raise SystemExit("[ERROR] missing: " + rel)
        zf.write(src, rel)

# 验证 start.bat 在 zip 内仍为 CRLF（DGHUB 硬性要求）
data = zipfile.ZipFile(out).read("start.bat")
crlf = data.count(b"\r\n")
bare_lf = data.count(b"\n") - crlf
if bare_lf > 0 or crlf == 0:
    raise SystemExit("[ERROR] start.bat in zip is NOT pure CRLF!")

size_mb = out.stat().st_size / 1048576
print("OK  " + str(out.name) + "  " + format(size_mb, ".1f")
      + " MB  " + str(len(FILES)) + " files  start.bat=CRLF")
