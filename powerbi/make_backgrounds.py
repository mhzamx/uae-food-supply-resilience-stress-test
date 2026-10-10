"""Draw the page background images used by the P2 Power BI report (dark theme).

Writes powerbi/assets/bg_<page>.png at 2x resolution (2560 x 1440) for each 1280 x 720 page.
Panel positions come from LAYOUT and PANELS in build_pbip.py so the visuals and the drawn panels stay aligned.

Usage: python powerbi/make_backgrounds.py
"""
import os
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
S = 2  # supersampling factor
BG, PANEL, BORDER, CYAN = (7, 18, 31), (11, 27, 43), (24, 55, 80), (34, 211, 238)


def rgba(c, a):
    return c + (int(round(a * 255)),)


def panel(layer, box, fill_alpha=0.92, bracket=14):
    x, y, w, h = (v * S for v in box)
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=4 * S, fill=rgba(PANEL, fill_alpha), outline=rgba(BORDER, 1), width=S)
    b, t = bracket * S, 2 * S
    for cx, cy, sx, sy in [(x, y, 1, 1), (x + w - 1, y, -1, 1), (x, y + h - 1, 1, -1), (x + w - 1, y + h - 1, -1, -1)]:
        d.line([cx, cy, cx + sx * b, cy], fill=rgba(CYAN, 0.9), width=t)
        d.line([cx, cy, cx, cy + sy * b], fill=rgba(CYAN, 0.9), width=t)


def glow(size, center, radius, color, alpha):
    g = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    cx, cy, r = center[0] * S, center[1] * S, radius * S
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgba(color, alpha))
    return g.filter(ImageFilter.GaussianBlur(r * 0.45))


def dots(layer, box, step=16, color=(20, 44, 66)):
    x, y, w, h = box
    d = ImageDraw.Draw(layer)
    for i in range(x + step, x + w - 4, step):
        for j in range(y + step, y + h - 4, step):
            d.ellipse([i * S - S, j * S - S, i * S + S, j * S + S], fill=rgba(color, 1))


def header_line(layer):
    d = ImageDraw.Draw(layer)
    d.line([16 * S, 66 * S, 1264 * S, 66 * S], fill=rgba(BORDER, 1), width=S)
    d.line([16 * S, 66 * S, 136 * S, 66 * S], fill=rgba(CYAN, 1), width=2 * S)


def plain(boxes, out):
    size = (1280 * S, 720 * S)
    img = Image.new("RGBA", size, rgba(BG, 1))
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    for box in boxes:
        panel(layer, box)
    header_line(layer)
    img = Image.alpha_composite(img, layer)
    img.convert("RGB").save(out, "PNG", optimize=True)


def overview(layout, out):
    size = (1280 * S, 720 * S)
    img = Image.new("RGBA", size, rgba(BG, 1))
    cx = layout["center"][0] + layout["center"][2] // 2
    cy = layout["center"][1] + layout["center"][3] // 2 + 10
    img = Image.alpha_composite(img, glow(size, (cx, cy), 210, CYAN, 0.16))
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    for key in ("left_top", "right", "left_bottom", "center_bottom"):
        panel(layer, layout[key])
    panel(layer, layout["center"], fill_alpha=0.35)
    dots(layer, layout["center"])
    header_line(layer)
    img = Image.alpha_composite(img, layer)
    img.convert("RGB").save(out, "PNG", optimize=True)


if __name__ == "__main__":
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_pbip", os.path.join(HERE, "build_pbip.py"))
    bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)
    os.makedirs(os.path.join(HERE, "assets"), exist_ok=True)
    out = os.path.join(HERE, "assets", "bg_overview.png")
    overview(bp.LAYOUT, out)
    print("written", out)
    for key, boxes in bp.PANELS.items():
        out = os.path.join(HERE, "assets", f"bg_{key}.png")
        plain(list(boxes.values()), out)
        print("written", out)
