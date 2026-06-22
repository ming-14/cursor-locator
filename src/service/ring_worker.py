"""
@file ring_worker.py
@brief 环线窗口线程：MouseRingWindow + 低层鼠标钩子 + 窗口过程
"""

import math
import time
import queue

import ctypes

from src.infra.logger import get_logger

_log = get_logger('RingWorker')

from src.infra.win32_api import *
from src.core.config import Config
from src.core.rendering import build_alpha_mask, render_ring_from_mask
from src.core.pixel_color import get_pixel_color, compute_complement

# ── 运行时通过 _init_module 设置 ──
_msg_queue: queue.Queue = None

# ── 低层鼠标钩子全局状态 ──
_hook_handle = None
_hook_proc_ref = None
_hook_latest_x = 0
_hook_latest_y = 0

# ── 显示器刷新率（由 _get_display_timer_interval 缓存） ──
_display_freq = 0  # 0 = 未知


def _query_display_frequency() -> int:
    """查询当前显示器刷新率，缓存到模块级 _display_freq。

    @return 刷新率（Hz），0 表示未知
    """
    global _display_freq
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    try:
        if _EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, byref(dm)):
            freq = dm.dmDisplayFrequency
            if freq > 1:
                _display_freq = freq
                return freq
    except Exception:
        pass
    _display_freq = 0
    return 0


def _get_display_timer_interval() -> int:
    """获取原始显示器同步定时器间隔（ms）。

    返回的间隔 = round(1000 / 刷新率)，最低限值 4ms。
    同时更新模块级 _display_freq 供 UI 使用。

    @return 定时器间隔（毫秒）
    """
    freq = _query_display_frequency()
    if freq > 0:
        return max(4, int(round(1000.0 / freq)))
    return 4


def init_module(mq: queue.Queue):
    """设置模块级消息队列引用（在后台线程启动时调用）。"""
    global _msg_queue
    _msg_queue = mq
    _log.info('模块初始化完成')


def _send_refresh_rate_info():
    """将当前检测到的显示器刷新率推送到 UI 控制面板。"""
    global _msg_queue, _display_freq
    if _msg_queue is not None:
        _msg_queue.put({
            'type': MSG_REFRESH_RATE,
            'freq': _display_freq,
        })


# ============================================================
# 低层鼠标钩子回调
# ============================================================
@HOOKPROC
def _mouse_hook_proc(nCode, wParam, lParam):
    """WH_MOUSE_LL 钩子回调：记录最新鼠标位置，合并投递渲染消息。"""
    if nCode >= 0 and wParam == WM_MOUSEMOVE:
        global _hook_latest_x, _hook_latest_y
        p = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        _hook_latest_x = p.pt.x
        _hook_latest_y = p.pt.y
        win = MouseRingWindow._instance
        if win is not None and not win._hook_move_pending:
            win._hook_move_pending = True
            _PostMessageW(win.hwnd, WM_RING_MOUSE_MOVE, 0, 0)
    return _CallNextHookEx(None, nCode, wParam, lParam)


