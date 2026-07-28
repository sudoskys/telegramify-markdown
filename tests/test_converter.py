import unittest

from telegramify_markdown.converter import convert, convert_with_segments
from telegramify_markdown.entity import MessageEntity, utf16_len


def _find_entity(entities: list[MessageEntity], etype: str) -> MessageEntity | None:
    for e in entities:
        if e.type == etype:
            return e
    return None


def _find_entities(entities: list[MessageEntity], etype: str) -> list[MessageEntity]:
    return [e for e in entities if e.type == etype]


def _extract_entity_text(text: str, entity: MessageEntity) -> str:
    """Extract the substring covered by an entity from plain text."""
    # Convert UTF-16 offset/length to Python string indices
    utf16_offset = 0
    py_start = None
    py_end = None
    for i, ch in enumerate(text):
        if utf16_offset == entity.offset and py_start is None:
            py_start = i
        if utf16_offset == entity.offset + entity.length and py_end is None:
            py_end = i
            break
        utf16_offset += 2 if ord(ch) > 0xFFFF else 1
    if py_start is not None and py_end is None:
        py_end = len(text)
    if py_start is None:
        return ""
    return text[py_start:py_end]


class BoldTest(unittest.TestCase):
    def test_simple_bold(self):
        text, entities = convert("**hello**", latex_escape=False)
        self.assertIn("hello", text)
        bold = _find_entity(entities, "bold")
        self.assertIsNotNone(bold)
        self.assertEqual(_extract_entity_text(text, bold), "hello")

    def test_bold_in_sentence(self):
        text, entities = convert("foo **bar** baz", latex_escape=False)
        bold = _find_entity(entities, "bold")
        self.assertIsNotNone(bold)
        self.assertEqual(_extract_entity_text(text, bold), "bar")


class ItalicTest(unittest.TestCase):
    def test_simple_italic(self):
        text, entities = convert("*hello*", latex_escape=False)
        italic = _find_entity(entities, "italic")
        self.assertIsNotNone(italic)
        self.assertEqual(_extract_entity_text(text, italic), "hello")


class StrikethroughTest(unittest.TestCase):
    def test_simple_strikethrough(self):
        text, entities = convert("~~hello~~", latex_escape=False)
        s = _find_entity(entities, "strikethrough")
        self.assertIsNotNone(s)
        self.assertEqual(_extract_entity_text(text, s), "hello")


class NestedFormattingTest(unittest.TestCase):
    def test_bold_italic(self):
        text, entities = convert("**bold *italic* bold**", latex_escape=False)
        bold = _find_entity(entities, "bold")
        italic = _find_entity(entities, "italic")
        self.assertIsNotNone(bold)
        self.assertIsNotNone(italic)
        # Italic should be contained within bold
        self.assertGreaterEqual(italic.offset, bold.offset)
        self.assertLessEqual(italic.offset + italic.length, bold.offset + bold.length)
        self.assertEqual(_extract_entity_text(text, italic), "italic")


class InlineCodeTest(unittest.TestCase):
    def test_inline_code(self):
        text, entities = convert("use `print()` here", latex_escape=False)
        code = _find_entity(entities, "code")
        self.assertIsNotNone(code)
        self.assertEqual(_extract_entity_text(text, code), "print()")


class CodeBlockTest(unittest.TestCase):
    def test_fenced_code_block(self):
        md = "```python\nprint('hello')\n```"
        text, entities = convert(md, latex_escape=False)
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(pre)
        self.assertEqual(pre.language, "python")
        self.assertIn("print('hello')", _extract_entity_text(text, pre))

    def test_code_block_segment(self):
        md = "```python\ncode\n```"
        _, _, segments = convert_with_segments(md, latex_escape=False)
        self.assertTrue(any(s.kind == "code_block" for s in segments))

    def test_mermaid_segment(self):
        md = "```mermaid\ngraph TD\nA-->B\n```"
        _, _, segments = convert_with_segments(md, latex_escape=False)
        self.assertTrue(any(s.kind == "mermaid" for s in segments))

    def test_code_block_no_language(self):
        md = "```\nsome code\n```"
        text, entities = convert(md, latex_escape=False)
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(pre)
        self.assertIsNone(pre.language)


class HeadingTest(unittest.TestCase):
    def test_h1(self):
        text, entities = convert("# Title", latex_escape=False)
        self.assertIn("📌", text)
        self.assertIsNotNone(_find_entity(entities, "bold"))
        self.assertIsNotNone(_find_entity(entities, "underline"))

    def test_h2(self):
        text, entities = convert("## Subtitle", latex_escape=False)
        self.assertIn("✏", text)
        self.assertIsNotNone(_find_entity(entities, "bold"))
        self.assertIsNotNone(_find_entity(entities, "underline"))

    def test_h3(self):
        text, entities = convert("### Section", latex_escape=False)
        self.assertIn("📚", text)
        self.assertIsNotNone(_find_entity(entities, "bold"))
        self.assertIsNone(_find_entity(entities, "underline"))

    def test_h4(self):
        text, entities = convert("#### Sub", latex_escape=False)
        self.assertIn("🔖", text)
        self.assertIsNotNone(_find_entity(entities, "bold"))

    def test_h5_italic_no_emoji(self):
        text, entities = convert("##### H5", latex_escape=False)
        self.assertTrue(text.startswith("H5"))
        self.assertIsNotNone(_find_entity(entities, "italic"))

    def test_h6_italic_no_emoji(self):
        text, entities = convert("###### H6", latex_escape=False)
        self.assertTrue(text.startswith("H6"))
        self.assertIsNotNone(_find_entity(entities, "italic"))


