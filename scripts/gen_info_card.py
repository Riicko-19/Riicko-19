#!/usr/bin/env python3
"""data/profile.json -> assets/info-card.svg

Every string, colour and dimension in the card comes from data/profile.json.
Nothing in this file needs editing to change the card's content: add a
highlight, rename a stack group, retheme the whole thing — it is all JSON.

The layout is a single top-to-bottom cursor. Text is measured with the
monospace advance ratio (0.6 em) so long lines are wrapped before they are
emitted, and the script hard-fails if the content ever runs past the bottom
of the card rather than silently drawing outside it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "data" / "profile.json"
OUT = ROOT / "assets" / "info-card.svg"

# Advance width of one character as a fraction of font-size. 0.6 is exact for
# Liberation/DejaVu/Menlo/JetBrains Mono and an over-estimate for Consolas
# (0.55), so measuring with it never under-estimates a line's width.
ADV = 0.6


# --------------------------------------------------------------------------
# text measuring / wrapping
# --------------------------------------------------------------------------

def width_of(text: str, size: float, tracking: float = 0.0) -> float:
    return len(text) * (size * ADV + tracking)


def wrap(text: str, size: float, max_width: float) -> list[str]:
    """Greedy word wrap to a character budget, hard-breaking over-long words."""
    budget = max(1, int(max_width // (size * ADV)))
    lines: list[str] = []
    line = ""
    for word in text.split():
        while len(word) > budget:                 # a single word wider than the box
            if line:
                lines.append(line)
                line = ""
            lines.append(word[: budget - 1] + "-")
            word = word[budget - 1 :]
        candidate = f"{line} {word}".strip()
        if len(candidate) <= budget:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or [""]


# --------------------------------------------------------------------------
# svg emitter
# --------------------------------------------------------------------------

class Card:
    def __init__(self, width: int, height: int, padding: int, font: str):
        self.w, self.h, self.pad, self.font = width, height, padding, font
        self.parts: list[str] = []
        self.y = float(padding)

    @property
    def content_width(self) -> float:
        return self.w - 2 * self.pad

    def gap(self, amount: float) -> None:
        self.y += amount

    def text(
        self,
        content: str,
        *,
        size: float,
        fill: str,
        weight: str = "normal",
        tracking: float = 0.0,
        opacity: float = 1.0,
        x: float | None = None,
        lead: float | None = None,
    ) -> None:
        """Draw one line at the cursor and advance past it."""
        x = self.pad if x is None else x
        self.y += size                                   # cursor -> baseline
        attrs = [
            f'x="{x:.1f}"',
            f'y="{self.y:.1f}"',
            f'font-size="{size:g}"',
            f'fill="{fill}"',
        ]
        if weight != "normal":
            attrs.append(f'font-weight="{weight}"')
        if tracking:
            attrs.append(f'letter-spacing="{tracking:g}"')
        if opacity != 1.0:
            attrs.append(f'opacity="{opacity:g}"')
        self.parts.append(f'<text {" ".join(attrs)}>{escape(content)}</text>')
        self.y += size * 0.32 if lead is None else lead  # descender + leading

    def paragraph(
        self, content: str, *, size: float, fill: str, x: float, opacity: float = 1.0
    ) -> None:
        for line in wrap(content, size, self.w - self.pad - x):
            self.text(line, size=size, fill=fill, x=x, opacity=opacity, lead=size * 0.42)

    def rule(self, colour: str) -> None:
        self.parts.append(
            f'<line x1="{self.pad}" y1="{self.y:.1f}" x2="{self.w - self.pad}" '
            f'y2="{self.y:.1f}" stroke="{colour}" stroke-width="1" opacity="0.7"/>'
        )

    def render(self, theme: dict, radius: int) -> str:
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" \
viewBox="0 0 {self.w} {self.h}" role="img" aria-label="Profile info card">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{theme['bg_from']}"/>
      <stop offset="55%" stop-color="{theme['bg_via']}"/>
      <stop offset="100%" stop-color="{theme['bg_to']}"/>
    </linearGradient>
  </defs>
  <rect width="{self.w}" height="{self.h}" rx="{radius}" fill="url(#bg)"/>
  <rect x="0.5" y="0.5" width="{self.w - 1}" height="{self.h - 1}" rx="{radius}"
        fill="none" stroke="{theme['accent']}" stroke-width="1" opacity="0.22"/>
  <g font-family="{escape(theme['font_mono'], {'"': '&quot;'})}">
{chr(10).join('    ' + p for p in self.parts)}
  </g>
</svg>
"""


# --------------------------------------------------------------------------

def main() -> int:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    ident, theme = profile["identity"], profile["theme"]
    cfg, hl, stack = profile["card"], profile["highlights"], profile["stack"]

    card = Card(cfg["info_width"], cfg["height"], cfg["padding"], theme["font_mono"])

    # header ---------------------------------------------------------------
    card.gap(6)
    card.text(ident["name"], size=25, fill=theme["text"], weight="bold", tracking=1.6)
    card.gap(2)
    card.text(ident["tagline"], size=10.5, fill=theme["accent"], lead=0)

    card.gap(18)
    card.rule(theme["rule"])
    card.gap(14)

    card.text(ident["education"], size=10, fill=theme["muted"])
    card.text(ident["location"], size=10, fill=theme["muted"])

    # highlights -----------------------------------------------------------
    card.gap(20)
    card.text(hl["label"], size=9.5, fill=theme["accent"], weight="bold", tracking=2.4)
    card.gap(8)

    bullet = hl.get("bullet", "-")
    indent = card.pad + 14
    for item in hl["items"]:
        card.text(
            f'{bullet} {item["title"]}',
            size=11,
            fill=theme["text"],
            weight="bold",
            lead=3,
        )
        card.paragraph(item["detail"], size=8.6, fill=theme["muted"], x=indent)
        card.gap(7)

    # stack ----------------------------------------------------------------
    card.gap(9)
    card.text(stack["label"], size=9.5, fill=theme["accent"], weight="bold", tracking=2.4)
    card.gap(8)

    sep = stack.get("separator", " · ")
    for group in stack["groups"]:
        card.text(group["label"], size=9.5, fill=theme["accent"], opacity=0.85, lead=2)
        card.paragraph(
            sep.join(group["items"]), size=9.5, fill=theme["text"], x=indent, opacity=0.9
        )
        card.gap(6)

    # overflow guard -------------------------------------------------------
    bottom = card.y
    limit = cfg["height"] - cfg["padding"]
    if bottom > limit:
        sys.stderr.write(
            f"info-card: content overflows by {bottom - limit:.0f}px "
            f"(used {bottom:.0f} of {limit:.0f}px).\n"
            f"Shorten a highlight detail in data/profile.json, or raise "
            f'card.height (currently {cfg["height"]}).\n'
        )
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(card.render(theme, cfg["radius"]), encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} "
        f"({cfg['info_width']}x{cfg['height']}, {limit - bottom:.0f}px headroom)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
