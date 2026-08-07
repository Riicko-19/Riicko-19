#!/usr/bin/env python3
"""GitHub GraphQL contribution calendar -> assets/contrib-heatmap.svg

Reads GH_TOKEN and GH_USERNAME from the environment. Standard library only.

  GH_TOKEN=ghp_...  GH_USERNAME=Riicko-19  python scripts/gen_heatmap.py
  python scripts/gen_heatmap.py --synthetic     # exercise the renderer, no token

Intensity is four levels of opacity on the single accent colour, so the chart
inherits the theme instead of introducing a second palette.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "data" / "profile.json"
OUT = ROOT / "assets" / "contrib-heatmap.svg"

API = "https://api.github.com/graphql"
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount weekday }
        }
      }
    }
  }
}
"""

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

def fetch_calendar(token: str, login: str) -> dict:
    request = urllib.request.Request(
        API,
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{login}-profile-readme",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"gen_heatmap: GitHub API returned HTTP {exc.code} {exc.reason}\n"
            f"{exc.read().decode(errors='replace')[:500]}"
        )
    except urllib.error.URLError as exc:
        raise SystemExit(f"gen_heatmap: could not reach {API}: {exc.reason}")

    # Fail loudly. A GraphQL error still comes back as HTTP 200 with a null
    # `data`, and rendering that would silently publish an empty chart.
    if payload.get("errors"):
        messages = "\n".join(f"  - {e.get('message', e)}" for e in payload["errors"])
        raise SystemExit(f"gen_heatmap: GraphQL errors from GitHub:\n{messages}")

    user = (payload.get("data") or {}).get("user")
    if not user:
        raise SystemExit(f"gen_heatmap: no user data returned for login {login!r}")

    return user["contributionsCollection"]["contributionCalendar"]


def synthetic_calendar(seed: int = 19) -> dict:
    """A year of plausible fake activity — for exercising the renderer only."""
    import random

    rng = random.Random(seed)
    end = date.today()
    start = end - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)   # back up to a Sunday

    weeks, week, total = [], [], 0
    day = start
    while day <= end:
        weekday = (day.weekday() + 1) % 7               # GitHub: 0 = Sunday
        weekend = weekday in (0, 6)
        count = 0 if rng.random() < (0.55 if weekend else 0.2) else rng.randint(1, 18)
        total += count
        week.append({"date": day.isoformat(), "contributionCount": count,
                     "weekday": weekday})
        if weekday == 6:
            weeks.append({"contributionDays": week})
            week = []
        day += timedelta(days=1)
    if week:
        weeks.append({"contributionDays": week})

    return {"totalContributions": total, "weeks": weeks}


def thresholds(counts: list[int]) -> tuple[int, int, int]:
    """Quartile cut points over the non-zero days, kept strictly increasing."""
    active = sorted(c for c in counts if c > 0)
    if not active:
        return 1, 2, 3
    q = [active[min(len(active) - 1, int(len(active) * f))] for f in (0.25, 0.5, 0.75)]
    q[1] = max(q[1], q[0] + 1)
    q[2] = max(q[2], q[1] + 1)
    return q[0], q[1], q[2]


