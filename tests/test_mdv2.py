"""tests for entities_to_markdownv2"""

import unittest

from telegramify_markdown.entity import MessageEntity, utf16_len
from telegramify_markdown.mdv2 import (
    _escape_code,
    _escape_markdownv2,
    _escape_url,
    entities_to_markdownv2,
)


# ── 第一层：基础转义 ──


class EscapeMarkdownV2Test(unittest.TestCase):
    def test_escape_plain_text(self):
        """20 个特殊字符全部转义"""
        special = "_*[]()~`>#+-=|{}.!\\"
        result = _escape_markdownv2(special)
        # 每个字符前都应该有反斜杠
        for ch in special:
            self.assertIn(f"\\{ch}", result)

    def test_no_escape_needed(self):
        self.assertEqual(_escape_markdownv2("hello world"), "hello world")

    def test_mixed(self):
        self.assertEqual(_escape_markdownv2("a*b"), "a\\*b")


class EscapeCodeTest(unittest.TestCase):
    def test_escape_code(self):
        """code 内只转义 ` 和 \\"""
        self.assertEqual(_escape_code("a`b\\c*d"), "a\\`b\\\\c*d")

    def test_no_escape_needed(self):
        self.assertEqual(_escape_code("hello"), "hello")


class EscapeUrlTest(unittest.TestCase):
    def test_escape_url(self):
        """URL 内只转义 ) 和 \\"""
        self.assertEqual(_escape_url("http://a.com/b(c)d\\e"), "http://a.com/b(c\\)d\\\\e")

    def test_no_escape_needed(self):
        self.assertEqual(_escape_url("https://example.com"), "https://example.com")


# ── 第二层：单一 entity type ──


class BoldTest(unittest.TestCase):
    def test_bold(self):
        text = "hello world"
        entities = [MessageEntity(type="bold", offset=0, length=5)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "*hello* world")

    def test_bold_middle(self):
        text = "say hello please"
        entities = [MessageEntity(type="bold", offset=4, length=5)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "say *hello* please")


class ItalicTest(unittest.TestCase):
    def test_italic(self):
        text = "hello world"
        entities = [MessageEntity(type="italic", offset=0, length=5)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "_hello_ world")


class UnderlineTest(unittest.TestCase):
    def test_underline(self):
        text = "hello"
        entities = [MessageEntity(type="underline", offset=0, length=5)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "__hello__")


class StrikethroughTest(unittest.TestCase):
    def test_strikethrough(self):
        text = "deleted"
        entities = [MessageEntity(type="strikethrough", offset=0, length=7)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "~deleted~")


class SpoilerTest(unittest.TestCase):
    def test_spoiler(self):
        text = "secret"
        entities = [MessageEntity(type="spoiler", offset=0, length=6)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "||secret||")


class CodeTest(unittest.TestCase):
    def test_code(self):
        text = "use print()"
        entities = [MessageEntity(type="code", offset=4, length=7)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "use `print()`")

    def test_code_with_backtick(self):
        """code 内的反引号应被转义"""
        text = "a`b"
        entities = [MessageEntity(type="code", offset=0, length=3)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "`a\\`b`")

    def test_code_special_chars_not_escaped(self):
        """code 内的 * _ 等不应被转义"""
        text = "a*b_c"
        entities = [MessageEntity(type="code", offset=0, length=5)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "`a*b_c`")


class PreTest(unittest.TestCase):
    def test_pre_no_lang(self):
        text = "line1\nline2"
        entities = [MessageEntity(type="pre", offset=0, length=11)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "```\nline1\nline2\n```")

    def test_pre_with_lang(self):
        text = "print(1)"
        entities = [MessageEntity(type="pre", offset=0, length=8, language="python")]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "```python\nprint(1)\n```")


class TextLinkTest(unittest.TestCase):
    def test_text_link(self):
        text = "click here"
        entities = [MessageEntity(type="text_link", offset=0, length=10, url="https://example.com")]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "[click here](https://example.com)")

    def test_text_link_url_with_paren(self):
        text = "link"
        entities = [MessageEntity(type="text_link", offset=0, length=4, url="https://a.com/b(c)")]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "[link](https://a.com/b(c\\))")


class CustomEmojiTest(unittest.TestCase):
    def test_custom_emoji(self):
        text = "😀"
        entities = [MessageEntity(type="custom_emoji", offset=0, length=2, custom_emoji_id="12345")]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "![😀](tg://emoji?id=12345)")


class BlockquoteTest(unittest.TestCase):
    def test_blockquote_single_line(self):
        text = "quoted text"
        entities = [MessageEntity(type="blockquote", offset=0, length=11)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, ">quoted text")

    def test_blockquote_multi_line(self):
        text = "line1\nline2\nline3"
        entities = [MessageEntity(type="blockquote", offset=0, length=utf16_len(text))]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, ">line1\n>line2\n>line3")


class ExpandableBlockquoteTest(unittest.TestCase):
    def test_expandable_blockquote(self):
        text = "summary\ndetails"
        entities = [MessageEntity(type="expandable_blockquote", offset=0, length=utf16_len(text))]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "**>summary\n>details||")


# ── 第三层：组合与边界 ──


