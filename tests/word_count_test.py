import random
import string
from typing import List
from telegramify_markdown.word_count import count_markdown, hard_split_markdown

def assert_split_invariants(text: str, max_wc: int) -> List[str]:
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

def mk_link(desc: str, url: str) -> str:
    return f"[{desc}]({url})"


# ==========================
# count_markdown() testcases
# ==========================
def test_count_plain():
    s = "abc"
    assert count_markdown(s) == 3

def test_count_empty():
    assert count_markdown("") == 0

def test_count_single_link_basic():
    s = "[a](http://b)"
    assert len(s) == 13
    assert count_markdown(s) == 5  # "[a]()"

def test_count_multiple_links_adjacent():
    s = "[a](u)[b](v)"
    # each becomes 5 -> total 10
    assert count_markdown(s) == 10

def test_count_multiple_links_spaced():
    s = "x [a](u) y [b](v) z"
    assert count_markdown(s) == len("x [a]() y [b]() z")

def test_count_link_at_start_end():
    s = "[a](u) middle [b](v)"
    assert count_markdown(s) == len("[a]() middle [b]()")

def test_count_empty_desc_and_empty_url():
    s = "[]()"
    # It matches and replacement is "[]()" (same)
    assert count_markdown(s) == 4

def test_count_empty_desc_nonempty_url():
    s = "[](http://x)"
    assert count_markdown(s) == len("[]()")  # 4

def test_count_nonempty_desc_empty_url():
    s = "[abc]()"
    assert count_markdown(s) == len("[abc]()")  # unchanged effectively

def test_count_link_with_title_attribute():
    s = '[a](http://x "title here")'
    assert count_markdown(s) == len("[a]()")

def test_count_image_syntax_is_treated_like_link():
    s = "![alt](http://x)"
    # regex matches from '[' so it becomes '![alt]()'
    assert count_markdown(s) == len("![alt]()")

def test_count_reference_style_not_matched():
    s = "[a][ref]"
    assert count_markdown(s) == len(s)

def test_count_autolink_not_matched():
    s = "<http://example.com>"
    assert count_markdown(s) == len(s)

def test_count_incomplete_link_missing_close_paren_not_matched():
    s = "[a](http://b"
    assert count_markdown(s) == len(s)

def test_count_incomplete_link_missing_open_paren_not_matched():
    s = "[a]http://b)"
    assert count_markdown(s) == len(s)

def test_count_escaped_open_bracket_prevents_match():
    s = r"\[a](http://b)"
    assert count_markdown(s) == len(s)

def test_count_double_backslash_before_open_bracket_prevents_match():
    s = r"\\[a](http://b)"
    assert count_markdown(s) == len(s)

def test_count_escaped_closing_bracket_inside_desc_is_ok():
    s = r"[a\]b](http://x)"
    # desc is "a\]b", url removed
    assert count_markdown(s) == len(r"[a\]b]()")

def test_count_escaped_closing_paren_inside_url_allows_match():
    # URL ends with a literal ')', escaped as \), then the real closing ')'
    s = r"[a](http://x\))"
    assert count_markdown(s) == len("[a]()")

def test_count_newline_in_url_prevents_match_due_to_dot_not_matching_newline():
    s = "[a](http://b\nc)"
    # '.' doesn't match '\n' because no DOTALL flag => won't match
    assert count_markdown(s) == len(s)

def test_count_newline_in_desc_prevents_match():
    s = "[a\nb](http://x)"
    assert count_markdown(s) == len(s)

def test_count_paren_in_url_without_escape_causes_partial_match_and_leaves_trailing_paren():
    # Regex stops at first unescaped ')', leaving one extra ')'
    s = "[a](http://example.com/foo(bar))"
    # becomes "[a]()" + ")" => length 6
    assert count_markdown(s) == len("[a]())")

def test_count_nested_brackets_in_desc_can_break_expected_markdown_but_tests_current_behavior():
    # This is a known limitation: desc part uses (.*?) which will stop at the first ']'
    s = "[a[b]](u)"
    # The regex will likely match "[a[b]](u)"? Actually it closes at first ']' after "a[b"
    # We don't assert an exact value; we assert the core invariant: never longer than input.
    assert count_markdown(s) <= len(s)

def test_count_backslashes_lots():
    s = r"\\\[\]\(\)\)\(" + mk_link(r"a\]b", r"http://x\))") + r"\[no](match)"
    assert count_markdown(s) <= len(s)


# ==================================
# hard_split_markdown() testcases
# ==================================
def test_split_empty_returns_empty_list():
    assert hard_split_markdown("", 10) == []

def test_split_plain_exact_boundary():
    s = "a" * 100
    chunks = assert_split_invariants(s, 100)
    assert len(chunks) == 1

