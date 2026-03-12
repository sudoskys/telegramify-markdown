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

    async def test_mermaid_rendering_disabled(self):
        md = "```mermaid\ngraph TD\nA-->B\n```"
        results = await process_markdown(md, render_mermaid=False)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], Text)
        self.assertEqual(len(results[0].entities), 1)
        self.assertEqual(results[0].entities[0].type, "pre")
        self.assertEqual(results[0].entities[0].language, "mermaid")


if __name__ == "__main__":
    unittest.main()