class LinkTest(unittest.TestCase):
    def test_inline_link(self):
        text, entities = convert("[Google](https://google.com)", latex_escape=False)
        link = _find_entity(entities, "text_link")
        self.assertIsNotNone(link)
        self.assertEqual(link.url, "https://google.com")
        self.assertEqual(_extract_entity_text(text, link), "Google")

    def test_autolink(self):
        text, entities = convert("visit https://example.com today", latex_escape=False)
        self.assertIn("https://example.com", text)


class ImageTest(unittest.TestCase):
    def test_image(self):
        text, entities = convert("![alt](https://example.com/img.png)", latex_escape=False)
        link = _find_entity(entities, "text_link")
        self.assertIsNotNone(link)
        self.assertEqual(link.url, "https://example.com/img.png")

    def test_telegram_emoji(self):
        text, entities = convert("![emoji](tg://emoji?id=5368324170671202286)", latex_escape=False)
        emoji = _find_entity(entities, "custom_emoji")
        self.assertIsNotNone(emoji)
        self.assertEqual(emoji.custom_emoji_id, "5368324170671202286")


class BlockquoteTest(unittest.TestCase):
    def test_simple_blockquote(self):
        text, entities = convert("> quoted text", latex_escape=False)
        bq = _find_entity(entities, "blockquote")
        self.assertIsNotNone(bq)
        self.assertIn("quoted text", _extract_entity_text(text, bq))

    def test_expandable_blockquote(self):
        long_text = "> " + "a" * 250
        text, entities = convert(long_text, latex_escape=False)
        bq = _find_entity(entities, "expandable_blockquote")
        self.assertIsNotNone(bq)

    def test_blockquote_before_code_block_without_blank_line(self):
        md = ">Text example 1\n```py\nSecond line example\nThird line example\n```"
        text, entities = convert(md, latex_escape=False)
        self.assertEqual(text, "Text example 1\nSecond line example\nThird line example")
        bq = _find_entity(entities, "blockquote")
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(bq)
        self.assertIsNotNone(pre)
        self.assertEqual(bq.length, 14)
        self.assertEqual(pre.offset, 15)

    def test_blockquote_before_code_block_with_blank_line(self):
        md = ">Text example 1\n\n```py\nSecond line example\nThird line example\n```"
        text, entities = convert(md, latex_escape=False)
        self.assertEqual(text, "Text example 1\n\nSecond line example\nThird line example")
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(pre)
        self.assertEqual(pre.offset, 16)


class TableTest(unittest.TestCase):
    def test_simple_table(self):
        md = "| a | b |\n| --- | --- |\n| 1 | 2 |"
        text, entities = convert(md, latex_escape=False)
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(pre)
        table_text = _extract_entity_text(text, pre)
        self.assertIn("a", table_text)
        self.assertIn("b", table_text)
        self.assertIn("1", table_text)
        self.assertIn("2", table_text)


class ListTest(unittest.TestCase):
    def test_unordered_list(self):
        md = "- item1\n- item2"
        text, entities = convert(md, latex_escape=False)
        self.assertIn("⦁ item1", text)
        self.assertIn("⦁ item2", text)

    def test_ordered_list(self):
        md = "1. first\n2. second"
        text, entities = convert(md, latex_escape=False)
        self.assertIn("1. first", text)
        self.assertIn("2. second", text)

    def test_task_list(self):
        md = "- [x] done\n- [ ] todo"
        text, entities = convert(md, latex_escape=False)
        self.assertIn("✅", text)
        self.assertIn("☑", text)


class SpoilerTest(unittest.TestCase):
    def test_spoiler(self):
        text, entities = convert("this is ||secret|| text", latex_escape=False)
        spoiler = _find_entity(entities, "spoiler")
        self.assertIsNotNone(spoiler)
        self.assertEqual(_extract_entity_text(text, spoiler), "secret")

    def test_spoiler_not_in_code(self):
        text, entities = convert("`||not spoiler||`", latex_escape=False)
        spoiler = _find_entity(entities, "spoiler")
        self.assertIsNone(spoiler)


class RuleTest(unittest.TestCase):
    def test_horizontal_rule(self):
        text, entities = convert("above\n\n---\n\nbelow", latex_escape=False)
        self.assertIn("————————", text)


class ParagraphSpacingTest(unittest.TestCase):
    def test_paragraphs_separated(self):
        text, entities = convert("para1\n\npara2", latex_escape=False)
        self.assertIn("para1\n\npara2", text)

    def test_heading_then_paragraph(self):
        text, entities = convert("# Title\n\nContent", latex_escape=False)
        self.assertIn("Title", text)
        self.assertIn("Content", text)


