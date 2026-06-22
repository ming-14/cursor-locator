"""
@file run.py
@brief 鼠标小圆圈 — 启动脚本
"""

import sys
import os
import ctypes

# ══════════════════════════════════════════════════════════
# Python 版本检查（3.8+）
# ══════════════════════════════════════════════════════════
if sys.version_info < (3, 8):
    _msg = f'需要 Python 3.8 或更高版本，当前版本：{sys.version}'
    try:
        ctypes.windll.user32.MessageBoxW(0, _msg, '版本不兼容', 0x10)
    except Exception:
        print(_msg)
    sys.exit(1)

# ══════════════════════════════════════════════════════════
# 单实例检测（Named Mutex）
# ══════════════════════════════════════════════════════════
_MUTEX_NAME = 'Local\\MouseCircleSingleInstance'
_kernel32   = ctypes.windll.kernel32
_user32     = ctypes.windll.user32

_mutex = _kernel32.CreateMutexW(None, False, _MUTEX_NAME)
if _kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    # 已有实例在运行，定位其控制面板窗口并激活
    _WND_TITLE = '鼠标小圆圈 - 控制面板'
    _hwnd = _user32.FindWindowW(None, _WND_TITLE)
    if _hwnd:
        _user32.ShowWindow(_hwnd, 9)  # SW_RESTORE = 9
        _user32.SetForegroundWindow(_hwnd)
    sys.exit(0)

# ══════════════════════════════════════════════════════════
# 自动最小化当前进程的控制台窗口
# ══════════════════════════════════════════════════════════
_hcon = _kernel32.GetConsoleWindow()
if _hcon:
    _user32.ShowWindow(_hcon, 6)  # SW_MINIMIZE = 6

# 将项目根目录加入 sys.path，确保可导入 src/ 下模块
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.main import main

if __name__ == '__main__':
    main()