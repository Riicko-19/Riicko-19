#!/usr/bin/env python3
"""assets/source-photo.jpg -> assets/ascii-portrait.svg

Pillow is the only dependency. The photo is EXIF-transposed, desaturated,
auto-contrasted and resampled onto a fixed-width character grid; each grid row
becomes one <text> element inside a rounded, gradient-filled card.

The preprocessed image is also written to build/ascii-preprocessed.png so the
crop and the contrast can be judged without squinting at glyphs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "data" / "profile.json"
SOURCE = ROOT / "assets" / "source-photo.jpg"
OUT = ROOT / "assets" / "ascii-portrait.svg"
PREVIEW = ROOT / "build" / "ascii-preprocessed.png"

# INVERT — which end of the brightness range gets the densest glyphs.
#
#   True  : BRIGHT pixels -> densest characters.  This is the right setting for
#           this card, because the card is dark and the glyphs are bright: the
#           lit side of the subject inks up and the dark background thins out
#           into whitespace, so the portrait floats on the gradient.
#   False : DARK pixels -> densest characters.  The classic "ink on paper"
#           mapping. Flip to this for a photo shot against a BRIGHT background
#           (a window, a white wall), otherwise the background is what inks up
#           and the subject disappears into it.
#
# Overridable from data/profile.json -> ascii.invert.
INVERT = True

# Advance width of one character as a fraction of font-size (0.6em for every
# monospace face in the stack). CELL_ASPECT is that advance divided by the line
# height, i.e. how wide one character cell is relative to its height — this is
# what keeps the portrait from coming out stretched.
ADV = 0.6
LINE_HEIGHT = 1.0          # in em
CELL_ASPECT = ADV / LINE_HEIGHT

DEFAULTS = {
    "columns": 96,
    "ramp": " .:-=+*#%@",
    "invert": INVERT,
}
FALLBACK_THEME = {
    "bg_from": "#0f2027",
    "bg_via": "#203a43",
    "bg_to": "#2c5364",
    "accent": "#00f7ff",
    "text": "#e6f1f5",
    "font_mono": "monospace",
}
FALLBACK_CARD = {"height": 620, "ascii_width": 400, "padding": 26, "radius": 14}


def load_config() -> tuple[dict, dict, dict]:
    """Theme and card geometry are shared with gen_info_card.py so the two
    cards sit side by side at the same height and in the same palette."""
    if not PROFILE.exists():
        return FALLBACK_THEME, FALLBACK_CARD, DEFAULTS
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    return (
        {**FALLBACK_THEME, **profile.get("theme", {})},
        {**FALLBACK_CARD, **profile.get("card", {})},
        {**DEFAULTS, **profile.get("ascii", {})},
    )


def preprocess(path: Path) -> Image.Image:
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)          # honour phone orientation
    image = image.convert("L")                      # grayscale
    image = ImageOps.autocontrast(image, cutoff=2)  # clip the flattest 2% tails
    return image


def to_rows(image: Image.Image, columns: int, ramp: str, invert: bool) -> list[str]:
    """Resample onto the character grid and map luminance to glyphs."""
    src_w, src_h = image.size
    rows = max(1, round(columns * (src_h / src_w) * CELL_ASPECT))
    grid = image.resize((columns, rows), Image.Resampling.LANCZOS)

    pixels = grid.load()
    last = len(ramp) - 1
    out: list[str] = []
    for y in range(rows):
        line = []
        for x in range(columns):
            value = pixels[x, y] / 255.0
            if invert:
                value = 1.0 - value       # bright pixel -> high ramp index
            line.append(ramp[last - round(value * last)])
        out.append("".join(line))
    return out


def build_svg(rows: list[str], theme: dict, card: dict) -> str:
    width, height = card["ascii_width"], card["height"]
    pad, radius = card["padding"], card["radius"]
    box_w, box_h = width - 2 * pad, height - 2 * pad

    columns = len(rows[0])
    # Largest font-size at which the whole grid still fits inside the padding
    # box, in both axes. Guarantees the art never spills out of the card.
    font_size = min(box_w / (columns * ADV), box_h / (len(rows) * LINE_HEIGHT))
    line_height = font_size * LINE_HEIGHT
    block_w = columns * font_size * ADV
    block_h = len(rows) * line_height

    x0 = pad + (box_w - block_w) / 2
    y0 = pad + (box_h - block_h) / 2

    lines = []
    for i, row in enumerate(rows):
        baseline = y0 + i * line_height + font_size * 0.8
        lines.append(
            f'<text x="{x0:.2f}" y="{baseline:.2f}" textLength="{block_w:.2f}" '
            f'lengthAdjust="spacingAndGlyphs">{escape(row)}</text>'
        )

    font_family = escape(theme["font_mono"], {'"': "&quot;"})
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" \
viewBox="0 0 {width} {height}" role="img" aria-label="ASCII-art portrait">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{theme['bg_from']}"/>
      <stop offset="55%" stop-color="{theme['bg_via']}"/>
      <stop offset="100%" stop-color="{theme['bg_to']}"/>
    </linearGradient>
    <linearGradient id="ink" gradientUnits="userSpaceOnUse"
                    x1="0" y1="0" x2="{width}" y2="{height}">
      <stop offset="0%" stop-color="{theme['accent']}"/>
      <stop offset="55%" stop-color="{theme['text']}"/>
      <stop offset="100%" stop-color="{theme['accent']}"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="{radius}" fill="url(#bg)"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="{radius}"
        fill="none" stroke="{theme['accent']}" stroke-width="1" opacity="0.22"/>
  <g font-family="{font_family}" font-size="{font_size:.3f}" fill="url(#ink)"
     xml:space="preserve" style="white-space:pre">
{chr(10).join('    ' + line for line in lines)}
  </g>
</svg>
"""


def main() -> int:
    if not SOURCE.exists():
        sys.stderr.write(
            f"gen_ascii: {SOURCE.relative_to(ROOT)} not found — nothing to do.\n"
        )
        return 0

    theme, card, cfg = load_config()
    invert = bool(cfg.get("invert", INVERT))

    image = preprocess(SOURCE)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    image.save(PREVIEW)

    rows = to_rows(image, int(cfg["columns"]), cfg["ramp"], invert)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_svg(rows, theme, card), encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} "
        f"({len(rows[0])}x{len(rows)} chars, invert={invert}); "
        f"preprocessed image at {PREVIEW.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