class Utf16OffsetTest(unittest.TestCase):
    def test_emoji_offset(self):
        # 📌 is 2 UTF-16 code units
        text, entities = convert("📌 **bold**", latex_escape=False)
        bold = _find_entity(entities, "bold")
        self.assertIsNotNone(bold)
        # "📌 " = 2 + 1 = 3 UTF-16 code units
        self.assertEqual(bold.offset, 3)
        self.assertEqual(bold.length, 4)

    def test_cjk_offset(self):
        text, entities = convert("你好 **世界**", latex_escape=False)
        bold = _find_entity(entities, "bold")
        self.assertIsNotNone(bold)
        # "你好 " = 2 + 1 = 3 UTF-16 code units (CJK is BMP, 1 each)
        self.assertEqual(bold.offset, 3)
        self.assertEqual(bold.length, 2)


class MathTest(unittest.TestCase):
    def test_inline_math(self):
        text, entities = convert("$x + y$", latex_escape=False)
        code = _find_entity(entities, "code")
        self.assertIsNotNone(code)
        self.assertIn("x + y", _extract_entity_text(text, code))

    def test_display_math(self):
        text, entities = convert("$$x + y$$", latex_escape=False)
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(pre)


class LatexHelperTest(unittest.TestCase):
    """Tests for the LaTeX-to-Unicode helper (latex_escape/helper.py)."""

    def setUp(self):
        from telegramify_markdown.latex_escape.helper import LatexToUnicodeHelper
        self.helper = LatexToUnicodeHelper()

    def test_superscript_latex_command(self):
        """Regression test for #87: \\lambda^\\phi should produce λᵠ."""
        result = self.helper.convert(r"\lambda^\phi")
        self.assertIn("λ", result)
        self.assertIn("ᵠ", result)
        self.assertNotIn("\\phi", result)

    def test_subscript_latex_command(self):
        result = self.helper.convert(r"a_\beta")
        self.assertIn("a", result)
        self.assertIn("ᵦ", result)
        self.assertNotIn("\\beta", result)

    def test_superscript_with_braces(self):
        result = self.helper.convert(r"x^{2}")
        self.assertEqual(result, "x²")

    def test_superscript_frac_after_command(self):
        result = self.helper.convert(r"x^\frac{1}{2}")
        self.assertIn("½", result)

    def test_basic_symbols(self):
        result = self.helper.convert(r"\Delta y")
        self.assertIn("Δ", result)

    def test_fraction(self):
        result = self.helper.convert(r"\frac{1}{2}")
        self.assertEqual(result, "½")

    # ── \sqrt 修复 ──

    def test_sqrt_single_arg(self):
        result = self.helper.convert(r"\sqrt{x}")
        self.assertIn("√", result)
        self.assertIn("x", result)

    def test_sqrt_with_optional_index(self):
        result = self.helper.convert(r"\sqrt[3]{x}")
        self.assertIn("∛", result)

    def test_sqrt_preserves_following(self):
        """\\sqrt{x} + y 不应吞掉后续内容。"""
        result = self.helper.convert(r"\sqrt{x} + y")
        self.assertIn("+", result)
        self.assertIn("y", result)

    def test_sqrt_fourth_root(self):
        result = self.helper.convert(r"\sqrt[4]{16}")
        self.assertIn("∜", result)

    # ── \left / \right 修复 ──

    def test_left_right_parens(self):
        result = self.helper.convert(r"\left(x + y\right)")
        self.assertIn("(", result)
        self.assertIn(")", result)
        self.assertIn("x", result)

    def test_left_right_braces(self):
        result = self.helper.convert(r"\left\{x\right\}")
        self.assertIn("{", result)
        self.assertIn("}", result)

    def test_left_right_invisible(self):
        result = self.helper.convert(r"\left.x\right|")
        self.assertIn("x", result)
        self.assertIn("|", result)

    # ── \not 修复 ──

    def test_not_equals(self):
        result = self.helper.convert(r"\not=")
        self.assertEqual(result, "≠")

    def test_not_in(self):
        result = self.helper.convert(r"\not\in")
        self.assertEqual(result, "∉")

    def test_not_subset(self):
        result = self.helper.convert(r"\not\subset")
        self.assertEqual(result, "⊄")

    # ── 双反斜杠换行 ──

    def test_double_backslash(self):
        result = self.helper.convert("a \\\\ b")
        self.assertIn("\n", result)

    # ── 数学算子 ──

    def test_trig_functions(self):
        result = self.helper.convert(r"\sin^2\theta + \cos^2\theta = 1")
        self.assertIn("sin", result)
        self.assertIn("cos", result)
        self.assertIn("θ", result)

    def test_log_ln(self):
        result = self.helper.convert(r"\log_2 n = \frac{\ln n}{\ln 2}")
        self.assertIn("log", result)
        self.assertIn("ln", result)

    def test_lim(self):
        result = self.helper.convert(r"\lim_{x \to 0} \frac{\sin x}{x} = 1")
        self.assertIn("lim", result)
        self.assertIn("sin", result)

    def test_layout_hints_silent(self):
        result = self.helper.convert(r"\displaystyle\sum\limits_{i=1}^{n} i")
        self.assertIn("∑", result)
        self.assertNotIn("displaystyle", result)
        self.assertNotIn("limits", result)

    # ── 新命令 ──

    def test_binom(self):
        result = self.helper.convert(r"\binom{n}{k}")
        self.assertIn("n", result)
        self.assertIn("k", result)

    def test_operatorname(self):
        result = self.helper.convert(r"\operatorname{argmax}_{x}")
        self.assertIn("argmax", result)

    def test_mathrm(self):
        result = self.helper.convert(r"\mathrm{d}x")
        self.assertIn("d", result)
        self.assertIn("x", result)

    def test_boxed(self):
        result = self.helper.convert(r"\boxed{E = mc^2}")
        self.assertIn("[", result)
        self.assertIn("]", result)

    def test_pmod(self):
        result = self.helper.convert(r"a \equiv b \pmod{p}")
        self.assertIn("mod", result)
        self.assertIn("p", result)

    def test_overset(self):
        result = self.helper.convert(r"\overset{*}{=}")
        self.assertIn("=", result)

    def test_underset(self):
        result = self.helper.convert(r"\underset{n \to \infty}{=}")
        self.assertIn("=", result)

    # ── 环境 ──

    def test_pmatrix(self):
        result = self.helper.convert(
            r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}")
        self.assertIn("(", result)
        self.assertIn("a", result)
        self.assertIn("d", result)
        self.assertIn(")", result)

    def test_bmatrix(self):
        result = self.helper.convert(
            r"\begin{bmatrix} 1 & 0 \\ 0 & 1 \end{bmatrix}")
        self.assertIn("[", result)
        self.assertIn("]", result)

    def test_cases(self):
        result = self.helper.convert(
            r"|x| = \begin{cases} x & x \geq 0 \\ -x & x < 0 \end{cases}")
        self.assertIn("\u23A7", result)  # Unicode 大括号上部
        self.assertIn("≥", result)

    def test_align_env(self):
        result = self.helper.convert(
            r"\begin{align} a &= b + c \\ d &= e + f \end{align}")
        self.assertIn("a", result)
        self.assertIn("=", result)

    # ── 综合公式压力测试（真实世界复杂公式） ──

    def test_euler_identity(self):
        """欧拉恒等式"""
        result = self.helper.convert(r"e^{i\pi} + 1 = 0")
        self.assertIn("π", result)

    def test_quadratic_formula(self):
        """二次公式"""
        result = self.helper.convert(
            r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}")
        self.assertIn("√", result)
        self.assertIn("±", result)

    def test_taylor_series(self):
        """泰勒级数"""
        result = self.helper.convert(
            r"e^x = \sum_{n=0}^{\infty} \frac{x^n}{n!}")
        self.assertIn("∑", result)
        self.assertIn("∞", result)

    def test_integral(self):
        """积分"""
        result = self.helper.convert(
            r"\int_{-\infty}^{\infty} e^{-x^2} \mathrm{d}x = \sqrt{\pi}")
        self.assertIn("∫", result)
        self.assertIn("∞", result)
        self.assertIn("π", result)

    def test_gaussian(self):
        """高斯分布"""
        result = self.helper.convert(
            r"f(x) = \frac{1}{\sigma\sqrt{2\pi}} "
            r"e^{-\frac{1}{2}\left(\frac{x-\mu}{\sigma}\right)^2}")
        self.assertIn("σ", result)
        self.assertIn("μ", result)
        self.assertIn("π", result)

    def test_maxwell_equations(self):
        """麦克斯韦方程（简化形式）"""
        result = self.helper.convert(
            r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon}")
        self.assertIn("∇", result)
        self.assertIn("⋅", result)
        self.assertIn("ρ", result)
        self.assertIn("ε", result)

    def test_schrodinger(self):
        """薛定谔方程"""
        result = self.helper.convert(
            r"i\hbar\frac{\partial}{\partial t}\Psi = \hat{H}\Psi")
        self.assertIn("ℏ", result)
        self.assertIn("∂", result)
        self.assertIn("Ψ", result)

    def test_binomial_theorem(self):
        """二项式定理"""
        result = self.helper.convert(
            r"(x+y)^n = \sum_{k=0}^{n} \binom{n}{k} x^k y^{n-k}")
        self.assertIn("∑", result)
        self.assertIn("n", result)
        self.assertIn("k", result)

    def test_matrix_determinant(self):
        """矩阵行列式"""
        result = self.helper.convert(
            r"\det\begin{pmatrix} a & b \\ c & d \end{pmatrix} = ad - bc")
        self.assertIn("det", result)
        self.assertIn("(", result)

    def test_piecewise_function(self):
        """分段函数"""
        result = self.helper.convert(
            r"f(x) = \begin{cases} "
            r"\frac{1}{x} & x \neq 0 \\ "
            r"0 & x = 0 "
            r"\end{cases}")
        self.assertIn("\u23A7", result)  # Unicode 大括号上部
        self.assertIn("≠", result)

    def test_limit_definition(self):
        """极限的 epsilon-delta 定义"""
        result = self.helper.convert(
            r"\forall \varepsilon > 0, \exists \delta > 0 : "
            r"|x - a| < \delta \Rightarrow |f(x) - L| < \varepsilon")
        self.assertIn("∀", result)
        self.assertIn("∃", result)
        self.assertIn("⇒", result)
        self.assertIn("ε", result)
        self.assertIn("δ", result)

    def test_stirling_approximation(self):
        """斯特林近似"""
        result = self.helper.convert(
            r"n! \sim \sqrt{2\pi n} \left(\frac{n}{e}\right)^n")
        self.assertIn("√", result)
        self.assertIn("π", result)
        self.assertIn("∼", result)

    def test_fourier_transform(self):
        """傅里叶变换"""
        result = self.helper.convert(
            r"\hat{f}(\xi) = \int_{-\infty}^{\infty} "
            r"f(x) e^{-2\pi i x \xi} \mathrm{d}x")
        self.assertIn("∫", result)
        self.assertIn("∞", result)
        self.assertIn("ξ", result)
        self.assertIn("π", result)

    def test_bayes_theorem(self):
        """贝叶斯定理"""
        result = self.helper.convert(
            r"P(A|B) = \frac{P(B|A) \cdot P(A)}{P(B)}")
        self.assertIn("P", result)
        self.assertIn("⋅", result)

    def test_entropy(self):
        """香农熵"""
        result = self.helper.convert(
            r"H(X) = -\sum_{i=1}^{n} p_i \log_2 p_i")
        self.assertIn("log", result)
        self.assertIn("∑", result)

    def test_residue_theorem(self):
        """留数定理"""
        result = self.helper.convert(
            r"\oint_C f(z) \mathrm{d}z = 2\pi i \sum \operatorname{Res}(f, a_k)")
        self.assertIn("∮", result)
        self.assertIn("Res", result)
        self.assertIn("π", result)

    def test_dirac_notation(self):
        """狄拉克符号"""
        result = self.helper.convert(
            r"\langle \psi | \hat{A} | \phi \rangle")
        self.assertIn("ψ", result)
        self.assertIn("φ", result)
        # \langle → U+2329, \rangle → U+232A
        self.assertIn("\u2329", result)
        self.assertIn("\u232A", result)

    def test_christoffel_symbols(self):
        """克里斯托费尔符号（复杂上下标）"""
        result = self.helper.convert(
            r"\Gamma^{\mu}_{\nu\rho} = \frac{1}{2} g^{\mu\sigma}")
        self.assertIn("Γ", result)
        self.assertIn("½", result)

    def test_product_notation(self):
        """连乘"""
        result = self.helper.convert(
            r"\prod_{p \text{ prime}} \frac{1}{1 - p^{-s}}")
        self.assertIn("∏", result)

    def test_nested_fractions(self):
        """嵌套分数（连分数）"""
        result = self.helper.convert(
            r"1 + \frac{1}{1 + \frac{1}{1 + \frac{1}{x}}}")
        self.assertIn("1", result)
        self.assertNotIn("\\frac", result)

    def test_complex_subscripts(self):
        """复杂下标"""
        result = self.helper.convert(r"a_{i,j}^{(n)}")
        self.assertIn("a", result)
        self.assertNotIn("\\", result)

    def test_tensor_notation(self):
        """张量记法"""
        result = self.helper.convert(
            r"T^{\mu\nu} = F^{\mu\alpha} F_{\alpha}^{\ \nu}")
        self.assertIn("T", result)
        self.assertIn("F", result)
        self.assertNotIn("\\", result)


