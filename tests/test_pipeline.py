import unittest

from telegramify_markdown.pipeline import process_markdown
from telegramify_markdown.content import Text, File, Photo


class ProcessMarkdownTest(unittest.IsolatedAsyncioTestCase):
    async def test_simple_text(self):
        results = await process_markdown("Hello **world**")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], Text)
        self.assertIn("world", results[0].text)
        self.assertTrue(any(e.type == "bold" for e in results[0].entities))

    async def test_code_block_extracted_as_file(self):
        md = "Some text\n\n```python\nprint('hello')\n```\n\nMore text"
        results = await process_markdown(md)
        types = [type(r) for r in results]
        self.assertIn(File, types)
        file_result = [r for r in results if isinstance(r, File)][0]
        self.assertIn("py", file_result.file_name)
        self.assertIn(b"print('hello')", file_result.file_data)

    async def test_code_block_as_text(self):
        md = "Some text\n\n```python\nprint('hello')\n```\n\nMore text"
        results = await process_markdown(md, min_file_lines=0)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], Text)
        self.assertIn("print('hello')", results[0].text)
        self.assertEqual(len(results[0].entities), 1)
        self.assertEqual(results[0].entities[0].type, "pre")
        self.assertEqual(results[0].entities[0].language, "python")

    async def test_code_block_min_lines(self):
        md = "Some text\n\n```python\nprint('line1')\nprint('line2')\n```\n\nMore text"
        results = await process_markdown(md, min_file_lines=3)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], Text)
        self.assertEqual(len(results[0].entities), 1)
        self.assertEqual(results[0].entities[0].type, "pre")
        self.assertEqual(results[0].entities[0].language, "python")

    async def test_text_around_code_block(self):
        md = "Before\n\n```python\ncode\n```\n\nAfter"
        results = await process_markdown(md)
        text_results = [r for r in results if isinstance(r, Text)]
        all_text = " ".join(t.text for t in text_results)
        self.assertIn("Before", all_text)
        self.assertIn("After", all_text)

    async def test_splitting_long_text(self):
        md = "\n\n".join([f"Paragraph {i} with some content." for i in range(100)])
        results = await process_markdown(md, max_message_length=200)
        text_results = [r for r in results if isinstance(r, Text)]
        self.assertGreater(len(text_results), 1)
        combined = " ".join(t.text for t in text_results)
        self.assertIn("Paragraph 0", combined)
        self.assertIn("Paragraph 99", combined)

    async def test_empty_input(self):
        results = await process_markdown("")
        self.assertEqual(len(results), 0)

    async def test_only_code_block(self):
        md = "```python\nprint('hello')\n```"
        results = await process_markdown(md)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], File)

    async def test_multiple_code_blocks(self):
        md = "text\n\n```python\na=1\n```\n\nmiddle\n\n```js\nb=2\n```\n\nend"
        results = await process_markdown(md)
        files = [r for r in results if isinstance(r, File)]
        texts = [r for r in results if isinstance(r, Text)]
        self.assertEqual(len(files), 2)
        self.assertGreaterEqual(len(texts), 1)

    async def test_content_ordering(self):
        md = "first\n\n```python\ncode\n```\n\nlast"
        results = await process_markdown(md)
        # Order should be: Text("first"), File, Text("last")
        self.assertIsInstance(results[0], Text)
        self.assertIn("first", results[0].text)
        self.assertIsInstance(results[1], File)
        self.assertIsInstance(results[2], Text)
        self.assertIn("last", results[2].text)

    async def test_mermaid_without_support(self):
        md = "```mermaid\ngraph TD\nA-->B\n```"
        results = await process_markdown(md)
        self.assertEqual(len(results), 1)
        self.assertIn(type(results[0]), (File, Photo))

    async def test_mermaid_caption_uses_text_link(self):
        """Mermaid Photo caption must use a text_link entity, not a bare URL.

        Bare URLs can exceed Telegram's 1024 code-unit caption limit because
        pako-encoded mermaid.live URLs grow with diagram complexity.
        """
        md = "```mermaid\ngraph TD\nA-->B\n```"
        results = await process_markdown(md)
        photos = [r for r in results if isinstance(r, Photo)]
        if not photos:
            self.skipTest("Mermaid rendering not available (missing aiohttp/Pillow)")
        photo = photos[0]
        # Caption 应该是短文本，不是裸 URL
        self.assertNotIn("pako:", photo.caption_text)
        self.assertLessEqual(len(photo.caption_text), 1024)
        # 必须有 text_link entity 指向 mermaid.live
        self.assertTrue(photo.caption_entities, "caption_entities should not be empty")
        link_entity = photo.caption_entities[0]
        self.assertEqual(link_entity.type, "text_link")
        self.assertIn("mermaid.live", link_entity.url)

    async def test_mermaid_rendering_disabled(self):
        md = "```mermaid\ngraph TD\nA-->B\n```"
        results = await process_markdown(md, render_mermaid=False)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], Text)
        self.assertEqual(len(results[0].entities), 1)
        self.assertEqual(results[0].entities[0].type, "pre")
        self.assertEqual(results[0].entities[0].language, "mermaid")


class DeprecatedArgumentTest(unittest.IsolatedAsyncioTestCase):
    """0.x compatibility parameters on telegramify().

    max_message_length = max_word_count used to sit inside the
    normalize_whitespace branch: the alias silently did nothing, and
    normalize_whitespace=True set the length limit to None and then crashed.
    """

    async def test_max_word_count_still_limits_length(self):
        import warnings

        from telegramify_markdown import telegramify
        from telegramify_markdown.entity import utf16_len

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            results = await telegramify("x\n\n" * 400, max_word_count=100)

        self.assertGreater(len(results), 1)
        for item in results:
            self.assertLessEqual(utf16_len(item.text), 100)

    async def test_normalize_whitespace_does_not_break_splitting(self):
        import warnings

        from telegramify_markdown import telegramify

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            results = await telegramify("hello\n\nworld", normalize_whitespace=True)

        self.assertEqual(len(results), 1)
        self.assertIn("hello", results[0].text)


class ConfigThreadingTest(unittest.IsolatedAsyncioTestCase):
    """config= must reach all the way down, or the parameter name promises
    something it cannot deliver."""

    async def test_telegramify_honours_isolated_config(self):
        from telegramify_markdown import telegramify
        from telegramify_markdown.config import RenderConfig, get_runtime_config

        cfg = RenderConfig.isolated()
        cfg.markdown_symbol.unordered_list_item = "-"

        results = await telegramify("- x", config=cfg)
        self.assertIn("- x", results[0].text)
        # The global was not modified by this call
        self.assertEqual(
            get_runtime_config().markdown_symbol.unordered_list_item, "⦁"
        )

    async def test_markdownify_honours_isolated_config(self):
        from telegramify_markdown import markdownify
        from telegramify_markdown.config import RenderConfig

        cfg = RenderConfig.isolated()
        cfg.markdown_symbol.unordered_list_item = "•"
        self.assertIn("• x", markdownify("- x", config=cfg, latex_escape=False))

    async def test_mermaid_settings_follow_the_given_config(self):
        from telegramify_markdown.config import RenderConfig
        from telegramify_markdown.mermaid import get_mermaid_ink_url

        cfg = RenderConfig.isolated()
        cfg.mermaid.width = 4242
        self.assertIn("width=4242", get_mermaid_ink_url("graph TD\nA-->B", cfg))
        # Without config= it still uses the global defaults
        self.assertIn("width=1000", get_mermaid_ink_url("graph TD\nA-->B"))


if __name__ == "__main__":
    unittest.main()