class NestedEntityTest(unittest.TestCase):
    def test_nested_bold_italic(self):
        """嵌套 entity：bold 包含 italic"""
        text = "bold italic end"
        # bold: 整个文本
        # italic: "italic" (offset=5, length=6)
        entities = [
            MessageEntity(type="bold", offset=0, length=15),
            MessageEntity(type="italic", offset=5, length=6),
        ]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "*bold _italic_ end*")

    def test_nested_italic_in_bold(self):
        """bold(0-10) 包含 italic(3-7)"""
        text = "abcdefghij"
        entities = [
            MessageEntity(type="bold", offset=0, length=10),
            MessageEntity(type="italic", offset=3, length=4),
        ]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "*abc_defg_hij*")

    def test_same_range_bold_underline(self):
        """相同范围的 bold+underline 应正确嵌套，不交叉"""
        text = "hello"
        entities = [
            MessageEntity(type="bold", offset=0, length=5),
            MessageEntity(type="underline", offset=0, length=5),
        ]
        result = entities_to_markdownv2(text, entities)
        # 应该是 *__hello__* 或 __*hello*__，不能交叉
        self.assertIn("hello", result)
        # 验证不会出现交叉标记
        self.assertNotIn("*__hello*__", result)
        self.assertNotIn("__*hello__*", result)


class AdjacentEntityTest(unittest.TestCase):
    def test_adjacent_entities(self):
        """相邻 entity：bold 紧接 italic"""
        text = "bolditalic"
        entities = [
            MessageEntity(type="bold", offset=0, length=4),
            MessageEntity(type="italic", offset=4, length=6),
        ]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "*bold*_italic_")


class EmojiUtf16Test(unittest.TestCase):
    def test_emoji_utf16_offset(self):
        """emoji 的 UTF-16 offset 正确性"""
        # 📌 = U+1F4CC = 2 UTF-16 code units
        text = "📌bold"
        entities = [MessageEntity(type="bold", offset=2, length=4)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "📌*bold*")

    def test_emoji_before_and_after(self):
        text = "📌hello📌"
        entities = [MessageEntity(type="bold", offset=2, length=5)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "📌*hello*📌")


class NoEntitiesTest(unittest.TestCase):
    def test_no_entities(self):
        text = "hello *world*"
        result = entities_to_markdownv2(text, [])
        self.assertEqual(result, "hello \\*world\\*")

    def test_none_entities(self):
        text = "hello"
        result = entities_to_markdownv2(text, None)
        self.assertEqual(result, "hello")


class EmptyTextTest(unittest.TestCase):
    def test_empty_text(self):
        result = entities_to_markdownv2("", [])
        self.assertEqual(result, "")

    def test_empty_text_none_entities(self):
        result = entities_to_markdownv2("", None)
        self.assertEqual(result, "")


class RoundtripTest(unittest.TestCase):
    """使用 convert() 的输出做往返验证"""

    def test_roundtrip_basic(self):
        """convert 的输出经过 entities_to_markdownv2 应生成合法 MarkdownV2"""
        from telegramify_markdown.converter import convert

        text, entities = convert("**bold** and _italic_")
        result = entities_to_markdownv2(text, entities)
        # 验证结果包含预期标记
        self.assertIn("*", result)
        self.assertIn("_", result)

    def test_roundtrip_code(self):
        from telegramify_markdown.converter import convert

        text, entities = convert("use `print()` function")
        result = entities_to_markdownv2(text, entities)
        self.assertIn("`", result)

    def test_roundtrip_link(self):
        from telegramify_markdown.converter import convert

        text, entities = convert("[click](https://example.com)")
        result = entities_to_markdownv2(text, entities)
        self.assertIn("[", result)
        self.assertIn("https://example.com", result)


class SpecialCharInEntityTest(unittest.TestCase):
    """entity 内部包含特殊字符"""

    def test_bold_with_special_chars(self):
        """bold 内的特殊字符也需要转义"""
        text = "a.b"
        entities = [MessageEntity(type="bold", offset=0, length=3)]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "*a\\.b*")


class PreBeforeBlockquoteTest(unittest.TestCase):
    """pre block 与 blockquote 共存时的行映射"""

    def test_pre_before_blockquote(self):
        """pre block 在 blockquote 前面，``` 不应干扰 blockquote 行索引"""
        text = "code\nquoted"
        entities = [
            MessageEntity(type="pre", offset=0, length=4),
            MessageEntity(type="blockquote", offset=5, length=6),
        ]
        result = entities_to_markdownv2(text, entities)
        self.assertIn(">quoted", result)
        self.assertNotIn(">code", result)

    def test_pre_inside_blockquote(self):
        """pre block 在 blockquote 内部，``` 行也应有 > 前缀"""
        text = "quoted code here"
        entities = [
            MessageEntity(type="blockquote", offset=0, length=16),
            MessageEntity(type="pre", offset=7, length=4),
        ]
        result = entities_to_markdownv2(text, entities)
        # 所有行都应有 > 前缀
        for line in result.split("\n"):
            self.assertTrue(line.startswith(">"), f"Line missing > prefix: {repr(line)}")

    def test_blockquote_not_at_start(self):
        """blockquote 不在文本开头"""
        text = "normal\nquoted"
        entities = [
            MessageEntity(type="blockquote", offset=7, length=6),
        ]
        result = entities_to_markdownv2(text, entities)
        self.assertEqual(result, "normal\n>quoted")

    def test_multiple_pre_before_blockquote(self):
        """多个 pre block 在 blockquote 前面"""
        text = "a\nb\nquoted"
        entities = [
            MessageEntity(type="pre", offset=0, length=1),
            MessageEntity(type="pre", offset=2, length=1),
            MessageEntity(type="blockquote", offset=4, length=6),
        ]
        result = entities_to_markdownv2(text, entities)
        self.assertIn(">quoted", result)


if __name__ == "__main__":
    unittest.main()
