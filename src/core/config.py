"""
@file config.py
@brief 线程安全配置管理，JSON 持久化
"""

import threading
import os
import json

# 配置文件路径（与脚本同目录）
_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'mouse_circle_config.json')


class Config:
    def __init__(self):
        self._lock = threading.Lock()
        self.outer_radius = 16
        self.inner_radius = 8
        self.alpha = 90
        self.use_complement = True
        self.fixed_color = (173, 216, 230)
        self.complement_algo = 'luminance'
        self.last_pixel_color = (0, 0, 0)
        self.last_complement_color = (0, 0, 0)
        self.on_ring = False
        self.collision_pause = True
        self.track_interval = 20          # 鼠标跟踪频率 (ms)
        self.sample_interval = 100        # 取色频率 (ms)
        self.tracking_mode = 'timer'      # 跟踪模式: 'hook'(消息驱动) 或 'timer'(轮询)
        self.force_refresh = False        # 强制立即刷新取色
        self.timer_mode = 'auto'          # 定时器模式: 'auto'(跟随显示器) 或 'custom'(自定义)
        self.timer_interval_custom = 16   # 自定义定时器间隔 (ms)
        self.timer_multiplier = 1.0       # 自动倍率 [1.0, 1.2, 1.5, 1.7, 2.0, 2.5]
        # 快捷键设置（默认 Ctrl+Alt+Shift+P）
        self.toggle_hotkey_modifiers = ['ctrl', 'alt', 'shift']
        self.toggle_hotkey_key = 'p'
        self.toggle_hotkey_vk = 0x50
        self.toggle_hotkey_level = -1     # 当前注册策略等级
        self.toggle_hotkey_level_msg = '' # 策略描述
        self.panel_visible = False         # 控制面板是否可见（运行时状态，不持久化）
        # 从文件加载持久化配置
        self._load()

    def _load(self):
        """从 mouse_circle_config.json 加载配置。"""
        try:
            with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return  # 文件不存在或损坏，使用默认值

        with self._lock:
            # 需要转 tuple 的键
            tuple_keys = {'fixed_color', 'last_pixel_color',
                          'last_complement_color'}
            for key, value in data.items():
                if key == 'force_refresh':
                    # force_refresh 是触发标志，重启后恒为 False
                    continue
                if hasattr(self, key):
                    if key in tuple_keys and isinstance(value, list):
                        value = tuple(value)
                    setattr(self, key, value)

    def save(self):
        """将当前全部配置持久化到 mouse_circle_config.json。"""
        d = self.snapshot()
        # 排除运行时状态（不持久化）
        d.pop('panel_visible', None)
        # 将 tuple 转为 list（JSON 兼容）
        for k in ('fixed_color', 'last_pixel_color', 'last_complement_color'):
            if isinstance(d.get(k), tuple):
                d[k] = list(d[k])
        try:
            with open(_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # 写入失败静默处理

    def get(self, key):
        with self._lock:
            return getattr(self, key)

    def set(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def snapshot(self):
        with self._lock:
            return {
                'outer_radius':           self.outer_radius,
                'inner_radius':           self.inner_radius,
                'alpha':                  self.alpha,
                'use_complement':         self.use_complement,
                'fixed_color':            self.fixed_color,
                'complement_algo':        self.complement_algo,
                'last_pixel_color':       self.last_pixel_color,
                'last_complement_color':  self.last_complement_color,
                'on_ring':                self.on_ring,
                'collision_pause':        self.collision_pause,
                'track_interval':         self.track_interval,
                'sample_interval':        self.sample_interval,
                'tracking_mode':          self.tracking_mode,
                'force_refresh':          self.force_refresh,
                'toggle_hotkey_modifiers': self.toggle_hotkey_modifiers,
                'toggle_hotkey_key':       self.toggle_hotkey_key,
                'toggle_hotkey_vk':        self.toggle_hotkey_vk,
                'toggle_hotkey_level':     self.toggle_hotkey_level,
                'toggle_hotkey_level_msg': self.toggle_hotkey_level_msg,
                'panel_visible':           self.panel_visible,
                'timer_mode':              self.timer_mode,
                'timer_interval_custom':   self.timer_interval_custom,
                'timer_multiplier':        self.timer_multiplier,
            }