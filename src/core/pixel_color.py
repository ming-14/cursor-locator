"""
@file pixel_color.py
@brief 屏幕像素颜色检测与多算法互补色计算
"""

from __future__ import annotations
import ctypes
from ctypes import windll, wintypes

_gdi32 = windll.gdi32
_user32 = windll.user32

_INVALID_COLOR = -1
_FALLBACK_COLOR = (0, 0, 0)

HDC = ctypes.c_void_p

_GetDC = _user32.GetDC
_GetDC.argtypes = [wintypes.HWND]
_GetDC.restype = HDC

_ReleaseDC = _user32.ReleaseDC
_ReleaseDC.argtypes = [wintypes.HWND, HDC]
_ReleaseDC.restype = ctypes.c_int

_GetPixel = _gdi32.GetPixel
_GetPixel.argtypes = [HDC, ctypes.c_int, ctypes.c_int]
_GetPixel.restype = wintypes.COLORREF


def get_pixel_color(x: int, y: int) -> tuple[int, int, int]:
    """获取屏幕指定坐标处的像素颜色 (R, G, B)，失败返回 (0, 0, 0)"""
    hdc = _GetDC(None)
    if not hdc:
        return _FALLBACK_COLOR
    try:
        color_ref = _GetPixel(hdc, x, y)
        if color_ref == _INVALID_COLOR:
            return _FALLBACK_COLOR
        return (color_ref & 0xFF, (color_ref >> 8) & 0xFF, (color_ref >> 16) & 0xFF)
    finally:
        _ReleaseDC(None, hdc)


# ---- 感知亮度（Rec. 709 权重）----
def _luminance(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ============================================================
# 算法 1：简单反色
# ============================================================
def _algo_invert(r, g, b):
    return (255 - r, 255 - g, 255 - b)


# ============================================================
# 算法 2：HSL 色调旋转 180°
# ============================================================
def _algo_hsl_rotate(r, g, b):
    rn, gn, bn = r / 255.0, g / 255.0, b / 255.0
    mx = max(rn, gn, bn)
    mn = min(rn, gn, bn)
    l = (mx + mn) / 2.0
    if mx == mn:
        return (0, 0, 0) if l > 0.5 else (255, 255, 255)
    d = mx - mn
    s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == rn:
        h = (gn - bn) / d
        if h < 0: h += 6.0
    elif mx == gn:
        h = (bn - rn) / d + 2.0
    else:
        h = (rn - gn) / d + 4.0
    h = h / 6.0
    h = (h + 0.5) % 1.0
    s = 1.0
    l = 1.0 - l
    if l < 0.15: l = 0.15
    elif l > 0.85: l = 0.85
    def _h2rgb(p, q, t):
        if t < 0: t += 1.0
        if t > 1: t -= 1.0
        if t < 1/6: return p + (q - p) * 6.0 * t
        if t < 0.5: return q
        if t < 2/3: return p + (q - p) * (2/3 - t) * 6.0
        return p
    q = l * (1.0 + s) if l < 0.5 else l + s - l * s
    p = 2.0 * l - q
    return (
        max(0, min(255, round(_h2rgb(p, q, h + 1/3) * 255))),
        max(0, min(255, round(_h2rgb(p, q, h) * 255))),
        max(0, min(255, round(_h2rgb(p, q, h - 1/3) * 255))),
    )


# ============================================================
# 算法 3：感知亮度自适应（简单反色 + HSL 中亮度区域）
# ============================================================
def _algo_luminance(r, g, b):
    lum = _luminance(r, g, b)
    if 80 <= lum <= 175:
        return _algo_hsl_rotate(r, g, b)
    return (255 - r, 255 - g, 255 - b)


# ============================================================
# 算法 4：纯黑/白（最大亮度对比）
# ============================================================
def _algo_black_white(r, g, b):
    return (0, 0, 0) if _luminance(r, g, b) > 128 else (255, 255, 255)


# ============================================================
# 算法 5：灰度反色（保留灰度，亮度反转）
# ============================================================
def _algo_gray_invert(r, g, b):
    lum = int(round(_luminance(r, g, b)))
    return (255 - lum,) * 3


# ============================================================
# 算法注册表
# ============================================================
ALGORITHMS = {
    'invert':        ('简单反色',        _algo_invert),
    'hsl_rotate':    ('HSL 色调旋转',    _algo_hsl_rotate),
    'luminance':     ('感知亮度自适应',   _algo_luminance),
    'black_white':   ('最大亮度对比',     _algo_black_white),
    'gray_invert':   ('灰度反色',         _algo_gray_invert),
}

ALGO_NAMES = {k: v[0] for k, v in ALGORITHMS.items()}
ALGO_LIST = list(ALGORITHMS.keys())
DEFAULT_ALGO = 'luminance'


def compute_complement(color: tuple[int, int, int], algo_name: str = DEFAULT_ALGO) -> tuple[int, int, int]:
    """根据算法名计算互补色"""
    r, g, b = color
    fn = ALGORITHMS.get(algo_name, ALGORITHMS[DEFAULT_ALGO])[1]
    return fn(r, g, b)