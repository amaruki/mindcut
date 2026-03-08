"""
Design tokens and theme helpers for MindCut Desktop UI.
Matches the web CSS variables from style.css.
"""

from kivy.graphics.texture import Texture
from kivy.core.text import LabelBase
import os

# Base Colors
BG_APP = "#030409"
BG_PANEL = "#0a0b10"
BG_PANEL_HOVER = "#12141d"
BG_HEADER = "#07080c"

# Foreground
FG = "#f3f4f6"
FG_MUTED = "#8b92a5"

# Borders
BORDER = "ffffff"  # we will use with alpha 0.08
BORDER_LIGHT = "ffffff"  # we will use with alpha 0.15

# Accent & Brand
ACCENT = "#8b5cf6"
ACCENT_HOVER = "#a78bfa"

SUCCESS = "36c55e"  # rgba(34, 197, 94, 0.9)

# Button Radii
RADIUS_SM = 10
RADIUS_MD = 16
RADIUS_LG = 24

FONT_FAMILY = "Roboto"


def hex_to_rgba(hex_color, alpha=1.0):
    """Convert hex string (#RRGGBB or RRGGBB) to Kivy's (R, G, B, A) 0-1 range."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b, alpha)
    return (1, 1, 1, alpha)


def create_gradient_texture(color1, color2, width=256, height=1):
    """Creates a simple linear 1D gradient texture for backgrounds."""
    texture = Texture.create(size=(width, height), colorfmt="rgba")
    buf = bytearray(width * height * 4)
    r1, g1, b1, _ = hex_to_rgba(color1)
    r2, g2, b2, _ = hex_to_rgba(color2)

    for x in range(width):
        t = x / (width - 1.0) if width > 1 else 0
        r = r1 * (1 - t) + r2 * t
        g = g1 * (1 - t) + g2 * t
        b = b1 * (1 - t) + b2 * t

        idx = x * 4
        buf[idx] = int(r * 255)
        buf[idx + 1] = int(g * 255)
        buf[idx + 2] = int(b * 255)
        buf[idx + 3] = 255

    texture.blit_buffer(buf, colorfmt="rgba", bufferfmt="ubyte")
    return texture


def get_primary_gradient():
    return create_gradient_texture("#7c3aed", "#db2777")


def get_primary_hover_gradient():
    return create_gradient_texture("#8b5cf6", "#f43f5e")


def register_fonts():
    """Register custom fonts if available. Fallback to default if not."""
    font_dir = os.path.join(os.path.dirname(__file__), "assets", "fonts")
    regular_path = os.path.join(font_dir, "Outfit-Regular.ttf")
    bold_path = os.path.join(font_dir, "Outfit-Bold.ttf")

    if os.path.exists(regular_path) and os.path.getsize(regular_path) > 10000:
        # We might not have italic/bolditalic files, fallback to regular/bold
        italic_path = regular_path
        bolditalic_path = bold_path if os.path.exists(bold_path) else regular_path
        bold_path_actual = bold_path if os.path.exists(bold_path) else regular_path

        # Register for explicit use if it's a valid font file (>10KB)
        LabelBase.register(
            name="Outfit",
            fn_regular=regular_path,
            fn_bold=bold_path_actual,
            fn_italic=italic_path,
            fn_bolditalic=bolditalic_path,
        )
    else:
        print(
            "WARNING: Valid Outfit fonts not found in assets/fonts/ - using default Roboto"
        )
