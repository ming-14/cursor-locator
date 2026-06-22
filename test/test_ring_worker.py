"""
@brief ring_worker 模块单元测试（Win32 API 使用 mock）
"""

import queue
from unittest.mock import patch, MagicMock

import pytest

from src.service.ring_worker import (
    _query_display_frequency, _get_display_timer_interval,
    _send_refresh_rate_info, init_module, _display_freq,
    MouseRingWindow, MSG_REFRESH_RATE,
)


# ═══════════════════════════════════════════════════════════════
# 模块级函数
# ═══════════════════════════════════════════════════════════════
class TestQueryDisplayFrequency:
    """验证 _query_display_frequency 的失败/异常路径。"""

    def test_query_failure_returns_zero_and_resets_freq(self):
        with patch('src.service.ring_worker._EnumDisplaySettingsW',
                   return_value=False):
            freq = _query_display_frequency()
            assert freq == 0
            import src.service.ring_worker as rw
            assert rw._display_freq == 0

    def test_query_exception_returns_zero(self):
        with patch('src.service.ring_worker._EnumDisplaySettingsW',
                   side_effect=OSError('API failed')):
            freq = _query_display_frequency()
            assert freq == 0


class TestGetDisplayTimerInterval:
    @patch('src.service.ring_worker._query_display_frequency')
    def test_144hz_interval(self, mock_query):
        mock_query.return_value = 144
        assert _get_display_timer_interval() == 7

    @patch('src.service.ring_worker._query_display_frequency')
    def test_60hz_interval(self, mock_query):
        mock_query.return_value = 60
        assert _get_display_timer_interval() == 17

    @patch('src.service.ring_worker._query_display_frequency')
    def test_240hz_min_4ms(self, mock_query):
        mock_query.return_value = 240
        assert _get_display_timer_interval() == 4

    @patch('src.service.ring_worker._query_display_frequency')
    def test_fallback_4ms(self, mock_query):
        mock_query.return_value = 0
        assert _get_display_timer_interval() == 4


class TestSendRefreshRateInfo:
    def test_sends_message_with_freq(self):
        mq = queue.Queue()
        init_module(mq)
        import src.service.ring_worker as rw
        rw._display_freq = 144
        _send_refresh_rate_info()
        msg = mq.get_nowait()
        assert msg['type'] == MSG_REFRESH_RATE
        assert msg['freq'] == 144

    def test_sends_zero_when_unknown(self):
        mq = queue.Queue()
        init_module(mq)
        import src.service.ring_worker as rw
        rw._display_freq = 0
        _send_refresh_rate_info()
        msg = mq.get_nowait()
        assert msg['freq'] == 0

    def test_no_crash_when_queue_none(self):
        import src.service.ring_worker as rw
        rw._msg_queue = None
        _send_refresh_rate_info()


# ═══════════════════════════════════════════════════════════════
# MouseRingWindow._compute_timer_interval
# ═══════════════════════════════════════════════════════════════
class TestComputeTimerInterval:
    """通过 __func__ 手动绑定到 mock 实例测试 _compute_timer_interval。"""

    def _make_win(self):
        win = object.__new__(MouseRingWindow)
        win.cfg = MagicMock()
        bound = MouseRingWindow._compute_timer_interval.__get__(win, MouseRingWindow)
        win._compute_timer_interval = bound
        return win

    def test_auto_mode_144hz(self):
        win = self._make_win()
        with patch('src.service.ring_worker._query_display_frequency',
                   return_value=144), \
             patch('src.service.ring_worker._display_freq', 144):
            snap = {
                'timer_mode': 'auto', 'timer_multiplier': 1.0,
                'timer_interval_custom': 16, 'track_interval': 20,
            }
            assert win._compute_timer_interval(snap) == 7

    def test_auto_mode_144hz_mult_2(self):
        win = self._make_win()
        with patch('src.service.ring_worker._query_display_frequency',
                   return_value=144), \
             patch('src.service.ring_worker._display_freq', 144):
            snap = {
                'timer_mode': 'auto', 'timer_multiplier': 2.0,
                'timer_interval_custom': 16, 'track_interval': 100,
            }
            assert win._compute_timer_interval(snap) == 14

    def test_auto_mode_capped_by_track(self):
        win = self._make_win()
        with patch('src.service.ring_worker._query_display_frequency',
                   return_value=30), \
             patch('src.service.ring_worker._display_freq', 30):
            snap = {
                'timer_mode': 'auto', 'timer_multiplier': 1.0,
                'timer_interval_custom': 16, 'track_interval': 20,
            }
            assert win._compute_timer_interval(snap) == 20

    def test_auto_144hz_mult_25(self):
        win = self._make_win()
        with patch('src.service.ring_worker._query_display_frequency',
                   return_value=144), \
             patch('src.service.ring_worker._display_freq', 144):
            snap = {
                'timer_mode': 'auto', 'timer_multiplier': 2.5,
                'timer_interval_custom': 16, 'track_interval': 60,
            }
            assert win._compute_timer_interval(snap) == 17

    def test_custom_mode(self):
        win = self._make_win()
        snap = {
            'timer_mode': 'custom', 'timer_multiplier': 1.0,
            'timer_interval_custom': 50, 'track_interval': 100,
        }
        assert win._compute_timer_interval(snap) == 50

    def test_custom_mode_capped_by_track(self):
        win = self._make_win()
        snap = {
            'timer_mode': 'custom', 'timer_interval_custom': 50,
            'track_interval': 30,
        }
        assert win._compute_timer_interval(snap) == 30

    def test_custom_min_4ms(self):
        win = self._make_win()
        snap = {
            'timer_mode': 'custom', 'timer_interval_custom': 1,
            'track_interval': 100,
        }
        assert win._compute_timer_interval(snap) == 4

    def test_auto_no_display_fallback(self):
        win = self._make_win()
        with patch('src.service.ring_worker._query_display_frequency',
                   return_value=0), \
             patch('src.service.ring_worker._display_freq', 0):
            snap = {
                'timer_mode': 'auto', 'timer_multiplier': 1.0,
                'timer_interval_custom': 16, 'track_interval': 100,
            }
            assert win._compute_timer_interval(snap) == 4


class TestInitModule:
    def test_init_sets_message_queue(self):
        mq = queue.Queue()
        init_module(mq)
        import src.service.ring_worker as rw
        assert rw._msg_queue is mq

    def test_double_init_override(self):
        mq1 = queue.Queue()
        mq2 = queue.Queue()
        init_module(mq1)
        init_module(mq2)
        import src.service.ring_worker as rw
        assert rw._msg_queue is mq2
