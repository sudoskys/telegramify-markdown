import re
from logging import getLogger
from telegramify_markdown.latex_escape.const import (
    COMBINING, CombiningType, NOT_MAP, SUBSCRIPTS, SUPERSCRIPTS, LATEX_STYLES, FRAC_MAP, LATEX_SYMBOLS
)

logger = getLogger(__name__)

class LatexToUnicodeHelper:
    @staticmethod
    def is_combining_char(char):
        """Whether a character is a combining character."""
        return (
                '\u0300' <= char <= '\u036F' or
                '\u1AB0' <= char <= '\u1AFF' or
                '\u1DC0' <= char <= '\u1DFF' or
                '\u20D0' <= char <= '\u20FF' or
                '\uFE20' <= char <= '\uFE2F'
        )

    @staticmethod
    def translate_combining(command, text):
        # 翻译组合命令，将组合字符应用于文本
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
        # 生成带否定符号的字符
        trimmed = negated.strip()
        if not trimmed:
            return " "
        return NOT_MAP.get(trimmed, f"{trimmed[0]}\u0338{trimmed[1:]}")

    @staticmethod
    def try_make_subscript(text):
        # 尝试将文本转换为下标
        if not text:
            return ""
        if all(ch in SUBSCRIPTS for ch in text):
            return ''.join(SUBSCRIPTS[ch] for ch in text)
        return None

    @staticmethod
    def make_subscript(text):
        # 生成下标
        text = text.strip()
        if not text:
            return ""
        if len(text) == 1 and text.isdecimal():
            return SUBSCRIPTS.get(text, f"_{text}")
        subscript = LatexToUnicodeHelper.try_make_subscript(text)
        return subscript if subscript is not None else f"_({text})"

    @staticmethod
    def try_make_superscript(text):
        # 尝试将文本转换为上标
        if not text:
            return ""
        if all(ch in SUPERSCRIPTS for ch in text):
            return ''.join(SUPERSCRIPTS[ch] for ch in text)
        return None

    @staticmethod
    def make_superscript(text):
        # 生成上标
        text = text.strip()
        if not text:
            return ""
        if len(text) == 1 and text.isdecimal():
            return SUPERSCRIPTS.get(text, f"^{text}")
        superscript = LatexToUnicodeHelper.try_make_superscript(text)
        return superscript if superscript is not None else f"^({text})"

    @staticmethod
    def translate_styles(command, text):
        # 翻译样式命令，例如粗体或斜体
        style_map = LATEX_STYLES.get(command)
        if not style_map:
            raise ValueError(f"Unknown style command: {command}")
        return ''.join(style_map.get(char, char) for char in text)

    @staticmethod
    def make_sqrt(index, radicand):
        # 生成平方根字符串
        radix = {"": "√", "2": "√", "3": "∛", "4": "∜"}.get(
            index, LatexToUnicodeHelper.try_make_superscript(index) or f"({index})" + "√"
        )
        return radix + LatexToUnicodeHelper.translate_combining("\\overline", radicand)

    @staticmethod
    def translate_sqrt(command, option, param):
        # 翻译 \sqrt 命令
        if command != "\\sqrt":
            raise ValueError(f"Unknown command: {command}")
        return LatexToUnicodeHelper.make_sqrt(option.strip(), param.strip())

    @staticmethod
    def maybe_parenthesize(text):
        def should_parenthesize_string_with_char(char):
            # 判断字符是否需要整体加括号
            return not (
                    char.isalnum() or
                    LatexToUnicodeHelper.is_combining_char(char) or
                    char.isdecimal() or
                    char == '_'
            )

        # 根据文本内容选择性地添加括号
        if any(should_parenthesize_string_with_char(c) for c in text):
            return f"({text})"
        return text

    @staticmethod
    def make_fraction(numerator, denominator):
        # 生成分数的 Unicode 表示
        n, d = numerator.strip(), denominator.strip()
        if not n and not d:
            return ""
        fraction_unicode = FRAC_MAP.get((n, d))
        if fraction_unicode:
            return fraction_unicode
        # 移除多余命令
        # n = n.replace("\\left", "").replace("\\right", "")
        # d = d.replace("\\left", "").replace("\\right", "")
        return f"{LatexToUnicodeHelper.maybe_parenthesize(n)}/{LatexToUnicodeHelper.maybe_parenthesize(d)}"

    @staticmethod
    def translate_frac(command, numerator, denominator):
        # 翻译 \frac 命令
        if command != "\\frac":
            raise ValueError(f"Unknown command: {command}")
        return LatexToUnicodeHelper.make_fraction(numerator, denominator)

    @staticmethod
    def translate_escape(name):
        return LATEX_SYMBOLS.get(name, name)

    def parse(self, latex):
        # Parse and convert LaTeX string to Unicode
        result, i = [], 0
        while i < len(latex):
            if latex[i] == '\\':
                command, i = self.parse_command(latex, i)
                # Check if it is a mixed fraction format (a number followed directly by \frac)
                if command == "\\frac" and result and result[-1] and result[-1][-1].isdigit():
                    # Add a space between the number and the fraction
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
                else:
                    arg, i = latex[i], i + 1
                result.append(self.make_subscript(arg) if sym == '_' else self.make_superscript(arg))
            elif latex[i].isspace():
                spaces, i = self.parse_spaces(latex, i)
                result.append(spaces)
            else:
                result.append(latex[i])
                i += 1
        return ''.join(result)

    def handle_command(self, command, latex, index):
        # 处理不同的 LaTeX 命令
        if command in LATEX_SYMBOLS:
            return self.translate_escape(command), index
        elif command in NOT_MAP:
            return self.make_not(latex[index:index + 1]), index + 1
        elif command in COMBINING:
            arg, index = self.parse_block(latex, index)
            return self.translate_combining(command, arg), index
        elif command == "\\frac":
            numer, index = self.parse_block(latex, index)
            denom, index = self.parse_block(latex, index)
            return self.make_fraction(numer, denom), index
        elif command == "\\sqrt":
            option, index = self.parse_block(latex, index)
            param, index = self.parse_block(latex, index)
            return self.translate_sqrt(command, option, param), index
        elif command in LATEX_STYLES:
            text, index = self.parse_block(latex, index)
            return self.translate_styles(command, text), index
        elif command == "\\text":
            text, index = self.parse_block(latex, index)
            return text, index
        elif command == "\\right":
            text, index = self.parse_block(latex, index)
            return text, index
        elif command == "\\left":
            text, index = self.parse_block(latex, index)
            return text, index
        return command, index

    @staticmethod
    def parse_command(latex, start):
        # 解析命令
        match = re.match(r'\\([a-zA-Z]+|.)', latex[start:])
        if match:
            return match.group(0), start + match.end()
        return '\\', start + 1

    def parse_block(self, latex, start):
        # 解析块内容
        level, pos = 1, start + 1
        while pos < len(latex) and level > 0:
            if latex[pos] == '{':
                level += 1
            elif latex[pos] == '}':
                level -= 1
            pos += 1
        return self.parse(latex[start + 1:pos - 1]), pos

    @staticmethod
    def parse_spaces(latex, start):
        # 解析连续空格
        end = start
        while end < len(latex) and latex[end].isspace():
            end += 1
        return ('\n\n' if '\n' in latex[start:end] else ' '), end

    def convert(self, latex):
        # 将 LaTeX 转换为 Unicode
        try:
            return self.parse(latex)
        except Exception as e:
            logger.error(f"Failed to convert LaTeX to Unicode: {e}")
            return latex


