import logging
import unittest
from html import unescape

from telegramify_markdown import InputRichMessage, RichMessage, richify, split_rich, telegramify_rich
from telegramify_markdown.rich import RichBlock, _RichHtmlWalker, _walk_blocks_from_markdown


class InputRichMessageTest(unittest.TestCase):
    def test_to_dict_omits_none_fields(self):
        rich = InputRichMessage(html="<p>x</p>")
        self.assertEqual(rich.to_dict(), {"html": "<p>x</p>"})

    def test_to_dict_includes_optional_fields(self):
        rich = InputRichMessage(
            markdown="**x**",
            is_rtl=True,
            skip_entity_detection=True,
        )
        self.assertEqual(
            rich.to_dict(),
            {
                "markdown": "**x**",
                "is_rtl": True,
                "skip_entity_detection": True,
            },
        )

    def test_requires_exactly_one_body_field(self):
        with self.assertRaises(ValueError):
            InputRichMessage()
        with self.assertRaises(ValueError):
            InputRichMessage(html="x", markdown="x")


class RichifyHtmlTest(unittest.TestCase):
    def test_basic_blocks_and_inline_formatting(self):
        rich = richify("# Title\n\nText **bold** and *italic* [x](https://e.com)")
        self.assertEqual(
            rich.html,
            '<h1>Title</h1><p>Text <b>bold</b> and <i>italic</i> '
            '<a href="https://e.com">x</a></p>',
        )

    def test_escaping_text_and_attributes(self):
        rich = richify('[a < b](https://e.com/?x=1&y="z")')
        self.assertEqual(
            rich.html,
            '<p><a href="https://e.com/?x=1&amp;y=&quot;z&quot;">a &lt; b</a></p>',
        )

    def test_spoiler_and_code(self):
        rich = richify("||secret|| `a<b`")
        self.assertEqual(
            rich.html,
            "<p><tg-spoiler>secret</tg-spoiler> <code>a&lt;b</code></p>",
        )

    def test_blockquote_code_and_math(self):
        rich = richify("> quote\n\n```python\nprint(1)\n```\n\n$$x^2$$")
        self.assertEqual(
            rich.html,
            '<blockquote><p>quote</p></blockquote>'
            '<pre><code class="language-python">print(1)</code></pre>'
            "<tg-math-block>x^2</tg-math-block>",
        )

    def test_math_fence_becomes_math_block(self):
        rich = richify("```math\nE = mc^2\n```")
        self.assertEqual(rich.html, "<tg-math-block>E = mc^2</tg-math-block>")

    def test_lists_and_task_markers(self):
        rich = richify("- [x] done\n- item")
        self.assertEqual(rich.html, "<ul><li>✅ done</li><li>item</li></ul>")

    def test_ordered_list_start(self):
        rich = richify("3. three\n4. four")
        self.assertEqual(rich.html, '<ol start="3"><li>three</li><li>four</li></ol>')

    def test_table(self):
        rich = richify("| A | B |\n|:--|--:|\n| 1 | 2 |")
        self.assertEqual(
            rich.html,
            '<table><tr><th align="left">A</th><th align="right">B</th></tr>'
            '<tr><td align="left">1</td><td align="right">2</td></tr></table>',
        )

    def test_image_http_block(self):
        rich = richify('![alt](https://example.com/a.jpg "cap")')
        self.assertEqual(
            rich.html,
            '<p><img src="https://example.com/a.jpg" alt="alt" title="cap"/></p>',
        )

    def test_custom_emoji_image(self):
        rich = richify("![👍](tg://emoji?id=5368324170671202286)")
        self.assertEqual(
            rich.html,
            '<p><tg-emoji emoji-id="5368324170671202286">👍</tg-emoji></p>',
        )

    def test_markdown_mode_passthrough(self):
        rich = richify("**x**", mode="markdown", skip_entity_detection=True)
        self.assertEqual(
            rich.to_dict(),
            {"markdown": "**x**", "skip_entity_detection": True},
        )

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            richify("x", mode="bad")  # type: ignore[arg-type]


