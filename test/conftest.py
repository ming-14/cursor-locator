"""
@brief pytest 共享 fixtures
"""

import sys
import os
import json
import tempfile

import pytest

# 将项目根目录加入 sys.path，方便导入 src 模块
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


@pytest.fixture(autouse=True)
def _isolate_config_path(monkeypatch):
    """**自动**将 Config._CONFIG_FILE 指向不存在的路径，避免加载真实配置文件。"""
    import src.core.config as mod
    monkeypatch.setattr(mod, '_CONFIG_FILE',
                        '/tmp/__nonexistent_test_config.json')


@pytest.fixture(autouse=True)
def _cleanup_loguru_handlers():
    """每个测试结束后清理 loguru handler，避免文件句柄泄漏。"""
    yield
    from loguru import logger
    logger.remove()


@pytest.fixture
def sample_config_dict():
    """返回一组典型的配置字典，用于构造 Config 或模拟持久化数据。"""
    return {
        'outer_radius': 16,
        'inner_radius': 8,
        'alpha': 90,
        'use_complement': True,
        'fixed_color': [173, 216, 230],
        'complement_algo': 'luminance',
        'collision_pause': True,
        'track_interval': 20,
        'sample_interval': 20,
        'tracking_mode': 'hook',
        'timer_mode': 'auto',
        'timer_interval_custom': 16,
        'timer_multiplier': 1.0,
        'toggle_hotkey_modifiers': ['ctrl', 'alt', 'shift'],
        'toggle_hotkey_key': 'p',
        'toggle_hotkey_vk': 0x50,
    }


@pytest.fixture
def temp_config_file(sample_config_dict):
    """创建一个临时 JSON 配置文件，返回 (filepath, config_dict)。"""
    import src.core.config as mod
    with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(sample_config_dict, f, ensure_ascii=False, indent=2)
        fpath = f.name
    # 指向临时文件
    mod._CONFIG_FILE = fpath
    yield fpath, sample_config_dict
    os.unlink(fpath)
