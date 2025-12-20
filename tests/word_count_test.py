import random
import string
import unittest
from typing import List
from telegramify_markdown.word_count import count_markdown, hard_split_markdown


def _assert_split_invariants(text: str, max_wc: int) -> List[str]:
    """Helper function to verify split invariants."""
    chunks = hard_split_markdown(text, max_wc)

    # 1) concat must equal original
    assert "".join(chunks) == text

    # 2) for non-empty input and max_wc > 0: no empty chunk
    if text and max_wc > 0:
        assert all(chunks), f"Empty chunk detected: {chunks!r}"

    # 3) each chunk must satisfy count_markdown(chunk) <= max_wc (for max_wc>0)
    if max_wc > 0:
        for i, ch in enumerate(chunks):
            c = count_markdown(ch)
            assert c <= max_wc, f"chunk[{i}] violates: count={c}, max={max_wc}, chunk={ch!r}"

    # 4) count_markdown should never exceed raw length (your stated goal)
    for s in [text] + chunks:
        assert count_markdown(s) <= len(s)

    return chunks


def _mk_link(desc: str, url: str) -> str:
    """Helper function to create markdown link."""
    return f"[{desc}]({url})"


def _random_url(rng: random.Random) -> str:
    """Generate random URL with annoying chars."""
    alphabet = string.ascii_letters + string.digits + "/:._-()\\\" "
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 80)))


def _random_desc(rng: random.Random) -> str:
    """Generate random link description."""
    alphabet = string.ascii_letters + string.digits + "[]\\ _-"
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30)))


def _random_piece(rng: random.Random) -> str:
    """Generate random markdown piece for fuzz testing."""
    choice = rng.random()
    if choice < 0.35:
        # plain chunk
        alphabet = string.ascii_letters + string.digits + " _-\\[]()"
        return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
    elif choice < 0.70:
        # link-like
        return _mk_link(_random_desc(rng), _random_url(rng))
    else:
        # tricky escapes / incomplete
        patterns = [
            r"\[a](u)",          # escaped open bracket => should not match
            r"[a](u",            # missing ')'
            r"[a\nb](u)",        # newline in desc
            r"[a](u\nv)",        # newline in url
            r"[a](x\))",         # escaped ')'
            r"[a](x(y))",        # nested parens
            r"![alt](url)",      # image
            r"[a][ref]",         # ref link
        ]
        return rng.choice(patterns)


