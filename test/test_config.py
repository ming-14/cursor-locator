"""
@brief Config 模块单元测试
"""

import os
import json
import copy

import pytest

from src.core.config import Config


class TestConfigDefaults:
    """测试 Config 默认值（路径已由 conftest 隔离）。"""

    def test_default_values(self):
        cfg = Config()
        assert cfg.get('outer_radius') == 16
        assert cfg.get('inner_radius') == 8
        assert cfg.get('alpha') == 90
        assert cfg.get('use_complement') is True
        assert cfg.get('fixed_color') == (173, 216, 230)
        assert cfg.get('complement_algo') == 'luminance'
        assert cfg.get('collision_pause') is True
        assert cfg.get('track_interval') == 20
        assert cfg.get('sample_interval') == 20
        assert cfg.get('tracking_mode') == 'hook'
        assert cfg.get('timer_mode') == 'auto'
        assert cfg.get('timer_interval_custom') == 16
        assert cfg.get('timer_multiplier') == 1.0
        assert cfg.get('force_refresh') is False
        assert cfg.get('panel_visible') is False

    def test_last_colors_default_tuple(self):
        cfg = Config()
        assert cfg.get('last_pixel_color') == (0, 0, 0)
        assert cfg.get('last_complement_color') == (0, 0, 0)

    def test_hotkey_defaults(self):
        cfg = Config()
        assert cfg.get('toggle_hotkey_modifiers') == ['ctrl', 'alt', 'shift']
        assert cfg.get('toggle_hotkey_key') == 'p'
        assert cfg.get('toggle_hotkey_vk') == 0x50


class TestConfigGetSet:
    """测试 get / set 方法。"""

    def test_set_and_get(self):
        cfg = Config()
        cfg.set(outer_radius=30, alpha=128)
        assert cfg.get('outer_radius') == 30
        assert cfg.get('alpha') == 128
        assert cfg.get('inner_radius') == 8  # 未修改

    def test_set_multiple_keys(self):
        cfg = Config()
        cfg.set(track_interval=50, sample_interval=100, tracking_mode='timer')
        assert cfg.get('track_interval') == 50
        assert cfg.get('sample_interval') == 100
        assert cfg.get('tracking_mode') == 'timer'


class TestConfigSnapshot:
    """测试 snapshot 的完整性与独立性。"""

    def test_snapshot_contains_core_keys(self):
        cfg = Config()
        snap = cfg.snapshot()
        required_keys = {
            'outer_radius', 'inner_radius', 'alpha', 'track_interval',
            'sample_interval', 'tracking_mode', 'timer_mode',
            'timer_multiplier', 'timer_interval_custom', 'panel_visible',
            'force_refresh', 'fixed_color',
        }
        assert required_keys.issubset(snap.keys())

    def test_snapshot_isolation(self):
        """修改返回的 snapshot 不应影响原始 Config。"""
        cfg = Config()
        snap = cfg.snapshot()
        snap['outer_radius'] = 999
        assert cfg.get('outer_radius') == 16

    def test_snapshot_color_tuple(self):
        """snapshot 中的颜色应为 tuple，方便比较。"""
        cfg = Config()
        snap = cfg.snapshot()
        assert isinstance(snap['fixed_color'], tuple)
        assert snap['fixed_color'] == (173, 216, 230)


class TestConfigSaveLoad:
    """测试持久化与加载。"""

    def test_save_and_load_roundtrip(self, temp_config_file):
        fpath, orig_dict = temp_config_file
        import src.core.config as mod

        # Config() 会从临时文件加载（conftest 已设置 _CONFIG_FILE）
        cfg = Config()
        assert cfg.get('outer_radius') == 16
        assert cfg.get('tracking_mode') == 'hook'

        # 修改并保存
        cfg.set(outer_radius=50, tracking_mode='timer',
                timer_multiplier=2.0)
        cfg.save()

        # 重新加载
        cfg2 = Config()
        assert cfg2.get('outer_radius') == 50
        assert cfg2.get('tracking_mode') == 'timer'
        assert cfg2.get('timer_multiplier') == 2.0

    def test_load_corrupted_file_uses_defaults(self):
        import src.core.config as mod
        import tempfile
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write('{corrupted json!!!')
            fpath = f.name
        mod._CONFIG_FILE = fpath

        cfg = Config()
        assert cfg.get('outer_radius') == 16
        os.unlink(fpath)

    def test_load_nonexistent_file_uses_defaults(self):
        import src.core.config as mod
        mod._CONFIG_FILE = '/tmp/__nonexistent_test_config_2.json'

        cfg = Config()
        assert cfg.get('outer_radius') == 16

    def test_force_refresh_not_loaded_from_file(self, temp_config_file):
        """force_refresh 是触发标志，重启后恒为 False。"""
        fpath, orig_dict = temp_config_file
        import src.core.config as mod

        # 模拟文件中保存了 force_refresh=True
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['force_refresh'] = True
        data['track_interval'] = 100
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        mod._CONFIG_FILE = fpath
        cfg = Config()
        assert cfg.get('force_refresh') is False
        assert cfg.get('track_interval') == 100


class TestConfigThreadSafety:
    """简单验证 Config 的线程安全 Lock。"""

    def test_concurrent_set_snapshot(self):
        cfg = Config()
        import threading
        results = []

        def writer():
            for i in range(100):
                cfg.set(outer_radius=i)

        def reader():
            for _ in range(100):
                results.append(cfg.snapshot())

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # 不会抛出异常即通过
        assert len(results) == 100


class TestConfigTupleListConversion:
    """测试 save 时 tuple→list，load 时 list→tuple 的转换。"""

    def test_save_converts_tuples_to_lists(self, temp_config_file):
        fpath, _ = temp_config_file
        import src.core.config as mod

        cfg = Config()
        cfg.set(fixed_color=(255, 0, 0))
        cfg.save()

        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data['fixed_color'] == [255, 0, 0]

    def test_load_converts_lists_to_tuples(self, temp_config_file):
        fpath, orig_dict = temp_config_file
        import src.core.config as mod

        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump({
                'fixed_color': [100, 150, 200],
                'last_pixel_color': [10, 20, 30],
                'last_complement_color': [200, 210, 220],
            }, f, ensure_ascii=False, indent=2)

        mod._CONFIG_FILE = fpath
        cfg = Config()
        assert cfg.get('fixed_color') == (100, 150, 200)
        assert cfg.get('last_pixel_color') == (10, 20, 30)
        assert cfg.get('last_complement_color') == (200, 210, 220)
