import base64
import json
import unittest
import zlib
from urllib.parse import parse_qs, urlparse

from telegramify_markdown.config import get_runtime_config
from telegramify_markdown.mermaid import b64_mermaid_url, generate_pako, get_mermaid_ink_url


def _decode_pako(payload: str) -> dict:
    encoded = payload.removeprefix("pako:")
    padded = encoded + "=" * (-len(encoded) % 4)
    compressed = base64.urlsafe_b64decode(padded)
    return json.loads(zlib.decompress(compressed).decode("ascii"))


class MermaidConfigTest(unittest.TestCase):
    def setUp(self):
        self.cfg = get_runtime_config().mermaid
        self._saved_theme = self.cfg.theme
        self._saved_width = self.cfg.width
        self._saved_scale = self.cfg.scale
        self._saved_image_type = self.cfg.image_type

    def tearDown(self):
        self.cfg.theme = self._saved_theme
        self.cfg.width = self._saved_width
        self.cfg.scale = self._saved_scale
        self.cfg.image_type = self._saved_image_type

    def test_generate_pako_uses_runtime_theme_by_default(self):
        self.cfg.theme = "neutral"

        payload = generate_pako("graph TD\nA-->B")
        decoded = _decode_pako(payload)

        self.assertEqual(decoded["mermaid"]["theme"], "neutral")

    def test_get_mermaid_ink_url_uses_runtime_config(self):
        self.cfg.theme = "forest"
        self.cfg.width = 1280
        self.cfg.scale = 3
        self.cfg.image_type = "png"

        url = get_mermaid_ink_url("graph TD\nA-->B")
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        payload = parsed.path.removeprefix("/img/")
        decoded = _decode_pako(payload)

        self.assertEqual(query["theme"], ["forest"])
        self.assertEqual(query["width"], ["1280"])
        self.assertEqual(query["scale"], ["3"])
        self.assertEqual(query["type"], ["png"])
        self.assertEqual(decoded["mermaid"]["theme"], "forest")

    def test_b64_mermaid_url_uses_runtime_config(self):
        self.cfg.theme = "dark"
        self.cfg.width = 900
        self.cfg.scale = 4
        self.cfg.image_type = "jpeg"

        url = b64_mermaid_url("graph TD\nA-->B")
        query = parse_qs(urlparse(url).query)

        self.assertEqual(query["theme"], ["dark"])
        self.assertEqual(query["width"], ["900"])
        self.assertEqual(query["scale"], ["4"])
        self.assertEqual(query["type"], ["jpeg"])


if __name__ == "__main__":
    unittest.main()
