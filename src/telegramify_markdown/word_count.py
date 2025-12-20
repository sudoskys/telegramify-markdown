import re
from typing import List

def count_markdown(md: str) -> int:
    md = re.sub(r'''
            (?<!\\)\[ # match [, but not match \[ (we just assume there won't be `\\[`)
                (.*?) # url description, \1
            (?<!\\)\] # similar as above
            \(
            .*? # url content
            (?<!\\)\)
        ''',
        r'[\1]()', # remove URL, because URL doesn't count as word count in Telegram
        md, flags=re.X)
    return len(md)

def hard_split_markdown(text: str, max_word_count: int) -> List[str]:
    assert max_word_count > 0
    chunks = []
    while text:
        limit = len(text)
        round = 0
        while limit > 0:
            round += 1
            c = count_markdown(text[:limit])
            if c <= max_word_count:
                break
            limit -= (c - max_word_count)
        # print(round, limit, c)
        
        chunks.append(text[:limit])
        text = text[limit:]
        
    return chunks


if __name__ == "__main__":
    # Test plain text split
    assert len(hard_split_markdown("a" * 200, 100)) == 2
    
    # Test expansion with large max_word_count
    # [a](http://b) -> 13 chars, 5 visible
    content = "[a](http://b)" * 100 # 1300 chars, 500 visible
    # max_word_count = 1000.
    # Should fit in 1 chunk (since 500 < 1000)
    # But strictly by length, 1300 > 1000, so it would split if not for count_markdown logic
    chunks = hard_split_markdown(content, 1000)
    assert len(chunks) == 1
    assert len(chunks[0]) == 1300

    content = "[a](http://b)" * 10000 # 1300 chars, 500 visible
    chunks = hard_split_markdown(content, 500)
    print(len(chunks))
    assert len(chunks) == 100

    print("hard_split_markdown passed")