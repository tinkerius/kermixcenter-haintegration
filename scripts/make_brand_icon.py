#!/usr/bin/env python3
"""Render the integration's brand icon (original artwork, not Kermi's logo).

A white house outline with a heat-pump fan on a warm-to-cool gradient (heating /
cooling). Drawn on a supersampled canvas and downscaled for smooth edges.

Usage::

    python3 scripts/make_brand_icon.py  # writes custom_components/kermixcenter/brand/

Requires Pillow (installed with Home Assistant).
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = REPO_ROOT / "custom_components" / "kermixcenter" / "brand"

N = 2048  # supersampled canvas size
OUTPUTS = ((256, "icon.png"), (512, "icon@2x.png"))

WARM = (251, 140, 0)  # heating
MID = (216, 27, 96)  # vivid midpoint (a 2-stop blend turns grey)
COOL = (25, 118, 210)  # cooling

Color = tuple[int, int, int]
Point = tuple[float, float]


def _lerp(a: Color, b: Color, t: float) -> Color:
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def _gradient() -> Image.Image:
    """Diagonal 3-stop gradient, top-left warm -> bottom-right cool."""
    img = Image.new("RGB", (N, N))
    px = img.load()
    for y in range(N):
        for x in range(N):
            t = (x + y) / (2 * (N - 1))
            px[x, y] = (
                _lerp(WARM, MID, t * 2) if t < 0.5 else _lerp(MID, COOL, t * 2 - 1)  # noqa: PLR2004
            )
    return img


def _dot(draw: ImageDraw.ImageDraw, p: Point, diameter: float) -> None:
    r = diameter / 2
    draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=255)


def _draw_house(draw: ImageDraw.ImageDraw, width: int) -> None:
    """House outline as one path; the walls meet the roof line."""
    cx = N / 2
    top, roof_end, bottom = N * 0.17, N * 0.50, N * 0.82
    half_roof, half_wall = N * 0.35, N * 0.25
    wall_top = top + (roof_end - top) * (half_wall / half_roof)
    path = [
        (cx - half_roof, roof_end),
        (cx - half_wall, wall_top),
        (cx - half_wall, bottom),
        (cx + half_wall, bottom),
        (cx + half_wall, wall_top),
        (cx + half_roof, roof_end),
    ]
    draw.line([*path[:2], (cx, top), *path[4:]], fill=255, width=width, joint="curve")
    draw.line(path[1:5], fill=255, width=width, joint="curve")
    for p in (path[0], path[-1], path[2], path[3]):
        _dot(draw, p, width)


def _draw_fan(draw: ImageDraw.ImageDraw, width: int) -> None:
    """Three swept blades, a hub and a ring, centred inside the house."""
    fx, fy = N / 2, N * 0.595
    radius = N * 0.115
    hub = radius * 0.22
    steps = 40
    for k in range(3):
        a0 = math.radians(-90 + k * 120)
        lead: list[Point] = []
        trail: list[Point] = []
        for i in range(steps + 1):
            t = i / steps
            r = hub + (radius - hub) * t
            sweep = math.radians(35) * t
            spread = math.radians(62) * math.sin(math.pi * t) ** 0.8 * (1 - 0.35 * t)
            lead.append((fx + r * math.cos(a0 + sweep), fy + r * math.sin(a0 + sweep)))
            trail.append(
                (
                    fx + r * math.cos(a0 + sweep + spread),
                    fy + r * math.sin(a0 + sweep + spread),
                )
            )
        draw.polygon(lead + trail[::-1], fill=255)
    _dot(draw, (fx, fy), hub * 2.5)
    ring = radius * 1.33
    draw.ellipse(
        [fx - ring, fy - ring, fx + ring, fy + ring],
        outline=255,
        width=int(width * 0.55),
    )


def render() -> Image.Image:
    """Return the full-size RGBA icon."""
    tile_mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(tile_mask).rounded_rectangle(
        [0, 0, N - 1, N - 1], radius=int(N * 0.22), fill=255
    )

    art = Image.new("L", (N, N), 0)
    draw = ImageDraw.Draw(art)
    stroke = int(N * 0.055)
    _draw_house(draw, stroke)
    _draw_fan(draw, stroke)

    white = Image.new("RGB", (N, N), (255, 255, 255))
    tile = Image.composite(white, _gradient(), art)
    icon = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    icon.paste(tile, (0, 0), tile_mask)
    return icon


def main() -> None:
    """Write icon.png and icon@2x.png into the integration's brand/ directory."""
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    icon = render()
    for size, name in OUTPUTS:
        icon.resize((size, size), Image.Resampling.LANCZOS).save(
            BRAND_DIR / name, optimize=True
        )
        print(f"wrote {BRAND_DIR / name}")


if __name__ == "__main__":
    main()
