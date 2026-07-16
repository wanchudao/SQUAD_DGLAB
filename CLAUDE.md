# CLAUDE.md

## 项目说明

本项目从 SQUAD_DGLAB（V1.0.2 独立桌面应用）迁移而来，当前目标是开发一个 **DGHUB 插件**，将 YOLO 视觉检测能力接入 DGHUB 平台。

原项目包含完整注释、日志、配置文件和运行脚本。可复用资产包括：vision/（YOLO + suppression）、model/best.pt、config.ini、python_trigger/（事件映射、cooldown、config 加载）。

DGHUB Plugin SDK v1 参考: 见 `PLUGIN_DEVELOPMENT.md`。

任何 AI 助手在处理本项目时，必须优先保护现有结构、注释风格、日志风格和稳定性。

## 总体原则

1. 修改前必须先阅读相关代码和上下文。
2. 修改前必须先说明计划，不允许直接大范围改代码。
3. 每次只处理一个明确任务。
4. 不允许无理由重写整个文件。
5. 不允许无理由删除已有注释。
6. 不允许无理由删除已有日志。
7. 不允许修改无关文件。
8. 不允许引入新依赖，除非先说明原因并得到确认。
9. 不允许修改密钥、账号、token、证书、私有配置等敏感内容。
10. 所有修改必须能通过人工 review。

## Python 代码规则

1. 保持现有 Python 代码风格。
2. 保持现有函数命名、模块划分和目录结构。
3. 修改函数逻辑时，必须同步检查调用方。
4. 修改异常处理时，必须检查日志是否仍然足够定位问题。
5. 新增代码应尽量小而清晰，不要过度设计。
6. 不要随意改变 public API、配置字段或外部调用方式。

## JavaScript 代码规则

1. 保持现有 JavaScript 代码风格。
2. 不要随意引入新的前端框架或构建工具。
3. 如果修改前后端交互逻辑，必须说明接口字段变化。
4. 不要改动与当前任务无关的 UI、样式或脚本。

## 注释规则

1. 保留解释业务逻辑、协议逻辑、设备逻辑、异常原因的注释。
2. 如果代码行为改变，必须同步更新相关注释。
3. 不要添加无意义的显而易见注释。
4. 对复杂逻辑，应解释“为什么这样做”，而不是只解释“代码做了什么”。

## 日志规则

1. 保持现有日志格式和日志等级习惯。
2. 不要删除关键路径上的日志。
3. 修改异常处理、设备连接、网络请求、文件读写、状态切换等逻辑时，必须检查日志是否完整。
4. 不要在日志中输出密码、token、密钥、私有配置或敏感数据。
5. 新增错误处理时，应加入有助于排查问题的日志。

## Git 工作流

1. 不要直接在 main 分支上工作。
2. AI 修改应优先在 ai-setup-test 或其他 ai-* 分支上进行。
3. 每次修改后必须说明：
   - 修改了哪些文件
   - 为什么修改
   - 是否影响现有功能
   - 如何测试
4. 修改后必须建议运行对应测试或启动脚本。
5. 不允许自动提交代码，除非用户明确要求。

## AI 工作流程

每次任务必须按以下流程执行：

1. 先分析相关文件。
2. 再给出修改计划。
3. 等待用户确认。
4. 只修改计划中明确提到的文件。
5. 修改后展示变更摘要。
6. 提供测试步骤。
7. 等待用户 review。

## 禁止行为

1. 禁止大范围格式化整个项目。
2. 禁止删除历史注释和日志。
3. 禁止修改与任务无关的文件。
4. 禁止猜测配置含义后直接改配置。
5. 禁止把临时调试代码长期留在项目中。
6. 禁止把本地路径、账号、密钥写死进代码。
7. 禁止在没有说明原因的情况下改变项目结构。

## 推荐提示词

当用户要求修改代码时，AI 应优先回应：

“我会先阅读相关文件并给出计划，暂不修改代码。”

当用户要求审查代码时，AI 应优先检查：

1. 是否破坏现有注释
2. 是否破坏现有日志
3. 是否引入不必要依赖
4. 是否影响现有运行脚本
5. 是否存在异常处理遗漏
6. 是否有敏感信息泄露风险



---

# AI 工作记录

## 2026-06-01 — Portable 一键启动版构建全过程

**模型**: deepseek-v4-pro
**分支**: main（未切 ai-* 分支，用户直接要求构建）

---

### 阶段一：全项目阅读

完整阅读了以下内容：

