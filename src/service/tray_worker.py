"""
@file tray_worker.py
@brief 托盘图标线程：托盘窗口 + 快捷键注册
"""

import queue

import ctypes
import ctypes.wintypes as w

from src.infra.win32_api import *
from src.core.config import Config
from src.core.hotkey_manager import Hotkey, HotkeyManager

# ── 模块级状态 ──
_tray_hwnd: int = 0
_tray_created = False
_tray_hotkey_triggered = False
_hotkey_mgr: HotkeyManager = None
_msg_queue: queue.Queue = None
_app_cfg: Config = None

TRAY_MENU_SHOW = 1001
TRAY_MENU_EXIT = 1002

HOTKEY_RESET_TIMER_ID = 101
HOTKEY_RESET_MS = 200


# ============================================================
# 快捷键注册
# ============================================================
def _reload_hotkey_internal():
    global _hotkey_mgr, _msg_queue, _app_cfg
    cfg = _app_cfg
    if cfg is None:
        return

    mods = cfg.get('toggle_hotkey_modifiers')
    key_name = cfg.get('toggle_hotkey_key')
    vk = cfg.get('toggle_hotkey_vk')
    hotkey = Hotkey(mods, key_name, vk)

    def on_hotkey_press():
        if _msg_queue is not None:
            _msg_queue.put(MSG_TOGGLE)

    if _hotkey_mgr is not None:
        if _hotkey_mgr.active:
            _hotkey_mgr.unregister()
        success, level, msg = _hotkey_mgr.register(hotkey, _tray_hwnd, on_hotkey_press)
    else:
        _hotkey_mgr = HotkeyManager()
        success, level, msg = _hotkey_mgr.register(hotkey, _tray_hwnd, on_hotkey_press)

    if cfg is not None:
        cfg.set(toggle_hotkey_level=level, toggle_hotkey_level_msg=msg)
        if _msg_queue is not None:
            _msg_queue.put({
                'type': MSG_HOTKEY_LVL,
                'level': level,
                'msg': msg,
            })


def reload_hotkey():
    global _tray_hwnd
    if _tray_hwnd:
        _PostMessageW(_tray_hwnd, WM_RELOAD_HOTKEY, 0, 0)


# ============================================================
# 托盘图标
# ============================================================
def _add_tray_icon(hwnd):
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hwnd = hwnd
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON
    nid.uCallbackMessage = WM_TRAY_CALLBACK
    nid.hIcon = _LoadIconW(NULL, c_void_p(32512))
    _Shell_NotifyIconW(NIM_ADD, byref(nid))


def _remove_tray_icon(hwnd):
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hwnd = hwnd
    nid.uID = 1
    _Shell_NotifyIconW(NIM_DELETE, byref(nid))


def _show_tray_menu(hwnd):
    pt = POINT()
    _GetCursorPos(byref(pt))
    menu = _CreatePopupMenu()
    if not menu:
        return
    flags = MF_BYPOSITION | MF_STRING
    _InsertMenuW(menu, 0, flags, TRAY_MENU_SHOW, '显示设置(&S)')
    _InsertMenuW(menu, 1, flags, TRAY_MENU_EXIT, '退出(&X)')
    _SetForegroundWindow(hwnd)
    _TrackPopupMenu(menu, TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, NULL)
    _DestroyMenu(menu)


def _show_settings_via_queue():
    global _msg_queue
    if _msg_queue is not None:
        _msg_queue.put(MSG_SHOW)


def _toggle_settings_via_queue():
    global _msg_queue
    if _msg_queue is not None:
        _msg_queue.put(MSG_TOGGLE)


def _exit_via_queue():
    global _msg_queue
    if _msg_queue is not None:
        _msg_queue.put(MSG_EXIT)


