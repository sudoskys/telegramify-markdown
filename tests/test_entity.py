import unittest

from telegramify_markdown.entity import MessageEntity, utf16_len, split_entities


class Utf16LenTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(utf16_len(""), 0)

    def test_ascii(self):
        self.assertEqual(utf16_len("hello"), 5)

    def test_cjk(self):
        # CJK characters are in BMP, 1 UTF-16 code unit each
        self.assertEqual(utf16_len("你好"), 2)

    def test_emoji_bmp(self):
        # ☑️ is U+2611 (BMP) + U+FE0F (BMP) = 2 code units
        self.assertEqual(utf16_len("☑️"), 2)

    def test_emoji_supplementary(self):
        # 📌 is U+1F4CC (supplementary plane) = 2 UTF-16 code units
        self.assertEqual(utf16_len("📌"), 2)

    def test_mixed(self):
        # "A📌B" = 1 + 2 + 1 = 4
        self.assertEqual(utf16_len("A📌B"), 4)

    def test_flag_emoji(self):
        # 🇺🇸 is two regional indicator symbols, each U+1F1FA/U+1F1F8 (supplementary)
        self.assertEqual(utf16_len("🇺🇸"), 4)

    def test_matches_encode(self):
        """utf16_len should match len(text.encode('utf-16-le')) // 2"""
        test_strings = [
            "",
            "hello",
            "你好世界",
            "📌✅🔗",
            "A📌B你好C",
            "test 🇺🇸 flag",
        ]
        for s in test_strings:
            with self.subTest(s=s):
                expected = len(s.encode("utf-16-le")) // 2
                self.assertEqual(utf16_len(s), expected)


class MessageEntityTest(unittest.TestCase):
    def test_to_dict_minimal(self):
        e = MessageEntity(type="bold", offset=0, length=5)
        self.assertEqual(e.to_dict(), {"type": "bold", "offset": 0, "length": 5})

    def test_to_dict_with_url(self):
        e = MessageEntity(type="text_link", offset=0, length=5, url="https://example.com")
        d = e.to_dict()
        self.assertEqual(d["url"], "https://example.com")
        self.assertNotIn("language", d)

    def test_to_dict_with_language(self):
        e = MessageEntity(type="pre", offset=0, length=10, language="python")
        d = e.to_dict()
        self.assertEqual(d["language"], "python")
        self.assertNotIn("url", d)

    def test_to_dict_with_custom_emoji(self):
        e = MessageEntity(type="custom_emoji", offset=0, length=2, custom_emoji_id="5368324170671202286")
        d = e.to_dict()
        self.assertEqual(d["custom_emoji_id"], "5368324170671202286")

    def test_to_dict_with_text_mention_user(self):
        user = {"id": 123, "is_bot": False, "first_name": "Ada"}
        e = MessageEntity(type="text_mention", offset=0, length=3, user=user)
        d = e.to_dict()
        self.assertEqual(d["user"], user)

    def test_to_dict_with_date_time(self):
        e = MessageEntity(
            type="date_time",
            offset=0,
            length=5,
            unix_time=1647531900,
            date_time_format="wDT",
        )
        d = e.to_dict()
        self.assertEqual(d["unix_time"], 1647531900)
        self.assertEqual(d["date_time_format"], "wDT")

    def test_copy_with_preserves_optional_fields(self):
        e = MessageEntity(
            type="date_time",
            offset=10,
            length=5,
            unix_time=1647531900,
            date_time_format="wDT",
        )
        copied = e.copy_with(offset=0, length=3)
        self.assertEqual(copied.offset, 0)
        self.assertEqual(copied.length, 3)
        self.assertEqual(copied.unix_time, 1647531900)
        self.assertEqual(copied.date_time_format, "wDT")