**源代码 (12 个文件)**:
- `python_trigger/app.py` — FastAPI /trigger 接口，DGLAB_REAL 环境变量切换
- `python_trigger/event_mapper.py` — 5 事件→5 动作映射
- `python_trigger/state.py` — 通用 cooldown 管理器
- `python_trigger/config_loader.py` — config.ini 加载器（fallback+clamp）
- `python_trigger/adapters/dglab_sender.py` — 真实发送器（safe stop + per-channel token）
- `python_trigger/adapters/dglab_ws_client.py` — WebSocket 客户端（二维码+重连）
- `python_trigger/adapters/mock_sender.py` — 高保真假发送器
- `vision/realtime_detect_and_trigger.py` — YOLO 实时识别主循环（808 行）
- `vision/suppression/__init__.py` — Suppression 检测器工厂
- `vision/suppression/detector_v1_blur.py` — v1: Laplacian 模糊+色差
- `vision/suppression/detector_v2_vignette.py` — v2: 暗角+边缘检测（18/18 校准）

**配置与脚本 (6 个文件)**:
- `config.ini` — 五档强度/时长配置
- `start_all.bat` — 三选一交互式启动器
- `install.bat` — 6 步一键安装（CUDA 智能映射）
- `check_deps.py` — 5 节依赖体检
- `requirements.txt` — 13 个依赖包
- `PYTORCH_INSTALL.md`、`KNOWN_ISSUES.md`、`README.md`

**测试脚本 (4 个)**:
- `tests/send_bleeding.py`、`send_incap.py`、`send_death.py`、`send_cooldown_test.py`

**历史日志 (10 份)**:
- 2026_4_28 ~ 2026_5_24，覆盖从 SOCKET v2 联调到 v1.0.1 发布全过程
- 真机验证记录：bleeding/incap/death 核心事件 + safe stop + token 防误伤全部通过

---

### 阶段二：打包策略讨论（参考 badwordshock 经验）

**badwordshock 的关键经验**:
- --onedir 而非 --onefile
- CUDA DLL 依赖链：cublas64 → cublasLt → cudart64（缺一不可）
- Windows DLL 加载优先级：已加载模块所在目录 > System32 > PATH
- `getattr(sys, 'frozen', False)` 路径兼容
- `collect_dynamic_libs` + `collect_data_files` 自动收集

**SQUAD_DGLAB 不适合 PyInstaller 的原因**:
1. 三进程架构（Node + FastAPI + Vision），PyInstaller 只能打单个 Python 脚本
2. PyTorch CUDA 体积 ~3GB，PyInstaller dist 后 4-5GB，GitHub 限制 2GB
3. Node.js 后端无法被 PyInstaller 打包
4. 项目已有成熟的 install.bat + start_all.bat，不需要重做安装流程

**最终选择**：Portable 方案——嵌入 Python + Node.js portable，不自带 GPU PyTorch。

---

### 阶段三：一键启动器设计讨论

**三个关键决策**:
1. Mock 模式 → 取消，默认 Real（Portable 用户都是有设备的）
2. IP 选择 → 必须保留，自动列出+用户选编号
3. Suppression 模式 → 必须保留，三选一（off/blur/vignette）

---

### 阶段四：实际构建 Portable 包

**Step 1**: 创建 `dist/SQUAD_DGLAB_portable/` 目录结构

**Step 2**: 下载 Python 3.11.9 embeddable (11MB zip)
- 解压到 `dist/python/`
- 编辑 `python311._pth`: 添加 `Lib/site-packages` + 取消注释 `import site`
- 下载 get-pip.py → 安装 pip 到嵌入式 Python
- **发现 `sys.path` 包含用户 site-packages**: `C:\Users\<user>\AppData\Roaming\Python\Python311\site-packages`
- 解决：`启动.bat` 中设置 `PYTHONNOUSERSITE=1`

**Step 3**: pip install 依赖
- 首次装 cu126 GPU 版 torch：2.6 GB 下载，dist 膨胀到 **4.8 GB**
- 其余依赖（ultralytics, opencv-python, fastapi, uvicorn, mss, websocket-client, qrcode, numpy, Pillow, PyYAML, tqdm 等）全部安装成功

**Step 4**: 下载 Node.js v22.20.0 portable (34MB zip)
- 解压到 `dist/node/`（含 node.exe + npm.cmd）

**Step 5**: 复制 `official_v2/` 到 dist
- `npm install` 462 个包（来自 npm 官方源）

**Step 6**: 复制源码
- `python_trigger/`、`vision/`、`model/best.pt`、`config.ini`

**Step 7**: 创建 `启动.bat`
- v1: 含 IP 选择 + Suppression 选择 + 三服务启动
- 编码：GBK/ANSI + CRLF（无 BOM），同 install.bat 规范