class WalkBlocksTest(unittest.TestCase):
    """测试 walk_blocks 输出正确的 RichBlock 列表。"""

    def test_multiple_paragraphs(self):
        blocks = _walk_blocks_from_markdown("para1\n\npara2\n\npara3")
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0].html, "<p>para1</p>")
        self.assertEqual(blocks[1].html, "<p>para2</p>")
        self.assertEqual(blocks[2].html, "<p>para3</p>")
        for b in blocks:
            self.assertEqual(b.block_count, 1)
            self.assertEqual(b.byte_len, len(b.html.encode("utf-8")))

    def test_mixed_blocks(self):
        md = "# Heading\n\nParagraph\n\n```python\ncode\n```\n\n---\n\n> quote"
        blocks = _walk_blocks_from_markdown(md)
        self.assertEqual(len(blocks), 5)
        self.assertEqual(blocks[0].html, "<h1>Heading</h1>")
        self.assertEqual(blocks[1].html, "<p>Paragraph</p>")
        self.assertEqual(blocks[2].html, '<pre><code class="language-python">code</code></pre>')
        self.assertEqual(blocks[3].html, "<hr/>")
        self.assertEqual(blocks[4].html, "<blockquote><p>quote</p></blockquote>")

    def test_nested_blockquote_is_single_block(self):
        md = "> para1\n>\n> para2"
        blocks = _walk_blocks_from_markdown(md)
        self.assertEqual(len(blocks), 1)
        self.assertIn("<blockquote>", blocks[0].html)

    def test_list_is_single_block(self):
        md = "- item1\n- item2\n- item3"
        blocks = _walk_blocks_from_markdown(md)
        self.assertEqual(len(blocks), 1)
        self.assertIn("<ul>", blocks[0].html)

    def test_table_is_single_block(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        blocks = _walk_blocks_from_markdown(md)
        self.assertEqual(len(blocks), 1)
        self.assertIn("<table>", blocks[0].html)

    def test_walk_blocks_matches_walk(self):
        """walk_blocks 的 join 结果应与 walk 完全一致。"""
        md = "# H\n\nText **b**\n\n- a\n- b\n\n> q\n\n```\ncode\n```"
        import pyromark
        from telegramify_markdown.rich import RICH_OPTIONS
        from telegramify_markdown.converter import _preprocess_spoilers

        preprocessed = _preprocess_spoilers(md)
        events = pyromark.events_with_range(preprocessed, options=RICH_OPTIONS)
        walk_result = _RichHtmlWalker().walk(events)

        # 重新解析（events 是 tuple, 消费后需要重新获取）
        events2 = pyromark.events_with_range(preprocessed, options=RICH_OPTIONS)
        blocks = _RichHtmlWalker().walk_blocks(events2)
        joined = "".join(b.html for b in blocks)

        self.assertEqual(joined, walk_result)

    def test_display_math_is_block(self):
        md = "$$E = mc^2$$"
        blocks = _walk_blocks_from_markdown(md)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].html, "<tg-math-block>E = mc^2</tg-math-block>")


