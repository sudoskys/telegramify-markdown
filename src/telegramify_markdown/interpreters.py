# somewhat english comment
import re
from typing import List, Any, Callable, Optional
from typing import TYPE_CHECKING

import mistletoe

from telegramify_markdown.logger import logger
from telegramify_markdown.mermaid import render_mermaid, support_mermaid
from telegramify_markdown.mime import get_filename
from telegramify_markdown.type import (
    TaskType,
    File,
    Text,
    Photo,
    SentType,
    ContentTrace,
)
from telegramify_markdown.word_count import count_markdown

if TYPE_CHECKING:
    try:
        from aiohttp import ClientSession
    except ImportError:
        ClientSession = None


class BaseInterpreter(object):
    """
    Base interpreter class, all interpreters should inherit this class
    """

    name = "base"
    priority = 0  # The priority, the larger the number, the higher the priority

    def __init__(self):
        self.next_interpreter = None

    def set_next(self, interpreter: "BaseInterpreter") -> "BaseInterpreter":
        """
        Set the next interpreter in the responsibility chain
        :param interpreter: BaseInterpreter
        :return: BaseInterpreter
        """
        self.next_interpreter = interpreter
        return interpreter

    async def can_handle(self, task: TaskType) -> bool:
        """
        Determine if the current interpreter can handle the task
        :param task: [(base, [(escaped,unescaped),(escaped,unescaped)]),....]
        :return: bool
        """
        task_type, _ = task
        return task_type == self.name

    async def merge(self, tasks: List[TaskType]) -> List[TaskType]:
        """
        Merge the tasks.
        :param tasks:  [(base, [(escaped,unescaped),(escaped,unescaped)]), (base, [(escaped,unescaped),(escaped,unescaped)])]
        :return:
        """
        return tasks

    async def split(self, task: TaskType) -> List[TaskType]:
        """
        Split the task.
        :param task: (base, [(escaped,unescaped),(escaped,unescaped)])
        :return: [(base, [(escaped,unescaped),(escaped,unescaped)]),....newTask]
        """
        return [task]

    async def handle(
        self,
        task: TaskType,
        render_block_func: Callable[[List[Any]], str],
        render_lines_func: Callable[[str], str],
        max_word_count: int = 4090,
    ) -> Optional[SentType]:
        """
        Handle the task.
        :param task: (base, [(escaped,unescaped),(escaped,unescaped)])
        :param render_block_func: Callable[[List[Any]], str]
        :param render_lines_func: Callable[[str], str]
        :param max_word_count: int
        :return: Optional[SentType]
        """
        if await self.can_handle(task):
            return await self.render_task(
                task, render_block_func, render_lines_func, max_word_count
            )
        elif self.next_interpreter:
            return await self.next_interpreter.handle(
                task, render_block_func, render_lines_func, max_word_count
            )
        # If there is no next interpreter, default to using TextInterpreter to process
        return await TextInterpreter().render_task(
            task, render_block_func, render_lines_func, max_word_count
        )

    async def render_task(
        self,
        task: TaskType,
        render_block_func: Callable[[List[Any]], str],
        render_lines_func: Callable[[str], str],
        max_word_count: int = 4090,
    ) -> SentType:
        """
        The specific implementation of rendering the task, which must be overridden by subclasses
        """
        raise NotImplementedError("Subclasses must implement render_task method, try TextInterpreter as the default processor")

    def _smart_split_text(self, text: str, max_word_count: int) -> List[str]:
        """
        Smart split text, try the following order:
        1. Split by newline
        2. If a line is still too long, split by punctuation
        3. If there are no punctuation marks, split by hard split
        """
        # If the text length is less than the maximum word count limit, return directly
        if count_markdown(text) <= max_word_count:
            return [text]

        # Split by newline
        lines = text.split("\n")
        result = []
        current_chunk = ""

        for line in lines:
            # If the current line plus the current block does not exceed the maximum word count limit, add it to the current block
            if count_markdown(current_chunk + line + "\n") <= max_word_count:
                current_chunk += line + "\n"
            else:
                # If the current line itself exceeds the maximum word count limit, it needs to be further split
                if count_markdown(line) > max_word_count:
                    # If the current block is not empty, save the current block first
                    if current_chunk:
                        result.append(current_chunk.rstrip())
                        current_chunk = ""

                    # Split long lines by punctuation
                    punctuation_chunks = self._split_by_punctuation(
                        line, max_word_count
                    )
                    result.extend(punctuation_chunks)
                else:
                    # Save the current block and start a new block
                    if current_chunk:
                        result.append(current_chunk.rstrip())
                    current_chunk = line + "\n"

        # Add the last block (if any)
        if current_chunk:
            result.append(current_chunk.rstrip())

        return result

    def _split_by_punctuation(self, text: str, max_word_count: int) -> List[str]:
        """
        Split the text by punctuation
        :param text: str
        :param max_word_count: int
        :return: List[str]
        """
        # Common Chinese and English punctuation marks
        punctuation_pattern = r"([。，,.!?；;：:\n])"

        # Split the text by punctuation
        segments = re.split(punctuation_pattern, text)

        # Recombine punctuation marks with their preceding text
        chunks = []
        current_chunk = ""

        for i in range(0, len(segments), 2):
            segment = segments[i]
            # Add punctuation (if any)
            if i + 1 < len(segments):
                segment += segments[i + 1]

            # If the current segment plus the current block does not exceed the maximum word count limit, add it to the current block
            if count_markdown(current_chunk + segment) <= max_word_count:
                current_chunk += segment
            else:
                # If the current segment itself exceeds the maximum word count limit, it needs to be hard split
                if count_markdown(segment) > max_word_count:
                    # If the current block is not empty, save the current block first
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = ""

                    # Hard split the current segment
                    hard_chunks = self._hard_split(segment, max_word_count)
                    chunks.extend(hard_chunks)
                else:
                    # Save the current block and start a new block
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = segment

        # Add the last block (if any)
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _hard_split(self, text: str, max_word_count: int) -> List[str]:
        """
        Hard split text, split directly according to the maximum word count limit.
        Uses count_markdown to approximate the split point efficiently.
        :param text: str
        :param max_word_count: int
        :return: List[str]
        """
        chunks = []
        while text:
            limit = max_word_count
            # Exponential probe to find the largest valid block (handling non-monotonicity of count_markdown)
            candidate = limit
            while candidate < len(text):
                candidate = min(len(text), candidate * 2)
                if count_markdown(text[:candidate]) <= max_word_count:
                    limit = candidate
                if candidate == len(text): break
            
            # Fine-tuning to fill the gap
            while limit < len(text):
                c = count_markdown(text[:limit])
                if max_word_count - c < 10: break
                new_limit = min(len(text), limit + (max_word_count - c))
                if count_markdown(text[:new_limit]) > max_word_count: break
                limit = new_limit

            chunks.append(text[:limit])
            text = text[limit:]
        return chunks


