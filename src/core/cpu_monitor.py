"""
@file cpu_monitor.py
@brief 进程 CPU 占用率监控（基于 Win32 GetProcessTimes）
"""

import ctypes
import ctypes.wintypes
import os
import time


# ============================================================
# Win32 FILETIME 结构体
# ============================================================
class _FILETIME(ctypes.Structure):
    _fields_ = [('dwLowDateTime', ctypes.c_uint32),
                ('dwHighDateTime', ctypes.c_uint32)]

_kernel32 = ctypes.windll.kernel32
_GetProcessTimes = _kernel32.GetProcessTimes
_GetProcessTimes.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.POINTER(_FILETIME), ctypes.POINTER(_FILETIME),
    ctypes.POINTER(_FILETIME), ctypes.POINTER(_FILETIME),
]
_GetProcessTimes.restype = ctypes.wintypes.BOOL
_GetCurrentProcess = _kernel32.GetCurrentProcess
_GetCurrentProcess.argtypes = []
_GetCurrentProcess.restype = ctypes.wintypes.HANDLE


class CPUMonitor:
    """利用 GetProcessTimes 计算进程 CPU 占用率（匹配任务管理器显示）"""

    def __init__(self):
        self._cpu_count = os.cpu_count() or 1
        self._prev_kernel = _FILETIME()
        self._prev_user = _FILETIME()
        self._prev_time = time.monotonic()
        self._snapshot()

    def _snapshot(self):
        creation = _FILETIME()
        exit_t = _FILETIME()
        _GetProcessTimes(_GetCurrentProcess(),
                         ctypes.byref(creation), ctypes.byref(exit_t),
                         ctypes.byref(self._prev_kernel),
                         ctypes.byref(self._prev_user))
        self._prev_time = time.monotonic()

    def get_cpu_percent(self):
        """返回 (相对总容量百分比, 相对单核百分比)"""
        creation = _FILETIME()
        exit_t = _FILETIME()
        kernel = _FILETIME()
        user = _FILETIME()
        _GetProcessTimes(_GetCurrentProcess(),
                         ctypes.byref(creation), ctypes.byref(exit_t),
                         ctypes.byref(kernel), ctypes.byref(user))
        now = time.monotonic()

        prev_proc = ((self._prev_kernel.dwHighDateTime << 32
                      | self._prev_kernel.dwLowDateTime)
                     + (self._prev_user.dwHighDateTime << 32
                        | self._prev_user.dwLowDateTime))
        curr_proc = ((kernel.dwHighDateTime << 32 | kernel.dwLowDateTime)
                     + (user.dwHighDateTime << 32 | user.dwLowDateTime))

        proc_delta = curr_proc - prev_proc
        time_delta = int((now - self._prev_time) * 10000000)

        self._prev_kernel = kernel
        self._prev_user = user
        self._prev_time = now

        if time_delta <= 0:
            return (0.0, 0.0)
        per_core = (proc_delta / time_delta) * 100.0
        return (per_core / self._cpu_count, per_core)