class SplitRichTest(unittest.TestCase):
    """测试 split_rich() 拆分逻辑。"""

    def test_within_limits_returns_single(self):
        """输入在限制内时直接返回单个 payload。"""
        rich = richify("Hello\n\nWorld")
        result = split_rich(rich)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].html, rich.html)

    def test_block_count_overflow(self):
        """600+ 短段落必须产生多个 chunk，每个 ≤ 500 blocks。"""
        # 生成 600 个短段落
        paragraphs = [f"Paragraph {i}" for i in range(600)]
        md = "\n\n".join(paragraphs)
        rich = richify(md)
        result = split_rich(rich)

        self.assertGreater(len(result), 1)
        # 验证每个 chunk 的 block 数 ≤ 500
        for chunk in result:
            # 用 heuristic 计算 block 数（每个 <p> = 1 block）
            block_count = chunk.html.count("<p>")
            self.assertLessEqual(block_count, 500)

    def test_byte_overflow(self):
        """3 个 ~15KB code block 必须产生多个 chunk，每个 ≤ 32768 bytes。"""
        # 每个 code block ~15KB
        code_content = "x" * 15000
        md = f"```\n{code_content}\n```\n\n```\n{code_content}\n```\n\n```\n{code_content}\n```"
        rich = richify(md)
        result = split_rich(rich)

        self.assertGreater(len(result), 1)
        for chunk in result:
            byte_len = len(chunk.html.encode("utf-8"))
            self.assertLessEqual(byte_len, 32768)

    def test_oversized_single_block(self):
        """40KB 的单个 pre block 应拆分成多个限制内 chunk。"""
        code_content = "y" * 40000
        md = f"```\n{code_content}\n```"
        rich = richify(md)

        result = split_rich(rich)

        self.assertGreater(len(result), 1)
        self.assertEqual(
            "".join(chunk.html.removeprefix("<pre>").removesuffix("</pre>") for chunk in result),
            code_content,
        )
        for chunk in result:
            self.assertLessEqual(len(chunk.html.encode("utf-8")), 32768)

    def test_markdown_mode_split(self):
        """markdown 模式按段落拆分。"""
        paragraphs = ["A" * 20000, "B" * 20000]
        md = "\n\n".join(paragraphs)
        rich = InputRichMessage(markdown=md)
        result = split_rich(rich)

        self.assertGreater(len(result), 1)
        for chunk in result:
            byte_len = len(chunk.markdown.encode("utf-8"))
            self.assertLessEqual(byte_len, 32768)

    def test_markdown_mode_splits_oversized_single_paragraph(self):
        """单段 Markdown 超限时也必须拆到限制内。"""
        rich = InputRichMessage(markdown="A" * 40000)
        result = split_rich(rich)

        self.assertGreater(len(result), 1)
        self.assertEqual("".join(chunk.markdown for chunk in result), "A" * 40000)
        for chunk in result:
            self.assertLessEqual(len(chunk.markdown.encode("utf-8")), 32768)

    def test_empty_html_payload(self):
        """空 html payload 的 split 返回空列表。"""
        rich = InputRichMessage(html="")
        result = split_rich(rich)
        self.assertEqual(result, [])

    def test_html_mode_splits_oversized_paragraph(self):
        """单个超长 paragraph 应拆成多个合法 paragraph chunk。"""
        md = "A" * 40000
        result = telegramify_rich(md)

        self.assertGreater(len(result), 1)
        for item in result:
            html = item.to_dict()["html"]
            self.assertTrue(html.startswith("<p>"))
            self.assertTrue(html.endswith("</p>"))
            self.assertLessEqual(len(html.encode("utf-8")), 32768)

    def test_html_mode_splits_oversized_escaped_paragraph(self):
        """超长 paragraph 含 HTML 特殊字符时不能拆断 escape entity。"""
        visible = "<&>" * 12000
        result = telegramify_rich(visible)

        self.assertGreater(len(result), 1)
        recovered = []
        for item in result:
            html = item.to_dict()["html"]
            self.assertTrue(html.startswith("<p>"))
            self.assertTrue(html.endswith("</p>"))
            self.assertLessEqual(len(html.encode("utf-8")), 32768)
            recovered.append(unescape(html.removeprefix("<p>").removesuffix("</p>")))
        self.assertEqual("".join(recovered), visible)

    def test_html_mode_splits_oversized_pre_block(self):
        """单个超长 code block 应拆成多个合法 pre chunk。"""
        md = "```\n" + ("A" * 40000) + "\n```"
        result = telegramify_rich(md)

        self.assertGreater(len(result), 1)
        for item in result:
            html = item.to_dict()["html"]
            self.assertTrue(html.startswith("<pre>"))
            self.assertTrue(html.endswith("</pre>"))
            self.assertLessEqual(len(html.encode("utf-8")), 32768)

    def test_html_mode_splits_oversized_escaped_pre_block(self):
        """超长 code block 含 HTML 特殊字符时保持可见文本。"""
        visible = "<&>" * 12000
        md = "```\n" + visible + "\n```"
        result = telegramify_rich(md)

        self.assertGreater(len(result), 1)
        recovered = []
        for item in result:
            html = item.to_dict()["html"]
            self.assertTrue(html.startswith("<pre>"))
            self.assertTrue(html.endswith("</pre>"))
            self.assertLessEqual(len(html.encode("utf-8")), 32768)
            recovered.append(unescape(html.removeprefix("<pre>").removesuffix("</pre>")))
        self.assertEqual("".join(recovered), visible)