class TextInterpreter(BaseInterpreter):
    """
    Pure text interpreter, only return text type
    """

    name = "text"
    priority = 10

    async def can_handle(self, task: TaskType) -> bool:
        """
        Determine if the task can be handled
        :param task: [(base, [(escaped,unescaped),(escaped,unescaped)]),....]
        :return: bool
        """
        task_type, token_pairs = task
        if task_type != "base":
            return False

        # Check if it contains a code block or other special content
        for token_pair in token_pairs:
            token1, _ = token_pair
            if isinstance(token1, mistletoe.block_token.CodeFence):
                return False
        return True

    async def render_task(
        self,
        task: TaskType,
        render_block_func: Callable[[List[Any]], str],
        render_lines_func: Callable[[str], str],
        max_word_count: int = 4090,
    ) -> SentType:
        """
        Render pure text task
        :param task: [(base, [(escaped,unescaped),(escaped,unescaped)]),....]
        :param render_block_func: Callable[[List[Any]], str]
        :param render_lines_func: Callable[[str], str]
        :param max_word_count: int
        :return: List[Union[Text, File, Photo]]
        """
        task_type, token_pairs = task
        escaped_tokens = list(__token1 for __token1, __token2 in token_pairs)
        unescaped_tokens = list(__token2 for __token1, __token2 in token_pairs)
        # Render the content
        escaped_content = render_block_func(escaped_tokens)
        unescaped_content = render_block_func(unescaped_tokens)
        # Check if it exceeds the maximum word count limit
        if len(escaped_content) > max_word_count:
            # Smartly split the text
            chunks = self._smart_split_text(unescaped_content, max_word_count)
            # Ensure each split block is correctly rendered
            return [
                Text(
                    # Use render_lines_func to ensure each block is correctly rendered
                    content=render_lines_func(chunk),
                    content_trace=ContentTrace(source_type=self.name),
                )
                for chunk in chunks
                if chunk  # Ensure not to return an empty string
            ]

        # If it does not exceed the maximum word count, send it as a text
        return [
            Text(
                content=escaped_content,
                content_trace=ContentTrace(source_type=self.name),
            )
        ]