class LatexConverterTest(unittest.TestCase):
    """Tests for LaTeX processing through the full convert() pipeline."""

    def test_inline_latex_escape(self):
        text, entities = convert(r"\(\lambda^\phi\)", latex_escape=True)
        self.assertIn("λ", text)
        self.assertIn("ᵠ", text)

    def test_display_latex_escape(self):
        text, entities = convert(r"\[\frac{1}{2}\]", latex_escape=True)
        self.assertIn("½", text)


class ComplexDocumentTest(unittest.TestCase):
    def test_mixed_content(self):
        md = """# Hello World

This is **bold** and *italic* text.

- item 1
- item 2

> A quote

```python
print("hello")
```
"""
        text, entities = convert(md, latex_escape=False)
        # Should have heading (bold), bold, italic, blockquote, pre
        types = {e.type for e in entities}
        self.assertIn("bold", types)
        self.assertIn("italic", types)
        self.assertIn("blockquote", types)
        self.assertIn("pre", types)
        # Text should contain all content
        self.assertIn("Hello World", text)
        self.assertIn("item 1", text)
        self.assertIn("A quote", text)
        self.assertIn('print("hello")', text)


class NestedListFormattingTest(unittest.TestCase):
    def test_nested_items_on_separate_lines(self):
        text, _ = convert("- parent\n    - child", latex_escape=False)
        self.assertIn("parent\n", text)  # parent 以换行结尾
        self.assertNotIn("parent  ⦁", text)  # 不在同一行

    def test_deeply_nested_items(self):
        text, _ = convert("- a\n    - b\n        - c", latex_escape=False)
        lines = text.strip().split("\n")
        self.assertEqual(len(lines), 3)  # 每项独占一行

    def test_ordered_with_nested_unordered(self):
        text, _ = convert("1. step\n    - detail", latex_escape=False)
        self.assertIn("step\n", text)


