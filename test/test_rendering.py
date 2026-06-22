"""
@brief rendering 模块单元测试（纯数学函数）
"""

import math

import pytest

from src.core.rendering import build_alpha_mask, render_ring_from_mask


class TestBuildAlphaMask:
    def test_mask_size(self):
        mask = build_alpha_mask(32, outer_r=12, inner_r=6)
        assert len(mask) == 32 * 32

    def test_mask_center_transparent(self):
        """圆环内部（圆心附近）alpha 应为 0。"""
        size = 64
        outer_r, inner_r = 20, 10
        mask = build_alpha_mask(size, outer_r, inner_r)
        half = size // 2
        center_alpha = mask[half * size + half]
        assert center_alpha == 0

    def test_mask_ring_solid(self):
        """内外半径之间的环体主体 alpha 应为 255。"""
        size = 64
        outer_r, inner_r = 20, 10
        mask = build_alpha_mask(size, outer_r, inner_r)
        half = size // 2
        # 距离圆心 ≈ 15 的点，在环体内部
        y = half
        x = half + 15
        a = mask[y * size + x]
        assert a == 255

    def test_mask_outside_transparent(self):
        """圆环外部远点 alpha 为 0。"""
        size = 64
        outer_r, inner_r = 10, 5
        mask = build_alpha_mask(size, outer_r, inner_r)
        # 左上角，远离圆环
        assert mask[0] == 0

    def test_mask_antialiasing_edge(self):
        """外边界应有抗锯齿过渡（0 < alpha < 255）。"""
        size = 64
        outer_r, inner_r = 16, 8
        mask = build_alpha_mask(size, outer_r, inner_r)
        half = size // 2
        x = half + outer_r  # 正好在外半径处
        y = half
        a = mask[y * size + x]
        assert 0 < a < 255, f'边缘应有过渡 alpha={a}'

    def test_mask_zero_inner_radius_is_solid_disk(self):
        """inner_r=0 时，中心因抗锯齿为半透明，但近中心已不透明。"""
        size = 32
        mask = build_alpha_mask(size, outer_r=12, inner_r=0)
        half = size // 2
        # 距离圆心约 10 的位置（内外之间）应为 255
        x = half + 10
        y = half
        a = mask[y * size + x]
        assert a == 255

    def test_equal_radii_produces_thin_aa_ring(self):
        """inner_r == outer_r 时仅抗锯齿过渡区有像素。"""
        size = 64
        mask = build_alpha_mask(size, outer_r=10, inner_r=10)
        non_zero = sum(1 for a in mask if a > 0)
        total = size * size
        assert non_zero < total * 0.12  # 过渡区不到 12%

    def test_negative_inner_gives_solid_disk(self):
        """负数 inner_r 等价于 solid disk（无条件跳过内圈透明区）。"""
        size = 16
        outer_r, inner_r = 6, -2
        mask = build_alpha_mask(size, outer_r, inner_r)
        half = size // 2
        # 内圈从 -0.5 到 -1.5 的过渡区不存在（dist>=0），直接从 solid 开始
        center = mask[half * size + half]
        assert center == 255

    def test_mask_all_sizes(self):
        for s in [8, 16, 32, 64, 128]:
            mask = build_alpha_mask(s, outer_r=s // 4, inner_r=s // 8)
            assert len(mask) == s * s


class TestRenderRingFromMask:
    def test_output_size(self):
        size = 32
        mask = build_alpha_mask(size, outer_r=10, inner_r=5)
        buf = render_ring_from_mask(mask, size, 255, 0, 0, 255)
        assert len(buf) == size * size * 4

    def test_black_color(self):
        size = 16
        mask = bytearray(size * size)
        mask[0] = 200
        buf = render_ring_from_mask(mask, size, 0, 0, 0, 255)
        assert buf[0] == 0      # B
        assert buf[1] == 0      # G
        assert buf[2] == 0      # R
        assert buf[3] == 200    # A

    def test_premultiplied_alpha(self):
        size = 8
        mask = bytearray(size * size)
        mask[0] = 128
        buf = render_ring_from_mask(mask, size, 200, 100, 50, 255)
        assert buf[0] == 50 * 128 // 255   # B
        assert buf[1] == 100 * 128 // 255  # G
        assert buf[2] == 200 * 128 // 255  # R
        assert buf[3] == 128               # A

    def test_user_alpha_scaling(self):
        size = 8
        mask = bytearray(size * size)
        mask[0] = 255
        buf_half = render_ring_from_mask(mask, size, 100, 150, 200, 128)
        assert buf_half[3] == 128
        ratio = 128 / 255
        assert buf_half[0] == int(200 * ratio)
        assert buf_half[1] == int(150 * ratio)
        assert buf_half[2] == int(100 * ratio)

    def test_transparent_mask(self):
        size = 16
        mask = bytearray(size * size)
        buf = render_ring_from_mask(mask, size, 255, 0, 0, 255)
        assert all(b == 0 for b in buf)

    def test_consistent_with_mask(self):
        size = 16
        mask = build_alpha_mask(size, outer_r=6, inner_r=3)
        buf = render_ring_from_mask(mask, size, 80, 160, 240, 200)
        for py in range(size):
            for px in range(size):
                off = (py * size + px) * 4
                if mask[py * size + px] == 0:
                    assert buf[off:off + 4] == b'\x00\x00\x00\x00', \
                        f'({px},{py}) mask=0 但 buf 非零'


class TestBuildAlphaMaskEdgeCases:
    def test_minimal_size(self):
        mask = build_alpha_mask(4, outer_r=2, inner_r=1)
        assert len(mask) == 16

    def test_radius_exceeds_size(self):
        mask = build_alpha_mask(16, outer_r=20, inner_r=5)
        assert len(mask) == 256