# 示例使用
if __name__ == "__main__":
    import textwrap

    helper = LatexToUnicodeHelper()
    print(helper.convert("\\frac{1}{2}"))  # 输出例如：½
    print(helper.convert("\\sqrt{3}{8}"))  # 输出例如：∛8
    print(helper.convert("\\sqrt{2}{3}"))  # 输出例如：√3
    print(helper.convert("\\sqrt{4}{5}"))  # 输出例如：∜5
    print(helper.convert("\\sqrt{1}{2}"))  # 输出例如：√2
    print(helper.convert(r"a = \frac{27.8}{3.85} \approx 7.22"))  # 输出例如：√2
    print(helper.convert(textwrap.dedent(r"""
二次公式（求解二次方程 \(ax^2 + bx + c = 0\)）：
   \[
   x = \frac{{-b \pm \sqrt{{b^2 - 4ac}}}}{2a}
   \]

自然对数的底 \(e\)（欧拉公式：
   \[
   e^{i\pi} + 1 = 0
   \]

电场强度：
   \[
   E = \frac{F}{q}
   \]

反应速率方程：
   \[
   \text{Rate} = k[A]^m[B]^n
   \]

需求价格弹性：
   \[
   E_d = \frac{{\%\Delta Q_d}}{{\%\Delta P}}
   \]
### 总预期时间：
\[
\text{总预期时间} = \text{正常飞行时间} + \text{故障增加的时间} = 20 \text{ 年} + 2 \text{ 年} = 22 \text{ 年}
\]
勾股定理：(a^2 + b^2 = c^2)
一元二次方程求解公式：(x = \frac{{-b \pm \sqrt{{b^2 - 4ac}}}}{2a})
圆的面积：(A = \pi r^2)
自然对数的底 (e) 的著名等式：(e^{i\pi} + 1 = 0)

A = X × \left( (P)/100 \right) × (V)/365

\text{R} = \frac{\text{EXAMPLE}}{\text{Any}}
        """)))