class LooseListParagraphTest(unittest.TestCase):
    def test_multi_paragraph_item(self):
        text, _ = convert("- para1\n\n  para2", latex_escape=False)
        self.assertIn("para1\n", text)
        self.assertIn("para2", text)
        self.assertNotIn("para1para2", text)  # 不粘连


class TaskListMarkerTest(unittest.TestCase):
    def test_no_redundant_bullet(self):
        text, _ = convert("- [ ] todo", latex_escape=False)
        self.assertNotIn("⦁", text)  # 无 bullet
        self.assertIn("☑", text)     # task marker 存在

    def test_completed_task(self):
        text, _ = convert("- [x] done", latex_escape=False)
        self.assertNotIn("⦁", text)
        self.assertIn("✅", text)


class BlockSpacingAfterListTest(unittest.TestCase):
    """A block after a list must keep the blank line the source had.

    pyromark's End(List) range already includes the trailing blank line, so the
    old "gap between previous block end and next block start" test always
    concluded there was no blank line after a list.
    """

    def test_paragraph_after_list_keeps_blank_line(self):
        text, _ = convert("- a\n- b\n\npara", latex_escape=False)
        self.assertIn("\n\npara", text)

    def test_ordered_list_then_heading_keeps_blank_line(self):
        text, _ = convert("1. a\n2. b\n\n# h", latex_escape=False)
        self.assertIn("\n\n", text.split("b")[1])

    def test_all_block_kinds_after_list_keep_blank_line(self):
        followers = ["para", "# h", "```py\nx=1\n```", "> q", "---", "$$e^x$$"]
        for follower in followers:
            with self.subTest(follower=follower):
                text, _ = convert(f"- a\n- b\n\n{follower}", latex_escape=False)
                self.assertIn("\n\n", text)

    def test_tight_list_then_block_has_no_blank_line(self):
        # No blank line in the source means none invented (a heading may
        # interrupt a list)
        text, _ = convert("- a\n- b\n# h", latex_escape=False)
        self.assertNotIn("\n\n", text)

    def test_all_line_endings_are_recognised(self):
        # CommonMark accepts bare CR as a line ending; counting only LF loses
        # the blank line on CR-terminated input.
        for name, source, blank_expected in (
            ("lf", "a\n\n# h", True),
            ("lf-tight", "a\n# h", False),
            ("cr", "a\r\r# h", True),
            ("cr-tight", "a\r# h", False),
            ("crlf", "a\r\n\r\n# h", True),
            ("crlf-tight", "a\r\n# h", False),
            ("cr-in-blockquote", "> a\r>\r> # h", True),
        ):
            with self.subTest(name=name):
                text, _ = convert(source, latex_escape=False)
                self.assertEqual("\n\n" in text, blank_expected, repr(text))


