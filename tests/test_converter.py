import unittest

from telegramify_markdown.converter import convert, convert_with_segments
from telegramify_markdown.entity import MessageEntity, utf16_len


def _find_entity(entities: list[MessageEntity], etype: str) -> MessageEntity | None:
    for e in entities:
        if e.type == etype:
            return e
    return None


def _find_entities(entities: list[MessageEntity], etype: str) -> list[MessageEntity]:
    return [e for e in entities if e.type == etype]


def _extract_entity_text(text: str, entity: MessageEntity) -> str:
    """Extract the substring covered by an entity from plain text."""
    # Convert UTF-16 offset/length to Python string indices
    utf16_offset = 0
    py_start = None
    py_end = None
    for i, ch in enumerate(text):
        if utf16_offset == entity.offset and py_start is None:
            py_start = i
        if utf16_offset == entity.offset + entity.length and py_end is None:
            py_end = i
            break
        utf16_offset += 2 if ord(ch) > 0xFFFF else 1
    if py_start is not None and py_end is None:
        py_end = len(text)
    if py_start is None:
        return ""
    return text[py_start:py_end]


class BoldTest(unittest.TestCase):
    def test_simple_bold(self):
        text, entities = convert("**hello**", latex_escape=False)
        self.assertIn("hello", text)
        bold = _find_entity(entities, "bold")
        self.assertIsNotNone(bold)
        self.assertEqual(_extract_entity_text(text, bold), "hello")

    def test_bold_in_sentence(self):
        text, entities = convert("foo **bar** baz", latex_escape=False)
        bold = _find_entity(entities, "bold")
        self.assertIsNotNone(bold)
        self.assertEqual(_extract_entity_text(text, bold), "bar")


class ItalicTest(unittest.TestCase):
    def test_simple_italic(self):
        text, entities = convert("*hello*", latex_escape=False)
        italic = _find_entity(entities, "italic")
        self.assertIsNotNone(italic)
        self.assertEqual(_extract_entity_text(text, italic), "hello")


class StrikethroughTest(unittest.TestCase):
    def test_simple_strikethrough(self):
        text, entities = convert("~~hello~~", latex_escape=False)
        s = _find_entity(entities, "strikethrough")
        self.assertIsNotNone(s)
        self.assertEqual(_extract_entity_text(text, s), "hello")


class NestedFormattingTest(unittest.TestCase):
    def test_bold_italic(self):
        text, entities = convert("**bold *italic* bold**", latex_escape=False)
        bold = _find_entity(entities, "bold")
        italic = _find_entity(entities, "italic")
        self.assertIsNotNone(bold)
        self.assertIsNotNone(italic)
        # Italic should be contained within bold
        self.assertGreaterEqual(italic.offset, bold.offset)
        self.assertLessEqual(italic.offset + italic.length, bold.offset + bold.length)
        self.assertEqual(_extract_entity_text(text, italic), "italic")


class InlineCodeTest(unittest.TestCase):
    def test_inline_code(self):
        text, entities = convert("use `print()` here", latex_escape=False)
        code = _find_entity(entities, "code")
        self.assertIsNotNone(code)
        self.assertEqual(_extract_entity_text(text, code), "print()")


class CodeBlockTest(unittest.TestCase):
    def test_fenced_code_block(self):
        md = "```python\nprint('hello')\n```"
        text, entities = convert(md, latex_escape=False)
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(pre)
        self.assertEqual(pre.language, "python")
        self.assertIn("print('hello')", _extract_entity_text(text, pre))

    def test_code_block_segment(self):
        md = "```python\ncode\n```"
        _, _, segments = convert_with_segments(md, latex_escape=False)
        self.assertTrue(any(s.kind == "code_block" for s in segments))

    def test_mermaid_segment(self):
        md = "```mermaid\ngraph TD\nA-->B\n```"
        _, _, segments = convert_with_segments(md, latex_escape=False)
        self.assertTrue(any(s.kind == "mermaid" for s in segments))

    def test_code_block_no_language(self):
        md = "```\nsome code\n```"
        text, entities = convert(md, latex_escape=False)
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(pre)
        self.assertIsNone(pre.language)


class HeadingTest(unittest.TestCase):
    def test_h1(self):
        text, entities = convert("# Title", latex_escape=False)
        bold = _find_entity(entities, "bold")
        self.assertIsNotNone(bold)
        self.assertIn("Title", _extract_entity_text(text, bold))
        # Should have emoji prefix
        self.assertIn("📌", text)

    def test_h2(self):
        text, entities = convert("## Subtitle", latex_escape=False)
        self.assertIn("✏", text)

    def test_h3(self):
        text, entities = convert("### Section", latex_escape=False)
        self.assertIn("📚", text)


class LinkTest(unittest.TestCase):
    def test_inline_link(self):
        text, entities = convert("[Google](https://google.com)", latex_escape=False)
        link = _find_entity(entities, "text_link")
        self.assertIsNotNone(link)
        self.assertEqual(link.url, "https://google.com")
        self.assertEqual(_extract_entity_text(text, link), "Google")

    def test_autolink(self):
        text, entities = convert("visit https://example.com today", latex_escape=False)
        self.assertIn("https://example.com", text)


