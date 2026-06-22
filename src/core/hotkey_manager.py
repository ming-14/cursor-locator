"""
@file hotkey_manager.py
@brief 全局热键管理器，多策略自动降级 + 冲突检测

策略优先级：
  1. RegisterHotKey — 系统级，Windows 内核管理，通过 WM_HOTKEY 窗口消息响应
  2. WH_KEYBOARD_LL — 低层键盘钩子，系统级，需在有消息泵的线程中安装
  3. GetAsyncKeyState — 应用级轮询，无系统依赖，响应延迟约 50ms

冲突检测：临时调用 RegisterHotKey 判断快捷键是否已被其他程序占用。
"""

import ctypes
import ctypes.wintypes as w
import threading
import time

from src.infra.win32_api import (
    MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT,
    WM_HOTKEY, WH_KEYBOARD_LL, HC_ACTION, _KBDLLHOOKSTRUCT,
)

# ── 兼容旧版 Python 缺少的 wintypes 类型 ──
if not hasattr(w, 'LRESULT'):
    w.LRESULT = ctypes.c_ssize_t if hasattr(ctypes, 'c_ssize_t') else ctypes.c_longlong

# ── 修饰键映射 ──
_MOD_MASK = {
    'ctrl':  MOD_CONTROL,
    'alt':   MOD_ALT,
    'shift': MOD_SHIFT,
    'win':   MOD_WIN,
}

_MOD_VK = {
    'ctrl':  0x11,
    'alt':   0x12,
    'shift': 0x10,
    'win':   0x5B,
}

_MOD_DISPLAY = {
    'ctrl':  'Ctrl',
    'alt':   'Alt',
    'shift': 'Shift',
    'win':   'Win',
}

# ── 虚拟键码查找表 ──
KEY_VK_MAP = {}
for i in range(0x41, 0x5B):
    KEY_VK_MAP[chr(i).lower()] = i
for i in range(0x30, 0x3A):
    KEY_VK_MAP[chr(i)] = i
KEY_VK_MAP.update({
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
    'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
    'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
})
KEY_VK_MAP.update({
    'space':     0x20,
    'tab':       0x09,
    'return':    0x0D,
    'backspace': 0x08,
    'delete':    0x2E,
    'insert':    0x2D,
    'home':      0x24,
    'end':       0x23,
    'prior':     0x21,
    'next':      0x22,
    'up':        0x26,
    'down':      0x28,
    'left':      0x25,
    'right':     0x27,
    'escape':    0x1B,
})
_VK_KEY_MAP = {v: k for k, v in KEY_VK_MAP.items()}


# ============================================================
# Hotkey 类
# ============================================================
class Hotkey:
    __slots__ = ('modifiers', 'key', 'vk')

    def __init__(self, modifiers=None, key='', vk=0):
        _ORDER = {'ctrl': 0, 'alt': 1, 'shift': 2, 'win': 3}
        self.modifiers = sorted((m.lower() for m in (modifiers or [])),
                                key=lambda x: _ORDER.get(x, 99))
        self.key = key.lower()
        self.vk = vk

    def __str__(self):
        parts = [_MOD_DISPLAY.get(m, m.capitalize()) for m in self.modifiers]
        parts.append(self.key.upper())
        return '+'.join(parts)

    def __eq__(self, other):
        if not isinstance(other, Hotkey):
            return NotImplemented
        return self.modifiers == other.modifiers and self.vk == other.vk

    def __hash__(self):
        return hash((tuple(self.modifiers), self.vk))

    def mod_mask(self):
        mask = 0
        for m in self.modifiers:
            mask |= _MOD_MASK.get(m, 0)
        return mask

    def to_dict(self):
        return {'modifiers': self.modifiers.copy(), 'key': self.key, 'vk': self.vk}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get('modifiers', []), d.get('key', ''), d.get('vk', 0))

    @classmethod
    def parse(cls, s):
        parts = s.lower().split('+')
        modifiers = [p for p in parts[:-1] if p in _MOD_MASK]
        key_part = parts[-1]
        vk = KEY_VK_MAP.get(key_part, 0)
        if not vk:
            return None
        return cls(modifiers, key_part, vk)

    @classmethod
    def from_mod_vk(cls, mod, vk):
        modifiers = []
        if mod & MOD_CONTROL:
            modifiers.append('ctrl')
        if mod & MOD_ALT:
            modifiers.append('alt')
        if mod & MOD_SHIFT:
            modifiers.append('shift')
        if mod & MOD_WIN:
            modifiers.append('win')
        key = _VK_KEY_MAP.get(vk, f'vk_{vk:#04x}')
        return cls(modifiers, key, vk)


