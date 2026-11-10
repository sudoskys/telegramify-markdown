import unittest

from telegramify_markdown import markdownify
from telegramify_markdown.converter import convert


class FootnoteTest(unittest.TestCase):
    def test_footnote_reference_is_not_a_link(self):
        text, entities = convert("Footnote[^1]\n\n[^1]: note", latex_escape=False)
        self.assertIn("[1]", text)
        links = [e for e in entities if e.type == "text_link"]
        self.assertEqual(links, [])

    def test_footnote_definition_text_is_kept(self):
        text, _entities = convert("Footnote[^1]\n\n[^1]: note", latex_escape=False)
        self.assertIn("note", text)

    def test_footnote_markdownify_has_no_bogus_link(self):
        out = markdownify("Footnote[^1]\n\n[^1]: note")
        self.assertNotIn("(note)", out)
        self.assertIn("\\[1\\]", out)


if __name__ == "__main__":
    unittest.main()
