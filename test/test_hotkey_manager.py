"""
@brief hotkey_manager 模块单元测试
"""

import pytest

from src.core.hotkey_manager import (
    Hotkey, HotkeyManager, KEY_VK_MAP, PARSABLE_KEYS,
    MODIFIER_NAMES, check_hotkey_safety,
)


# ═══════════════════════════════════════════════════════════════
# Hotkey 类
# ═══════════════════════════════════════════════════════════════
class TestHotkeyCreation:
    def test_default_construction(self):
        hk = Hotkey()
        assert hk.modifiers == []
        assert hk.key == ''
        assert hk.vk == 0

    def test_with_modifiers_and_key(self):
        hk = Hotkey(['ctrl', 'alt'], 'x', 0x58)
        assert hk.modifiers == ['ctrl', 'alt']
        assert hk.key == 'x'
        assert hk.vk == 0x58

    def test_normalize_modifier_order(self):
        hk = Hotkey(['shift', 'ctrl'], 'a', 0x41)
        assert hk.modifiers == ['ctrl', 'shift']

    def test_unknown_modifier_preserved(self):
        """未知修饰键不会被过滤，会保留并按排序规则放置。"""
        hk = Hotkey(['ctrl', 'unknown_mod', 'alt'], 'p', 0x50)
        assert 'unknown_mod' in hk.modifiers


class TestHotkeyString:
    def test_simple_hotkey_str(self):
        hk = Hotkey(['ctrl', 'alt', 'shift'], 'p', 0x50)
        assert 'Ctrl' in str(hk)
        assert 'Alt' in str(hk)
        assert 'Shift' in str(hk)
        assert 'P' in str(hk)

    def test_parse_ctrl_alt_p(self):
        hk = Hotkey.parse('Ctrl+Alt+P')
        assert 'ctrl' in hk.modifiers
        assert 'alt' in hk.modifiers
        assert hk.key == 'p'
        assert hk.vk == 0x50

    def test_parse_win_f1(self):
        hk = Hotkey.parse('Win+F1')
        assert 'win' in hk.modifiers
        assert hk.key == 'f1'

    def test_parse_single_key(self):
        hk = Hotkey.parse('F5')
        assert hk.modifiers == []
        assert hk.key == 'f5'


class TestHotkeyEquality:
    def test_equal_hotkeys(self):
        a = Hotkey(['ctrl', 'alt'], 'x', 0x58)
        b = Hotkey(['alt', 'ctrl'], 'x', 0x58)
        assert a == b

    def test_not_equal_different_key(self):
        a = Hotkey(['ctrl'], 'x', 0x58)
        b = Hotkey(['ctrl'], 'y', 0x59)
        assert a != b

    def test_not_equal_different_modifiers(self):
        a = Hotkey(['ctrl'], 'x', 0x58)
        b = Hotkey(['ctrl', 'alt'], 'x', 0x58)
        assert a != b

    def test_hashable(self):
        a = Hotkey(['ctrl', 'shift'], 'z', 0x5A)
        b = Hotkey(['shift', 'ctrl'], 'z', 0x5A)
        s = {a}
        assert b in s


class TestHotkeyModMask:
    def test_ctrl_alt_mask(self):
        hk = Hotkey(['ctrl', 'alt'], 'p', 0x50)
        mask = hk.mod_mask()
        assert mask & 0x0001
        assert mask & 0x0002
        assert not (mask & 0x0004)

    def test_empty_mask(self):
        hk = Hotkey([], 'f5', 0x74)
        assert hk.mod_mask() == 0


class TestHotkeySerialization:
    def test_roundtrip(self):
        orig = Hotkey(['ctrl', 'alt', 'shift'], 'p', 0x50)
        d = orig.to_dict()
        restored = Hotkey.from_dict(d)
        assert restored == orig
        assert restored.key == 'p'

    def test_from_dict_missing_modifiers(self):
        d = {'key': 'a', 'vk': 0x41}
        hk = Hotkey.from_dict(d)
        assert hk.modifiers == []
        assert hk.key == 'a'


class TestHotkeyFromModVk:
    def test_from_mod_vk_ctrl_alt(self):
        hk = Hotkey.from_mod_vk(0x0003, 0x50)
        assert 'ctrl' in hk.modifiers
        assert 'alt' in hk.modifiers
        assert 'shift' not in hk.modifiers
        assert 'win' not in hk.modifiers


# ═══════════════════════════════════════════════════════════════
# HotkeyManager 类
# ═══════════════════════════════════════════════════════════════
class TestHotkeyManagerInit:
    def test_initial_state(self):
        mgr = HotkeyManager()
        assert mgr.active is False
        assert mgr._hotkey is None


class TestCheckHotkeySafety:
    def test_safe_hotkey(self):
        """Ctrl+Alt+Shift+P 是安全的。"""
        safe, msg = check_hotkey_safety(
            Hotkey(['ctrl', 'alt', 'shift'], 'p', 0x50))
        assert safe is True

    def test_common_hotkeys_flagged(self):
        """常见系统快捷键应被标记为不安全。"""
        unsafes = [
            ('ctrl', 'c'),   # Ctrl+C - 复制
            ('ctrl', 'v'),   # Ctrl+V - 粘贴
            ('alt', 'f4'),   # Alt+F4 - 关闭窗口
            ('win', 'd'),    # Win+D - 显示桌面
            ('ctrl', 's'),   # Ctrl+S - 保存
        ]
        for mod, key in unsafes:
            vk = KEY_VK_MAP.get(key, 0)
            hk = Hotkey([mod], key, vk)
            safe, msg = check_hotkey_safety(hk)
            assert safe is False, f'{hk} 应被标记为不安全'


# ═══════════════════════════════════════════════════════════════
# KEY_VK_MAP 与 PARSABLE_KEYS
# ═══════════════════════════════════════════════════════════════
class TestKeyVkMap:
    def test_letters(self):
        for c in 'abcdefghijklmnopqrstuvwxyz':
            assert c in KEY_VK_MAP
            assert isinstance(KEY_VK_MAP[c], int)

    def test_numbers(self):
        for n in '0123456789':
            assert n in KEY_VK_MAP

    def test_function_keys_f1_to_f12(self):
        for i in range(1, 13):
            name = f'f{i}'
            assert name in KEY_VK_MAP, f'缺少 {name}'

    def test_navigation_keys(self):
        nav = ['space', 'tab', 'return', 'backspace',
               'delete', 'insert', 'home', 'end',
               'prior', 'next', 'escape']
        for k in nav:
            assert k in KEY_VK_MAP, f'缺少 {k}'

    def test_arrow_keys(self):
        arrows = ['left', 'right', 'up', 'down']
        for k in arrows:
            assert k in KEY_VK_MAP

    def test_vk_values_unique(self):
        vks = list(KEY_VK_MAP.values())
        assert len(vks) == len(set(vks))


class TestParsableKeys:
    def test_parsable_keys_subset(self):
        for k in PARSABLE_KEYS:
            assert k in KEY_VK_MAP

    def test_modifiers_not_in_parsable(self):
        for m in MODIFIER_NAMES:
            assert m not in PARSABLE_KEYS