class SpoilerCodeRegionTest(unittest.TestCase):
    """Spoiler preprocessing must not rewrite code block content."""

    def test_tilde_fence_not_rewritten(self):
        text, entities = convert("~~~py\n||x||\n~~~", latex_escape=False)
        self.assertEqual(text, "||x||")
        self.assertIsNone(_find_entity(entities, "spoiler"))

    def test_indented_code_not_rewritten(self):
        text, entities = convert("para\n\n    ||x||\n\ntail", latex_escape=False)
        self.assertIn("||x||", text)
        self.assertIsNone(_find_entity(entities, "spoiler"))

    def test_tilde_inside_backtick_fence_does_not_close_it(self):
        text, _ = convert("```\n~~~\n||a||\n```", latex_escape=False)
        self.assertIn("||a||", text)

    def test_shorter_fence_does_not_close_longer_one(self):
        text, _ = convert("````\n||a||\n```\n||b||\n````", latex_escape=False)
        self.assertIn("||a||", text)
        self.assertIn("||b||", text)

    def test_unterminated_fence_runs_to_end(self):
        text, entities = convert("```\n||a||", latex_escape=False)
        self.assertIn("||a||", text)
        self.assertIsNone(_find_entity(entities, "spoiler"))

    def test_single_line_triple_backtick_does_not_open_a_fence(self):
        # A backtick fence's info string may not contain a backtick, so
        # ```x``` on one line is a code span, not the start of a block.
        # Reading it as a fence swallowed everything up to the next fence and
        # silently disabled spoilers in between.
        md = '```print("x")```\n\n||secret||\n\n```py\ncode\n```\n'
        text, entities = convert(md, latex_escape=False)
        spoiler = _find_entity(entities, "spoiler")
        self.assertIsNotNone(spoiler)
        self.assertEqual(_extract_entity_text(text, spoiler), "secret")

    def test_info_string_without_backtick_still_opens_a_fence(self):
        text, entities = convert("```python title\n||x||\n```", latex_escape=False)
        self.assertIn("||x||", text)
        self.assertIsNone(_find_entity(entities, "spoiler"))

    def test_fence_inside_blockquote_is_code(self):
        # A fence can sit behind a container prefix. Missing that rewrites the
        # quoted code instead of leaving it alone.
        text, entities = convert("> ```\n> a || b || c\n> ```", latex_escape=False)
        self.assertIn("a || b || c", text)
        self.assertIsNone(_find_entity(entities, "spoiler"))

    def test_fence_inside_list_item_is_code(self):
        text, entities = convert("- ```\n  a || b || c\n  ```", latex_escape=False)
        self.assertIn("a || b || c", text)
        self.assertIsNone(_find_entity(entities, "spoiler"))

    def test_multi_backtick_inline_code_is_skipped(self):
        text, entities = convert("x ``a || b || c`` y", latex_escape=False)
        self.assertIn("a || b || c", text)
        self.assertIsNone(_find_entity(entities, "spoiler"))

    def test_container_and_fence_shapes_never_rewrite_code(self):
        # Every shape a hand-rolled line scanner got wrong. The parser decides
        # what is code now, so these must all survive untouched.
        for name, source in (
            ("blockquote fence", "> ```\n> ||x||\n> ```"),
            ("nested blockquote fence", "> > ```\n> > ||x||\n> > ```"),
            ("list item fence", "- ```\n  ||x||\n  ```"),
            ("indented code, many lines", "    a\n    ||x||"),
            ("indented fence-looking code", "    ```\n    ||x||\n    ```"),
            ("invalid closing fence", "```\na\n```oops\n||x||\n```"),
            ("paragraph line that looks like a list", "para\n2. fake\n\n    ||x||"),
            ("tab indented code", "\ta\n\t||x||"),
        ):
            with self.subTest(name=name):
                text, entities = convert(source, latex_escape=False)
                self.assertIn("||x||", text)
                self.assertIsNone(_find_entity(entities, "spoiler"))

    def test_spoiler_still_applies_outside_code(self):
        for name, source in (
            ("plain", "a ||x|| b"),
            ("list item", "- ||x||"),
            ("blockquote", "> ||x||"),
            ("deeply indented list item", "- a\n    - ||x||"),
            ("paragraph continuation", "p\n    ||x||"),
            ("html block nearby", "<div>\n```\n</div>\n\n||x||"),
        ):
            with self.subTest(name=name):
                _, entities = convert(source, latex_escape=False)
                self.assertIsNotNone(_find_entity(entities, "spoiler"))

    def test_spoiler_in_deeply_indented_list_still_works(self):
        # A list item indented four spaces is not an indented code block, so
        # the spoiler must still apply
        text, entities = convert("- a\n    - ||x||\n", latex_escape=False)
        self.assertIsNotNone(_find_entity(entities, "spoiler"))
        self.assertNotIn("||", text)

    def test_spoiler_in_paragraph_continuation_still_works(self):
        text, entities = convert("para\n    ||x|| cont\n", latex_escape=False)
        self.assertIsNotNone(_find_entity(entities, "spoiler"))


