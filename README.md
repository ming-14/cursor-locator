# Cursor Locator

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows-blue?logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/github/stars/ming-14/cursor-locator?style=social" alt="Stars">
</p>

轻量级 Windows 工具，在鼠标光标周围显示**自适应颜色**圆环，帮你快速找到鼠标在哪

<div align="center">
  <img src="data:image/png;base64,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" alt="001" style="zoom: 150%;" />
  <img src="data:image/png;base64,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" alt="002" style="zoom:150%;" />
</div>

---

<a name="中文"></a>

<p align="right"><b>中文</b> | <a href="#english">English</a></p>

## 功能特性

- **自适应互补色** — 自动检测光标下方像素颜色，渲染高对比度圆环，任何背景上都清晰可见

## 运行环境

- Windows 7 / 10 / 11 但是我exe打包环境用的是Python3.11，Windows7需要自己下载`.py`源代码运行
- Python 3.8+ 应该可以更低，可以去试试

## 安装与运行

```bash
git clone https://github.com/ming-14/cursor-locator.git
cd cursor-locator
python run.py
```

或下载Release的`.exe`（需Windows10+）

启动后自动最小化到系统托盘，右键托盘图标可打开设置或退出

### 控制面板快捷键

默认控制面板快捷键：`Ctrl + Alt + Shift + P`，也可在控制面板中自定义

## 配置项

所有设置自动保存在 `mouse_circle_config.json`

控制面板可以编辑配置，不需要手动编辑文件

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `outer_radius` | 16 | 圆环外半径（像素） |
| `inner_radius` | 8 | 圆环内半径（像素） |
| `alpha` | 90 | 圆环透明度（0–255） |
| `use_complement` | `true` | 启用自适应互补色 |
| `fixed_color` | `(173, 216, 230)` | 固定颜色（关闭互补色时生效） |
| `complement_algo` | `luminance` | 配色算法：`invert`、`hsl_rotate`、`luminance`、`black_white`、`gray_invert` |
| `collision_pause` | `true` | 鼠标在圆环上时暂停取色 |
| `tracking_mode` | `timer` | 追踪模式：`hook`（低延迟）或 `timer`（轮询） |
| `track_interval` | 20 | 鼠标采样间隔（毫秒） |
| `sample_interval` | 100 | 取色间隔（毫秒） |
| `timer_mode` | `auto` | 定时器模式：`auto`（跟随显示器）或 `custom` |
| `timer_multiplier` | 1.0 | 自动模式刷新率倍率 |
| `timer_interval_custom` | 16 | 自定义定时器间隔（毫秒） |

## 项目结构

```
cursor-locator/
├── run.py                  # 启动入口（单实例检测 + 启动）
├── src/
│   ├── main.py             # 编排：后台线程 + Tkinter 主循环
│   ├── core/
│   │   ├── config.py       # 线程安全 JSON 配置管理
│   │   ├── rendering.py    # 圆环 alpha 掩码 + BGRA 合成
│   │   ├── pixel_color.py  # 屏幕取色 & 互补色算法
│   │   ├── hotkey_manager.py  # 全局快捷键注册
│   │   └── cpu_monitor.py  # 进程 CPU 占用监控
│   ├── service/
│   │   ├── ring_worker.py  # 分层窗口渲染 + 鼠标追踪
│   │   └── tray_worker.py  # 系统托盘图标 & 右键菜单
│   ├── ui/
│   │   └── settings_panel.py  # Tkinter 设置面板
│   └── infra/
│       ├── win32_api.py    # Win32 API 绑定与常量
│       └── logger.py       # 基于 Loguru 的日志
├── test/                   # 单元测试
└── doc/                    # 开发文档
```

## 配色算法

| 算法 | 键名 | 说明 |
|------|------|------|
| 简单反色 | `invert` | `255 - R, 255 - G, 255 - B` |
| HSL 色调旋转 | `hsl_rotate` | 在 HSL 空间旋转 180° |
| 感知亮度自适应 | `luminance` | 暗/亮背景用简单反色，中间亮度用 HSL 旋转 |
| 最大亮度对比 | `black_white` | 根据感知亮度直接输出纯黑或纯白 |
| 灰度反色 | `gray_invert` | 转灰度后反转亮度 |