class FileInterpreter(BaseInterpreter):
    """
    File interpreter, handle content that needs to be sent as a file
    """

    name = "file"
    priority = 20

    async def can_handle(self, task: TaskType) -> bool:
        """
        Determine if the task can be handled
        :param task: [(base, [(escaped,unescaped),(escaped,unescaped)]),....]
        :return: bool
        """
        task_type, token_pairs = task
        if task_type == "file":
            return True

        if task_type != "base":
            return False

        # Check if it contains a code block
        for token_pair in token_pairs:
            token1, _ = token_pair
            if (
                isinstance(token1, mistletoe.block_token.CodeFence)
                and token1.language.lower() != "mermaid"
            ):
                return True
        return False

    async def split(self, task: TaskType) -> List[TaskType]:
        """
        Split the task
        :param task: [(base, [(escaped,unescaped),(escaped,unescaped)]),....]
        :return: [(base, [(escaped,unescaped),(escaped,unescaped)]),....newTask]
        """
        task_type, token_pairs = task
        # Only process base blocks
        if task_type != "base":
            return [task]

        # Use to store the new tasks
        tasks = []
        # Temporary cache non-code blocks
        current_base_tokens = []

        for token_pair in token_pairs:
            token1, _ = token_pair
            # Check if it is a code block (non-mermaid)
            if (
                isinstance(token1, mistletoe.block_token.CodeFence)
                and token1.language.lower() != "mermaid"
            ):
                if current_base_tokens:
                    # Generate a new base task from the cached non-code blocks
                    tasks.append(("base", current_base_tokens))
                    current_base_tokens = []
                # Add a code block task
                tasks.append(("file", [token_pair]))
            else:
                # Accumulate base blocks
                current_base_tokens.append(token_pair)

        # Process the remaining base blocks
        if current_base_tokens:
            tasks.append(("base", current_base_tokens))

        return tasks

    async def render_task(
        self,
        task: TaskType,
        render_block_func: Callable[[List[Any]], str],
        render_lines_func: Callable[[str], str],
        max_word_count: int = 4090,
    ) -> SentType:
        """Render file task
        :param task: [(base, [(escaped,unescaped),(escaped,unescaped)]),....]
        :param render_block_func: Callable[[List[Any]], str]
        :param render_lines_func: Callable[[str], str]
        :param max_word_count: int
        :return: List[Union[Text, File, Photo]]
        """
        task_type, token_pairs = task
        token1_l = list(__token1 for __token1, __token2 in token_pairs)
        token2_l = list(__token2 for __token1, __token2 in token_pairs)

        # Check if it is a single code block
        if (
            all(
                isinstance(_per_token1, mistletoe.block_token.CodeFence)
                for _per_token1 in token1_l
            )
            and len(token1_l) == 1
            and len(token2_l) == 1
        ):
            # If this pack is a completely code block, then send as a file
            _escaped_code = token1_l[0]
            _unescaped_code_child = list(token2_l[0].children)
            file_content = render_block_func(token2_l)
            if _unescaped_code_child:
                _code_text = _unescaped_code_child[0]
                if isinstance(_code_text, mistletoe.span_token.RawText):
                    file_content = _code_text.content
            lang = "txt"
            if isinstance(_escaped_code, mistletoe.block_token.CodeFence):
                lang = _escaped_code.language
            file_name = get_filename(line=render_block_func(token1_l), language=lang)
            return [
                File(
                    file_name=file_name,
                    file_data=file_content.encode(),
                    caption="",
                    content_trace=ContentTrace(source_type=self.name),
                )
            ]

        # Other cases, send as a normal text file
        return [
            File(
                file_name="letter.txt",
                file_data=render_block_func(token2_l).encode(),
                caption="",
                content_trace=ContentTrace(source_type=self.name),
            )
        ]


