import unittest

from telegramify_markdown import InputRichMessage, richify


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


if __name__ == "__main__":
    unittest.main()