class ImageTest(unittest.TestCase):
    def test_image(self):
        text, entities = convert("![alt](https://example.com/img.png)", latex_escape=False)
        link = _find_entity(entities, "text_link")
        self.assertIsNotNone(link)
        self.assertEqual(link.url, "https://example.com/img.png")

    def test_telegram_emoji(self):
        text, entities = convert("![emoji](tg://emoji?id=5368324170671202286)", latex_escape=False)
        emoji = _find_entity(entities, "custom_emoji")
        self.assertIsNotNone(emoji)
        self.assertEqual(emoji.custom_emoji_id, "5368324170671202286")


class BlockquoteTest(unittest.TestCase):
    def test_simple_blockquote(self):
        text, entities = convert("> quoted text", latex_escape=False)
        bq = _find_entity(entities, "blockquote")
        self.assertIsNotNone(bq)
        self.assertIn("quoted text", _extract_entity_text(text, bq))

    def test_expandable_blockquote(self):
        long_text = "> " + "a" * 250
        text, entities = convert(long_text, latex_escape=False)
        bq = _find_entity(entities, "expandable_blockquote")
        self.assertIsNotNone(bq)


class TableTest(unittest.TestCase):
    def test_simple_table(self):
        md = "| a | b |\n| --- | --- |\n| 1 | 2 |"
        text, entities = convert(md, latex_escape=False)
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(pre)
        table_text = _extract_entity_text(text, pre)
        self.assertIn("a", table_text)
        self.assertIn("b", table_text)
        self.assertIn("1", table_text)
        self.assertIn("2", table_text)


class ListTest(unittest.TestCase):
    def test_unordered_list(self):
        md = "- item1\n- item2"
        text, entities = convert(md, latex_escape=False)
        self.assertIn("⦁ item1", text)
        self.assertIn("⦁ item2", text)

    def test_ordered_list(self):
        md = "1. first\n2. second"
        text, entities = convert(md, latex_escape=False)
        self.assertIn("1. first", text)
        self.assertIn("2. second", text)

    def test_task_list(self):
        md = "- [x] done\n- [ ] todo"
        text, entities = convert(md, latex_escape=False)
        self.assertIn("✅", text)
        self.assertIn("☑", text)


class SpoilerTest(unittest.TestCase):
    def test_spoiler(self):
        text, entities = convert("this is ||secret|| text", latex_escape=False)
        spoiler = _find_entity(entities, "spoiler")
        self.assertIsNotNone(spoiler)
        self.assertEqual(_extract_entity_text(text, spoiler), "secret")

    def test_spoiler_not_in_code(self):
        text, entities = convert("`||not spoiler||`", latex_escape=False)
        spoiler = _find_entity(entities, "spoiler")
        self.assertIsNone(spoiler)


class RuleTest(unittest.TestCase):
    def test_horizontal_rule(self):
        text, entities = convert("above\n\n---\n\nbelow", latex_escape=False)
        self.assertIn("————————", text)


class ParagraphSpacingTest(unittest.TestCase):
    def test_paragraphs_separated(self):
        text, entities = convert("para1\n\npara2", latex_escape=False)
        self.assertIn("para1\npara2", text)

    def test_heading_then_paragraph(self):
        text, entities = convert("# Title\n\nContent", latex_escape=False)
        self.assertIn("Title", text)
        self.assertIn("Content", text)


class Utf16OffsetTest(unittest.TestCase):
    def test_emoji_offset(self):
        # 📌 is 2 UTF-16 code units
        text, entities = convert("📌 **bold**", latex_escape=False)
        bold = _find_entity(entities, "bold")
        self.assertIsNotNone(bold)
        # "📌 " = 2 + 1 = 3 UTF-16 code units
        self.assertEqual(bold.offset, 3)
        self.assertEqual(bold.length, 4)

    def test_cjk_offset(self):
        text, entities = convert("你好 **世界**", latex_escape=False)
        bold = _find_entity(entities, "bold")
        self.assertIsNotNone(bold)
        # "你好 " = 2 + 1 = 3 UTF-16 code units (CJK is BMP, 1 each)
        self.assertEqual(bold.offset, 3)
        self.assertEqual(bold.length, 2)


class MathTest(unittest.TestCase):
    def test_inline_math(self):
        text, entities = convert("$x + y$", latex_escape=False)
        code = _find_entity(entities, "code")
        self.assertIsNotNone(code)
        self.assertIn("x + y", _extract_entity_text(text, code))

    def test_display_math(self):
        text, entities = convert("$$x + y$$", latex_escape=False)
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(pre)


class ComplexDocumentTest(unittest.TestCase):
    def test_mixed_content(self):
        md = """# Hello World

This is **bold** and *italic* text.

- item 1
- item 2

> A quote

```python
print("hello")
```
"""
        text, entities = convert(md, latex_escape=False)
        # Should have heading (bold), bold, italic, blockquote, pre
        types = {e.type for e in entities}
        self.assertIn("bold", types)
        self.assertIn("italic", types)
        self.assertIn("blockquote", types)
        self.assertIn("pre", types)
        # Text should contain all content
        self.assertIn("Hello World", text)
        self.assertIn("item 1", text)
        self.assertIn("A quote", text)
        self.assertIn('print("hello")', text)


if __name__ == "__main__":
    unittest.main()