**⚠️ 关键转折 — CUDA 兼容性问题**:
用户指出："其他用户不一定是我这个版本的 CUDA，pytorch 也是同样的问题"

预装 cu126 GPU torch 的包只能在 CUDA 12.6+ 驱动上运行。如果用户驱动只支持 CUDA 11.8，torch 会崩溃。

**Step 8**: 改为 CPU 兜底 + 自动升级方案
- 卸载 cu126 torch (2.6 GB)
- 安装 CPU torch (123 MB)
- dist 从 **4.8 GB → 1.3 GB**（预估 zip ~450 MB）

**Step 9**: `启动.bat` 加入 Step 0 — CUDA 检测 + 自动 PyTorch GPU 升级

逻辑（复用 install.bat 的 CUDA 映射）:
```
1. python -c "torch.cuda.is_available()" → 已就绪? 跳过
2. nvidia-smi → 无? 警告但继续 (CPU 模式)
3. 解析 "CUDA Version: X.Y"
4. 映射: >=13→cu126, 12.6+→cu126, 12.4+→cu124, 12.0-12.3→cu121, 11.x→cu118
5. pip install torch torchvision torchaudio --index-url $TORCH_INDEX
6. 首次约 2.6GB 下载，后续启动秒开
```

**Step 10**: 验证 + 清理
- Python 导入验证：torch (CPU), cv2, fastapi, websocket-client 全部通过
- Node.js 启动验证：node.exe + npm 正常
- 清理 `__pycache__`、`.pyc`、下载缓存

---

### 最终产物

```
位置: E:\SQUAD_DGLAB\SQUAD_DGLAB\dist\SQUAD_DGLAB_portable\

SQUAD_DGLAB_portable/        1.3 GB (预估 zip ~450 MB)
├── 启动.bat                 ← 一键启动（含 CUDA 自动检测+GPU 升级）
├── python/                  1.2 GB（Python 3.11.9 + CPU torch + 全部依赖）
│   ├── python.exe
│   └── Lib/site-packages/   ← torch(cpu), ultralytics, cv2, fastapi...
├── node/                    99 MB（Node.js v22.20 portable）
│   ├── node.exe
│   └── npm.cmd
├── official_v2/socket/v2/backend/
│   └── node_modules/        56 MB（462 packages）
├── python_trigger/          源码
├── vision/                  源码（含 suppression/）
├── model/best.pt            22 MB
└── config.ini               默认强度配置
```

### 未创建 build_portable.bat

本应创建自动化构建脚本，但本次构建是手动逐步执行的，`build_portable.bat` 留待后续。

### 涉及的现有文件
- **未修改任何现有文件**。所有改动仅限于 `dist/` 目录下的新增文件。
- `install.bat`、`start_all.bat`、`check_deps.py` 全部原样保留，供开发者和 A 版用户使用。

---

# AI 工作记录

## 2026-06-05 — 发布前防御性改进（方向 C）

**模型**: deepseek-v4-pro
**分支**: ai-setup-test → main

---

### 背景

用户即将为 v1.0.1 制作宣传片，项目已经发布在 GitHub 上。我们分析了用户（小白）从下载到跑起来的完整依赖链，识别出 8 道 "关卡"：

| 关卡 | 依赖 | 用户可能遇到的问题 |
|------|------|-------------------|
| 1 | Python 3.10-3.12 | 没装、装了没加 PATH、版本太新 |
| 2 | pip + requirements.txt | 下载超时（PyTorch ~3GB） |
| 3 | NVIDIA 驱动 + CUDA | 不是 N 卡、驱动太旧 |
| 4 | Node.js | 没装（Mock 模式可跳过） |
| 5 | npm install | npm 官方源超时 |
| 6 | 端口 9999/18000 | 被其他程序占用 |
| 7 | 手机 + 局域网 | 不在同一网络、APP 强度上限没设 |
| 8 | 游戏内交互 | 预期偏差 |

核心结论：install.bat 的能力边界内不可能替用户装 Python、装驱动、修网络。**方向 C**——在边界处加防御，让用户遇到问题时能自愈或带有效信息报 bug。

---

### 改动清单：解决 9 个具体用户问题

#### 问题 1: 用户不知道报什么 bug → 无从下手

