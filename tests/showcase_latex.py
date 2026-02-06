"""LaTeX→Unicode 转换实战展示。

运行: pdm run python tests/showcase_latex.py
"""
from telegramify_markdown.latex_escape.helper import LatexToUnicodeHelper

h = LatexToUnicodeHelper()

formulas = [
    # ── 经典物理 ──
    ("牛顿第二定律",
     r"\vec{F} = m\vec{a}"),

    ("万有引力",
     r"F = G\frac{m_1 m_2}{r^2}"),

    ("麦克斯韦方程组（微分形式）",
     r"\begin{align} \nabla \cdot \mathbf{E} &= \frac{\rho}{\varepsilon_0} \\ \nabla \cdot \mathbf{B} &= 0 \\ \nabla \times \mathbf{E} &= -\frac{\partial \mathbf{B}}{\partial t} \\ \nabla \times \mathbf{B} &= \mu_0 \mathbf{J} + \mu_0 \varepsilon_0 \frac{\partial \mathbf{E}}{\partial t} \end{align}"),

    # ── 量子力学 ──
    ("薛定谔方程",
     r"i\hbar \frac{\partial}{\partial t} \Psi(\vec{r}, t) = \hat{H} \Psi(\vec{r}, t)"),

    ("狄拉克方程",
     r"(i\gamma^\mu \partial_\mu - m)\psi = 0"),

    ("不确定性原理",
     r"\Delta x \cdot \Delta p \geq \frac{\hbar}{2}"),

    ("狄拉克 bra-ket",
     r"\langle \phi | \hat{A} | \psi \rangle = \int \phi^*(x) \hat{A} \psi(x) \mathrm{d}x"),

    # ── 数学分析 ──
    ("欧拉恒等式",
     r"e^{i\pi} + 1 = 0"),

    ("高斯积分",
     r"\int_{-\infty}^{\infty} e^{-x^2} \mathrm{d}x = \sqrt{\pi}"),

    ("高斯分布",
     r"f(x) = \frac{1}{\sigma\sqrt{2\pi}} \exp\left(-\frac{(x - \mu)^2}{2\sigma^2}\right)"),

    ("泰勒展开",
     r"e^x = \sum_{n=0}^{\infty} \frac{x^n}{n!} = 1 + x + \frac{x^2}{2!} + \frac{x^3}{3!} + \cdots"),

    ("柯西积分公式",
     r"f(a) = \frac{1}{2\pi i} \oint_C \frac{f(z)}{z - a} \mathrm{d}z"),

    ("留数定理",
     r"\oint_C f(z)\mathrm{d}z = 2\pi i \sum_{k=1}^{n} \operatorname{Res}(f, a_k)"),

    ("傅里叶变换",
     r"\hat{f}(\xi) = \int_{-\infty}^{\infty} f(x) e^{-2\pi i x \xi} \mathrm{d}x"),

    ("黎曼 ζ 函数",
     r"\zeta(s) = \sum_{n=1}^{\infty} \frac{1}{n^s} = \prod_{p \text{ prime}} \frac{1}{1 - p^{-s}}"),

    # ── 线性代数 ──
    ("单位矩阵",
     r"I = \begin{pmatrix} 1 & 0 & 0 \\ 0 & 1 & 0 \\ 0 & 0 & 1 \end{pmatrix}"),

    ("行列式",
     r"\det\begin{vmatrix} a & b \\ c & d \end{vmatrix} = ad - bc"),

    ("特征值方程",
     r"\det(A - \lambda I) = 0"),

    # ── 概率与信息论 ──
    ("贝叶斯定理",
     r"P(A|B) = \frac{P(B|A) \cdot P(A)}{P(B)}"),

    ("香农熵",
     r"H(X) = -\sum_{i=1}^{n} p_i \log_2 p_i"),

    ("KL 散度",
     r"D_{KL}(P \| Q) = \sum_{x} P(x) \ln \frac{P(x)}{Q(x)}"),

    # ── 广义相对论 ──
    ("爱因斯坦场方程",
     r"R_{\mu\nu} - \frac{1}{2} R g_{\mu\nu} + \Lambda g_{\mu\nu} = \frac{8\pi G}{c^4} T_{\mu\nu}"),

    ("克里斯托费尔符号",
     r"\Gamma^{\lambda}_{\mu\nu} = \frac{1}{2} g^{\lambda\sigma} \left( \frac{\partial g_{\sigma\mu}}{\partial x^\nu} + \frac{\partial g_{\sigma\nu}}{\partial x^\mu} - \frac{\partial g_{\mu\nu}}{\partial x^\sigma} \right)"),

    # ── 数论 ──
    ("二次互反律",
     r"\left(\frac{p}{q}\right) \left(\frac{q}{p}\right) = (-1)^{\frac{p-1}{2} \cdot \frac{q-1}{2}}"),

    ("费马大定理",
     r"x^n + y^n = z^n \quad (n \geq 3, \text{ no integer solutions})"),

    # ── 分段函数 ──
    ("绝对值",
     r"|x| = \begin{cases} x & x \geq 0 \\ -x & x < 0 \end{cases}"),

    ("Heaviside 阶跃函数",
     r"\Theta(x) = \begin{cases} 0 & x < 0 \\ \frac{1}{2} & x = 0 \\ 1 & x > 0 \end{cases}"),

    # ── 组合数学 ──
    ("二项式定理",
     r"(x + y)^n = \sum_{k=0}^{n} \binom{n}{k} x^{n-k} y^k"),

    ("斯特林近似",
     r"n! \sim \sqrt{2\pi n} \left(\frac{n}{e}\right)^n"),

    # ── 深度学习 ──
    ("Softmax",
     r"\sigma(z_i) = \frac{e^{z_i}}{\sum_{j=1}^{K} e^{z_j}}"),

    ("交叉熵损失",
     r"\mathcal{L} = -\sum_{c=1}^{C} y_c \log(\hat{y}_c)"),

    ("Attention",
     r"\operatorname{Attention}(Q, K, V) = \operatorname{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}\right) V"),

    # ── 连分数 ──
    ("黄金比例",
     r"\phi = 1 + \frac{1}{1 + \frac{1}{1 + \frac{1}{1 + \cdots}}}"),

    # ── 极端嵌套 ──
    ("嵌套根号",
     r"\sqrt{1 + \sqrt{1 + \sqrt{1 + \sqrt{1 + \cdots}}}}"),

    ("嵌套上下标",
     r"e^{e^{e^{e^{\cdot^{\cdot^{\cdot}}}}}}"),
]

if __name__ == "__main__":
    print("=" * 60)
    print("  LaTeX → Unicode 转换实战展示")
    print("=" * 60)
    for title, latex in formulas:
        result = h.convert(latex)
        print(f"\n{'─' * 60}")
        print(f"  {title}")
        print(f"  LaTeX: {latex}")
        print(f"  Unicode: {result}")
    print(f"\n{'═' * 60}")
    print(f"  共 {len(formulas)} 个公式全部转换完成")
    print("=" * 60)