class TelegramifyRichTest(unittest.TestCase):
    """测试 telegramify_rich() 端到端流程。"""

    def test_returns_list_of_rich_message(self):
        """基本输出类型检查。"""
        result = telegramify_rich("# Hello\n\nWorld")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for item in result:
            self.assertIsInstance(item, RichMessage)
            self.assertIsNotNone(item.rich_message)
            self.assertIsNotNone(item.content_trace)
            d = item.to_dict()
            self.assertIn("html", d)

    def test_coherence_with_richify_and_split(self):
        """telegramify_rich 和 split_rich(richify()) 产生相同的 HTML 内容。"""
        md = "# Title\n\nparagraph 1\n\nparagraph 2\n\n- item"
        items = telegramify_rich(md)
        rich = richify(md)
        chunks = split_rich(rich)

        # 合并所有 html
        telegramify_html = "".join(item.to_dict()["html"] for item in items)
        split_html = "".join(chunk.html for chunk in chunks)
        self.assertEqual(telegramify_html, split_html)

    def test_large_document_produces_multiple_chunks(self):
        """大文档产生多个 RichMessage。"""
        paragraphs = [f"Content block number {i} with some text." for i in range(600)]
        md = "\n\n".join(paragraphs)
        result = telegramify_rich(md)
        self.assertGreater(len(result), 1)

    def test_empty_input_matches_split_rich_empty_semantics(self):
        """空输入不返回可发送的空 RichMessage。"""
        self.assertEqual(telegramify_rich(""), [])
        self.assertEqual(telegramify_rich("   \n\n   "), [])

    def test_richify_still_returns_single_payload(self):
        """确认 richify() 仍返回单个 InputRichMessage（无回归）。"""
        rich = richify("# Hello\n\nWorld")
        self.assertIsInstance(rich, InputRichMessage)
        self.assertIsNotNone(rich.html)


class HtmlBlockBoundaryTest(unittest.TestCase):
    """HtmlBlock must leave the block scope it entered.

    Without _leave_block, _block_depth never returns to 0 and everything after
    an HTML block merges into a single RichBlock, defeating the byte and block
    budgets.
    """

    def test_blocks_after_html_block_stay_separate(self):
        blocks = _walk_blocks_from_markdown("para1\n\n<div>raw</div>\n\npara2\n\npara3")
        self.assertEqual(len(blocks), 4)
        self.assertEqual(blocks[-1].html, "<p>para3</p>")

    def test_paragraph_after_html_block_is_not_glued(self):
        html = richify("<div>raw</div>\n\npara2").html
        self.assertIn("<p>para2</p>", html)