- **新增** `.github/ISSUE_TEMPLATE/install-failed.yml` — 安装失败表单（卡在哪步、Windows 版本、显卡、Python 版本）
- **新增** `.github/ISSUE_TEMPLATE/startup-failed.yml` — 启动失败表单（哪个窗口报错、错误信息、是否跑过 install）
- **新增** `.github/ISSUE_TEMPLATE/pairing-failed.yml` — 配对失败表单（扫码问题、网络、APP 强度设置）
- **解决的痛点**: 用户报 "闪退"、"连不上" 时没有结构化信息，没法排查

#### 问题 2: Python 没装 → install.bat 直接退，用户不知道去哪下

- **修改** `install.bat` `:no_python` — 自动用 `start` 打开 Python 下载页，再退出
- **解决的痛点**: 不再需要用户手动搜 "python download"

#### 问题 3: Python 装了但没勾 "Add to PATH" → 报 "没找到 Python"

- **修改** `install.bat` `:find_python` — 新增自动搜索逻辑：
  1. 尝试 `py -3` 启动器（python.org 安装器自带），通过 `sys.executable` 定位完整路径
  2. 扫描 `%LOCALAPPDATA%\Programs\Python\Python3*`
  3. 扫描 `C:\Python3*`
  4. 扫描 `%ProgramFiles%\Python3*`
  5. 任意找到 → 自动加入 PATH → 继续安装
  6. 全没找到 → 增强提示（"装了但没找到？重跑安装器勾选 Add to PATH"）
- **解决的痛点**: 这是小白最高频问题——Python 装了，但 cmd 里敲 `python` 无效

#### 问题 4: Node.js 没装 → 用户不知道去哪下

- **修改** `install.bat` `:no_node` — 自动用 `start` 打开 Node.js 下载页
- **解决的痛点**: 同上，减少用户搜索成本

#### 问题 5: PyTorch ~3GB 下载超时 → 安装失败

- **修改** `install.bat` `:step3_install` — `--default-timeout 120` + 失败后自动重试一次
- **解决的痛点**: 国内用户直连 PyTorch 官方源下载 3GB 大概率 timeout

#### 问题 6: npm install 官方源超时 → 安装失败

- **修改** `install.bat` `:npm_failed` — 首次失败自动 `npm config set registry https://registry.npmmirror.com` 重试
- **解决的痛点**: npm 官方源在国内经常超时

#### 问题 7: 端口被占 → 启动后窗口闪退，不知道原因

- **修改** `check_deps.py` — 新增第 6 节 `check_ports()`，检查 9999 (Node 后端) 和 18000 (Trigger) 是否被占用
- **解决的痛点**: 上次没关干净或别的程序占了端口，启动失败但不知道原因

#### 问题 8: 没装 GPU 驱动 → Vision 用 CPU 跑 YOLO，用户以为 "卡住了"

- **修改** `start_all.bat` — Vision 启动前跑 `python -c "import torch; assert torch.cuda.is_available()"` 预检
  - CUDA 不可用 → 打印醒目标语 "YOLO will be much slower on CPU"，但不阻塞启动
- **解决的痛点**: CPU 模式 FPS 很低，用户以为程序坏了

#### 问题 9: 编辑 config.ini 写错格式 → 配置被静默忽略，用户不知道

- **修改** `check_deps.py` — 新增第 7 节 `check_config()`，逐项校验：
  - `[strength]` / `[duration]` 节是否存在
  - 5 个 key 是否齐全
  - 值是否为合法数字
  - 值是否在安全范围内 (0-200 / 0.1-30.0)
  - 任意问题 → WARN，不影响启动（容错由 config_loader.py 的 fallback 机制兜底）
- **解决的痛点**: 用户改完配置以为生效了，实际用的默认值，体感不对

---

### 附带修复

- `check_deps.py` — 修复 `check_files()` 返回值 bug (`opt_passed + opt_total - opt_total + opt_passed` → `opt_passed`)
- `vision/realtime_detect_and_trigger.py` — 帧间隔改为 `time.sleep(max(0.0, FRAME_INTERVAL - elapsed))`，补偿处理耗时
- `README.md` — 修正配置格式文档（`[ACTION_PROFILES]` → `[strength]` + `[duration]`）
- `check_deps.py` — 末尾加 `input("Press Enter to exit...")`，双击运行时窗口不会闪退

---

### 涉及文件

| 文件 | 改动类型 |
|------|----------|
| `.github/ISSUE_TEMPLATE/install-failed.yml` | 新建 |
| `.github/ISSUE_TEMPLATE/startup-failed.yml` | 新建 |
| `.github/ISSUE_TEMPLATE/pairing-failed.yml` | 新建 |
| `install.bat` | 修改（7 处防御性增强） |
| `start_all.bat` | 修改（CUDA 预检） |
| `check_deps.py` | 修改（端口检测、配置校验、pause、bug 修复） |
| `vision/realtime_detect_and_trigger.py` | 修改（帧间隔补偿） |
| `README.md` | 修改（配置文档修正） |

