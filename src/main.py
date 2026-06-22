"""
@file main.py
@brief 鼠标小圆圈 — 入口编排

负责启动后台线程（环线 + 托盘）和 Tkinter 主循环。
"""

import sys
import os
import threading
import time
import queue
import tkinter as tk
import ctypes

# 确保项目根目录在 sys.path 中（run.py 已做，但防止直接 python src/main.py）
_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from src.core.config import Config
from src.service import ring_worker
from src.service import tray_worker
from src.ui.settings_panel import SettingsPanel
from src.infra.win32_api import *
from src.core.hotkey_manager import Hotkey
from src.infra.logger import init_logging, get_logger


# ============================================================
# 后台线程
# ============================================================
def _run_backend(cfg: Config, mq: queue.Queue):
    """环线 + 托盘后台线程：创建 Win32 窗口后进入消息循环。"""
    ring_worker.init_module(mq)

    tray_hwnd = tray_worker.init_tray(cfg, mq)

    for _ in range(50):
        if tray_worker.is_tray_created():
            break
        time.sleep(0.01)

    ring = ring_worker.MouseRingWindow(cfg)
    ring.show()
    ring._update_frame(0, 0, cfg.get('outer_radius'),
                       cfg.get('inner_radius'), cfg.get('alpha'))

    success, init_hotkey, level, msg = tray_worker.register_initial_hotkey(cfg)

    if not success and init_hotkey.key:
        _MessageBoxW = ctypes.windll.user32.MessageBoxW
        ret = _MessageBoxW(
            tray_hwnd,
            f'快捷键 {init_hotkey} 注册失败（{msg}）。\n\n'
            '是否尝试使用 Ctrl+Alt+Shift+P？\n'
            '选择"是"将尝试注册默认快捷键，\n'
            '选择"否"将禁用快捷键。',
            '快捷键冲突',
            0x00000004 | 0x00000030)

        if ret == 6:
            default_hotkey = Hotkey(['ctrl', 'alt', 'shift'], 'p', 0x50)

            def on_hk():
                if mq is not None:
                    mq.put(MSG_TOGGLE)

            from src.core.hotkey_manager import HotkeyManager
            hk_mgr_retry = HotkeyManager()
            success2, level2, msg2 = hk_mgr_retry.register(
                default_hotkey, tray_hwnd, on_hk)

            if success2:
                cfg.set(
                    toggle_hotkey_modifiers=default_hotkey.modifiers,
                    toggle_hotkey_key=default_hotkey.key,
                    toggle_hotkey_vk=default_hotkey.vk,
                    toggle_hotkey_level=level2,
                    toggle_hotkey_level_msg=msg2,
                )
            else:
                cfg.set(toggle_hotkey_level=level2, toggle_hotkey_level_msg=msg2)
        else:
            cfg.set(toggle_hotkey_level=level, toggle_hotkey_level_msg=msg)

        if not success:
            cfg.set(
                toggle_hotkey_modifiers=[],
                toggle_hotkey_key='',
                toggle_hotkey_vk=0,
                toggle_hotkey_level=-1,
                toggle_hotkey_level_msg='快捷键已禁用',
            )
            _MessageBoxW(
                tray_hwnd,
                f'默认快捷键 Ctrl+Alt+Shift+P 也无法注册（{msg}）。\n\n'
                '快捷键已被禁用，请在设置面板中手动更换。',
                '快捷键不可用',
                0x00000000 | 0x00000030)
    else:
        cfg.set(toggle_hotkey_level=level, toggle_hotkey_level_msg=msg)

    cfg.save()

    if mq is not None:
        mq.put({
            'type': MSG_HOTKEY_LVL,
            'level': cfg.get('toggle_hotkey_level'),
            'msg': cfg.get('toggle_hotkey_level_msg'),
        })

    msg = MSG()
    while ring.running:
        ret = _GetMessageW(byref(msg), NULL, 0, 0)
        if ret <= 0:
            break
        _TranslateMessage(byref(msg))
        _DispatchMessageW(byref(msg))

    ring.cleanup()
    tray_worker.cleanup(cfg)
    _PostQuitMessage(0)


# ============================================================
# 主入口
# ============================================================
def main():
    init_logging()
    log = get_logger('Main')
    log.info('鼠标小圆圈启动')
    cfg = Config()
    mq = queue.Queue()

    t = threading.Thread(target=_run_backend, args=(cfg, mq), daemon=True)
    t.start()

    for _ in range(50):
        if tray_worker.is_tray_created():
            break
        time.sleep(0.05)

    root = tk.Tk()
    root.attributes('-topmost', True)
    root.withdraw()

    def on_hotkey_change():
        tray_worker.reload_hotkey()

    settings = SettingsPanel(root, cfg, mq, on_hotkey_change=on_hotkey_change)

    def poll_queue():
        try:
            while True:
                msg = mq.get_nowait()
                if isinstance(msg, dict):
                    settings.handle_message(msg)
                elif msg == MSG_SHOW:
                    settings._show_panel()
                    root.lift()
                    root.focus_force()
                elif msg == MSG_TOGGLE:
                    if root.state() == 'normal' and root.winfo_viewable():
                        settings._hide_panel()
                    else:
                        settings._show_panel()
                        root.lift()
                        root.focus_force()
                elif msg == MSG_EXIT:
                    cfg.save()
                    root.quit()
                    from src.service.ring_worker import MouseRingWindow
                    ring = MouseRingWindow._instance
                    if ring:
                        ring.running = False
                    return
        except queue.Empty:
            pass
        if root.winfo_exists():
            root.after(100, poll_queue)

    root.after(100, poll_queue)
    root.mainloop()


if __name__ == '__main__':
    main()