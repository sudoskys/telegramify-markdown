"""Complexity regression tests for the conversion paths.

These assert a *ratio* -- quadrupling the input must not multiply the time by
more than ten -- rather than an absolute duration. Absolute timings depend on
the machine; the ratio does not. A linear implementation lands around 4x and a
quadratic one around 16x, so a 10x threshold separates them cleanly while
leaving room for CI noise.

Two quadratic regressions have shipped here before:
- _TextBuffer.py_offset recomputed sum(len(p) for p in _parts) on every read,
  and _on_start_item reads it once per list item; a 4000-item document took
  400ms.
- The MarkdownV2 blockquote lookup scanned bq_ranges linearly once per line;
  a 43KB all-quote document took 161ms.
"""

import time
import unittest

from telegramify_markdown import convert, markdownify

# Maximum time growth allowed for 4x the input. Linear is ~4x, quadratic ~16x.
_MAX_GROWTH = 10.0


def _best_of(fn, rounds: int = 3) -> float:
    """Take the minimum across rounds to mask GC and scheduler noise."""
    best = float("inf")
    for _ in range(rounds):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


class ConversionScalingTest(unittest.TestCase):
    def _assert_scales_linearly(self, build, small: int, large: int):
        self.assertEqual(large, small * 4, "the threshold assumes a 4x step")
        small_time = _best_of(lambda: convert(build(small), latex_escape=False))
        large_time = _best_of(lambda: convert(build(large), latex_escape=False))
        growth = large_time / small_time
        self.assertLess(
            growth,
            _MAX_GROWTH,
            f"{small}->{large} grew {growth:.1f}x "
            f"({small_time * 1000:.2f}ms -> {large_time * 1000:.2f}ms), "
            f"suspected quadratic complexity",
        )

    def test_list_items_scale_linearly(self):
        self._assert_scales_linearly(
            lambda n: "\n".join(f"- item {i}" for i in range(n)), 500, 2000
        )

    def test_paragraphs_scale_linearly(self):
        self._assert_scales_linearly(
            lambda n: "\n\n".join(f"para {i}" for i in range(n)), 500, 2000
        )


class MarkdownV2ScalingTest(unittest.TestCase):
    def test_blockquotes_scale_linearly(self):
        def build(n: int) -> str:
            return "\n\n".join("> quote line\n> second line" for _ in range(n))

        small_time = _best_of(lambda: markdownify(build(400)))
        large_time = _best_of(lambda: markdownify(build(1600)))
        growth = large_time / small_time
        self.assertLess(
            growth,
            _MAX_GROWTH,
            f"400->1600 quotes grew {growth:.1f}x "
            f"({small_time * 1000:.2f}ms -> {large_time * 1000:.2f}ms), "
            f"suspected quadratic complexity",
        )


if __name__ == "__main__":
    unittest.main()