class CountMarkdownTest(unittest.TestCase):
    """Tests for count_markdown() function."""

    def test_count_plain(self):
        s = "abc"
        self.assertEqual(count_markdown(s), 3)

    def test_count_empty(self):
        self.assertEqual(count_markdown(""), 0)

    def test_count_single_link_basic(self):
        s = "[a](http://b)"
        self.assertEqual(len(s), 13)
        self.assertEqual(count_markdown(s), 5)  # "[a]()"

    def test_count_multiple_links_adjacent(self):
        s = "[a](u)[b](v)"
        # each becomes 5 -> total 10
        self.assertEqual(count_markdown(s), 10)

    def test_count_multiple_links_spaced(self):
        s = "x [a](u) y [b](v) z"
        self.assertEqual(count_markdown(s), len("x [a]() y [b]() z"))

    def test_count_link_at_start_end(self):
        s = "[a](u) middle [b](v)"
        self.assertEqual(count_markdown(s), len("[a]() middle [b]()"))

    def test_count_empty_desc_and_empty_url(self):
        s = "[]()"
        # It matches and replacement is "[]()" (same)
        self.assertEqual(count_markdown(s), 4)

    def test_count_empty_desc_nonempty_url(self):
        s = "[](http://x)"
        self.assertEqual(count_markdown(s), len("[]()")  )  # 4

    def test_count_nonempty_desc_empty_url(self):
        s = "[abc]()"
        self.assertEqual(count_markdown(s), len("[abc]()"))  # unchanged effectively

    def test_count_link_with_title_attribute(self):
        s = '[a](http://x "title here")'
        self.assertEqual(count_markdown(s), len("[a]()"))

    def test_count_image_syntax_is_treated_like_link(self):
        s = "![alt](http://x)"
        # regex matches from '[' so it becomes '![alt]()'
        self.assertEqual(count_markdown(s), len("![alt]()"))

    def test_count_reference_style_not_matched(self):
        s = "[a][ref]"
        self.assertEqual(count_markdown(s), len(s))

    def test_count_autolink_not_matched(self):
        s = "<http://example.com>"
        self.assertEqual(count_markdown(s), len(s))

    def test_count_incomplete_link_missing_close_paren_not_matched(self):
        s = "[a](http://b"
        self.assertEqual(count_markdown(s), len(s))

    def test_count_incomplete_link_missing_open_paren_not_matched(self):
        s = "[a]http://b)"
        self.assertEqual(count_markdown(s), len(s))

    def test_count_escaped_open_bracket_prevents_match(self):
        s = r"\[a](http://b)"
        self.assertEqual(count_markdown(s), len(s))

    def test_count_double_backslash_before_open_bracket_prevents_match(self):
        s = r"\\[a](http://b)"
        self.assertEqual(count_markdown(s), len(s))

    def test_count_escaped_closing_bracket_inside_desc_is_ok(self):
        s = r"[a\]b](http://x)"
        # desc is "a\]b", url removed
        self.assertEqual(count_markdown(s), len(r"[a\]b]()"))

    def test_count_escaped_closing_paren_inside_url_allows_match(self):
        # URL ends with a literal ')', escaped as \), then the real closing ')'
        s = r"[a](http://x\))"
        self.assertEqual(count_markdown(s), len("[a]()"))

    def test_count_newline_in_url_prevents_match_due_to_dot_not_matching_newline(self):
        s = "[a](http://b\nc)"
        # '.' doesn't match '\n' because no DOTALL flag => won't match
        self.assertEqual(count_markdown(s), len(s))

    def test_count_newline_in_desc_prevents_match(self):
        s = "[a\nb](http://x)"
        self.assertEqual(count_markdown(s), len(s))

    def test_count_paren_in_url_without_escape_causes_partial_match_and_leaves_trailing_paren(self):
        # Regex stops at first unescaped ')', leaving one extra ')'
        s = "[a](http://example.com/foo(bar))"
        # becomes "[a]()" + ")" => length 6
        self.assertEqual(count_markdown(s), len("[a]())"))

    def test_count_nested_brackets_in_desc_can_break_expected_markdown_but_tests_current_behavior(self):
        # This is a known limitation: desc part uses (.*?) which will stop at the first ']'
        s = "[a[b]](u)"
        # The regex will likely match "[a[b]](u)"? Actually it closes at first ']' after "a[b"
        # We don't assert an exact value; we assert the core invariant: never longer than input.
        self.assertLessEqual(count_markdown(s), len(s))

    def test_count_backslashes_lots(self):
        s = r"\\\[\]\(\)\)\(" + _mk_link(r"a\]b", r"http://x\))") + r"\[no](match)"
        self.assertLessEqual(count_markdown(s), len(s))