class MermaidInterpreter(BaseInterpreter):
    """Mermaid chart interpreter"""

    name = "mermaid"
    priority = 30
    session = None
    support = support_mermaid()

    def __init__(self, session: "ClientSession" = None):
        super().__init__()
        if not self.support:
            logger.error(
                "Mermaid is not supported because the required libraries are not installed. "
                "Run `pip install telegramify-markdown[mermaid]` or remove MermaidInterpreter"
            )
        self.session = session

    async def can_handle(self, task: TaskType) -> bool:
        """
        Determine if the task can be handled
        :param task: [(base, [(escaped,unescaped),(escaped,unescaped)]),....]
        :return: bool
        """
        if not self.support:
            return False

        task_type, token_pairs = task
        if task_type == "mermaid":
            return True

        if task_type != "base":
            return False

        # Check if it contains a Mermaid block
        for token_pair in token_pairs:
            token1, _ = token_pair
            if (
                isinstance(token1, mistletoe.block_token.CodeFence)
                and token1.language.lower() == "mermaid"
            ):
                return True
        return False

    async def split(self, task: TaskType) -> List[TaskType]:
        """
        Split the task
        :param task: [(base, [(escaped,unescaped),(escaped,unescaped)]),....]
        :return: [(base, [(escaped,unescaped),(escaped,unescaped)]),....newTask]
        """
        task_type, token_pairs = task
        # Only process base blocks
        if task_type != "base":
            return [task]
        # Do not produce new tasks if Mermaid is not supported
        if not self.support:
            return [task]
        # Use to store the new tasks
        tasks = []
        # Temporary cache non-Mermaid blocks
        current_base_tokens = []
        for token_pair in token_pairs:
            token1, _ = token_pair
            # Check if it is a Mermaid block
            if (
                isinstance(token1, mistletoe.block_token.CodeFence)
                and token1.language.lower() == "mermaid"
            ):
                if current_base_tokens:
                    # Generate a new base task from the cached non-Mermaid blocks
                    tasks.append(("base", current_base_tokens))
                    current_base_tokens = []
                # Add a Mermaid block task
                tasks.append(("mermaid", [token_pair]))
            else:
                # Accumulate base blocks
                current_base_tokens.append(token_pair)
        # Process the remaining base blocks
        if current_base_tokens:
            tasks.append(("base", current_base_tokens))
        return tasks

    async def render_task(
        self,
        task: TaskType,
        render_block_func: Callable[[List[Any]], str],
        render_lines_func: Callable[[str], str],
        max_word_count: int = 4090,
    ) -> SentType:
        """
        Render Mermaid task
        :param task: [(base, [(escaped,unescaped),(escaped,unescaped)]),....]
        :param render_block_func: Callable[[List[Any]], str]
        :param render_lines_func: Callable[[str], str]
        :param max_word_count: int
        :return: List[Union[Text, File, Photo]]
        """
        task_type, token_pairs = task
        if task_type != "mermaid":
            raise ValueError("Invalid task type for MermaidInterpreter.")
        # Only process Mermaid blocks
        if len(token_pairs) != 1:
            raise ValueError("Invalid token length for MermaidInterpreter.")
        escaped_tokens = list(__token1 for __token1, __token2 in token_pairs)
        unescape_tokens = list(__token2 for __token1, __token2 in token_pairs)
        if not all(
            isinstance(_per_token, mistletoe.block_token.CodeFence)
            for _per_token in escaped_tokens
        ):
            raise ValueError("Invalid token type for MermaidInterpreter.")
        unescaped_code_token = unescape_tokens[0]
        if (
            isinstance(unescaped_code_token, mistletoe.block_token.CodeFence)
            and unescaped_code_token.language.lower() == "mermaid"
        ):
            file_content = render_block_func(unescape_tokens)
            _unescaped_code_child = list(unescaped_code_token.children)
            if _unescaped_code_child:
                _raw_text = _unescaped_code_child[0]
                if isinstance(_raw_text, mistletoe.span_token.RawText):
                    file_content = _raw_text.content
            try:
                img_io, url = await render_mermaid(
                    diagram=file_content.replace("```mermaid", "").replace("```", ""),
                    session=self.session,
                )
                message = f"[edit in mermaid.live]({url})"
            except Exception as e:
                logger.warning(f"Mermaid render error: {e}")
                return [
                    File(
                        file_name="invalid_mermaid.txt",
                        file_data=render_block_func(unescape_tokens).encode(),
                        caption=render_lines_func("invalid_mermaid"),
                        content_trace=ContentTrace(source_type=self.name),
                    )
                ]
            else:
                return [
                    Photo(
                        file_name="mermaid.png",
                        file_data=img_io.getvalue(),
                        caption=render_lines_func(message),
                        content_trace=ContentTrace(source_type=self.name),
                    )
                ]
        return [
            File(
                file_name="mermaid_code.txt",
                file_data=render_block_func(unescape_tokens).encode(),
                caption="",
                content_trace=ContentTrace(source_type=self.name),
            )
        ]