### 未修改的文件
- `python_trigger/` 全部
- `vision/suppression/` 全部
- `official_v2/` 全部
- `config.ini`、`requirements.txt`

---

### GBK 编码事故（2026-06-05 同日）

**现象**: 用户测试 install.bat 时发现所有中文变成乱码（锟斤拷），开头报 `'拷锟?GBK' 不是内部或外部命令`。

**根因**: `install.bat` 原本是 GBK/ANSI 编码（v3.1 规范：不用 UTF-8，中文 Windows 兼容）。Edit 工具读写文件时默认为 UTF-8，导致 GBK 字节被当成 Latin-1 解码后重新编码为 UTF-8，中文全部损毁。

**影响范围**: 仅 `install.bat`。`check_deps.py`、`start_all.bat` 等文件本身是 UTF-8/ASCII，不受影响。GitHub release v1.0.2 的 install.bat 有乱码。

**修复过程**:
1. 从 git 历史恢复原始 GBK 文件 (`ff0c597`)
2. 编写 Python 脚本，以 `decode('gbk')` → Unicode → 应用纯 ASCII 文本替换 → `encode('gbk')` 写回
3. 7 处编辑全部成功，文件从 11,954 字节 → 13,146 字节（新增内容均为 ASCII）
4. 提交、推送、强制更新 v1.0.2 tag (`43a4b89`)

**教训**:
- **用 Edit/Write 工具修改 GBK 文件有编码风险**。工具不会自动检测 GBK，会按 UTF-8 处理导致多字节字符被破坏。
- **安全方案**: 对于 GBK 编码文件，先 `git checkout` 恢复原始版本，用 Python 脚本 `decode('gbk')` → 修改 → `encode('gbk')` 写回。
- **可防御的编码模式**: 如果新增内容全部为 ASCII（英文日志标签 `[ERROR]`/`[WARN]`/`[INFO]`），则新增内容在 GBK 和 UTF-8 下字节一致，不会产生混合编码。本次 `install.bat` 的所有编辑恰好符合这个条件。
- **验证方法**: 用 Python `open(f, 'rb').read().decode('gbk')` 验证文件仍为合法 GBK；检查中文是否可读。

---

### 发布

- **v1.0.2** tag 创建于 `1a56d88`，后因 GBK 修复强制更新至 `43a4b89`
- Release notes: https://github.com/wanchudao/SQUAD_DGLAB/releases/tag/v1.0.2
- 分支策略: `ai-setup-test` → `main`，后续直接在 `main` 上工作

---

## 2026-06-05 — 项目迁移至 DGHUB 插件开发

**模型**: deepseek-v4-pro
**分支**: main

---

### 迁移背景

原始的 SQUAD_DGLAB 是一个**独立运行的三进程桌面应用**（Node.js 后端 + FastAPI Trigger + YOLO Vision），通过 DG-LAB SOCKET v2 协议直接与 DG-LAB 设备通信。

DGHUB 是一个**中间件平台**，它在游戏和硬件设备之间做了一层抽象。插件不再直接与设备通信，而是通过 DGHUB 的 WebSocket 协议发送触发指令，由 DGHUB 负责实际的设备通信和强度管理。

### 迁移目标

开发一个 **DGHUB 插件**，将 SQUAD_DGLAB 的 YOLO 视觉检测能力接入 DGHUB 平台，使任何支持 DGHUB 的游戏/应用都能使用 SQUAD 的击杀/倒地事件触发。

### DGHUB Plugin SDK v1 关键信息

已阅读 `PLUGIN_DEVELOPMENT.md`（位于 C:/Users/<user>/Downloads/），关键协议要点：

**连接与认证**:
- 插件通过 WebSocket 连接 DGHUB，地址/端口/Token 从环境变量读取: `DGHUB_HOST`, `DGHUB_PORT`, `DGHUB_TOKEN`, `DGHUB_PLUGIN_ID`
- 连接后发送 `hello` 握手，携带 manifest JSON + token

**manifest.json 结构**:
- 必需字段: `id`, `name`, `version`, `sdk` ("1")
- 可选 `config_schema` — DGHUB 会自动生成配置 UI
- 可选 `entry` — 入口文件路径

**核心操作 (op)**:
- `trigger` — 核心消息原语，参数: `delta_pct`（强度增量百分比）, `strength_mode`（rollback/permanent）, `duration_s`, `preset`, `channel`, `label`
- `pulse` — 瞬时脉冲
- `event` — 事件上报
- `set_strength` — 设置绝对强度

