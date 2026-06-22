# Cursor Locator

轻量级 Windows 工具，在鼠标光标周围显示自适应颜色圆环，帮你快速找到鼠标在哪。

## 功能特性

- **自适应互补色** — 自动检测光标下方像素颜色，渲染高对比度圆环，任何背景上都清晰可见
- **5 种配色算法** — 简单反色、HSL 色调旋转、感知亮度自适应、最大亮度对比、灰度反色
- **平滑追踪** — 匀速线性插值，圆环跟随鼠标流畅无卡顿
- **显示器同步** — 定时器可跟随显示器刷新率，渲染更顺滑
- **双追踪模式** — 钩子模式（消息驱动，低延迟）或定时器模式（轮询，兼容性好）
- **系统托盘** — 最小化到托盘运行，右键菜单快速操作
- **全局快捷键** — 一键切换圆环显示/隐藏，快捷键可自定义
- **单实例运行** — 重复启动时自动激活已有窗口，不会开多个
- **截屏不可见** — 圆环不会出现在截图/录屏中
- **低 CPU 占用** — 纯 Win32 分层窗口渲染，无重型框架依赖

## 运行环境

- Windows 10 / 11
- Python 3.8+

## 安装与运行

```bash
git clone https://github.com/ming-14/cursor-locator.git
cd cursor-locator
python run.py
```

启动后自动最小化到系统托盘，右键托盘图标可打开设置或退出。

### 快捷键

默认切换快捷键：`Ctrl + Alt + Shift + P`

可在设置面板中自定义。若快捷键冲突，程序会弹窗提示选择替代方案。

## 配置项

所有设置自动保存在 `mouse_circle_config.json`（首次运行自动创建）。

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