PARSABLE_KEYS = set(KEY_VK_MAP.keys())
MODIFIER_NAMES = set(_MOD_MASK.keys())


# ── 安全检测 ──
_SAFETY_WARNINGS = {
    ('c', frozenset({'ctrl'})):        'Ctrl+C — 复制，几乎全部应用通用',
    ('v', frozenset({'ctrl'})):        'Ctrl+V — 粘贴',
    ('x', frozenset({'ctrl'})):        'Ctrl+X — 剪切',
    ('z', frozenset({'ctrl'})):        'Ctrl+Z — 撤销',
    ('y', frozenset({'ctrl'})):        'Ctrl+Y — 重做',
    ('a', frozenset({'ctrl'})):        'Ctrl+A — 全选',
    ('s', frozenset({'ctrl'})):        'Ctrl+S — 保存',
    ('f', frozenset({'ctrl'})):        'Ctrl+F — 查找',
    ('h', frozenset({'ctrl'})):        'Ctrl+H — 替换',
    ('p', frozenset({'ctrl'})):        'Ctrl+P — 打印',
    ('n', frozenset({'ctrl'})):        'Ctrl+N — 新建',
    ('o', frozenset({'ctrl'})):        'Ctrl+O — 打开',
    ('w', frozenset({'ctrl'})):        'Ctrl+W — 关闭标签页',
    ('b', frozenset({'ctrl'})):        'Ctrl+B — 加粗',
    ('i', frozenset({'ctrl'})):        'Ctrl+I — 斜体',
    ('u', frozenset({'ctrl'})):        'Ctrl+U — 下划线',
    ('t', frozenset({'ctrl'})):        'Ctrl+T — 新建标签页',
    ('r', frozenset({'ctrl'})):        'Ctrl+R — 刷新',
    ('e', frozenset({'ctrl'})):        'Ctrl+E — 搜索栏定位',
    ('d', frozenset({'ctrl'})):        'Ctrl+D — 收藏/删除',
    ('k', frozenset({'ctrl'})):        'Ctrl+K — 链接/搜索',
    ('l', frozenset({'ctrl'})):        'Ctrl+L — 地址栏',
    ('j', frozenset({'ctrl'})):        'Ctrl+J — 下载',
    ('f4', frozenset({'alt'})):        'Alt+F4 — 关闭窗口',
    ('tab', frozenset({'alt'})):       'Alt+Tab — 切换窗口',
    ('space', frozenset({'alt'})):     'Alt+Space — 窗口菜单',
    ('enter', frozenset({'alt'})):     'Alt+Enter — 属性',
    ('d', frozenset({'alt'})):         'Alt+D — 地址栏定位',
    ('d', frozenset({'win'})):         'Win+D — 显示桌面',
    ('e', frozenset({'win'})):         'Win+E — 资源管理器',
    ('r', frozenset({'win'})):         'Win+R — 运行',
    ('i', frozenset({'win'})):         'Win+I — 设置',
    ('s', frozenset({'win'})):         'Win+S — 搜索',
    ('l', frozenset({'win'})):         'Win+L — 锁定',
    ('x', frozenset({'win'})):         'Win+X — 快捷菜单',
    ('v', frozenset({'win'})):         'Win+V — 剪贴板历史',
    ('c', frozenset({'ctrl', 'shift'})): 'Ctrl+Shift+C — IDE 中注释代码等',
    ('v', frozenset({'ctrl', 'shift'})): 'Ctrl+Shift+V — 纯文本粘贴',
    ('z', frozenset({'ctrl', 'shift'})): 'Ctrl+Shift+Z — 重做',
    ('f', frozenset({'ctrl', 'shift'})): 'Ctrl+Shift+F — IDE/浏览器全局搜索',
    ('h', frozenset({'ctrl', 'shift'})): 'Ctrl+Shift+H — 替换/历史',
    ('n', frozenset({'ctrl', 'shift'})): 'Ctrl+Shift+N — 无痕模式/新建文件夹',
    ('t', frozenset({'ctrl', 'shift'})): 'Ctrl+Shift+T — 恢复关闭的标签页',
    ('s', frozenset({'ctrl', 'shift'})): 'Ctrl+Shift+S — 另存为',
    ('p', frozenset({'ctrl', 'shift'})): 'Ctrl+Shift+P — 打印/命令面板',
}
_SAFETY_MORE = {
    ('f1', frozenset()):       'F1 — 帮助',
    ('f5', frozenset()):       'F5 — 刷新',
    ('delete', frozenset()):   'Delete — 删除',
    ('tab', frozenset()):      'Tab — 切换焦点',
    ('space', frozenset()):    'Space — 翻页/选中',
    ('escape', frozenset()):   'Esc — 取消/退出',
    ('enter', frozenset()):    'Enter — 确认',
    ('delete', frozenset({'shift'})): 'Shift+Delete — 永久删除',
}
_SAFETY_WARNINGS.update(_SAFETY_MORE)