def level_of(count: int, cuts: tuple[int, int, int]) -> int:
    if count <= 0:
        return 0
    return 1 + sum(count > cut for cut in cuts)


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def build_svg(calendar: dict, theme: dict, cfg: dict) -> str:
    weeks = calendar["weeks"]
    cell, gap = cfg["cell"], cfg["gap"]
    step = cell + gap
    pad, gutter = cfg["padding"], cfg["gutter"]
    opacity = cfg["level_opacity"]
    day_labels = {int(k): v for k, v in cfg["day_labels"].items()}

    grid_x = pad + gutter
    month_band = 16
    grid_y = pad + month_band
    grid_w = len(weeks) * step - gap
    grid_h = 7 * step - gap

    width = grid_x + grid_w + pad
    footer_y = grid_y + grid_h + 26
    height = footer_y + pad

    counts = [d["contributionCount"] for w in weeks for d in w["contributionDays"]]
    cuts = thresholds(counts)

    parts: list[str] = []

    # month labels — printed at the first week that lands in a new month
    seen: set[str] = set()
    for i, week in enumerate(weeks):
        first = week["contributionDays"][0]["date"]
        year_month, month = first[:7], int(first[5:7])
        if year_month in seen:
            continue
        seen.add(year_month)
        if i == 0 and int(first[8:10]) > 21:      # skip a stub leading month
            continue
        parts.append(
            f'<text x="{grid_x + i * step}" y="{pad + 9}" font-size="9.5" '
            f'fill="{theme["muted"]}">{MONTHS[month - 1]}</text>'
        )

    # weekday labels
    for weekday, label in sorted(day_labels.items()):
        y = grid_y + weekday * step + cell * 0.8
        parts.append(
            f'<text x="{pad}" y="{y:.1f}" font-size="9" '
            f'fill="{theme["muted"]}">{escape(label)}</text>'
        )

    # cells
    for i, week in enumerate(weeks):
        for day in week["contributionDays"]:
            x = grid_x + i * step
            y = grid_y + day["weekday"] * step
            count = day["contributionCount"]
            plural = "" if count == 1 else "s"
            tooltip = escape(f'{count} contribution{plural} on {day["date"]}')
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'rx="{cfg["radius"]}" fill="{theme["accent"]}" '
                f'opacity="{opacity[level_of(count, cuts)]}">'
                f"<title>{tooltip}</title></rect>"
            )

    # footer: annual total on the left, intensity legend on the right
    days = [d for w in weeks for d in w["contributionDays"]]
    footer = cfg["footer"].format(
        total=f'{calendar["totalContributions"]:,}',
        start=days[0]["date"],
        end=days[-1]["date"],
    )
    parts.append(
        f'<text x="{grid_x}" y="{footer_y}" font-size="10.5" '
        f'fill="{theme["text"]}" opacity="0.85">{escape(footer)}</text>'
    )

    legend_w = 5 * step - gap
    legend_x = width - pad - legend_w - 62
    parts.append(
        f'<text x="{legend_x - 6}" y="{footer_y}" font-size="9.5" text-anchor="end" '
        f'fill="{theme["muted"]}">Less</text>'
    )
    for level in range(5):
        parts.append(
            f'<rect x="{legend_x + level * step}" y="{footer_y - cell + 2}" '
            f'width="{cell}" height="{cell}" rx="{cfg["radius"]}" '
            f'fill="{theme["accent"]}" opacity="{opacity[level]}"/>'
        )
    parts.append(
        f'<text x="{legend_x + legend_w + 6}" y="{footer_y}" font-size="9.5" '
        f'fill="{theme["muted"]}">More</text>'
    )

    font_family = escape(theme["font_mono"], {'"': "&quot;"})
    body = "\n".join("    " + p for p in parts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" \
viewBox="0 0 {width} {height}" role="img" aria-label="GitHub contribution heatmap">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{theme['bg_from']}"/>
      <stop offset="55%" stop-color="{theme['bg_via']}"/>
      <stop offset="100%" stop-color="{theme['bg_to']}"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="14" fill="url(#bg)"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14"
        fill="none" stroke="{theme['accent']}" stroke-width="1" opacity="0.22"/>
  <g font-family="{font_family}">
{body}
  </g>
</svg>
"""


# --------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    theme, cfg = profile["theme"], profile["heatmap"]

    if "--synthetic" in argv:
        print("gen_heatmap: rendering SYNTHETIC data — do not commit this output")
        calendar = synthetic_calendar()
    else:
        token = os.environ.get("GH_TOKEN", "").strip()
        login = os.environ.get("GH_USERNAME", "").strip()
        missing = [n for n, v in (("GH_TOKEN", token), ("GH_USERNAME", login)) if not v]
        if missing:
            print(
                f"gen_heatmap: {' and '.join(missing)} not set — skipping heatmap. "
                "(Pass --synthetic to render sample data instead.)"
            )
            return 0
        calendar = fetch_calendar(token, login)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_svg(calendar, theme, cfg), encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} "
        f'({calendar["totalContributions"]:,} contributions, '
        f'{len(calendar["weeks"])} weeks)'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
