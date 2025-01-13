import matplotlib.pyplot as plt
from io import BytesIO


def render_latex_with_matplotlib(latex_expr, bg_color="#FFFFFF", text_color="#000000", dpi=300, font_size=20):
    """
    Renders a LaTeX math formula using matplotlib and saves it to a BytesIO object.

    Parameters:
        latex_expr (str): LaTeX math formula (e.g., r"$\int_a^b f(x) \, dx = F(b) - F(a)$")
        bg_color (str): Background color in HEX format (default is white: "#FFFFFF")
        text_color (str): Text (formula) color in HEX format (default is black: "#000000")
        dpi (int): Dots per inch for rendered output (default: 300).
        font_size (int): Font size for the formula text (default: 20).

    Returns:
        BytesIO: A BytesIO object containing the rendered formula as PNG.
    """
    # Create a figure with transparent axes and no ticks
    plt.figure(figsize=(4, 2), dpi=dpi)
    plt.axis('off')  # Hide axes

    # Using the 'text' function to render LaTeX
    plt.text(0.5, 0.5, latex_expr, color=text_color, fontsize=font_size, ha='center', va='center',
             transform=plt.gca().transAxes, usetex=True)  # `usetex=True` enables LaTeX rendering in matplotlib

    # Set the figure background color
    plt.gcf().patch.set_facecolor(bg_color)

    # Save the figure directly to BytesIO
    buffer = BytesIO()
    plt.savefig(buffer, format="png", bbox_inches='tight', pad_inches=0, transparent=True)
    buffer.seek(0)
    plt.close()

    return buffer

# Example usage:
latex_formula = r"$F = G\frac{{m_1m_2}}{{r^2}}$"
bg_color = "#F0F8FF"  # AliceBlue background
text_color = "#000000"  # Black text color

# Render the LaTeX math expression
latex_bytesio = render_latex_with_matplotlib(latex_formula, bg_color=bg_color, text_color=text_color, font_size=30)

# Save the rendered formula as a PNG file (optional)
from PIL import Image

img = Image.open(latex_bytesio)
img.save("latex_matplotlib_rendered.png")