# ============================================================
# 环线窗口
# ============================================================
class MouseRingWindow:
    """圆环渲染窗口（运行在后台 Win32 消息循环线程）。"""

    _instance = None

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.hwnd = None
        self.hdc_mem = None
        self.hbitmap = None
        self.bits_ptr = None
        self.running = True
        self._size = 0
        self._color = (173, 216, 230)
        self._ring_center_x = 0
        self._ring_center_y = 0
        self._last_sample_time = time.monotonic()
        self._current_track_ms = cfg.get('track_interval')

        self._alpha_mask = None
        self._last_shape_outer = 0
        self._last_shape_inner = 0
        self._last_frame_key = None
        self._prev_on_ring = False
        self._hook_move_pending = False
        self._current_tracking_mode = None

        # ── 匀速平滑追踪（轮询模式用） ──
        self._smooth_from_x = 0.0       # 当前移动段起点 X
        self._smooth_from_y = 0.0       # 当前移动段起点 Y
        self._smooth_to_x = 0.0         # 当前移动段终点 X（采样时的鼠标位置）
        self._smooth_to_y = 0.0         # 当前移动段终点 Y
        self._smooth_start_time = 0.0   # 当前移动段开始时间
        self._smooth_duration = 0.0     # 移动段持续时间（= track_interval）
        self._last_track_time = 0.0     # 上次鼠标采样时间

        # ── 定时器参数（仅轮询模式使用） ──
        self._current_timer_interval = 4  # 当前 Win32 定时器间隔 (ms)

        MouseRingWindow._instance = self

        hinst = _GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0
        wc.lpfnWndProc = ctypes.cast(_ring_wnd_proc, c_void_p)
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinst
        wc.hIcon = NULL
        wc.hCursor = NULL
        wc.hbrBackground = NULL
        wc.lpszMenuName = None
        wc.lpszClassName = 'MouseRingClass'
        wc.hIconSm = NULL

        atom = _RegisterClassExW(byref(wc))
        if atom == 0:
            raise RuntimeError('注册窗口类失败')

        cfg_snap = cfg.snapshot()
        self._size = cfg_snap['outer_radius'] * 3

        ex_style = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT
        self.hwnd = _CreateWindowExW(
            ex_style, 'MouseRingClass', '鼠标圆环', WS_POPUP,
            0, 0, self._size, self._size, NULL, NULL, hinst, NULL,
        )
        if not self.hwnd:
            raise RuntimeError('创建窗口失败')

        _SetWindowDisplayAffinity(self.hwnd, WDA_EXCLUDEFROMCAPTURE)

        self._init_drawing()
        self._start_tracking()

    # ── 跟踪模式管理 ──

    def _start_tracking(self):
        mode = self.cfg.get('tracking_mode')
        if mode == 'hook':
            self._start_hook_tracking()
        else:
            self._start_timer_tracking()
        self._current_tracking_mode = mode
        # 首次启动时推送显示器刷新率信息
        _send_refresh_rate_info()

    def _compute_timer_interval(self, snap=None) -> int:
        """根据当前配置计算定时器间隔。

        支持三种模式：
          - auto（跟随显示器）：间隔 = 1000 / 刷新率 × 倍率
          - custom（自定义）：间隔 = 用户设定的毫秒值
        最终结果受跟踪频率约束：定时器不能比跟踪采样慢。

        @param snap  配置快照（可选，为 None 时自动获取）
        @return 最终定时器间隔（ms）
        """
        if snap is None:
            snap = self.cfg.snapshot()
        mode = snap.get('timer_mode', 'auto')
        if mode == 'custom':
            interval = max(4, snap.get('timer_interval_custom', 16))
        else:
            _query_display_frequency()
            freq = _display_freq
            if freq > 0:
                mult = snap.get('timer_multiplier', 1.0)
                interval = max(4, int(round(1000.0 / freq * mult)))
            else:
                interval = 4  # 无法检测时回退
        # 定时器频率不能低于跟踪频率，否则匀速插值无法及时响应
        track_ms = snap.get('track_interval', 20)
        if interval > track_ms:
            interval = track_ms
        return interval

    def _start_timer_tracking(self):
        # 计算并设置定时器间隔，后续可在 _on_timer 中检测变更并重建
        interval = self._compute_timer_interval()
        self._current_timer_interval = interval
        _SetTimer(self.hwnd, c_void_p(1), interval, NULL)
        _log.info('定时器启动 interval={}ms display_freq={}Hz',
                  interval, _display_freq)
        _send_refresh_rate_info()

    def _stop_timer_tracking(self):
        _KillTimer(self.hwnd, c_void_p(1))

    def _start_hook_tracking(self):
        global _hook_handle, _hook_proc_ref
        if _hook_handle:
            _send_refresh_rate_info()
            return
        _hook_proc_ref = _mouse_hook_proc
        _hook_handle = _SetWindowsHookExW(
            WH_MOUSE_LL, _hook_proc_ref, _GetModuleHandleW(None), 0)
        if not _hook_handle:
            print('[警告] 无法安装鼠标钩子，回退到定时器模式')
            self.cfg.set(tracking_mode='timer')
            self._start_timer_tracking()
            return
        _send_refresh_rate_info()

    def _stop_hook_tracking(self):
        global _hook_handle, _hook_proc_ref
        self._hook_move_pending = False
        if _hook_handle:
            _UnhookWindowsHookEx(_hook_handle)
            _hook_handle = None
            _hook_proc_ref = None

    def _switch_tracking_mode(self, new_mode):
        if new_mode == self._current_tracking_mode:
            return
        if self._current_tracking_mode == 'hook':
            self._stop_hook_tracking()
        elif self._current_tracking_mode == 'timer':
            self._stop_timer_tracking()
        if new_mode == 'hook':
            self._start_hook_tracking()
        elif new_mode == 'timer':
            self._start_timer_tracking()
        self._current_tracking_mode = new_mode

    # ── 绘图资源 ──

    def _init_drawing(self):
        s = self._size
        self.hdc_mem = _CreateCompatibleDC(NULL)
        if not self.hdc_mem:
            raise RuntimeError('创建内存 DC 失败')
        bmi = BITMAPV5HEADER()
        bmi.bV5Size = ctypes.sizeof(BITMAPV5HEADER)
        bmi.bV5Width = s
        bmi.bV5Height = -s
        bmi.bV5Planes = 1
        bmi.bV5BitCount = 32
        bmi.bV5Compression = BI_RGB
        bits = c_void_p()
        self.hbitmap = _CreateDIBSection(self.hdc_mem, byref(bmi),
                                         DIB_RGB_COLORS, byref(bits), NULL, 0)
        if not self.hbitmap:
            raise RuntimeError('创建 DIBSection 失败')
        self.bits_ptr = bits
        _SelectObject(self.hdc_mem, self.hbitmap)

    def _reinit_drawing(self):
        if self.hbitmap:
            _DeleteObject(self.hbitmap)
            self.hbitmap = None
        if self.hdc_mem:
            _DeleteDC(self.hdc_mem)
            self.hdc_mem = None
        self._init_drawing()

    def _resize(self, new_outer):
        new_size = new_outer * 3
        if new_size != self._size:
            self._size = new_size
            self._alpha_mask = None
            _SetWindowPos(self.hwnd, NULL, 0, 0, new_size, new_size,
                          SWP_NOMOVE | SWP_NOACTIVATE)
            self._reinit_drawing()

    # ── 渲染循环 ──

    def _update_frame(self, mouse_x, mouse_y, outer_r, inner_r, user_alpha):
        _SetWindowPos(self.hwnd, c_void_p(-1), 0, 0, 0, 0,
                      SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        # _ring_center_x/y 由 _on_timer 插值维护，此处不覆写
        cr, cg, cb = self._color

        if (self._alpha_mask is None
                or self._last_shape_outer != outer_r
                or self._last_shape_inner != inner_r):
            self._alpha_mask = build_alpha_mask(self._size, outer_r, inner_r)
            self._last_shape_outer = outer_r
            self._last_shape_inner = inner_r

        buf = render_ring_from_mask(self._alpha_mask, self._size, cr, cg, cb, user_alpha)

        arr = (ctypes.c_ubyte * len(buf)).from_buffer(buf)
        ctypes.memmove(self.bits_ptr, arr, len(buf))

        dst = POINT(mouse_x - self._size // 2, mouse_y - self._size // 2)
        sz = SIZE(self._size, self._size)
        src = POINT(0, 0)
        bf = BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
        _UpdateLayeredWindow(self.hwnd, NULL, byref(dst), byref(sz),
                             self.hdc_mem, byref(src), 0, byref(bf), ULW_ALPHA)

    # ── 核心逻辑 ──

    def _on_timer(self):
        """轮询模式定时器回调：采样 → 匀速插值 → 渲染（定时器固定 4ms 快速触发）"""
        now = time.monotonic()
        _log.trace('_on_timer enter timer={}ms track={}ms ring=({}, {})',
                   self._current_timer_interval, self._current_track_ms,
                   self._ring_center_x, self._ring_center_y)
        snap = self.cfg.snapshot()

        # ── 配置变更检查 ──
        if snap['force_refresh']:
            self._last_sample_time = 0
            self.cfg.set(force_refresh=False)

        if snap['track_interval'] != self._current_track_ms:
            self._current_track_ms = snap['track_interval']

        if snap['tracking_mode'] != self._current_tracking_mode:
            self._switch_tracking_mode(snap['tracking_mode'])
            return

        # 定时器参数变更检测（timer_mode / 倍率 / 自定义间隔），实时重建 Win32 定时器
        new_timer = self._compute_timer_interval(snap)
        if new_timer != self._current_timer_interval:
            _log.info('定时器重建 {}ms → {}ms (timer_mode={} mult={})',
                      self._current_timer_interval, new_timer,
                      snap.get('timer_mode'), snap.get('timer_multiplier', 1.0))
            self._current_timer_interval = new_timer
            _KillTimer(self.hwnd, c_void_p(1))
            _SetTimer(self.hwnd, c_void_p(1), new_timer, NULL)
            _send_refresh_rate_info()

        want = snap['outer_radius'] * 3
        if want != self._size:
            self._resize(snap['outer_radius'])
            self._last_frame_key = None

        # ── 阶段1: 按跟踪频率读取鼠标位置，触发新的平滑段 ──
        if (now - self._last_track_time) * 1000 >= self._current_track_ms:
            self._last_track_time = now
            pt = POINT()
            _GetCursorPos(byref(pt))

            if self._current_timer_interval >= self._current_track_ms * 0.8:
                # 定时器与跟踪接近同频，无插值空间，直接瞬移
                _log.trace('瞬移 x={} y={} | timer={}ms track={}ms',
                           pt.x, pt.y, self._current_timer_interval,
                           self._current_track_ms)
                self._ring_center_x = pt.x
                self._ring_center_y = pt.y
                # 同步更新平滑段，防止阶段2插值覆写 _ring_center
                self._smooth_from_x = float(pt.x)
                self._smooth_from_y = float(pt.y)
                self._smooth_to_x = float(pt.x)
                self._smooth_to_y = float(pt.y)
                self._smooth_start_time = now
                self._smooth_duration = 0.0
            else:
                # 记录新的匀速移动段：从当前显示位置 → 新采样位置
                # 插值耗时 = 跟踪间隔，下采样到来时恰好到达
                _log.trace('采样 x={} y={} | from=({}, {}) duration={}ms',
                           pt.x, pt.y, int(self._ring_center_x),
                           int(self._ring_center_y),
                           self._current_track_ms)
                self._smooth_from_x = float(self._ring_center_x)
                self._smooth_from_y = float(self._ring_center_y)
                self._smooth_to_x = float(pt.x)
                self._smooth_to_y = float(pt.y)
                self._smooth_start_time = now
                self._smooth_duration = self._current_track_ms / 1000.0

            # 取色 & 碰撞检测（用实际鼠标位置）
            self._on_sample(pt.x, pt.y, snap)

        # ── 阶段2: 匀速线性插值 ──
        elapsed = now - self._smooth_start_time
        if (self._smooth_duration > 0 and elapsed >= 0.001
                and elapsed < self._smooth_duration):
            t = elapsed / self._smooth_duration  # 0~1
            disp_x = self._smooth_from_x + (self._smooth_to_x - self._smooth_from_x) * t
            disp_y = self._smooth_from_y + (self._smooth_to_y - self._smooth_from_y) * t
            _log.trace('插值 t={:.3f} disp=({:.0f}, {:.0f}) elapsed={:.1f}ms',
                       t, disp_x, disp_y, elapsed * 1000)
        else:
            # 已超时（elapsed >= smooth_duration），对齐到终点
            if elapsed >= self._smooth_duration:
                disp_x = self._smooth_to_x
                disp_y = self._smooth_to_y
                if self._smooth_duration > 0:
                    _log.trace('超时对齐 ({}ms >= {}ms) → ({:.0f}, {:.0f})',
                               elapsed * 1000, self._smooth_duration * 1000,
                               disp_x, disp_y)
            else:
                # 刚采样（elapsed ≈ 0），保持当前位置，
                # 否则跳终点后下一帧又从头插值，导致瞬移后倒回去
                disp_x = float(self._ring_center_x)
                disp_y = float(self._ring_center_y)

        self._ring_center_x = int(round(disp_x))
        self._ring_center_y = int(round(disp_y))

        # ── 阶段3: 渲染 ──
        frame_key = (self._ring_center_x, self._ring_center_y, self._color, snap['alpha'])
        if frame_key == self._last_frame_key:
            return
        self._last_frame_key = frame_key

        self._update_frame(self._ring_center_x, self._ring_center_y,
                           snap['outer_radius'], snap['inner_radius'], snap['alpha'])

    def _on_hook_move(self):
        self._hook_move_pending = False
        # 钩子模式：瞬移圆环到鼠标位置
        self._ring_center_x = _hook_latest_x
        self._ring_center_y = _hook_latest_y
        self._on_tick(_hook_latest_x, _hook_latest_y)

    def _on_sample(self, mouse_x, mouse_y, snap):
        """鼠标采样时执行：取色 + 碰撞检测

        @param mouse_x 实际鼠标屏幕 X（用于取色）
        @param mouse_y 实际鼠标屏幕 Y
        @param snap    当前配置快照
        """
        now = time.monotonic()
        if (now - self._last_sample_time) * 1000 < snap['sample_interval']:
            return
        self._last_sample_time = now

        # 碰撞检测：判断鼠标是否悬停在圆环上
        dx = mouse_x - self._ring_center_x
        dy = mouse_y - self._ring_center_y
        dist = math.sqrt(dx * dx + dy * dy)
        on_ring = snap['outer_radius'] > dist >= snap['inner_radius']

        if on_ring != self._prev_on_ring:
            self._prev_on_ring = on_ring
            self.cfg.set(on_ring=on_ring)
            if snap['panel_visible'] and _msg_queue is not None:
                _msg_queue.put({'type': MSG_ON_RING, 'value': on_ring})

        if not (on_ring and snap['collision_pause']):
            pixel = get_pixel_color(mouse_x, mouse_y)
            if snap['use_complement']:
                comp = compute_complement(pixel, snap['complement_algo'])
            else:
                comp = snap['fixed_color']
            self._color = comp
            self.cfg.set(last_pixel_color=pixel,
                         last_complement_color=comp)
            if snap['panel_visible'] and _msg_queue is not None:
                _msg_queue.put({
                    'type': MSG_COLOR,
                    'pixel': pixel,
                    'complement': comp,
                })

    def _on_tick(self, mouse_x, mouse_y):
        """消息/钩子模式：瞬移渲染逻辑

        @param mouse_x 鼠标屏幕 X 坐标
        @param mouse_y 鼠标屏幕 Y 坐标
        """
        cfg = self.cfg
        snap = cfg.snapshot()

        # 配置变更检查
        if snap['force_refresh']:
            self._last_sample_time = 0
            cfg.set(force_refresh=False)
        if snap['track_interval'] != self._current_track_ms:
            self._current_track_ms = snap['track_interval']
        if snap['tracking_mode'] != self._current_tracking_mode:
            self._switch_tracking_mode(snap['tracking_mode'])
        want = snap['outer_radius'] * 3
        if want != self._size:
            self._resize(snap['outer_radius'])
            self._last_frame_key = None

        # 取色 + 碰撞检测
        self._on_sample(mouse_x, mouse_y, snap)

        # 渲染
        frame_key = (mouse_x, mouse_y, self._color, snap['alpha'])
        if frame_key == self._last_frame_key:
            return
        self._last_frame_key = frame_key

        self._update_frame(mouse_x, mouse_y, snap['outer_radius'],
                           snap['inner_radius'], snap['alpha'])

    # ── 窗口管理 ──

    def show(self):
        _SetWindowPos(self.hwnd, c_void_p(-1), 0, 0, 0, 0,
                      SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def cleanup(self):
        if self._current_tracking_mode == 'hook':
            self._stop_hook_tracking()
        elif self._current_tracking_mode == 'timer':
            self._stop_timer_tracking()
        if self.hbitmap:
            _DeleteObject(self.hbitmap)
            self.hbitmap = None
        if self.hdc_mem:
            _DeleteDC(self.hdc_mem)
            self.hdc_mem = None
        if self.hwnd:
            _DestroyWindow(self.hwnd)
            self.hwnd = None


# ============================================================
# Win32 窗口过程
# ============================================================
@WNDPROC
def _ring_wnd_proc(hwnd, msg, wparam, lparam):
    win = MouseRingWindow._instance
    if win is None:
        return _DefWindowProcW(hwnd, msg, wparam, lparam)
    if msg == WM_TIMER:
        win._on_timer()
        return 0
    elif msg == WM_RING_MOUSE_MOVE:
        win._on_hook_move()
        return 0
    elif msg == WM_DESTROY:
        win.running = False
        return 0
    elif msg == WM_PAINT:
        ps = PAINTSTRUCT()
        _BeginPaint(hwnd, byref(ps))
        _EndPaint(hwnd, byref(ps))
        return 0
    return _DefWindowProcW(hwnd, msg, wparam, lparam)