class InterpreterChain:
    """Interpreter Chain Management Class"""

    def __init__(self, interpreters: List[BaseInterpreter] = None):
        self.interpreters = interpreters or []
        self.head = None
        self._build_chain()

    def _build_chain(self):
        """Build the responsibility chain"""
        if not self.interpreters:
            return

        # 按优先级排序
        sorted_interpreters = sorted(
            self.interpreters, key=lambda x: x.priority, reverse=True
        )

        # 构建链
        self.head = sorted_interpreters[0]
        current = self.head
        for interpreter in sorted_interpreters[1:]:
            current.set_next(interpreter)
            current = interpreter

    def add_interpreter(self, interpreter: BaseInterpreter):
        """Add an interpreter"""
        self.interpreters.append(interpreter)
        self._build_chain()

    async def process(
        self,
        task: TaskType,
        render_block_func: Callable[[List[Any]], str],
        render_lines_func: Callable[[str], str],
        max_word_count: int = 4090,
    ) -> SentType:
        """
        Process the task.
        :param task: [(base, [(escaped,unescaped),(escaped,unescaped)]),....]
        :param render_block_func: Callable[[List[Any]], str]
        :param render_lines_func: Callable[[str], str]
        :param max_word_count: int
        :return: List[Union[Text, File, Photo]]
        """
        if not self.head:
            raise ValueError("No interpreters in the chain")

        result = await self.head.handle(
            task, render_block_func, render_lines_func, max_word_count
        )
        if result is None:
            # If no interpreter can handle, use TextInterpreter as the default processor
            text_interpreter = TextInterpreter()
            return await text_interpreter.render_task(
                task, render_block_func, render_lines_func, max_word_count
            )
        return result


# Create a default interpreter chain
def create_default_chain(session: "ClientSession" = None) -> InterpreterChain:
    """Create a default interpreter chain"""
    chain = InterpreterChain(
        [
            TextInterpreter(),
            FileInterpreter(),
            MermaidInterpreter(session=session),
        ]
    )
    return chain
