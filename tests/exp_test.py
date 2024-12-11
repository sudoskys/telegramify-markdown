import pathlib
import unittest

from dotenv import load_dotenv

import telegramify_markdown
from server import server_t
from telegramify_markdown import markdownify

load_dotenv()


class TestCase(unittest.TestCase):
    def test_markdownify(self):
        md = pathlib.Path(__file__).parent.joinpath("exp1.md").read_text(encoding="utf-8")
        converted = markdownify(md)
        self.assertEqual(server_t(converted), True)

    def test_telegramify(self):
        long_md = pathlib.Path(__file__).parent.joinpath("exp2.md").read_text(encoding="utf-8")
        rendered = telegramify_markdown.telegramify(long_md)
        self.assertEqual(isinstance(rendered, list), True)


if __name__ == '__main__':
    unittest.main()