## 许可证

MIT

---

<a name="english"></a>

<p align="right"><a href="#中文">中文</a> | <b>English</b></p>

Lightweight Windows tool that displays an **adaptive color** ring around the mouse cursor, helping you quickly locate where your mouse is.

## Features

- **Adaptive complementary color** — Automatically detects the pixel color under the cursor and renders a high-contrast ring, making it clearly visible on any background.

## Requirements

- Windows 7 / 10 / 11 — however, the packaged EXE is built with Python 3.11; Windows 7 users need to run the `.py` source code directly.
- Python 3.8+ (may work with lower versions, feel free to try).

## Installation & Usage

```bash
git clone https://github.com/ming-14/cursor-locator.git
cd cursor-locator
python run.py
```

Or download the `.exe` from Releases (requires Windows 10+).

Once launched, it auto-minimizes to the system tray. Right-click the tray icon to open settings or exit.

### Toggle Panel Hotkey

Default hotkey: `Ctrl + Alt + Shift + P`. Customizable in the control panel.

## Configuration

All settings are automatically saved to `mouse_circle_config.json`.

The control panel provides a GUI to edit config — no manual editing required.

| Setting | Default | Description |
|---------|---------|-------------|
| `outer_radius` | 16 | Outer radius of the ring (pixels) |
| `inner_radius` | 8 | Inner radius of the ring (pixels) |
| `alpha` | 90 | Ring opacity (0–255) |
| `use_complement` | `true` | Enable adaptive complementary color |
| `fixed_color` | `(173, 216, 230)` | Fixed color (used when complement is off) |
| `complement_algo` | `luminance` | Color algorithm: `invert`, `hsl_rotate`, `luminance`, `black_white`, `gray_invert` |
| `collision_pause` | `true` | Pause color sampling when mouse is on the ring |
| `tracking_mode` | `timer` | Tracking mode: `hook` (low latency) or `timer` (polling) |
| `track_interval` | 20 | Mouse sampling interval (ms) |
| `sample_interval` | 100 | Color sampling interval (ms) |
| `timer_mode` | `auto` | Timer mode: `auto` (sync with display) or `custom` |
| `timer_multiplier` | 1.0 | Auto mode refresh rate multiplier |
| `timer_interval_custom` | 16 | Custom timer interval (ms) |

## Project Structure

```
cursor-locator/
├── run.py                  # Entry point (single instance detection + launch)
├── src/
│   ├── main.py             # Orchestration: backend thread + Tkinter main loop
│   ├── core/
│   │   ├── config.py       # Thread-safe JSON config management
│   │   ├── rendering.py    # Ring alpha mask + BGRA compositing
│   │   ├── pixel_color.py  # Screen pixel color & complement color algorithms
│   │   ├── hotkey_manager.py  # Global hotkey registration
│   │   └── cpu_monitor.py  # Process CPU usage monitor
│   ├── service/
│   │   ├── ring_worker.py  # Layered window rendering + mouse tracking
│   │   └── tray_worker.py  # System tray icon & context menu
│   ├── ui/
│   │   └── settings_panel.py  # Tkinter settings panel
│   └── infra/
│       ├── win32_api.py    # Win32 API bindings & constants
│       └── logger.py       # Loguru-based logging
├── test/                   # Unit tests
└── doc/                    # Development docs
```

## Color Algorithms

| Algorithm | Key | Description |
|-----------|-----|-------------|
| Simple invert | `invert` | `255 - R, 255 - G, 255 - B` |
| HSL hue rotate | `hsl_rotate` | Rotate 180° in HSL space |
| Luminance adaptive | `luminance` | Simple invert for dark/bright backgrounds, HSL rotation for mid-tones |
| Max contrast | `black_white` | Pure black or white based on perceived luminance |
| Gray invert | `gray_invert` | Convert to grayscale, then invert luminance |

## License

MIT