class HardSplitMarkdownTest(unittest.TestCase):
    """Tests for hard_split_markdown() function."""

    def test_split_empty_returns_empty_list(self):
        self.assertEqual(hard_split_markdown("", 10), [])

    def test_split_plain_exact_boundary(self):
        s = "a" * 100
        chunks = _assert_split_invariants(s, 100)
        self.assertEqual(len(chunks), 1)

    def test_split_plain_over_boundary(self):
        s = "a" * 200
        chunks = _assert_split_invariants(s, 100)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(len(c) == 100 for c in chunks))

    def test_split_max_1_ascii(self):
        s = "abc"
        chunks = _assert_split_invariants(s, 1)
        self.assertEqual(chunks, ["a", "b", "c"])

    def test_split_unicode(self):
        s = "你好世界" * 50
        chunks = _assert_split_invariants(s, 10)
        # 每个 chunk 的 count <= 10
        self.assertTrue(all(count_markdown(c) <= 10 for c in chunks))

    def test_split_emoji(self):
        s = "🙂" * 120
        chunks = _assert_split_invariants(s, 50)
        self.assertEqual(len(chunks), 3)  # 50 + 50 + 20

    def test_split_allows_huge_url_because_url_not_counted(self):
        url = "x" * 5000
        s = _mk_link("a", url)  # "[a](xxxxx....)"
        # count_markdown(s) == len("[a]()") == 5
        chunks = _assert_split_invariants(s, 5)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], s)

    def test_split_huge_url_with_small_max_forces_cutting_inside_syntax_but_still_valid(self):
        url = "x" * 5000
        s = _mk_link("a", url)
        chunks = _assert_split_invariants(s, 1)
        # 必然会被切碎，但仍应满足不变量
        self.assertGreaterEqual(len(chunks), 2)

    def test_split_many_links_should_pack_more_than_raw_length_limit(self):
        content = "[a](http://b)" * 100  # raw 1300, visible 500
        chunks = _assert_split_invariants(content, 1000)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 1300)

    def test_split_many_links_exact_visible_budget(self):
        content = "[a](http://b)" * 10000  # raw 130k, visible 50k
        chunks = _assert_split_invariants(content, 500)
        # each link counts as 5 => 100 links per chunk => 100 chunks
        self.assertEqual(len(chunks), 100)

    def test_split_mixed_text_links_and_noise(self):
        s = "HEAD-" + ("x" * 30) + _mk_link("a", "http://b") + ("y" * 40) + _mk_link("zz", "u") + "-TAIL"
        chunks = _assert_split_invariants(s, 25)
        self.assertEqual("".join(chunks), s)

    def test_split_truncation_can_break_link_matching_but_still_respects_count(self):
        s = _mk_link("abc", "http://example.com") + "X" * 10
        chunks = _assert_split_invariants(s, 4)
        # 4 很小，chunk 很可能卡在半个 link 上；只要满足 count <= 4 即可
        self.assertTrue(all(count_markdown(c) <= 4 for c in chunks))

    def test_split_monotonic_chunk_count_wrt_max_on_fixed_input(self):
        s = ("hello " + _mk_link("a", "http://b") + " world ") * 30
        chunks_10 = _assert_split_invariants(s, 10)
        chunks_20 = _assert_split_invariants(s, 20)
        chunks_50 = _assert_split_invariants(s, 50)
        self.assertGreaterEqual(len(chunks_10), len(chunks_20))
        self.assertGreaterEqual(len(chunks_20), len(chunks_50))

    def test_split_when_max_equals_count_whole_text_should_be_single_chunk(self):
        s = ("A" * 20) + _mk_link("a", "http://b" * 50) + ("B" * 20)
        max_wc = count_markdown(s)
        chunks = _assert_split_invariants(s, max_wc)
        self.assertEqual(len(chunks), 1)

    def test_split_no_empty_chunks_for_max_gt_0(self):
        s = "a" * 10
        chunks = _assert_split_invariants(s, 3)
        self.assertTrue(all(chunks))

    def test_split_stress_medium(self):
        s = (_mk_link("a", "http://b") + "Z" * 7) * 2000
        chunks = _assert_split_invariants(s, 73)
        self.assertEqual("".join(chunks), s)

    def test_fuzz_invariants_many_cases(self):
        rng = random.Random(0xC0FFEE)
        for _ in range(200):
            s = "".join(_random_piece(rng) for __ in range(rng.randint(1, 50)))
            max_wc = rng.choice([1, 2, 3, 5, 8, 13, 21, 34, 55])
            _assert_split_invariants(s, max_wc)


if __name__ == "__main__":
    unittest.main()
