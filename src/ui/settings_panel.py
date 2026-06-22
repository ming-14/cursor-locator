"""
@file settings_panel.py
@brief Tkinter 控制面板 UI（消息驱动 + CPU 轮询）
"""

import queue

import tkinter as tk
import ctypes
from tkinter import ttk, colorchooser

from src.core.config import Config
from src.core.pixel_color import ALGO_LIST, ALGO_NAMES
from src.core.hotkey_manager import Hotkey, HotkeyManager, KEY_VK_MAP
from src.core.cpu_monitor import CPUMonitor


# ============================================================
# Tkinter 设置面板
# ============================================================
class SettingsPanel:
    def __init__(self, master: tk.Tk, cfg: Config, mq: queue.Queue,
                 on_hotkey_change=None):
        self.cfg = cfg
        self.mq = mq
        self.master = master
        self._on_hotkey_change = on_hotkey_change
        self._cpu_mon = CPUMonitor()
        self._capturing = False
        self._capture_keys_prev = {}
        self._capture_timeout_id = None

        master.title('鼠标小圆圈 - 控制面板')
        try:
            _hwnd = ctypes.c_void_p(master.winfo_id())
            _hIcon = ctypes.windll.user32.LoadIconW(None, 32512)
            ctypes.windll.user32.SendMessageW(_hwnd, 0x0080, 0, _hIcon)
            ctypes.windll.user32.SendMessageW(_hwnd, 0x0080, 1, _hIcon)
        except Exception:
            pass

        master.resizable(False, False)

        main = ttk.Frame(master, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(1, weight=1)

        row = 0

        # ═══ 圆环参数 ═══
        sep1 = ttk.Label(main, text='── 圆环参数 ──', font=('', 9, 'bold'))
        sep1.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))
        row += 1

        ttk.Label(main, text='外圈半径').grid(row=row, column=0, sticky=tk.W, pady=2)
        self.outer_var = tk.IntVar(value=cfg.get('outer_radius'))
        self._outer_scale = self._add_slider(main, row, 1, self.outer_var, 5, 60)
        row += 1

        ttk.Label(main, text='中间空隙').grid(row=row, column=0, sticky=tk.W, pady=2)
        self.inner_var = tk.IntVar(value=cfg.get('inner_radius'))
        self._inner_scale = self._add_slider(main, row, 1, self.inner_var, 0, 60)
        row += 1

        ttk.Label(main, text='透明度').grid(row=row, column=0, sticky=tk.W, pady=2)
        self.alpha_var = tk.IntVar(value=cfg.get('alpha'))
        self._add_slider(main, row, 1, self.alpha_var, 0, 255)
        row += 1

        # ═══ 颜色选项 ═══
        sep2 = ttk.Label(main, text='── 颜色选项 ──', font=('', 9, 'bold'))
        sep2.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(8, 4))
        row += 1

        self.comp_var = tk.BooleanVar(value=cfg.get('use_complement'))
        ttk.Checkbutton(main, text='使用互补色（随背景变色）',
                        variable=self.comp_var,
                        command=self._on_comp_toggle).grid(
                            row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        row += 1

        fr_algo = ttk.Frame(main)
        fr_algo.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(fr_algo, text='互补算法:').pack(side=tk.LEFT)
        self.algo_var = tk.StringVar(value=cfg.get('complement_algo'))
        algo_names = [f'{k} - {ALGO_NAMES[k]}' for k in ALGO_LIST]
        self.algo_combo = ttk.Combobox(fr_algo, values=algo_names,
                                       state='readonly', width=22)
        default_idx = ALGO_LIST.index(cfg.get('complement_algo'))
        self.algo_combo.current(default_idx)
        self.algo_combo.pack(side=tk.LEFT, padx=4)
        self.algo_combo.bind('<<ComboboxSelected>>', self._on_algo_change)
        row += 1

        self._fr_fixed = ttk.Frame(main)
        self._fr_fixed.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        self._fixed_prefix = ttk.Label(self._fr_fixed, text='固定颜色:')
        self._fixed_prefix.pack(side=tk.LEFT)
        self.fixed_r, self.fixed_g, self.fixed_b = cfg.get('fixed_color')
        self.color_btn = tk.Button(self._fr_fixed, text='    ', command=self._pick_color,
                                   bg=f'#{self.fixed_r:02x}{self.fixed_g:02x}{self.fixed_b:02x}',
                                   width=3, relief=tk.RIDGE)
        self.color_btn.pack(side=tk.LEFT, padx=4)
        self.color_label = ttk.Label(self._fr_fixed,
                                     text=f'RGB({self.fixed_r},{self.fixed_g},{self.fixed_b})')
        self.color_label.pack(side=tk.LEFT)
        row += 1

        self.collision_var = tk.BooleanVar(value=cfg.get('collision_pause'))
        ttk.Checkbutton(main, text='启用碰撞暂停改色',
                        variable=self.collision_var,
                        command=self._apply).grid(
                            row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        row += 1

        # ═══ 性能设置 ═══
        sep3 = ttk.Label(main, text='── 性能设置 ──', font=('', 9, 'bold'))
        sep3.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(8, 4))
        row += 1

        self._track_label = ttk.Label(main, text='跟踪频率(ms)')
        self._track_label.grid(row=row, column=0, sticky=tk.W, pady=2)
        self.track_int_var = tk.IntVar(value=cfg.get('track_interval'))
        self._track_scale = self._add_slider(main, row, 1, self.track_int_var, 4, 500)
        row += 1

        ttk.Label(main, text='取色频率(ms)').grid(row=row, column=0, sticky=tk.W, pady=2)
        self.sample_int_var = tk.IntVar(value=cfg.get('sample_interval'))
        self._add_slider(main, row, 1, self.sample_int_var, 4, 500)
        row += 1

        fr_mode = ttk.Frame(main)
        fr_mode.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(fr_mode, text='跟踪模式:').pack(side=tk.LEFT)
        self.tracking_mode_var = tk.StringVar(value=cfg.get('tracking_mode'))
        mode_combo = ttk.Combobox(fr_mode, values=['hook - 消息驱动', 'timer - 定时轮询'],
                                  state='readonly', width=18,
                                  textvariable=self.tracking_mode_var)
        if cfg.get('tracking_mode') == 'hook':
            mode_combo.current(0)
        else:
            mode_combo.current(1)
        mode_combo.pack(side=tk.LEFT, padx=4)
        mode_combo.bind('<<ComboboxSelected>>', self._on_tracking_mode_change)
        row += 1

        self._mode_hint = ttk.Label(main, text='消息驱动：鼠标移动时立即响应，静止时零开销',
                                    foreground='#888', font=('', 8))
        self._mode_hint.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))
        row += 1

        # ═══ 定时器模式 ═══
        # 仅在 timer（轮询）模式下显示
        self._timer_frame = ttk.Frame(main)
        self._timer_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self._timer_frame, text='定时器模式:').pack(side=tk.LEFT)
        self.timer_mode_var = tk.StringVar(value=cfg.get('timer_mode'))
        timer_mode_combo = ttk.Combobox(
            self._timer_frame, values=['auto - 跟随显示器', 'custom - 自定义'],
            state='readonly', width=18, textvariable=self.timer_mode_var)
        timer_mode_combo.pack(side=tk.LEFT, padx=4)
        if cfg.get('timer_mode') == 'auto':
            timer_mode_combo.current(0)
        else:
            timer_mode_combo.current(1)
        timer_mode_combo.bind('<<ComboboxSelected>>', self._on_timer_mode_change)
        row += 1

        # ── 倍率（auto 模式） ──
        self._mult_frame = ttk.Frame(main)
        self._mult_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self._mult_frame, text='倍率:').pack(side=tk.LEFT)
        MULT_OPTIONS = ['1.0x', '1.2x', '1.5x', '1.7x', '2.0x', '2.5x']
        self.mult_var = tk.StringVar(value=f'{cfg.get("timer_multiplier"):.1f}x')
        self.mult_combo = ttk.Combobox(
            self._mult_frame, values=MULT_OPTIONS,
            state='readonly', width=8, textvariable=self.mult_var)
        try:
            idx = MULT_OPTIONS.index(f'{cfg.get("timer_multiplier"):.1f}x')
            self.mult_combo.current(idx)
        except ValueError:
            self.mult_combo.current(0)
        self.mult_combo.pack(side=tk.LEFT, padx=4)
        self.mult_combo.bind('<<ComboboxSelected>>', self._on_multiplier_change)
        row += 1

        # ── 自定义间隔（custom 模式） ──
        self._custom_frame = ttk.Frame(main)
        self._custom_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self._custom_frame, text='定时器间隔(ms)').pack(side=tk.LEFT)
        self.timer_custom_var = tk.IntVar(value=cfg.get('timer_interval_custom'))
        # 手动创建滑块（避免 _add_slider 内 grid 与已有 pack 冲突）
        _sf = ttk.Frame(self._custom_frame)
        _sf.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        self._timer_custom_scale = ttk.Scale(_sf, from_=4, to=500,
                                              orient=tk.HORIZONTAL)
        self._timer_custom_scale.set(cfg.get('timer_interval_custom'))
        self._timer_custom_scale.configure(
            command=lambda v: self._on_timer_custom_slide(v))
        self._timer_custom_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        _lbl = ttk.Label(_sf, textvariable=self.timer_custom_var,
                         width=3, anchor=tk.E)
        _lbl.pack(side=tk.LEFT, padx=(6, 2))
        row += 1
        # 同步 auto/custom 子控件可见性
        self._sync_timer_mode_ui()

        # ═══ 实时信息 ═══
        sep4 = ttk.Label(main, text='── 实时信息 ──', font=('', 9, 'bold'))
        sep4.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(8, 4))
        row += 1

        fr_px = ttk.Frame(main)
        fr_px.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(fr_px, text='鼠标像素:').pack(side=tk.LEFT)
        self.pixel_swatch = tk.Canvas(fr_px, width=20, height=16,
                                      highlightthickness=1, highlightbackground='#aaa',
                                      cursor='hand2')
        self.pixel_swatch.pack(side=tk.LEFT, padx=4)
        self.pixel_swatch.bind('<Button-1>', self._force_refresh)
        _pc = cfg.get('last_pixel_color')
        self.pixel_swatch.config(bg=f'#{_pc[0]:02x}{_pc[1]:02x}{_pc[2]:02x}')
        self.pixel_label = ttk.Label(fr_px, text=f'RGB({_pc[0]},{_pc[1]},{_pc[2]})', width=18)
        self.pixel_label.pack(side=tk.LEFT)
        row += 1

        fr_cc = ttk.Frame(main)
        fr_cc.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(fr_cc, text='圆环颜色:').pack(side=tk.LEFT)
        _cc = cfg.get('last_complement_color')
        self.comp_swatch = tk.Canvas(fr_cc, width=20, height=16,
                                     highlightthickness=1, highlightbackground='#aaa',
                                     cursor='hand2',
                                     bg=f'#{_cc[0]:02x}{_cc[1]:02x}{_cc[2]:02x}')
        self.comp_swatch.pack(side=tk.LEFT, padx=4)
        self.comp_swatch.bind('<Button-1>', self._force_refresh)
        self.comp_label = ttk.Label(fr_cc, text=f'RGB({_cc[0]},{_cc[1]},{_cc[2]})', width=18)
        self.comp_label.pack(side=tk.LEFT)
        row += 1

        fr_status = ttk.Frame(main)
        fr_status.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        self._status_prefix = ttk.Label(fr_status, text='悬停状态:')
        self._status_prefix.pack(side=tk.LEFT)
        self.status_label = ttk.Label(fr_status, text='正常', foreground='green')
        self.status_label.pack(side=tk.LEFT, padx=4)
        row += 1

        self._gap_warning = ttk.Label(main, text='', foreground='orange', font=('', 8))
        self._gap_warning_row = row
        row += 1

        fr_cpu = ttk.Frame(main)
        fr_cpu.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(fr_cpu, text='进程 CPU:').pack(side=tk.LEFT)
        self.cpu_label = ttk.Label(fr_cpu, text='0.0% (总)', foreground='#555', cursor='hand2')
        self.cpu_label.pack(side=tk.LEFT, padx=4)
        self._cpu_per_core = False
        self.cpu_label.bind('<Button-1>', self._toggle_cpu_mode)
        row += 1

        fr_disp = ttk.Frame(main)
        fr_disp.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(fr_disp, text='显示器帧率:').pack(side=tk.LEFT)
        self.display_freq_label = ttk.Label(fr_disp, text='检测中...', foreground='#555')
        self.display_freq_label.pack(side=tk.LEFT, padx=4)
        row += 1

        # ═══ 快捷键设置 ═══
        sep5 = ttk.Label(main, text='── 快捷键设置 ──', font=('', 9, 'bold'))
        sep5.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(8, 4))
        row += 1

        hk_frame = ttk.Frame(main)
        hk_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(hk_frame, text='显示/隐藏面板:').pack(side=tk.LEFT)

        mods = cfg.get('toggle_hotkey_modifiers')
        key_name = cfg.get('toggle_hotkey_key')
        current_hotkey = Hotkey(mods, key_name, cfg.get('toggle_hotkey_vk'))
        self.hotkey_label = ttk.Label(
            hk_frame, text=str(current_hotkey),
            foreground='#0066cc', font=('', 9, 'bold'))
        self.hotkey_label.pack(side=tk.LEFT, padx=4)

        self.hotkey_btn = ttk.Button(
            hk_frame, text='更改...', command=self._start_capture, width=8)
        self.hotkey_btn.pack(side=tk.LEFT, padx=2)
        row += 1

        self.hotkey_status = ttk.Label(main, text='', foreground='red')
        self._status_row = row
        row += 1

        self.hotkey_level_label = ttk.Label(
            main, text='', foreground='#888', font=('', 8))
        self.hotkey_level_label.grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))
        row += 1
        self._update_hotkey_level_display()

        # ═══ 按钮 ═══
        ttk.Separator(main, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=8)
        row += 1
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=row, column=0, columnspan=2)
        ttk.Button(btn_frame, text='关闭', command=self._hide_panel).pack()

        self._on_comp_toggle()
        master.protocol('WM_DELETE_WINDOW', self._hide_panel)
        master.update_idletasks()
        master.geometry('')
        self._poll_cpu()
        self._sync_track_mode_ui()

    # ----------------------------------------------------------
    def _show_panel(self):
        self.cfg.set(panel_visible=True, force_refresh=True)
        self.master.deiconify()
        self._update_hotkey_level_display()

    def _hide_panel(self):
        self.cfg.set(panel_visible=False)
        self.master.withdraw()

    # ----------------------------------------------------------
    def handle_message(self, msg):
        try:
            msg_type = msg.get('type')

            # ── 显示器帧率更新：不依赖面板可见性，始终更新 ──
            if msg_type == 'refresh_rate':
                freq = msg.get('freq', 0)
                if freq > 0:
                    self.display_freq_label.config(text=f'{freq} Hz')
                else:
                    self.display_freq_label.config(text='未知', foreground='#999')
                return

            if not self.cfg.get('panel_visible'):
                return
            if msg_type == 'color':
                pc = msg['pixel']
                cc = msg['complement']
                self.pixel_swatch.config(
                    bg=f'#{pc[0]:02x}{pc[1]:02x}{pc[2]:02x}')
                self.pixel_label.config(
                    text=f'RGB({pc[0]},{pc[1]},{pc[2]})')
                self.comp_swatch.config(
                    bg=f'#{cc[0]:02x}{cc[1]:02x}{cc[2]:02x}')
                self.comp_label.config(
                    text=f'RGB({cc[0]},{cc[1]},{cc[2]})')
            elif msg_type == 'on_ring':
                self._update_status_display(msg['value'])
            elif msg_type == 'hotkey_level':
                self._update_hotkey_level_display()
        except Exception:
            import traceback
            traceback.print_exc()

    # ----------------------------------------------------------
    def _update_hotkey_level_display(self):
        level = self.cfg.get('toggle_hotkey_level')
        msg = self.cfg.get('toggle_hotkey_level_msg')
        if level >= 0 and msg:
            self.hotkey_level_label.config(text=f'注册方式: {msg}')
        else:
            self.hotkey_level_label.config(text='')

    # ----------------------------------------------------------
    def _set_status(self, text, foreground='red', duration=3000):
        self.hotkey_status.config(text=text, foreground=foreground)
        self.hotkey_status.grid(
            row=self._status_row, column=0, columnspan=2,
            sticky=tk.W, pady=(0, 2))
        if duration > 0:
            self.master.after(duration, self._clear_status)

    def _clear_status(self):
        try:
            self.hotkey_status.grid_remove()
            self.hotkey_status.config(text='')
        except Exception:
            pass

    # ----------------------------------------------------------
    def _refresh_hotkey_label(self):
        mods = self.cfg.get('toggle_hotkey_modifiers')
        key_name = self.cfg.get('toggle_hotkey_key')
        current = Hotkey(mods, key_name, self.cfg.get('toggle_hotkey_vk'))
        self.hotkey_label.config(text=str(current), foreground='#0066cc')

    # ----------------------------------------------------------
    def _toggle_cpu_mode(self, event=None):
        self._cpu_per_core = not self._cpu_per_core
        total_pct, per_core = self._cpu_mon.get_cpu_percent()
        if self._cpu_per_core:
            self.cpu_label.config(text=f'{per_core:.1f}% (核)')
        else:
            self.cpu_label.config(text=f'{total_pct:.1f}% (总)')

    # ----------------------------------------------------------
    def _force_refresh(self, event=None):
        self.cfg.set(force_refresh=True)

    # ----------------------------------------------------------
    def _add_slider(self, parent, row, col, var, minv, maxv):
        f = ttk.Frame(parent)
        f.grid(row=row, column=col, sticky=tk.EW, padx=(4, 0))
        s = ttk.Scale(f, from_=minv, to=maxv, orient=tk.HORIZONTAL)
        s.set(var.get())
        s.configure(command=lambda v: self._on_slide(var, s, v))
        s.pack(side=tk.LEFT, fill=tk.X, expand=True)
        lbl = ttk.Label(f, textvariable=var, width=3, anchor=tk.E)
        lbl.pack(side=tk.LEFT, padx=(6, 2))
        return s

    def _on_timer_custom_slide(self, val):
        self.timer_custom_var.set(round(float(val)))
        self._apply()

    def _on_slide(self, var, scale, val):
        var.set(round(float(val)))
        inner = self.inner_var.get()
        outer = self.outer_var.get()
        if inner > outer:
            if var is self.outer_var:
                self.inner_var.set(outer)
                self._inner_scale.set(outer)
            else:
                self.outer_var.set(inner)
                self._outer_scale.set(inner)
        self._apply()

    def _on_comp_toggle(self):
        disabled = self.comp_var.get()
        state = tk.DISABLED if disabled else tk.NORMAL
        fg = 'gray' if disabled else 'black'
        self.color_btn.config(state=state)
        self._fixed_prefix.config(foreground=fg)
        self.color_label.config(foreground=fg)

    def _on_algo_change(self, event=None):
        text = self.algo_combo.get()
        key = text.split(' - ')[0]
        self.cfg.set(complement_algo=key)
        self._live_apply()

    def _on_tracking_mode_change(self, event=None):
        text = self.tracking_mode_var.get()
        mode = 'hook' if 'hook' in text else 'timer'
        self.cfg.set(tracking_mode=mode)
        self.cfg.save()
        self._sync_track_mode_ui()

    def _sync_track_mode_ui(self):
        mode = self.cfg.get('tracking_mode')
        if mode == 'hook':
            self._track_scale.config(state=tk.DISABLED)
            self._mode_hint.config(
                text='消息驱动：鼠标移动时立即响应，静止时零开销')
        else:
            self._track_label.config(foreground='black')
            self._track_scale.config(state=tk.NORMAL)
            self._mode_hint.config(
                text='定时轮询：固定间隔检测，兼容性好，持续消耗 CPU')
        self._sync_timer_mode_ui()

    # ── 定时器模式切换 ──
    def _on_timer_mode_change(self, event=None):
        text = self.timer_mode_var.get()
        mode = 'auto' if 'auto' in text else 'custom'
        self.cfg.set(timer_mode=mode)
        self.cfg.save()
        self._sync_timer_mode_ui()
        self._apply_timer()

    def _on_multiplier_change(self, event=None):
        text = self.mult_var.get()
        mult = float(text.rstrip('x'))
        self.cfg.set(timer_multiplier=mult)
        self.cfg.save()
        self._apply_timer()

    def _sync_timer_mode_ui(self):
        """根据跟踪模式 + 定时器模式显示/隐藏相关控件。"""
        track_mode = self.cfg.get('tracking_mode')
        enabled = (track_mode == 'timer')
        timer_mode = self.cfg.get('timer_mode')
        if enabled:
            self._timer_frame.grid()
            if timer_mode == 'auto':
                self._mult_frame.grid()
                self._custom_frame.grid_remove()
            else:
                self._mult_frame.grid_remove()
                self._custom_frame.grid()
        else:
            self._timer_frame.grid_remove()
            self._mult_frame.grid_remove()
            self._custom_frame.grid_remove()

    def _apply_timer(self):
        """保存定时器相关配置并立即生效。"""
        self.cfg.set(
            timer_mode=self.timer_mode_var.get().split(' - ')[0],
            timer_multiplier=float(self.mult_var.get().rstrip('x')),
            timer_interval_custom=self.timer_custom_var.get(),
        )
        self.cfg.save()

    def _pick_color(self):
        rgb, _ = colorchooser.askcolor(
            color=f'#{self.fixed_r:02x}{self.fixed_g:02x}{self.fixed_b:02x}',
            title='选择固定颜色', parent=self.master,
        )
        if rgb:
            self.fixed_r, self.fixed_g, self.fixed_b = map(int, rgb)
            self.color_btn.config(
                bg=f'#{self.fixed_r:02x}{self.fixed_g:02x}{self.fixed_b:02x}')
            self.color_label.config(
                text=f'RGB({self.fixed_r},{self.fixed_g},{self.fixed_b})')
            self._apply()

    def _live_apply(self):
        self._apply()

    def _apply(self):
        self.cfg.set(
            outer_radius=self.outer_var.get(),
            inner_radius=self.inner_var.get(),
            alpha=self.alpha_var.get(),
            use_complement=self.comp_var.get(),
            fixed_color=(self.fixed_r, self.fixed_g, self.fixed_b),
            collision_pause=self.collision_var.get(),
            track_interval=self.track_int_var.get(),
            sample_interval=self.sample_int_var.get(),
            timer_interval_custom=self.timer_custom_var.get(),
        )
        self.cfg.save()
        self._update_status_display(self.cfg.get('on_ring'))

    # ----------------------------------------------------------
    def _poll_cpu(self):
        try:
            total_pct, per_core = self._cpu_mon.get_cpu_percent()
            if self._cpu_per_core:
                self.cpu_label.config(text=f'{per_core:.1f}% (核)')
            else:
                self.cpu_label.config(text=f'{total_pct:.1f}% (总)')
        except Exception:
            import traceback
            traceback.print_exc()
        if self.master.winfo_exists():
            self.master.after(1000, self._poll_cpu)

    # ----------------------------------------------------------
    def _update_status_display(self, on_ring):
        pause_on = self.cfg.get('collision_pause')
        if pause_on:
            self._status_prefix.config(foreground='black')
            if on_ring:
                self.status_label.config(
                    text='已暂停（鼠标在圆环上）', foreground='red')
            else:
                self.status_label.config(text='正常', foreground='green')
        else:
            self._status_prefix.config(foreground='gray')
            self.status_label.config(text='未开启', foreground='gray')
        self._update_gap_warning()

    # ----------------------------------------------------------
    def _update_gap_warning(self):
        inner_r = self.cfg.get('inner_radius')
        pause_on = self.cfg.get('collision_pause')
        if inner_r == 0:
            tip = ('当前颜色不会被更改'
                   if pause_on else '圆圈颜色可能出现闪动')
            self._gap_warning.config(text=f'⚠ 空隙为零，{tip}')
            self._gap_warning.grid(
                row=self._gap_warning_row, column=0, columnspan=2,
                sticky=tk.W, pady=(0, 2))
        else:
            self._gap_warning.grid_remove()

    # ----------------------------------------------------------
    def _start_capture(self):
        self._capturing = True
        self._capture_keys_prev = {}
        self.hotkey_btn.config(text='按下新快捷键...', state=tk.DISABLED)
        self._clear_status()
        self._capture_timeout_id = self.master.after(
            15000, self._on_capture_timeout)
        self._capture_poll()

    def _capture_poll(self):
        if not self._capturing:
            return
        if not self.master.winfo_viewable():
            self._cancel_capture()
            return

        user32 = ctypes.windll.user32

        esc_vk = 0x1B
        esc_down = bool(user32.GetAsyncKeyState(esc_vk) & 0x8000)
        esc_prev = self._capture_keys_prev.get(esc_vk, False)
        if esc_down and not esc_prev:
            self._capture_keys_prev[esc_vk] = esc_down
            self._cancel_capture()
            self._clear_status()
            return
        self._capture_keys_prev[esc_vk] = esc_down

        modifiers = []
        if user32.GetAsyncKeyState(0x11) & 0x8000:
            modifiers.append('ctrl')
        if user32.GetAsyncKeyState(0x12) & 0x8000:
            modifiers.append('alt')
        if user32.GetAsyncKeyState(0x10) & 0x8000:
            modifiers.append('shift')
        if user32.GetAsyncKeyState(0x5B) & 0x8000:
            modifiers.append('win')

        has_system_mod = any(m in modifiers for m in ('ctrl', 'alt', 'win'))

        for key_name, vk in KEY_VK_MAP.items():
            now_down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
            prev_down = self._capture_keys_prev.get(vk, False)

            if now_down and not prev_down:
                if has_system_mod:
                    hotkey = Hotkey(modifiers, key_name, vk)
                    cur_mods = self.cfg.get('toggle_hotkey_modifiers')
                    cur_key = self.cfg.get('toggle_hotkey_key')
                    cur_vk = self.cfg.get('toggle_hotkey_vk')
                    cur_hotkey = Hotkey(cur_mods, cur_key, cur_vk)
                    if hotkey == cur_hotkey:
                        self._cancel_capture()
                        self._refresh_hotkey_label()
                        self._set_status('与当前快捷键相同，无需更改', 'orange')
                        return
                    available, msg = HotkeyManager.test_available(hotkey)
                    if not available:
                        self._cancel_capture()
                        self._refresh_hotkey_label()
                        self._set_status(f'冲突: {msg}', 'red')
                        return
                    if msg:
                        self._cancel_capture()
                        self._refresh_hotkey_label()
                        self._set_status(f'拒绝: {msg}', 'red', 5000)
                        return
                    self._apply_hotkey(hotkey)
                    return
                else:
                    self._set_status(
                        '请同时按住 Ctrl/Alt/Win + 字母键', 'red', 2000)

            self._capture_keys_prev[vk] = now_down

        self.master.after(30, self._capture_poll)

    def _apply_hotkey(self, hotkey):
        self._cancel_capture()
        self.cfg.set(
            toggle_hotkey_modifiers=hotkey.modifiers,
            toggle_hotkey_key=hotkey.key,
            toggle_hotkey_vk=hotkey.vk,
        )
        self.cfg.save()
        self.hotkey_label.config(text=str(hotkey), foreground='#0066cc')
        self._set_status('快捷键已更新 ✓', 'green', 3000)
        if self._on_hotkey_change:
            self._on_hotkey_change()

    def _cancel_capture(self):
        self._capturing = False
        self._capture_keys_prev = {}
        if self._capture_timeout_id:
            try:
                self.master.after_cancel(self._capture_timeout_id)
            except Exception:
                pass
            self._capture_timeout_id = None
        try:
            self.hotkey_btn.config(text='更改...', state=tk.NORMAL)
        except Exception:
            pass

    def _on_capture_timeout(self):
        if self._capturing:
            self._cancel_capture()
            self._set_status('操作超时，请重试', 'orange', 3000)