class SplitEntitiesTest(unittest.TestCase):
    def test_no_split_needed(self):
        text = "hello"
        entities = [MessageEntity(type="bold", offset=0, length=5)]
        result = split_entities(text, entities, max_utf16_len=100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "hello")
        self.assertEqual(len(result[0][1]), 1)

    def test_empty_text(self):
        result = split_entities("", [], max_utf16_len=100)
        self.assertEqual(result, [])

    def test_whitespace_only_text_is_omitted_without_splitting(self):
        result = split_entities("\n\n", [], max_utf16_len=100)
        self.assertEqual(result, [])

    def test_whitespace_only_chunks_are_omitted_after_splitting(self):
        result = split_entities("\n" * 5000, [], max_utf16_len=4096)
        self.assertEqual(result, [])

    def test_omits_whitespace_only_chunk_but_keeps_content_chunk(self):
        text = ("\n" * 5000) + "hello"
        entities = [MessageEntity(type="bold", offset=5000, length=5)]
        result = split_entities(text, entities, max_utf16_len=4096)
        self.assertEqual(
            result,
            [("\n" * 904 + "hello", [MessageEntity(type="bold", offset=904, length=5)])],
        )

    def test_split_at_newline(self):
        text = "aaa\nbbb\nccc"
        entities = []
        result = split_entities(text, entities, max_utf16_len=5)
        # "aaa\n" = 4 code units, "bbb\n" = 4, "ccc" = 3
        self.assertTrue(len(result) >= 2)
        combined = "".join(chunk for chunk, _ in result)
        self.assertEqual(combined, text)

    def test_entity_fully_in_first_chunk(self):
        text = "bold\nnormal"
        entities = [MessageEntity(type="bold", offset=0, length=4)]
        result = split_entities(text, entities, max_utf16_len=5)
        self.assertTrue(len(result) >= 2)
        # First chunk should have the bold entity
        self.assertEqual(len(result[0][1]), 1)
        self.assertEqual(result[0][1][0].type, "bold")

    def test_entity_fully_in_second_chunk(self):
        text = "normal\nbold"
        entities = [MessageEntity(type="bold", offset=7, length=4)]
        result = split_entities(text, entities, max_utf16_len=7)
        # Second chunk should have the entity with adjusted offset
        found = False
        for chunk_text, chunk_entities in result:
            for e in chunk_entities:
                if e.type == "bold":
                    self.assertEqual(e.offset, 0)
                    self.assertEqual(e.length, 4)
                    found = True
        self.assertTrue(found)

    def test_entity_spans_split_boundary(self):
        text = "aabbcc\nddee"
        # Bold spans the entire text
        entities = [MessageEntity(type="bold", offset=0, length=utf16_len(text))]
        result = split_entities(text, entities, max_utf16_len=7)
        self.assertTrue(len(result) >= 2)
        # Both chunks should have a bold entity
        for chunk_text, chunk_entities in result:
            self.assertTrue(
                any(e.type == "bold" for e in chunk_entities),
                f"Chunk '{chunk_text}' missing bold entity",
            )

    def test_split_preserves_date_time_fields(self):
        text = "time\nlater"
        entities = [
            MessageEntity(
                type="date_time",
                offset=0,
                length=4,
                unix_time=1647531900,
                date_time_format="wDT",
            )
        ]
        result = split_entities(text, entities, max_utf16_len=5)
        self.assertEqual(result[0][1][0].unix_time, 1647531900)
        self.assertEqual(result[0][1][0].date_time_format, "wDT")

    def test_split_preserves_total_text(self):
        text = "line1\nline2\nline3\nline4\nline5"
        entities = [MessageEntity(type="italic", offset=0, length=5)]
        result = split_entities(text, entities, max_utf16_len=12)
        combined = "".join(chunk for chunk, _ in result)
        self.assertEqual(combined, text)

    def test_split_with_emoji(self):
        # 📌 = 2 UTF-16 code units
        text = "📌\n📌\n📌"
        entities = []
        result = split_entities(text, entities, max_utf16_len=4)
        combined = "".join(chunk for chunk, _ in result)
        self.assertEqual(combined, text)

    def test_hard_split_no_newlines(self):
        text = "abcdefghij"
        entities = []
        result = split_entities(text, entities, max_utf16_len=4)
        combined = "".join(chunk for chunk, _ in result)
        self.assertEqual(combined, text)
        for chunk_text, _ in result:
            self.assertLessEqual(utf16_len(chunk_text), 4)


if __name__ == "__main__":
    unittest.main()