class MultilineSpoilerTest(unittest.TestCase):
    """An open tag alone on a line becomes a CommonMark HTML block, and the
    whole span gets dropped."""

    def test_newline_wrapped_spoiler_survives(self):
        text, entities = convert("||\nsecret\n||", latex_escape=False)
        spoiler = _find_entity(entities, "spoiler")
        self.assertIsNotNone(spoiler)
        self.assertEqual(_extract_entity_text(text, spoiler), "secret")

    def test_multiline_content_preserved(self):
        text, entities = convert("||\nline1\nline2\n||", latex_escape=False)
        self.assertIn("line1", text)
        self.assertIn("line2", text)
        self.assertIsNotNone(_find_entity(entities, "spoiler"))

    def test_crlf_wrapped_spoiler_survives(self):
        # Stripping only "\n" leaves the leading "\r", which still puts the
        # open tag alone on its line under CRLF input and drops the span.
        for source in ("||\r\nsecret\r\n||", "||\rsecret\r||", "||\r\nsecret\n||"):
            with self.subTest(source=source):
                text, entities = convert(source, latex_escape=False)
                spoiler = _find_entity(entities, "spoiler")
                self.assertIsNotNone(spoiler)
                self.assertEqual(_extract_entity_text(text, spoiler), "secret")


class ImageInTableCellTest(unittest.TestCase):
    """An image symbol in a cell must stay inside the rendered table."""

    def test_image_symbol_stays_inside_table(self):
        md = "| a |\n|---|\n| ![alt](https://e.com/i.png) |"
        text, entities = convert(md, latex_escape=False)
        pre = _find_entity(entities, "pre")
        self.assertIsNotNone(pre)
        # pre covering the whole span means the image symbol did not leak out
        # ahead of the table
        self.assertEqual(pre.offset, 0)
        self.assertEqual(pre.length, utf16_len(text))
        self.assertIn("🖼alt", text)