**强度模型**:
- 每个插件有独立的强度层（layer），层内有一个 baseline anchor
- 所有插件层的强度求和后输出到设备
- `delta_pct` 是基于 baseline 的百分比偏移
- `rollback` 模式: 持续 `duration_s` 秒后回落到 baseline
- `permanent` 模式: 永久修改 baseline

**config_schema 类型**: bool, percent, duration, number, text, select, channel, preset, path

**目录结构约定**:
```
plugins/my_plugin/
├── manifest.json
└── main.py
```

**打包**: zip 文件，manifest.json 在根目录

### 可复用的 SQUAD_DGLAB 资产

从原项目可直接复用:
- `vision/realtime_detect_and_trigger.py` — YOLO 实时检测主循环（核心逻辑）
- `vision/suppression/` — v1 blur / v2 vignette 抑制检测器
- `model/best.pt` — 已训练的 YOLO 模型
- `python_trigger/event_mapper.py` — 5 事件→5 动作映射逻辑
- `python_trigger/state.py` — cooldown 管理器
- `python_trigger/config_loader.py` — config.ini 加载+fallback+clamp
- `config.ini` — 五档强度/时长配置参数

需要重写的:
- `python_trigger/adapters/dglab_ws_client.py` → 替换为 DGHUB WebSocket 协议
- `python_trigger/adapters/dglab_sender.py` → 替换为 DGHUB trigger/pulse 操作
- `python_trigger/app.py` → 不再需要 FastAPI HTTP 服务，改为 DGHUB 插件主循环

不再需要的:
- `official_v2/` — Node.js SOCKET v2 后端（DGHUB 替代）
- `start_all.bat` — 三进程启动器（改为单插件进程）

### 新目录结构

```
E:\SQUAD_DGLAB_DGHUB\
├── manifest.json              ← 待创建
├── main.py                    ← 待创建（插件入口）
├── vision/                    ← 复用（YOLO + suppression）
├── model/best.pt              ← 复用
├── config.ini                 ← 复用
├── CLAUDE.md                  ← 本文件
└── PLUGIN_DEVELOPMENT.md      ← SDK 参考（从 Downloads 复制）
```

### 当前状态

- 项目文件已从 `E:\SQUAD_DGLAB\SQUAD_DGLAB` 迁移至 `E:\SQUAD_DGLAB_DGHUB`
- 原始项目保持不变，可继续作为独立应用使用
- DGHUB 插件开发将在新目录进行
- 用户将新开一个对话开始实际开发

---

## 2026-06-06 — DGHUB 插件架构分析与实现计划

**模型**: deepseek-v4-pro
**分支**: main

---

### 全项目阅读确认

完整阅读了以下文件以制定实现计划：

**DGHUB SDK 协议**: `PLUGIN_DEVELOPMENT.md`
**核心源码**: `vision/realtime_detect_and_trigger.py` (808行), `python_trigger/app.py`, `python_trigger/event_mapper.py`, `python_trigger/state.py`, `python_trigger/config_loader.py`, `python_trigger/adapters/dglab_sender.py`, `vision/suppression/__init__.py`
**配置**: `config.ini`

### 架构变化

```
旧链路: Vision → POST /trigger → FastAPI → dglab_sender → dglab_ws_client → DG-LAB 设备
新链路: Vision → DGHUB WebSocket (trigger op) → DGHUB 平台 → DG-LAB 设备
```

插件不再直接操控设备，而是通过 DGHUB 的 `trigger` 协议消息，由 DGHUB 负责强度叠加和设备通信。

### 实现计划

**新建 2 个文件**:

1. **`manifest.json`** — 插件元信息 + `config_schema`:
   - id: `squad_dglab`, name: `SQUAD DG-LAB`, version: `1.0.0`, sdk: `1`
   - config_schema 暴露: 5 种事件的强度/时长、通道选择、抑制模式、检测置信度阈值、帧间隔、预览开关、设备类型偏好
   - entry: `main.py`

2. **`main.py`** — 插件入口:
   - 从环境变量读取 `DGHUB_HOST`/`DGHUB_PORT`/`DGHUB_TOKEN`/`DGHUB_PLUGIN_ID`
   - WebSocket 连接 DGHUB → `hello` 握手 → 接收 `config` 推送
   - 启动 YOLO 检测循环（复用 vision/ 模块）
   - 检测结果通过 DGHUB `trigger` op 发送（action=both, mode=rollback, delta_pct 从 config.ini 读取映射到百分比）
   - 处理 `stop` / `config_changed` / `ping` 消息
   - 通过 `log` op 转发日志到 DGHUB 面板
   - 通过 `status` op 上报运行状态

