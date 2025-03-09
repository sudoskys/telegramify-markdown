import re

sp_p = re.compile(r"(?<!\\)(?:\\\\)*\|\|(.+?)\|\|", re.DOTALL)
todo_p = re.compile(r"^- \[([ xX])\] (.*)", re.DOTALL | re.MULTILINE)
math_p = re.compile(r'(?:\$\$(.*?)\$\$|\\\[(.*?)\\\])', re.DOTALL | re.MULTILINE)
inline_math_p = re.compile(r'(?<!\\)(?:\\\\)*\$(.+?)\$', re.DOTALL)
math = r"""
\[
\begin{aligned}
\text{Let } f(x) &= \frac{1}{x} \\
\text{Then } f'(x) &= -\frac{1}{x^2} \\
\text{And } f''(x) &= \frac{2}{x^3}
\end{aligned}
\]

inline $f(x) = \frac{1}{x}$

"""

print(inline_math_p.findall(math))
print("====")
print(math_p.findall(math))