class ListMarkerConfigTest(unittest.TestCase):
    """@see https://github.com/sudoskys/telegramify-markdown/issues/116"""

    def setUp(self):
        from telegramify_markdown.config import get_runtime_config

        self.symbol = get_runtime_config().markdown_symbol
        self._saved = (self.symbol.unordered_list_item, self.symbol.ordered_list_suffix)

    def tearDown(self):
        self.symbol.unordered_list_item, self.symbol.ordered_list_suffix = self._saved

    def test_default_is_unchanged(self):
        text, _ = convert("- a\n- b", latex_escape=False)
        self.assertIn("⦁ a", text)

    def test_custom_unordered_marker(self):
        self.symbol.unordered_list_item = "-"
        text, _ = convert("- a\n- b", latex_escape=False)
        self.assertIn("- a", text)
        self.assertNotIn("⦁", text)

    def test_custom_marker_applies_to_nested_items(self):
        self.symbol.unordered_list_item = "•"
        text, _ = convert("- a\n  - b", latex_escape=False)
        self.assertIn("• a", text)
        self.assertIn("  • b", text)

    def test_custom_ordered_suffix(self):
        self.symbol.ordered_list_suffix = ")"
        text, _ = convert("1. a\n2. b", latex_escape=False)
        self.assertIn("1) a", text)
        self.assertIn("2) b", text)

    def test_task_marker_still_replaces_custom_bullet(self):
        self.symbol.unordered_list_item = "-"
        text, _ = convert("- [x] done", latex_escape=False)
        self.assertIn("✅", text)
        self.assertNotIn("- [", text)
        self.assertFalse(text.startswith("-"))


class RenderConfigIsolationTest(unittest.TestCase):
    """The global config is shared mutable state; isolated() hands out copies
    that do not affect each other.

    Mutating the global inside concurrent handlers crosses configurations:
    pyTelegramBotAPI is multi-threaded by default, and on the asyncio side
    "mutate global -> await -> render" always yields control in between.
    """

    def setUp(self):
        from telegramify_markdown.config import get_runtime_config

        self.symbol = get_runtime_config().markdown_symbol
        self._saved = self.symbol.unordered_list_item

    def tearDown(self):
        self.symbol.unordered_list_item = self._saved

    def test_bare_construction_still_returns_global(self):
        # 1.x compatibility: RenderConfig() is equivalent to get_runtime_config()
        from telegramify_markdown.config import RenderConfig, get_runtime_config

        self.assertIs(RenderConfig(), get_runtime_config())
        self.assertIs(RenderConfig(), RenderConfig())

    def test_repeated_construction_does_not_reset_settings(self):
        from telegramify_markdown.config import RenderConfig

        RenderConfig().markdown_symbol.unordered_list_item = "@"
        self.assertEqual(RenderConfig().markdown_symbol.unordered_list_item, "@")

    def test_isinstance_works(self):
        # Under the decorator implementation RenderConfig was a function and
        # isinstance raised TypeError
        from telegramify_markdown.config import RenderConfig, get_runtime_config

        self.assertIsInstance(get_runtime_config(), RenderConfig)
        self.assertIsInstance(RenderConfig.isolated(), RenderConfig)

    def test_isolated_starts_from_defaults_and_stays_independent(self):
        from telegramify_markdown.config import RenderConfig, get_runtime_config

        get_runtime_config().markdown_symbol.unordered_list_item = "@"
        isolated = RenderConfig.isolated()
        self.assertEqual(isolated.markdown_symbol.unordered_list_item, "⦁")

        isolated.markdown_symbol.unordered_list_item = "*"
        self.assertEqual(get_runtime_config().markdown_symbol.unordered_list_item, "@")

    def test_copy_inherits_current_values_but_is_independent(self):
        from telegramify_markdown.config import get_runtime_config

        get_runtime_config().markdown_symbol.unordered_list_item = "@"
        clone = get_runtime_config().copy()
        self.assertEqual(clone.markdown_symbol.unordered_list_item, "@")

        clone.markdown_symbol.unordered_list_item = "#"
        self.assertEqual(get_runtime_config().markdown_symbol.unordered_list_item, "@")

    def test_two_isolated_configs_render_differently(self):
        from telegramify_markdown.config import RenderConfig

        dash = RenderConfig.isolated()
        dash.markdown_symbol.unordered_list_item = "-"
        bullet = RenderConfig.isolated()
        bullet.markdown_symbol.unordered_list_item = "•"

        self.assertIn("- x", convert("- x", config=dash, latex_escape=False)[0])
        self.assertIn("• x", convert("- x", config=bullet, latex_escape=False)[0])

    def test_concurrent_threads_do_not_share_isolated_config(self):
        import threading

        from telegramify_markdown.config import RenderConfig

        rendered = {}
        aligned = threading.Barrier(2)

        def handler(name: str, marker: str) -> None:
            cfg = RenderConfig.isolated()
            cfg.markdown_symbol.unordered_list_item = marker
            aligned.wait()  # render only after both threads have configured,
            # maximising the chance of crossing configurations
            rendered[name] = convert("- item", config=cfg, latex_escape=False)[0].strip()

        threads = [
            threading.Thread(target=handler, args=("a", "-")),
            threading.Thread(target=handler, args=("b", "•")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(rendered["a"], "- item")
        self.assertEqual(rendered["b"], "• item")


if __name__ == "__main__":
    unittest.main()
