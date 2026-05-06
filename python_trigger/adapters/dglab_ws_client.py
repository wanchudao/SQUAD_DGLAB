# ============================================================
# 文件：adapters/dglab_ws_client.py
# 作用：DG-LAB SOCKET v2 官方后端的 WebSocket 长连接管理器
#
# 设计原则：
#   1. 用同步库 websocket-client + 后台线程，对新手友好
#   2. 收到的 bind / break / msg / heartbeat 自动分发处理
#   3. clientId 由后端分配，targetId 由 APP 扫码后分配
#   4. 提供 send_json() 让上层 dglab_sender 发消息
#   5. 自动重连：连接断开 5 秒后重连
#   6. 拿到 clientId 后自动把二维码画成图片弹窗 + 保存 PNG
# ============================================================

import os
import json
import time
import threading
from typing import Optional, Callable

try:
    import websocket  # pip install websocket-client
except ImportError:
    raise ImportError(
        "请先安装 websocket-client：pip install websocket-client"
    )

# ------------------------------------------------------------
# 方式 C 所需：自动把二维码 URL 画成图片
# 没装也不会让 WS 连接挂掉，只是退化为“只打印 URL 文本”
# ------------------------------------------------------------
try:
    import qrcode  # pip install qrcode[pil]
    _HAS_QRCODE = True
except ImportError:
    _HAS_QRCODE = False
    print("[DGLAB WS] 提示：未安装 qrcode 库，将不会自动弹出二维码图片。")
    print("           启用方式 C：pip install qrcode[pil]")


# ------------------------------------------------------------
# 默认后端地址（本机 Node.js 服务）
# ------------------------------------------------------------
DEFAULT_WS_URL = "ws://127.0.0.1:9999/"


# ------------------------------------------------------------
# 默认局域网 IP（用于生成给手机扫码的二维码 URL）
#
# 优先读取环境变量 DGLAB_LAN_IP。
# 没设置时使用示例地址 192.168.1.100。
#
# CMD 示例：
#   set DGLAB_LAN_IP=192.168.x.x
#
# PowerShell 示例：
#   $env:DGLAB_LAN_IP="192.168.x.x"
# ------------------------------------------------------------
DEFAULT_LAN_IP = os.getenv("DGLAB_LAN_IP", "192.168.1.100")


