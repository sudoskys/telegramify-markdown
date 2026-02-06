import re
from logging import getLogger
from telegramify_markdown.latex_escape.const import (
    COMBINING, CombiningType, NOT_MAP, SUBSCRIPTS, SUPERSCRIPTS, LATEX_STYLES, FRAC_MAP, LATEX_SYMBOLS
)

logger = getLogger(__name__)


class LatexToUnicodeHelper:
    """递归下降 LaTeX→Unicode 转换引擎。

    设计原则：
    1. 数据驱动 — 符号映射集中在 const.py
    2. 鲁棒降级 — 未知命令返回原文，不崩溃
    3. 标准 LaTeX 语法 — 可选参数用 [...]
    4. Unicode 优先 — 尽量用 Unicode，无法表示时用可读 ASCII 近似
    """

    # ──────────────────────────────────────────────
    # 静态工具方法
    # ──────────────────────────────────────────────

    @staticmethod
    def is_combining_char(char):
        """判断字符是否为 Unicode 组合字符。"""
        return (
            '\u0300' <= char <= '\u036F' or
            '\u1AB0' <= char <= '\u1AFF' or
            '\u1DC0' <= char <= '\u1DFF' or
            '\u20D0' <= char <= '\u20FF' or
            '\uFE20' <= char <= '\uFE2F'
        )

    @staticmethod
    def translate_combining(command, text):
        """将组合字符应用于文本。"""
        sample = COMBINING.get(command)
        if not sample:
            return text
        combining_char, combining_type = sample
        if combining_type == CombiningType.FirstChar:
            i = 1
            while i < len(text) and (text[i].isspace() or LatexToUnicodeHelper.is_combining_char(text[i])):
                i += 1
            return text[:i] + combining_char + text[i:]
        elif combining_type == CombiningType.LastChar:
            return text + combining_char
        elif combining_type == CombiningType.EveryChar:
            return ''.join(text[i] + combining_char for i in range(len(text)))
        return text

    @staticmethod
    def make_not(negated):
        """生成带否定符号的字符。"""
        trimmed = negated.strip()
        if not trimmed:
            return " "
        return NOT_MAP.get(trimmed, f"{trimmed[0]}\u0338{trimmed[1:]}")

    # ──────────────────────────────────────────────
    # 上下标
    # ──────────────────────────────────────────────

    @staticmethod
    def try_make_subscript(text):
        """尝试将文本完整转换为 Unicode 下标，失败返回 None。"""
        if not text:
            return ""
        if all(ch in SUBSCRIPTS for ch in text):
            return ''.join(SUBSCRIPTS[ch] for ch in text)
        return None

    @staticmethod
    def make_subscript(text):
        """生成下标表示。"""
        text = text.strip()
        if not text:
            return ""
        subscript = LatexToUnicodeHelper.try_make_subscript(text)
        if subscript is not None:
            return subscript
        if len(text) == 1:
            return SUBSCRIPTS.get(text, f"_{text}")
        return f"_({text})"

    @staticmethod
    def try_make_superscript(text):
        """尝试将文本完整转换为 Unicode 上标，失败返回 None。"""
        if not text:
            return ""
        if all(ch in SUPERSCRIPTS for ch in text):
            return ''.join(SUPERSCRIPTS[ch] for ch in text)
        return None

    @staticmethod
    def make_superscript(text):
        """生成上标表示。"""
        text = text.strip()
        if not text:
            return ""
        superscript = LatexToUnicodeHelper.try_make_superscript(text)
        if superscript is not None:
            return superscript
        if len(text) == 1:
            return SUPERSCRIPTS.get(text, f"^{text}")
        return f"^({text})"

    # ──────────────────────────────────────────────
    # 样式、分数、根号
    # ──────────────────────────────────────────────

    @staticmethod
    def translate_styles(command, text):
        """翻译样式命令（粗体、斜体、正体等）。"""
        style_map = LATEX_STYLES.get(command)
        if style_map is None:
            raise ValueError(f"Unknown style command: {command}")
        # 空 dict（如 \mathrm）通过 .get(char, char) 原样返回
        return ''.join(style_map.get(char, char) for char in text)

    @staticmethod
    def make_sqrt(index, radicand):
        """生成根号的 Unicode 表示。"""
        radix = {"": "√", "2": "√", "3": "∛", "4": "∜"}.get(
            index, (LatexToUnicodeHelper.try_make_superscript(index) or f"({index})") + "√"
        )
        return radix + LatexToUnicodeHelper.translate_combining("\\overline", radicand)

    @staticmethod
    def translate_sqrt(command, option, param):
        """翻译 \\sqrt 命令。"""
        if command != "\\sqrt":
            raise ValueError(f"Unknown command: {command}")
        return LatexToUnicodeHelper.make_sqrt(option.strip(), param.strip())

    @staticmethod
    def maybe_parenthesize(text):
        """根据内容决定是否添加括号。"""
        def needs_parens(char):
            return not (
                char.isalnum() or
                LatexToUnicodeHelper.is_combining_char(char) or
                char.isdecimal() or
                char == '_'
            )
        if any(needs_parens(c) for c in text):
            return f"({text})"
        return text

    @staticmethod
    def make_fraction(numerator, denominator):
        """生成分数的 Unicode 表示。"""
        n, d = numerator.strip(), denominator.strip()
        if not n and not d:
            return ""
        fraction_unicode = FRAC_MAP.get((n, d))
        if fraction_unicode:
            return fraction_unicode
        return f"{LatexToUnicodeHelper.maybe_parenthesize(n)}/{LatexToUnicodeHelper.maybe_parenthesize(d)}"

    @staticmethod
    def translate_frac(command, numerator, denominator):
        """翻译 \\frac 命令。"""
        if command != "\\frac":
            raise ValueError(f"Unknown command: {command}")
        return LatexToUnicodeHelper.make_fraction(numerator, denominator)

    @staticmethod
    def translate_escape(name):
        return LATEX_SYMBOLS.get(name, name)

    # ──────────────────────────────────────────────
    # 解析器核心
    # ──────────────────────────────────────────────

    def parse(self, latex):
        """递归下降解析 LaTeX 字符串，转换为 Unicode。"""
        result, i = [], 0
        while i < len(latex):
            if latex[i] == '\\':
                command, i = self.parse_command(latex, i)
                # 混合分数格式（数字后紧跟 \frac）
                if command == "\\frac" and result and result[-1] and result[-1][-1].isdigit():
                    result[-1] = result[-1] + " "
                handled, i = self.handle_command(command, latex, i)
                result.append(handled)
            elif latex[i] == '{':
                block, i = self.parse_block(latex, i)
                result.append(block)
            elif latex[i] in '_^':
                sym, arg, i = latex[i], '', i + 1
                if i < len(latex) and latex[i] == '{':
                    arg, i = self.parse_block(latex, i)
                elif i < len(latex) and latex[i] == '\\':
                    command, i = self.parse_command(latex, i)
                    if command == "\\frac" and result and result[-1] and result[-1][-1].isdigit():
                        result[-1] = result[-1] + " "
                    arg, i = self.handle_command(command, latex, i)
                elif i < len(latex):
                    arg, i = latex[i], i + 1
                result.append(self.make_subscript(arg) if sym == '_' else self.make_superscript(arg))
            elif latex[i].isspace():
                spaces, i = self.parse_spaces(latex, i)
                result.append(spaces)
            else:
                result.append(latex[i])
                i += 1
        return ''.join(result)

    # ──────────────────────────────────────────────
    # 命令分派（有序优先级）
    # ──────────────────────────────────────────────

    def handle_command(self, command, latex, index):
        """根据命令类型分派处理。按优先级有序排列。"""

        # 1. 符号表直查（最常见路径）
        if command in LATEX_SYMBOLS:
            return self.translate_escape(command), index

        # 2. \not 前缀否定
        elif command == "\\not":
            if index < len(latex):
                if latex[index] == '\\':
                    next_cmd, next_idx = self.parse_command(latex, index)
                    symbol = LATEX_SYMBOLS.get(next_cmd, next_cmd)
                    return self.make_not(symbol), next_idx
                else:
                    return self.make_not(latex[index]), index + 1
            return "\u0338", index

        # 3. 组合字符命令（\hat, \bar, \vec, \dot 等）
        elif command in COMBINING:
            arg, index = self.parse_block(latex, index)
            return self.translate_combining(command, arg), index

        # 4. \frac{num}{den}
        elif command == "\\frac":
            numer, index = self.parse_block(latex, index)
            denom, index = self.parse_block(latex, index)
            return self.make_fraction(numer, denom), index

        # 5. \sqrt[n]{x} — 可选参数用 []
        elif command == "\\sqrt":
            option, index = self.parse_optional(latex, index)
            param, index = self.parse_block(latex, index)
            return self.translate_sqrt(command, option, param), index

        # 6. 样式命令（\mathbb, \mathbf, \mathrm, \mathit 等）
        elif command in LATEX_STYLES:
            text, index = self.parse_block(latex, index)
            return self.translate_styles(command, text), index

        # 7. 文本直通命令
        elif command in ("\\text", "\\operatorname", "\\mbox",
                         "\\textrm", "\\textup", "\\mathop"):
            text, index = self.parse_block(latex, index)
            return text, index

        # 8. \left / \right 定界符
        elif command in ("\\left", "\\right"):
            delim, index = self._parse_delimiter(latex, index)
            return delim, index

        # 9. \binom{n}{k} / \tbinom / \dbinom
        elif command in ("\\binom", "\\tbinom", "\\dbinom"):
            n_val, index = self.parse_block(latex, index)
            k_val, index = self.parse_block(latex, index)
            return f"C({n_val},{k_val})", index

        # 10. \boxed{x}
        elif command == "\\boxed":
            text, index = self.parse_block(latex, index)
            return f"[{text}]", index

        # 11. \pmod{p}
        elif command == "\\pmod":
            text, index = self.parse_block(latex, index)
            return f" (mod {text})", index

        # 12. \phantom / \hphantom / \vphantom — 等宽空白
        elif command in ("\\phantom", "\\hphantom", "\\vphantom"):
            text, index = self.parse_block(latex, index)
            return " " * max(len(text), 1), index

        # 13. \overset{over}{base}
        elif command == "\\overset":
            over, index = self.parse_block(latex, index)
            base, index = self.parse_block(latex, index)
            sup = self.try_make_superscript(over)
            return (f"{base}{sup}" if sup else f"{base}^({over})"), index

        # 14. \underset{under}{base}
        elif command == "\\underset":
            under, index = self.parse_block(latex, index)
            base, index = self.parse_block(latex, index)
            sub = self.try_make_subscript(under)
            return (f"{base}{sub}" if sub else f"{base}_({under})"), index

        # 15. \stackrel{over}{base}
        elif command == "\\stackrel":
            over, index = self.parse_block(latex, index)
            base, index = self.parse_block(latex, index)
            sup = self.try_make_superscript(over)
            return (f"{base}{sup}" if sup else f"{base}^({over})"), index

        # 16. \substack{...} — 多行下标
        elif command == "\\substack":
            text, index = self.parse_block(latex, index)
            lines = [l.strip() for l in text.split("\\\\") if l.strip()]
            return ", ".join(self.parse(l) for l in lines), index

        # 17. \color{...} — 忽略颜色参数
        elif command == "\\color":
            _, index = self.parse_block(latex, index)
            return "", index

        # 18. \cancel / \bcancel / \xcancel / \sout — 删除线效果
        elif command in ("\\cancel", "\\bcancel", "\\xcancel", "\\sout"):
            text, index = self.parse_block(latex, index)
            return self.translate_combining("\\underline", text), index

        # 19. \overbrace / \underbrace
        elif command == "\\overbrace":
            text, index = self.parse_block(latex, index)
            return self.translate_combining("\\overline", text), index
        elif command == "\\underbrace":
            text, index = self.parse_block(latex, index)
            return self.translate_combining("\\underline", text), index

        # 20. \xrightarrow / \xleftarrow
        elif command == "\\xrightarrow":
            text, index = self.parse_block(latex, index)
            return (f"→({text})" if text.strip() else "→"), index
        elif command == "\\xleftarrow":
            text, index = self.parse_block(latex, index)
            return (f"←({text})" if text.strip() else "←"), index

        # 21. \begin{...}\end{...} 环境
        elif command == "\\begin":
            env_name, index = self._parse_env_name(latex, index)
            content, index = self._parse_environment(latex, index, env_name)
            return self._render_environment(env_name, content), index
        elif command == "\\end":
            env_name, index = self._parse_env_name(latex, index)
            return "", index

        # 22. 兜底：返回原始命令文本
        return command, index

    # ──────────────────────────────────────────────
    # 底层解析方法
    # ──────────────────────────────────────────────

    @staticmethod
    def parse_command(latex, start):
        """解析 LaTeX 命令（\\word 或 \\符号）。"""
        match = re.match(r'\\([a-zA-Z]+|.)', latex[start:])
        if match:
            return match.group(0), start + match.end()
        return '\\', start + 1

    def parse_block(self, latex, start):
        """解析 {...} 块。若无 { 则按标准 LaTeX 读取单个 token。"""
        if start >= len(latex):
            return "", start
        if latex[start] != '{':
            # 无 {} 包裹 — 读取单个 token（标准 LaTeX 行为）
            if latex[start] == '\\':
                cmd, new_index = self.parse_command(latex, start)
                return self.handle_command(cmd, latex, new_index)
            return latex[start], start + 1
        # 标准 {...} 块解析
        level, pos = 1, start + 1
        while pos < len(latex) and level > 0:
            if latex[pos] == '{':
                level += 1
            elif latex[pos] == '}':
                level -= 1
            pos += 1
        return self.parse(latex[start + 1:pos - 1]), pos

    def parse_optional(self, latex, start):
        """解析可选参数 [...]，若无则返回空字符串。"""
        if start >= len(latex) or latex[start] != '[':
            return "", start
        level, pos = 1, start + 1
        while pos < len(latex) and level > 0:
            if latex[pos] == '[':
                level += 1
            elif latex[pos] == ']':
                level -= 1
            pos += 1
        return self.parse(latex[start + 1:pos - 1]), pos

    @staticmethod
    def parse_spaces(latex, start):
        """解析连续空白字符。"""
        end = start
        while end < len(latex) and latex[end].isspace():
            end += 1
        return ('\n\n' if '\n' in latex[start:end] else ' '), end

    # ──────────────────────────────────────────────
    # 定界符解析
    # ──────────────────────────────────────────────

    @staticmethod
    def _parse_delimiter(latex, index):
        """解析 \\left / \\right 后面的定界符。"""
        if index >= len(latex):
            return "", index
        ch = latex[index]
        if ch == '\\':
            cmd_match = re.match(r'\\([a-zA-Z]+|.)', latex[index:])
            if cmd_match:
                cmd = cmd_match.group(0)
                return LATEX_SYMBOLS.get(cmd, cmd.lstrip('\\')), index + cmd_match.end()
            return "\\", index + 1
        elif ch == '.':
            return "", index + 1  # 不可见定界符
        else:
            return ch, index + 1

    # ──────────────────────────────────────────────
    # 环境解析与渲染
    # ──────────────────────────────────────────────

    @staticmethod
    def _parse_env_name(latex, index):
        """解析环境名 {env_name}。"""
        if index < len(latex) and latex[index] == '{':
            close = latex.find('}', index)
            if close != -1:
                return latex[index + 1:close], close + 1
        return "", index

    def _parse_environment(self, latex, index, env_name):
        """提取 \\begin{env} 到 \\end{env} 之间的原始内容。"""
        end_marker = f"\\end{{{env_name}}}"
        end_pos = latex.find(end_marker, index)
        if end_pos == -1:
            return latex[index:], len(latex)
        return latex[index:end_pos], end_pos + len(end_marker)

    # 矩阵类环境类型 → (左定界符, 右定界符)
    _MATRIX_TYPES = {
        "matrix": ("", ""),
        "pmatrix": ("(", ")"),
        "bmatrix": ("[", "]"),
        "Bmatrix": ("{", "}"),
        "vmatrix": ("|", "|"),
        "Vmatrix": ("‖", "‖"),
        "smallmatrix": ("", ""),
    }

    # align 类环境
    _ALIGN_TYPES = frozenset({
        "align", "aligned", "gather", "gathered",
        "equation", "equation*", "multline", "multline*",
        "split", "flalign", "flalign*",
    })

    def _render_environment(self, env_name, content):
        """根据环境类型渲染内容。"""
        if env_name in self._MATRIX_TYPES:
            left, right = self._MATRIX_TYPES[env_name]
            compact = (env_name == "smallmatrix")
            return self._render_matrix(content, left, right, compact)
        elif env_name == "cases":
            return self._render_cases(content)
        elif env_name in self._ALIGN_TYPES:
            return self._render_align(content)
        elif env_name == "array":
            return self._render_array(content)
        else:
            # 未知环境 — 直接解析内容
            return self.parse(content)

    def _render_matrix(self, content, left, right, compact=False):
        """渲染矩阵环境。"""
        rows = [r.strip() for r in content.split("\\\\") if r.strip()]
        rendered = []
        for row in rows:
            cells = [self.parse(c.strip()) for c in row.split("&")]
            sep = ", " if compact else "  "
            rendered.append(sep.join(cells))
        joiner = "; " if compact else "\n"
        body = joiner.join(rendered)
        if left or right:
            if compact:
                return f"{left}{body}{right}"
            return f"{left}{body}{right}"
        return body

    def _render_cases(self, content):
        """渲染 cases 环境（分段函数），使用 Unicode 大括号避免干扰 Markdown 解析。"""
        rows = [r.strip() for r in content.split("\\\\") if r.strip()]
        parts = []
        for row in rows:
            segments = row.split("&", 1)
            val = self.parse(segments[0].strip())
            cond = self.parse(segments[1].strip()) if len(segments) > 1 else ""
            parts.append(f"{val}, {cond}" if cond else val)
        n = len(parts)
        if n == 0:
            return ""
        if n == 1:
            return f"\u23A7 {parts[0]}"
        lines = []
        for i, part in enumerate(parts):
            if i == 0:
                lines.append(f"\u23A7 {part}")
            elif i == n - 1:
                lines.append(f"\u23A9 {part}")
            else:
                lines.append(f"\u23A8 {part}")
        return "\n".join(lines)

    def _render_align(self, content):
        """渲染 align / gather 类环境。"""
        rows = [r.strip() for r in content.split("\\\\") if r.strip()]
        return "\n".join(self.parse(r.replace("&", " ")) for r in rows)

    def _render_array(self, content):
        """渲染 array 环境（跳过列格式参数）。"""
        # array 第一个 {} 是列格式说明（如 {ccc}），跳过
        stripped = content.lstrip()
        if stripped.startswith('{'):
            close = stripped.find('}')
            if close != -1:
                content = stripped[close + 1:]
        return self._render_matrix(content, "", "")

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    def convert(self, latex):
        """将 LaTeX 字符串转换为 Unicode 文本。出错时返回原文。"""
        try:
            return self.parse(latex)
        except Exception as e:
            logger.error(f"Failed to convert LaTeX to Unicode: {e}")
            return latex


# 示例使用
if __name__ == "__main__":
    helper = LatexToUnicodeHelper()

    # 基础功能
    print(helper.convert("\\frac{1}{2}"))         # ½
    print(helper.convert("\\sqrt{x}"))             # √x̅
    print(helper.convert("\\sqrt[3]{8}"))          # ∛8̅
    print(helper.convert("\\sqrt[4]{16}"))         # ∜1̅6̅

    # 数学算子
    print(helper.convert(r"\sin^2\theta + \cos^2\theta = 1"))
    print(helper.convert(r"\lim_{x \to 0} \frac{\sin x}{x} = 1"))

    # 环境
    print(helper.convert(r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}"))
    print(helper.convert(r"\begin{cases} x & x > 0 \\ -x & x \leq 0 \end{cases}"))

    # 复杂公式
    print(helper.convert(r"e^{i\pi} + 1 = 0"))
    print(helper.convert(r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon}"))
