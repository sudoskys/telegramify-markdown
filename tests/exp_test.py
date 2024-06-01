import pathlib
import unittest
from dotenv import load_dotenv
from telegramify_markdown import markdownify
from server import server_t

load_dotenv()


class TestCase(unittest.TestCase):
    def test_something(self):
        md = pathlib.Path(__file__).parent.joinpath("exp1.md").read_text(encoding="utf-8")
        converted = markdownify(md)
        self.assertEqual(server_t(converted), True)


if __name__ == '__main__':
    unittest.main()