class DGLabWSClient:
    """DG-LAB 官方后端 WebSocket 客户端（单例）"""

    def __init__(self, ws_url: str = DEFAULT_WS_URL):
        self.ws_url = ws_url
        self.client_id: Optional[str] = None
        self.target_id: Optional[str] = None
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._should_stop = False

        # 状态回调
        self._on_paired: Optional[Callable[[str, str], None]] = None
        self._on_unpaired: Optional[Callable[[], None]] = None

    # --------------------------------------------------------
    # 对外查询接口
    # --------------------------------------------------------
    def is_connected(self) -> bool:
        """是否已连接到后端"""
        return self._ws is not None and self.client_id is not None

    def is_paired(self) -> bool:
        """是否已与 APP 配对成功"""
        return self.is_connected() and self.target_id is not None

    def get_qrcode_url(self, lan_ip: str = DEFAULT_LAN_IP) -> Optional[str]:
        """
        生成 APP 扫码用的二维码 URL。

        注意：
        只有拿到 clientId 后才能生成有效 URL。
        """
        if not self.client_id:
            return None

        port = self.ws_url.split(":")[-1].rstrip("/")

        return (
            f"https://www.dungeon-lab.com/app-download.php"
            f"#DGLAB-SOCKET#ws://{lan_ip}:{port}/{self.client_id}"
        )

    def show_qrcode(
        self,
        lan_ip: str = DEFAULT_LAN_IP,
        save_path: Optional[str] = None,
    ) -> bool:
        """
        把当前 clientId 对应的二维码 URL 画成图片并弹窗显示。

        同时保存一份 PNG 到磁盘，便于反复扫描或备份。

        参数：
            lan_ip    : 写进二维码的局域网 IP（手机扫码时连这个 IP）
            save_path : PNG 保存路径，默认 ./qrcode_latest.png

        返回：
            True  -> 成功生成图片
            False -> 未安装 qrcode、未拿到 clientId、或生成失败
        """
        if not _HAS_QRCODE:
            return False

        url = self.get_qrcode_url(lan_ip)

        if not url:
            print("[DGLAB WS] 暂无 clientId，无法生成二维码")
            return False

        try:
            img = qrcode.make(url)

            # 默认保存到当前工作目录下的 qrcode_latest.png
            if save_path is None:
                save_path = os.path.join(os.getcwd(), "qrcode_latest.png")

            img.save(save_path)
            print(f"[DGLAB WS] 二维码图片已保存：{save_path}")

            # 弹出系统默认看图工具显示二维码
            img.show()
            print("[DGLAB WS] 二维码图片已弹出，请用 DG-LAB APP 扫描")

            return True

        except Exception as e:
            print(f"[DGLAB WS] 生成二维码失败（不影响 WS 连接）：{e}")
            return False

    def set_pair_callbacks(
        self,
        on_paired: Optional[Callable[[str, str], None]] = None,
        on_unpaired: Optional[Callable[[], None]] = None,
    ):
        """注册配对/解绑回调，让 dglab_sender 能感知状态变化"""
        self._on_paired = on_paired
        self._on_unpaired = on_unpaired

    # --------------------------------------------------------
    # 连接管理
    # --------------------------------------------------------
    def start(self):
        """启动后台连接线程（非阻塞）"""
        if self._thread is not None and self._thread.is_alive():
            print("[DGLAB WS] 已经在运行，跳过 start")
            return

        self._should_stop = False

        self._thread = threading.Thread(
            target=self._run_forever,
            daemon=True,
            name="DGLabWSClient",
        )
        self._thread.start()

        print(f"[DGLAB WS] 已启动，目标后端：{self.ws_url}")

    def stop(self):
        """停止连接"""
        self._should_stop = True

        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def _run_forever(self):
        """后台线程主循环：连接 → 断开 → 重连，循环往复"""
        while not self._should_stop:
            try:
                self._ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(
                    ping_interval=30,
                    ping_timeout=10,
                )

            except Exception as e:
                print(f"[DGLAB WS] 连接异常：{e}")

            if self._should_stop:
                break

            print("[DGLAB WS] 5 秒后重连...")

            with self._lock:
                self.client_id = None
                self.target_id = None

            time.sleep(5)

    # --------------------------------------------------------
    # 事件回调
    # --------------------------------------------------------
    def _on_open(self, ws):
        print("[DGLAB WS] 已连接到后端，等待 clientId 分配...")

    def _on_message(self, ws, raw_msg):
        try:
            msg = json.loads(raw_msg)
        except json.JSONDecodeError:
            print(f"[DGLAB WS] 收到非 JSON 消息：{raw_msg}")
            return

        msg_type = msg.get("type")

        if msg_type == "bind":
            self._handle_bind(msg)

        elif msg_type == "break":
            self._handle_break(msg)

        elif msg_type == "error":
            print(f"[DGLAB WS] 收到错误：code={msg.get('message')}, raw={msg}")

        elif msg_type == "heartbeat":
            # 心跳包，服务端探活，不用回
            pass

        elif msg_type == "msg":
            self._handle_app_msg(msg)

        else:
            print(f"[DGLAB WS] 未知消息类型：{msg_type}, raw={msg}")

    def _on_error(self, ws, error):
        print(f"[DGLAB WS] WebSocket 错误：{error}")

    def _on_close(self, ws, status_code, close_msg):
        print(f"[DGLAB WS] 连接关闭：code={status_code}, msg={close_msg}")

        with self._lock:
            old_paired = self.target_id is not None
            self.client_id = None
            self.target_id = None

        if old_paired and self._on_unpaired:
            try:
                self._on_unpaired()
            except Exception as e:
                print(f"[DGLAB WS] on_unpaired 回调异常：{e}")

    # --------------------------------------------------------
    # 业务消息处理
    # --------------------------------------------------------
    def _handle_bind(self, msg: dict):
        client_id = msg.get("clientId", "")
        target_id = msg.get("targetId", "")
        message = msg.get("message", "")

        # 第一条 bind：服务端分配 clientId，targetId 为空
        if not target_id and message == "targetId":
            with self._lock:
                self.client_id = client_id

            print(f"[DGLAB WS] 收到 clientId：{client_id}")
            print("[DGLAB WS] 二维码 URL：")
            print(f"           {self.get_qrcode_url(DEFAULT_LAN_IP)}")

            # 自动把二维码画成图片弹窗 + 保存 PNG
            self.show_qrcode(DEFAULT_LAN_IP)

            return

        # 第二条 bind：APP 扫码配对，message="200" 表示成功
        if message == "200":
            with self._lock:
                self.client_id = client_id
                self.target_id = target_id

            print(f"[DGLAB WS] 配对成功！clientId={client_id}, targetId={target_id}")

            if self._on_paired:
                try:
                    self._on_paired(client_id, target_id)
                except Exception as e:
                    print(f"[DGLAB WS] on_paired 回调异常：{e}")

            return

        # 配对失败
        if message in ("400", "401"):
            print(f"[DGLAB WS] 配对失败：code={message}")
            return

        print(f"[DGLAB WS] 未知 bind 消息：{msg}")

    def _handle_break(self, msg: dict):
        code = msg.get("message", "")
        print(f"[DGLAB WS] 对方断开：code={code}")

        with self._lock:
            self.target_id = None

        if self._on_unpaired:
            try:
                self._on_unpaired()
            except Exception as e:
                print(f"[DGLAB WS] on_unpaired 回调异常：{e}")

    def _handle_app_msg(self, msg: dict):
        """APP 通过服务端转发回来的消息（强度回传 / 反馈按钮）"""
        message = msg.get("message", "")

        if message.startswith("strength-"):
            # 格式：strength-A强度+B强度+A上限+B上限
            print(f"[DGLAB WS] APP 强度回传：{message}")

        elif message.startswith("feedback-"):
            print(f"[DGLAB WS] APP 反馈按钮：{message}")

        else:
            print(f"[DGLAB WS] APP 转发消息：{message}")

    # --------------------------------------------------------
    # 发送接口
    # --------------------------------------------------------
    def send_json(self, payload: dict) -> bool:
        """
        发送 JSON 消息。

        会自动填充 clientId / targetId。
        返回 True 表示已发出，False 表示未发出。
        """
        if not self.is_paired():
            print(f"[DGLAB WS] 未配对，丢弃消息：{payload}")
            return False

        with self._lock:
            payload["clientId"] = self.client_id
            payload["targetId"] = self.target_id

        try:
            self._ws.send(json.dumps(payload))
            return True

        except Exception as e:
            print(f"[DGLAB WS] 发送失败：{e}")
            return False


# ------------------------------------------------------------
# 模块级单例
# ------------------------------------------------------------
_client_instance: Optional[DGLabWSClient] = None
_instance_lock = threading.Lock()


def get_client() -> DGLabWSClient:
    """获取全局唯一的 WS 客户端实例"""
    global _client_instance

    with _instance_lock:
        if _client_instance is None:
            _client_instance = DGLabWSClient()

        return _client_instance

