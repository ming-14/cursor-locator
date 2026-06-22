"""
@brief pixel_color 模块单元测试
"""

import pytest

from src.core.pixel_color import (
    ALGO_LIST, ALGO_NAMES, DEFAULT_ALGO,
    compute_complement, get_pixel_color,
)


class TestComputeComplement:
    def test_invert_simple(self):
        """简单反色各分量 255 - c。"""
        result = compute_complement((100, 150, 200), algo_name='invert')
        assert result == (155, 105, 55)

    def test_invert_black(self):
        assert compute_complement((0, 0, 0), algo_name='invert') == (255, 255, 255)

    def test_invert_white(self):
        assert compute_complement((255, 255, 255), algo_name='invert') == (0, 0, 0)

    def test_luminance_mid_gray_uses_hsl(self):
        """中灰 (128,128,128) 亮度在 80-175 之间，使用 hsl 旋转。"""
        result = compute_complement((128, 128, 128), algo_name='luminance')
        # hsl_rotate 对于纯灰 (l≈0.502>0.5) 返回 (0,0,0)
        assert result == (0, 0, 0)

    def test_luminance_dark_uses_invert(self):
        """暗色 (20,20,20) 亮度 < 80，使用简单反色。"""
        result = compute_complement((20, 20, 20), algo_name='luminance')
        assert result == (235, 235, 235)

    def test_luminance_bright_uses_invert(self):
        """亮色 (200,200,200) 亮度 > 175，使用简单反色。"""
        result = compute_complement((200, 200, 200), algo_name='luminance')
        assert result == (55, 55, 55)

    def test_black_white_algo(self):
        dark = compute_complement((30, 30, 30), algo_name='black_white')
        bright = compute_complement((200, 200, 200), algo_name='black_white')
        assert dark == (255, 255, 255)
        assert bright == (0, 0, 0)

    def test_gray_invert(self):
        """灰度反色：先算亮度再取反。"""
        result = compute_complement((100, 150, 200), algo_name='gray_invert')
        # luminance = 0.2126*100 + 0.7152*150 + 0.0722*200 = 142.98
        # int(round(142.98)) = 143, 255-143 = 112
        assert result == (112, 112, 112)

    def test_default_algo_is_luminance(self):
        assert DEFAULT_ALGO == 'luminance'

    def test_unknown_algo_falls_back_to_luminance(self):
        """未知算法名回退到 DEFAULT_ALGO='luminance'。"""
        result = compute_complement((128, 128, 128), algo_name='nonexistent')
        assert result == (0, 0, 0)  # luminance 对中灰的结果

    def test_all_algos_return_valid_tuple(self):
        test_colors = [
            (0, 0, 0), (255, 255, 255), (128, 128, 128),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
            (100, 150, 200),
        ]
        for algo in ALGO_LIST:
            for color in test_colors:
                result = compute_complement(color, algo_name=algo)
                assert isinstance(result, tuple) and len(result) == 3
                assert all(0 <= c <= 255 for c in result), \
                    f'algo={algo} color={color} → {result}'

    def test_hsl_rotate_red_to_cyan(self):
        result = compute_complement((255, 0, 0), algo_name='hsl_rotate')
        assert result[0] < 30
        assert result[1] > 200
        assert result[2] > 200


class TestAlgoListAndNames:
    def test_algo_list_contains_all(self):
        for a in ['invert', 'hsl_rotate', 'luminance', 'black_white', 'gray_invert']:
            assert a in ALGO_LIST

    def test_algo_names_match_list(self):
        assert set(ALGO_NAMES.keys()) == set(ALGO_LIST)

    def test_algo_names_readable(self):
        assert ALGO_NAMES['invert'] == '简单反色'
        assert ALGO_NAMES['luminance'] == '感知亮度自适应'


class TestGetPixelColor:
    def test_get_pixel_returns_tuple(self):
        result = get_pixel_color(0, 0)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_get_pixel_range(self):
        result = get_pixel_color(100, 100)
        assert all(0 <= c <= 255 for c in result)
