import pathlib
import unittest

from dotenv import load_dotenv

import telegramify_markdown
from server import server_t
from telegramify_markdown import markdownify

load_dotenv()


class TestCase(unittest.IsolatedAsyncioTestCase):
    async def test_markdownify(self):
        md = pathlib.Path(__file__).parent.joinpath("exp1.md").read_text(encoding="utf-8")
        converted = markdownify(md)
        self.assertEqual(server_t(converted), True)

    async def test_telegramify(self):
        long_md = pathlib.Path(__file__).parent.joinpath("exp2.md").read_text(encoding="utf-8")
        rendered = await telegramify_markdown.telegramify(
            content=long_md,
            max_word_count=4090,
            latex_escape=True,
            interpreters_use=[
                telegramify_markdown.interpreters.BaseInterpreter(),
                telegramify_markdown.interpreters.MermaidInterpreter(),
            ]
        )
        self.assertEqual(isinstance(rendered, list), True)


if __name__ == '__main__':
    unittest.main()
