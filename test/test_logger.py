"""
@brief logger 模块单元测试
"""

import os
import tempfile

import pytest

from src.infra.logger import init_logging, get_logger


class TestGetLogger:
    def test_returns_logger(self):
        log = get_logger('Test')
        assert hasattr(log, 'info')
        assert hasattr(log, 'debug')
        assert hasattr(log, 'trace')
        assert hasattr(log, 'warning')
        assert hasattr(log, 'error')

    def test_different_names_different_loggers(self):
        log_a = get_logger('ModuleA')
        log_b = get_logger('ModuleB')
        assert log_a is not log_b

    def test_same_name_has_same_bind_key(self):
        """相同模块名返回绑定了相同 extra 的 logger。"""
        log1 = get_logger('SameTest')
        log2 = get_logger('SameTest')
        assert log1._core.extra.get('module') == log2._core.extra.get('module')

    def test_logging_does_not_raise(self):
        """确保调用日志方法不抛出异常。"""
        log = get_logger('NoCrash')
        log.info('info message')
        log.debug('debug message')
        log.trace('trace message')
        log.warning('warning message')
        log.error('error message')


class TestInitLogging:
    def test_init_does_not_raise(self):
        """init_logging 不抛出异常。"""
        init_logging()

    def test_init_creates_logs_dir(self):
        import src.infra.logger as mod
        import shutil
        orig_dir = mod._LOG_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            test_dir = os.path.join(tmpdir, 'logs')
            mod._LOG_DIR = test_dir
            init_logging()
            assert os.path.isdir(test_dir)
        finally:
            mod._LOG_DIR = orig_dir
            from loguru import logger
            logger.remove()
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_logging_writes_to_file(self):
        import src.infra.logger as mod
        import time, shutil
        orig_dir = mod._LOG_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            test_dir = os.path.join(tmpdir, 'logs')
            mod._LOG_DIR = test_dir
            init_logging()
            log = get_logger('TestFile')
            log.info('this is a test log message')
            time.sleep(0.3)
            found = any(f.endswith('.log') for f in os.listdir(test_dir))
            assert found, '日志文件未被创建'
        finally:
            mod._LOG_DIR = orig_dir
            from loguru import logger
            logger.remove()
            shutil.rmtree(tmpdir, ignore_errors=True)