# ============================================================
# 托盘窗口过程
# ============================================================
@WNDPROC
def _tray_wnd_proc(hwnd, msg, wparam, lparam):
    global _tray_created
    if msg == WM_CREATE:
        _add_tray_icon(hwnd)
        _tray_created = True
        return 0
    elif msg == WM_DESTROY:
        _remove_tray_icon(hwnd)
        _tray_created = False
        _PostQuitMessage(0)
        return 0
    elif msg == WM_HOTKEY:
        global _tray_hotkey_triggered
        if not _tray_hotkey_triggered:
            _tray_hotkey_triggered = True
            if _msg_queue is not None:
                _msg_queue.put(MSG_TOGGLE)
        _KillTimer(hwnd, c_void_p(HOTKEY_RESET_TIMER_ID))
        _SetTimer(hwnd, c_void_p(HOTKEY_RESET_TIMER_ID), HOTKEY_RESET_MS, NULL)
        return 0
    elif msg == WM_TIMER:
        if wparam == HOTKEY_RESET_TIMER_ID:
            _KillTimer(hwnd, c_void_p(HOTKEY_RESET_TIMER_ID))
            _tray_hotkey_triggered = False
        return 0
    elif msg == WM_RELOAD_HOTKEY:
        _reload_hotkey_internal()
        return 0
    elif msg == WM_TRAY_CALLBACK:
        if lparam == 0x0205:
            _show_tray_menu(hwnd)
        elif lparam == 0x0202:
            _toggle_settings_via_queue()
        return 0
    elif msg == WM_COMMAND:
        mid = wparam & 0xFFFF
        if mid == TRAY_MENU_SHOW:
            _show_settings_via_queue()
        elif mid == TRAY_MENU_EXIT:
            _exit_via_queue()
        return 0
    return _DefWindowProcW(hwnd, msg, wparam, lparam)


# ============================================================
# 初始化
# ============================================================
def init_tray(cfg: Config, mq: queue.Queue) -> int:
    global _tray_hwnd, _msg_queue, _app_cfg
    _msg_queue = mq
    _app_cfg = cfg

    hinst = _GetModuleHandleW(None)

    twc = WNDCLASSEXW()
    twc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    twc.style = 0
    twc.lpfnWndProc = ctypes.cast(_tray_wnd_proc, c_void_p)
    twc.cbClsExtra = 0
    twc.cbWndExtra = 0
    twc.hInstance = hinst
    twc.hIcon = NULL
    twc.hCursor = NULL
    twc.hbrBackground = NULL
    twc.lpszMenuName = None
    twc.lpszClassName = 'TrayNotifyClass'
    twc.hIconSm = NULL
    _RegisterClassExW(byref(twc))

    _tray_hwnd = _CreateWindowExW(
        0, 'TrayNotifyClass', 'TrayNotify', 0,
        0, 0, 0, 0, NULL, NULL, hinst, NULL,
    )
    return _tray_hwnd


def is_tray_created() -> bool:
    return _tray_created


def register_initial_hotkey(cfg: Config):
    global _hotkey_mgr

    mods = cfg.get('toggle_hotkey_modifiers')
    key_name = cfg.get('toggle_hotkey_key')
    vk = cfg.get('toggle_hotkey_vk')
    init_hotkey = Hotkey(mods, key_name, vk)

    def on_hk():
        if _msg_queue is not None:
            _msg_queue.put(MSG_TOGGLE)

    _hotkey_mgr = HotkeyManager()
    success, level, msg = _hotkey_mgr.register(
        init_hotkey, _tray_hwnd, on_hk)

    return success, init_hotkey, level, msg


def cleanup(cfg: Config):
    global _hotkey_mgr, _tray_hwnd, _tray_created
    if _hotkey_mgr and _hotkey_mgr.active:
        _hotkey_mgr.unregister()
        _hotkey_mgr = None
    if _tray_hwnd:
        _remove_tray_icon(_tray_hwnd)
        _DestroyWindow(_tray_hwnd)
        _tray_hwnd = 0
    _tray_created = False