def check_hotkey_safety(hotkey):
    mod_set = frozenset(hotkey.modifiers)
    key = hotkey.key
    key_and_mod = (key, mod_set)
    if key_and_mod in _SAFETY_WARNINGS:
        return False, _SAFETY_WARNINGS[key_and_mod]
    if len(mod_set) == 1 and not mod_set.intersection({'shift'}):
        mod = next(iter(mod_set))
        if mod in ('ctrl', 'alt', 'win') and len(key) == 1 and key.isalpha():
            return False, f'{mod.capitalize()}+{key.upper()} 为常用快捷键，可能与其他应用冲突'
    return True, ''


# ============================================================
# HotkeyManager
# ============================================================
class HotkeyManager:
    LEVEL_NAMES = [
        'RegisterHotKey（系统级）',
        'WH_KEYBOARD_LL 钩子（系统级）',
        'GetAsyncKeyState 轮询（应用级）',
    ]

    def __init__(self):
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        self._hotkey = None
        self._hwnd = 0
        self._id = 0
        self._callback = None
        self._level = -1
        self._active = False
        self._strategy0_callback = None
        self._hook_handle = None
        self._hook_proc = None
        self._hook_triggered = False
        self._poll_thread = None
        self._poll_stop = threading.Event()
        self._poll_prev = False

    @property
    def active(self):
        return self._active

    @property
    def level(self):
        return self._level

    def level_name(self):
        if 0 <= self._level < len(self.LEVEL_NAMES):
            return self.LEVEL_NAMES[self._level]
        return '未激活'

    def register(self, hotkey, hwnd, callback, hotkey_id=1):
        self.unregister()
        self._hotkey = hotkey
        self._hwnd = hwnd
        self._id = hotkey_id
        self._callback = callback
        if self._try_register():
            self._level = 0
            self._active = True
            return True, 0, self.LEVEL_NAMES[0]
        if self._try_hook():
            self._level = 1
            self._active = True
            return True, 1, self.LEVEL_NAMES[1]
        if self._try_poll():
            self._level = 2
            self._active = True
            return True, 2, self.LEVEL_NAMES[2]
        self._active = False
        return False, -1, '所有策略均失败'

    def unregister(self):
        if not self._active:
            return
        if self._level == 0:
            self._user32.UnregisterHotKey(self._hwnd, self._id)
        elif self._level == 1:
            self._stop_hook()
        elif self._level == 2:
            self._stop_poll()
        self._active = False
        self._hotkey = None
        self._callback = None
        self._strategy0_callback = None
        self._level = -1

    @staticmethod
    def test_available(hotkey):
        user32 = ctypes.windll.user32
        _RegisterHotKey = user32.RegisterHotKey
        _RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, w.UINT, w.UINT]
        _RegisterHotKey.restype = w.BOOL
        _UnregisterHotKey = user32.UnregisterHotKey
        _UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
        _UnregisterHotKey.restype = w.BOOL
        test_id = 0x7FFF
        mod = hotkey.mod_mask()
        vk = hotkey.vk
        for use_norepeat in (True, False):
            flags = mod | (MOD_NOREPEAT if use_norepeat else 0)
            result = _RegisterHotKey(None, test_id, flags, vk)
            if result:
                _UnregisterHotKey(None, test_id)
                safe, warn = check_hotkey_safety(hotkey)
                if not safe:
                    return True, warn
                return True, ''
        ec = ctypes.get_last_error()
        if ec == 0 or ec == 1409:
            return False, '该快捷键已被占用，请更换'
        return False, f'注册失败 (系统错误码: {ec})'

    def _try_register(self):
        if not self._hwnd:
            return False
        mod = self._hotkey.mod_mask()
        vk = self._hotkey.vk
        for use_norepeat in (True, False):
            flags = mod | (MOD_NOREPEAT if use_norepeat else 0)
            if self._user32.RegisterHotKey(self._hwnd, self._id, flags, vk):
                return True
        return False

    def strategy0_hotkey_matches(self, msg, wparam, lparam):
        return (self._active and self._level == 0
                and msg == WM_HOTKEY and wparam == self._id)

    def _try_hook(self):
        HOOKPROC = ctypes.WINFUNCTYPE(w.LRESULT, ctypes.c_int, w.WPARAM, w.LPARAM)
        _SetWindowsHookExW = self._user32.SetWindowsHookExW
        _SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, w.DWORD]
        _SetWindowsHookExW.restype = ctypes.c_void_p
        _UnhookWindowsHookEx = self._user32.UnhookWindowsHookEx
        _UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        _UnhookWindowsHookEx.restype = w.BOOL
        _CallNextHookEx = self._user32.CallNextHookEx
        _CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, w.WPARAM, w.LPARAM]
        _CallNextHookEx.restype = w.LRESULT
        hotkey = self._hotkey
        cb = self._callback
        mod_vks = [_MOD_VK[m] for m in hotkey.modifiers if m in _MOD_VK]
        target_vk = hotkey.vk
        user32 = self._user32
        state = {'triggered': False}

        def hook_fn(nCode, wParam, lParam):
            if nCode == HC_ACTION and wParam in (0x0100, 0x0104):
                kbd = ctypes.cast(lParam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
                current_vk = kbd.vkCode
                all_mods = all(bool(user32.GetAsyncKeyState(mvk) & 0x8000) for mvk in mod_vks)
                if all_mods and current_vk == target_vk:
                    if not state['triggered']:
                        state['triggered'] = True
                        if cb:
                            cb()
                    return 1
                else:
                    if state['triggered'] and current_vk != target_vk:
                        state['triggered'] = False
            return _CallNextHookEx(None, nCode, wParam, lParam)

        self._hook_proc = HOOKPROC(hook_fn)
        hMod = self._kernel32.GetModuleHandleW(None)
        self._hook_handle = _SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, hMod, 0)
        if not self._hook_handle:
            self._hook_proc = None
            return False
        return True

    def _stop_hook(self):
        _UnhookWindowsHookEx = self._user32.UnhookWindowsHookEx
        _UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        _UnhookWindowsHookEx.restype = w.BOOL
        if self._hook_handle:
            _UnhookWindowsHookEx(self._hook_handle)
            self._hook_handle = None
        self._hook_proc = None

    def _try_poll(self):
        self._poll_stop.clear()
        self._poll_prev = False
        hotkey = self._hotkey
        cb = self._callback
        mod_vks = [_MOD_VK[m] for m in hotkey.modifiers if m in _MOD_VK]
        target_vk = hotkey.vk
        user32 = self._user32

        def loop():
            while not self._poll_stop.is_set():
                all_mods = all(bool(user32.GetAsyncKeyState(mvk) & 0x8000) for mvk in mod_vks)
                key_down = bool(user32.GetAsyncKeyState(target_vk) & 0x8000)
                combo = all_mods and key_down
                if combo and not self._poll_prev:
                    self._poll_prev = True
                    if cb:
                        cb()
                elif not combo:
                    self._poll_prev = False
                time.sleep(0.05)

        self._poll_thread = threading.Thread(target=loop, daemon=True, name='HotkeyPoll')
        self._poll_thread.start()
        return True

    def _stop_poll(self):
        self._poll_stop.set()
        self._poll_thread = None