class OversizedContainerSplitTest(unittest.TestCase):
    """Oversized container blocks split by child instead of going out whole
    for Telegram to reject."""

    LIMIT = 4096

    def _chunks(self, markdown: str):
        from telegramify_markdown.rich import _bin_blocks

        blocks = _walk_blocks_from_markdown(markdown)
        return _bin_blocks(
            blocks,
            byte_limit=self.LIMIT,
            block_limit=500,
            is_rtl=None,
            skip_entity_detection=None,
            mode="html",
        )

    def _assert_within_limit(self, chunks):
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.html.encode("utf-8")), self.LIMIT)

    def test_oversized_blockquote(self):
        self._assert_within_limit(self._chunks("> " + "x" * 10000))

    def test_oversized_table_splits_by_row(self):
        rows = "\n".join(f"| {'y' * 100} | {'z' * 100} |" for _ in range(60))
        chunks = self._chunks("| a | b |\n|---|---|\n" + rows)
        self._assert_within_limit(chunks)
        for chunk in chunks:
            self.assertTrue(chunk.html.startswith("<table>"))
            self.assertTrue(chunk.html.endswith("</table>"))

    def test_oversized_unordered_list_splits_by_item(self):
        chunks = self._chunks("\n".join(f"- {'i' * 200}" for _ in range(60)))
        self._assert_within_limit(chunks)
        for chunk in chunks:
            self.assertTrue(chunk.html.startswith("<ul>"))

    def test_oversized_ordered_list_continues_numbering(self):
        chunks = self._chunks("\n".join(f"{i + 1}. {'i' * 200}" for i in range(60)))
        self._assert_within_limit(chunks)
        self.assertTrue(chunks[0].html.startswith('<ol start="1">'))
        first_items = chunks[0].html.count("<li>")
        self.assertTrue(chunks[1].html.startswith(f'<ol start="{1 + first_items}">'))

    def test_content_within_limit_is_untouched(self):
        chunks = self._chunks("# t\n\npara\n\n- a\n- b\n")
        self.assertEqual(len(chunks), 1)

    def test_ordered_list_renumbering_never_overflows_the_limit(self):
        # A continued <ol start="N"> is a longer opening tag than the original
        # once N gains a digit. Budgeting against the original tag let the last
        # parts overflow by exactly those extra bytes.
        for limit in (60, 80, 120, 200):
            with self.subTest(limit=limit):
                from telegramify_markdown.rich import _bin_blocks

                blocks = _walk_blocks_from_markdown(
                    "\n".join(f"1. {'B' * 20}" for _ in range(30))
                )
                chunks = _bin_blocks(
                    blocks,
                    byte_limit=limit,
                    block_limit=500,
                    is_rtl=None,
                    skip_entity_detection=None,
                    mode="html",
                )
                self.assertGreater(len(chunks), 1)
                for chunk in chunks:
                    self.assertLessEqual(len(chunk.html.encode("utf-8")), limit)
                # numbering still continues rather than restarting
                self.assertTrue(chunks[0].html.startswith('<ol start="1">'))
                self.assertNotIn('<ol start="1">', chunks[-1].html)

    def test_unsplittable_oversized_child_still_warns(self):
        # A single 40KB list item cannot be split further. Splitting the
        # surrounding <ul> partially succeeds, which used to bypass the warning
        # and emit an over-limit payload silently.
        from telegramify_markdown.rich import RICH_BYTE_LIMIT

        with self.assertLogs("telegramify_markdown.rich", level="WARNING") as logs:
            items = telegramify_rich("- " + "A" * 40000 + "\n- b")

        oversized = [
            item
            for item in items
            if len(item.rich_message.html.encode("utf-8")) > RICH_BYTE_LIMIT
        ]
        self.assertEqual(len(oversized), 1)
        self.assertTrue(any("cannot be split further" in line for line in logs.output))


class CallerAuthoredHtmlSplitTest(unittest.TestCase):
    """split_rich() is public, so it also receives HTML the caller wrote.

    richify() escapes every attribute and only ever emits `<ol start="N">`, so
    none of these shapes come out of the library itself — but rewriting the
    open tag must not invent invalid HTML for them either.
    """

    def _split(self, html: str, byte_limit: int) -> list[str]:
        return [chunk.html for chunk in split_rich(InputRichMessage(html=html), byte_limit=byte_limit)]

    def test_single_quoted_start_is_continued_not_duplicated(self):
        parts = self._split(
            "<ol start='98'><li>AAAAAAAAAA</li><li>BBBBBBBBBB</li></ol>", 45
        )
        self.assertEqual(len(parts), 2)
        self.assertIn("start='99'", parts[1])
        self.assertEqual(parts[1].count("start="), 1)

    def test_similarly_named_attribute_is_not_rewritten(self):
        parts = self._split(
            '<ol data-start="98" start="7"><li>AAAAAAAAAA</li><li>BBBBBBBBBB</li></ol>', 45
        )
        self.assertIn('data-start="98"', parts[1])
        self.assertIn('start="8"', parts[1])

    def test_unparsable_start_leaves_the_tag_alone(self):
        parts = self._split(
            '<ol start="abc"><li>AAAAAAAAAA</li><li>BBBBBBBBBB</li></ol>', 45
        )
        for part in parts:
            self.assertEqual(part.count("start="), 1)
            self.assertIn('start="abc"', part)

    def test_quoted_attribute_containing_gt_keeps_the_open_tag_intact(self):
        html = (
            "<ol start='98' data-x='a>b'>"
            + "".join(f"<li>{'A' * 10}</li>" for _ in range(3))
            + "</ol>"
        )
        parts = self._split(html, 60)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertIn("data-x='a>b'", part)
            self.assertTrue(part.endswith("</ol>"))
            self.assertLessEqual(len(part.encode("utf-8")), 60)


if __name__ == "__main__":
    unittest.main()