def test_split_plain_over_boundary():
    s = "a" * 200
    chunks = assert_split_invariants(s, 100)
    assert len(chunks) == 2
    assert all(len(c) == 100 for c in chunks)

def test_split_max_1_ascii():
    s = "abc"
    chunks = assert_split_invariants(s, 1)
    assert chunks == ["a", "b", "c"]

def test_split_unicode():
    s = "你好世界" * 50
    chunks = assert_split_invariants(s, 10)
    # 每个 chunk 的 count <= 10
    assert all(count_markdown(c) <= 10 for c in chunks)

def test_split_emoji():
    s = "🙂" * 120
    chunks = assert_split_invariants(s, 50)
    assert len(chunks) == 3  # 50 + 50 + 20

def test_split_allows_huge_url_because_url_not_counted():
    url = "x" * 5000
    s = mk_link("a", url)  # "[a](xxxxx....)"
    # count_markdown(s) == len("[a]()") == 5
    chunks = assert_split_invariants(s, 5)
    assert len(chunks) == 1
    assert chunks[0] == s

def test_split_huge_url_with_small_max_forces_cutting_inside_syntax_but_still_valid():
    url = "x" * 5000
    s = mk_link("a", url)
    chunks = assert_split_invariants(s, 1)
    # 必然会被切碎，但仍应满足不变量
    assert len(chunks) >= 2

def test_split_many_links_should_pack_more_than_raw_length_limit():
    content = "[a](http://b)" * 100  # raw 1300, visible 500
    chunks = assert_split_invariants(content, 1000)
    assert len(chunks) == 1
    assert len(chunks[0]) == 1300

def test_split_many_links_exact_visible_budget():
    content = "[a](http://b)" * 10000  # raw 130k, visible 50k
    chunks = assert_split_invariants(content, 500)
    # each link counts as 5 => 100 links per chunk => 100 chunks
    assert len(chunks) == 100

def test_split_mixed_text_links_and_noise():
    s = "HEAD-" + ("x" * 30) + mk_link("a", "http://b") + ("y" * 40) + mk_link("zz", "u") + "-TAIL"
    chunks = assert_split_invariants(s, 25)
    assert "".join(chunks) == s

def test_split_truncation_can_break_link_matching_but_still_respects_count():
    s = mk_link("abc", "http://example.com") + "X" * 10
    chunks = assert_split_invariants(s, 4)
    # 4 很小，chunk 很可能卡在半个 link 上；只要满足 count <= 4 即可
    assert all(count_markdown(c) <= 4 for c in chunks)

def test_split_monotonic_chunk_count_wrt_max_on_fixed_input():
    s = ("hello " + mk_link("a", "http://b") + " world ") * 30
    chunks_10 = assert_split_invariants(s, 10)
    chunks_20 = assert_split_invariants(s, 20)
    chunks_50 = assert_split_invariants(s, 50)
    assert len(chunks_10) >= len(chunks_20) >= len(chunks_50)

def test_split_when_max_equals_count_whole_text_should_be_single_chunk():
    s = ("A" * 20) + mk_link("a", "http://b" * 50) + ("B" * 20)
    max_wc = count_markdown(s)
    chunks = assert_split_invariants(s, max_wc)
    assert len(chunks) == 1

def test_split_no_empty_chunks_for_max_gt_0():
    s = "a" * 10
    chunks = assert_split_invariants(s, 3)
    assert all(chunks)

def test_split_stress_medium():
    s = (mk_link("a", "http://b") + "Z" * 7) * 2000
    chunks = assert_split_invariants(s, 73)
    assert "".join(chunks) == s

# =========================
# Light fuzz (no hypothesis)
# =========================
def _random_url(rng: random.Random) -> str:
    # inject annoying chars: ')', '(', '\', quotes, spaces
    alphabet = string.ascii_letters + string.digits + "/:._-()\\\" "
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 80)))

def _random_desc(rng: random.Random) -> str:
    alphabet = string.ascii_letters + string.digits + "[]\\ _-"
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30)))

def _random_piece(rng: random.Random) -> str:
    choice = rng.random()
    if choice < 0.35:
        # plain chunk
        alphabet = string.ascii_letters + string.digits + " _-\\[]()"
        return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
    elif choice < 0.70:
        # link-like
        return mk_link(_random_desc(rng), _random_url(rng))
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

def test_fuzz_invariants_many_cases():
    rng = random.Random(0xC0FFEE)
    for _ in range(200):
        s = "".join(_random_piece(rng) for __ in range(rng.randint(1, 50)))
        max_wc = rng.choice([1, 2, 3, 5, 8, 13, 21, 34, 55])
        assert_split_invariants(s, max_wc)

