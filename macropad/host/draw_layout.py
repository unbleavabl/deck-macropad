#!/usr/bin/env python3
"""Draw layout.png from the deckd config: what every key, knob and slider does.
Reads ~/.config/deckd/config.toml if present, else config.toml here. Run after editing it."""

import tomllib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
CONFIG = Path.home() / ".config/deckd/config.toml"
OUT = HERE / "layout.png"
FONT = "/usr/share/fonts/TTF/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"

BG, PANEL, INK, MUTED, EDGE, ACCENT = "#ffffff", "#f3f4f6", "#111827", "#6b7280", "#9ca3af", "#2563eb"
KNOB_TEXT = {
    "media": ("Seek - / + 5 s", "push: play/pause · hold+turn: track", "Track title", "1:23"),
    "nightlight": ("Night light cooler / warmer", "push: on / off", "NIGHT LIGHT", "4000K"),
}
SLIDER_TEXT = {
    "master": "output volume",
    "focused": "focused app volume",
    "brightness": "monitor brightness",
    "mic": "mic volume",
    "apps": "app volume",
}
S = 2  # supersample


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size * S)


def text(d, xy, s, size, color=INK, bold=False, anchor="mm"):
    d.text((xy[0] * S, xy[1] * S), s, font=font(size, bold), fill=color, anchor=anchor)


def wrap(s, size, width, bold=False):
    """Split s into lines that fit width px."""
    f, lines, line = font(size, bold), [], ""
    for w in s.split():
        t = f"{line} {w}".strip()
        if f.getlength(t) / S > width and line:
            lines.append(line)
            line = w
        else:
            line = t
    return lines + [line]


def box(d, x0, y0, x1, y1, fill, outline=EDGE, r=8, width=1):
    d.rounded_rectangle((x0 * S, y0 * S, x1 * S, y1 * S), r * S, fill=fill, outline=outline, width=width * S)


def screen(d, x, y, w, h, title, value):
    box(d, x, y, x + w, y + h, "#0b0f19", "#0b0f19", r=4)
    text(d, (x + 5, y + 4), title, 9, "#e5e7eb", anchor="la")
    text(d, (x + w / 2, y + h - 13), value, 14, "#e5e7eb", bold=True)


def main():
    path = CONFIG if CONFIG.exists() else HERE / "config.toml"
    cfg = tomllib.load(open(path, "rb"))
    keys, knobs, sliders = cfg.get("keys", {}), cfg.get("knob", {}), cfg.get("slider", [])

    W, H = 900, 560
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)
    text(d, (24, 30), "Macropad", 26, INK, bold=True, anchor="lm")
    text(d, (24, 56), f"from {path.name if path.parent == HERE else '~/.config/deckd/config.toml'}"
         " — the pad sends everything to deckd, which runs what the config says", 12, MUTED, anchor="lm")
    ox, oy = 20, 78
    box(d, ox, oy, W - 20, oy + 440, PANEL, PANEL, r=14)
    top = oy + 24

    # sliders S1-S3 with their screens in front
    for i, s in enumerate(sliders[:3]):
        x = ox + 24 + i * 76
        box(d, x + 30, top, x + 38, top + 270, "#d1d5db", "#d1d5db", r=4)
        box(d, x + 20, top + 120, x + 48, top + 136, "#374151", "#374151", r=3)
        label = s.get("label", s["target"].upper())
        text(d, (x + 34, top + 290), label, 10, INK, bold=True)
        for j, line in enumerate(wrap(SLIDER_TEXT.get(s["target"], s["target"]), 9, 70)):
            text(d, (x + 34, top + 305 + j * 12), line, 9, MUTED)
        screen(d, x + 4, top + 336, 62, 48, f"S{i + 1}", "42%")

    # keys 3 x 4
    kx, kw, kh, gap = ox + 268, 132, 82, 8
    for r in range(4):
        for c in range(3):
            n = f"K{r * 3 + c + 1}"
            k = keys.get(n, {})
            x, y = kx + c * (kw + gap), top + r * (kh + gap)
            box(d, x, y, x + kw, y + kh, "#ffffff", ACCENT if k else EDGE, width=2 if k else 1)
            text(d, (x + 7, y + 6), n, 9, MUTED, anchor="la")
            lines = wrap(k.get("label", "—"), 13, kw - 12, bold=True)
            y0 = y + kh / 2 - (len(lines) - 1) * 8 + 4
            for j, line in enumerate(lines):
                text(d, (x + kw / 2, y0 + j * 16), line, 13, INK if k else MUTED, bold=True)

    # knob column: E2, S5, E1, S4 (front)
    ex = ox + 768

    def knob(cy, name, scr_y, scr):
        k = knobs.get(name)
        turn, push, title, value = KNOB_TEXT.get(k["type"], (k.get("label", "commands"), "push: command", k.get("label", ""), k.get("text", ""))) if k else ("—", "", "", "")
        d.ellipse(((ex - 28) * S, (cy - 28) * S, (ex + 28) * S, (cy + 28) * S), fill="#ffffff", outline=ACCENT, width=2 * S)
        text(d, (ex, cy), name, 15, INK, bold=True)
        for j, line in enumerate(wrap(turn, 11, 150, bold=True)):
            text(d, (ex, cy + 42 + j * 14), line, 11, ACCENT, bold=True)
        text(d, (ex, cy + 42 + len(wrap(turn, 11, 150, True)) * 14), push, 10, MUTED)
        screen(d, ex - 40, scr_y, 80, 48, f"{scr} {title}", value)

    knob(top + 34, "E2", top + 132, "S5")
    knob(top + 222, "E1", top + 336, "S4")

    text(d, (24, H - 22), "Flash: `deckd.py boot`, or hold both knob pushes for 1 s.   Redraw: host/draw_layout.py",
         12, MUTED, anchor="lm")
    img.resize((W, H), Image.LANCZOS).save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