**复用 6 个模块（基本不改）**:
| 模块 | 作用 |
|------|------|
| `vision/realtime_detect_and_trigger.py` | YOLO 检测主循环 + 死亡/抑制仲裁 |
| `vision/suppression/` | v1 blur / v2 vignette 抑制检测器 |
| `python_trigger/event_mapper.py` | 5 事件 → 动作名映射 |
| `python_trigger/state.py` | 通用 cooldown 管理器 |
| `python_trigger/config_loader.py` | config.ini 读取 + fallback + clamp |
| `model/best.pt` + `config.ini` | 模型权重 + 强度/时长配置 |

**不再需要（保留不删）**:
- `python_trigger/app.py` — FastAPI HTTP 服务
- `python_trigger/adapters/` — DG-LAB 私有协议发送器/WS 客户端
- `official_v2/` — Node.js SOCKET v2 后端
- `start_all.bat` — 三进程启动器

### 关键映射

5 种游戏事件 → DGHUB `trigger` 参数:
- `bleeding` → delta_pct 从 weak_pulse 强度映射, rollback, duration 从 config 读取
- `incap` → delta_pct 从 strong_pulse 强度映射, rollback
- `death` → delta_pct 从 death_pulse 强度映射, rollback
- `suppression_light` → delta_pct 从 suppression_light_pulse 映射, rollback
- `suppression_heavy` → delta_pct 从 suppression_heavy_pulse 映射, rollback

delta_pct 计算: DGHUB 的 delta_pct 是基于 baseline 的百分比偏移。config.ini 中的强度值(0-200)需要映射为合理的百分比增量。baseline 由用户在前端配置(通过 config_schema 的 idle_strength 字段)。

### 待用户确认

1. delta_pct 的映射策略 — config.ini 中的绝对值(如 10/20/40)如何映射到 DGHUB 百分比偏移
2. 波形预设名 — DGHUB 的 preset 字段需要匹配主程序内置波形名，需确认可用波形列表
3. 抑制模式是否需要作为 config_schema 暴露给前端切换

---

## 2026-06-06 — 插件代码实现 (第一轮)

**模型**: deepseek-v4-pro
**分支**: main

---

### 背景

用户确认了 4 个设计决策后，开始写代码。创建了完整的 DGHUB 插件。

### 新建文件

| 文件 | 说明 |
|------|------|
| `manifest.json` | 插件元信息 + 16 字段 config_schema（4 节：触发强度/触发时长/输出设置/检测设置）|
| `main.py` | 插件入口，6 阶段启动（轻量导入→WS连接→握手→重量导入→启动vision→消息循环）|
| `vision/__init__.py` | 使 vision/ 成为 Python package |

### 核心架构

- **6 阶段启动**: Phase1 轻量导入 → Phase2 WS连接 → Phase3 握手+config → Phase4 torch/ultralytics导入(延后避免CUDA初始化阻塞) → Phase5 vision线程启动 → Phase6 消息循环
- **Monkey-patch**: `main.py` 在运行时替换 `vision.realtime_detect_and_trigger.send_trigger()`，从 HTTP POST 改为 DGHUB WebSocket `trigger` 消息
- **线程模型**: 主线程 asyncio WebSocket，vision daemon 线程通过 `asyncio.run_coroutine_threadsafe()` 投递消息
- **文件日志**: `_log()` 函数同时写 stdout 和 `plugin.log`，flush 每次写入，便于排查 DGHUB 后台进程问题

---

## 2026-06-06 — Bug 修复：消除 websockets 依赖 (第二轮)

**模型**: deepseek-v4-pro
**分支**: main

---

### 问题

插件在 DGHUB 中持续报 `10.0s 内未接入 WebSocket` 超时。经排查 PLUGIN_DEVELOPMENT.md 第 10 节：

> 当前 SDK 用主程序的 Python 解释器跑 `.py` 入口，依赖必须在主程序的 venv 里。

DGHUB 用自己的 Python 运行 `main.py`。Phase 1 的 `import websockets` 是第三方库，DGHUB Python 环境里没有安装 → 导入失败 → 进程崩溃 → 10s 超时。

**plugin.log 不存在** 也佐证了这一点——进程在 Python 导入阶段就崩溃了，连 `_log()` 都没来得及调用。

### 修复

删除 `import websockets`，用 Python stdlib 实现最小 WebSocket 客户端 `_WsClient`（~110 行）：

