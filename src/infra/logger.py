"""
@file logger.py
@brief 日志初始化模块（基于 Loguru），遵循 doc/ 中的设计规范。
         若 Loguru 未安装则自动降级为静默日志器，不影响程序运行。
"""

import sys
import os

try:
    from loguru import logger
    _HAS_LOGURU = True
except ImportError:
    _HAS_LOGURU = False

# ── 日志目录 ──
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'logs')


class _NullLogger:
    """Loguru 未安装时的静默替代品，所有调用均为空操作。"""

    def bind(self, **kwargs):
        return self

    def trace(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def critical(self, *args, **kwargs):
        pass

    def success(self, *args, **kwargs):
        pass

    def remove(self, *args, **kwargs):
        pass

    def add(self, *args, **kwargs):
        pass


_null_logger = _NullLogger()


def init_logging():
    """初始化全局日志配置：控制台 + 文件。

    若 Loguru 未安装则跳过，程序正常运行但不输出日志。
    """
    if not _HAS_LOGURU:
        return

    logger.remove()

    logger.add(
        sys.stdout,
        level='INFO',
        format=(
            '<green>[{time:YYYY-MM-DD HH:mm:ss.SSS}]</green> '
            '<level>[{level:<7}]</level> '
            '<cyan>[{extra[module]:<12}]</cyan> '
            '<level>{message}</level>'
        ),
        enqueue=True,
        colorize=True,
    )

    os.makedirs(_LOG_DIR, exist_ok=True)
    logger.add(
        os.path.join(_LOG_DIR, 'app_{time:YYYY-MM-DD}.log'),
        level='TRACE',
        format=(
            '[{time:YYYY-MM-DD HH:mm:ss.SSS}] '
            '[{level:<7}] '
            '[{extra[module]:<12}] '
            '{message}'
        ),
        rotation='00:00',
        retention='7 days',
        compression='gz',
        enqueue=True,
        catch=True,
    )


def get_logger(name: str):
    """获取绑定了模块名的日志器。

    @param name 模块名（建议大驼峰）
    @return 绑定了 module=name 的 Logger；Loguru 未安装时返回静默日志器
    """
    if _HAS_LOGURU:
        return logger.bind(module=name)
    return _null_logger