- `asyncio.open_connection()` TCP 连接
- 手动 HTTP Upgrade 握手（`Sec-WebSocket-Key` + `Sec-WebSocket-Version: 13`）
- RFC 6455 文本帧收发（FIN=1, opcode=0x01, masked payload）
- ping/pong 自动应答
- close frame 发送
- 支持 `async for` 迭代

新增的依赖 `struct`, `base64` 均为 Python stdlib。

### 涉及文件

| 文件 | 改动 |
|------|------|
| `main.py` | 删除 `import websockets`，新增 `_WsClient` + `_WsClosed` 类，`_connect_ws()` 改用 `_WsClient.connect()` |

### 结果

**依然 10 秒超时**。问题不在第三方依赖。下次排查方向：
- 需要确认 DGHUB 如何启动插件进程（Python 路径、工作目录）
- 可能需要参考 SDK 推荐的 PyInstaller `.exe` 打包方案
- 需要写一个最简测试插件（仅 WS 连接 + hello 握手，无 vision/torch）来隔离问题
- 需要查看 DGHUB 主程序的日志以获取子进程启动错误信息


---

## 2026-06-06 — 根因定位：entry 机制 + start.bat CRLF (第三轮调试)

**模型**: deepseek-v4-pro
**分支**: main

---

### 问题

前两轮修复后（删 websockets 依赖 → 自写 _WsClient → 恢复 websockets），插件依然 10s 超时。

### 调试过程：test_minimal 最简测试插件 6 轮迭代

| 版本 | entry | WS 实现 | 结果 |
|------|-------|---------|------|
| v1 | `main.py` | 自定义 `_WsClient` | 10s 超时，无 log |
| v2 | `start.bat` (LF) | `websockets` | exit_code=120 |
| v3 | `main.py` | `websockets` | 10s 超时，无 log |
| v4 | `start.bat` (LF) | 纯 stdlib（只写 log 文件） | exit_code=120 |
| v5 | `main.py` | SDK 最小示例原样 | 10s 超时 |
| **v6** | **`start.bat` (CRLF)** | **SDK 最小示例原样** | **0.4s 上线** |

### 关键发现

1. **DGHUB 是 PyInstaller 打包的应用**（`DGLab-Console.exe` + `_internal/`），没有独立 `python.exe`
2. **`entry: "main.py"`** → DGHUB 通过 `DGLab-Console.exe <脚本路径>` 启动子进程，使用嵌入式 Python。在本机此机制不通（10s 超时，Python 进程似乎未正常执行业务代码）
3. **`entry: "start.bat"`** → DGHUB 通过 `cmd.exe /c` 启动，走系统 Python（`C:\Program Files\Python311\python.exe`），**可以正常工作**
4. **`.bat 文件必须是 CRLF 换行**，LF 会导致 exit_code=120
5. **`websockets` 在系统 Python 中可用**（DGHUB `_internal/` 中有 websockets-12.0，系统 Python 也已安装）
6. **badwordshock 能工作的原因**：它一直用的是 `entry: "start.bat"` + 系统 Python，从未用过 `entry: "main.py"`

### 下一步

将 squad_dglab 插件也切到 `entry: "start.bat"` + `websockets`，删除自定义 `_WsClient`。


---

## 2026-06-06 — 修复 squad_dglab：entry + websockets (第四轮)

**模型**: deepseek-v4-pro
**分支**: main

---

### 变更

| 文件 | 改动 |
|------|------|
| `manifest.json` | `"entry": "main.py"` → `"entry": "start.bat"` |
| `start.bat` | **新建**（CRLF 换行），内容 `@echo off` + `python "%~dp0main.py"` |
| `main.py` | 删自定义 `_WsClient`（~120行）+ `_WsClosed`（~5行）；删 `import struct, base64`；加 `import websockets`；`_connect_ws()` 改用 `websockets.connect()`；`_WsClosed` → `websockets.exceptions.ConnectionClosed` |

### 新增文件

| 文件 | 说明 |
|------|------|
| `test_minimal/` | 最简测试插件目录（SDK 最小示例原样），后续调试可用 |
| `test_minimal.zip` | 测试插件分发包 |

### 待验证（下次会话）

1. 在 DGHUB 导入 `squad_dglab.zip`，启用插件
2. 预期：0.4s 内上线（同 test_minimal v6）
3. 如有报错，查看 `plugin.log`（位于 `<DGHub安装目录>\plugins\squad_dglab\` 下）
4. 验证 vision 检测线程是否正常启动（YOLO 模型在 Phase 4 加载，需要系统 Python 已安装 torch/ultralytics/cv2）
