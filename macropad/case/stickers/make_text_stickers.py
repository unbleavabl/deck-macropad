#!/usr/bin/env python3
"""Text legend stickers for the 12 keys on DSA keycaps, laid out as on the pad: one set
per text size in SIZES, side by side, size printed above each.

Writes text_yellow.{svg,pdf,png} and text_black.{svg,pdf,png} (A4, 1:1 mm).
Print at 100% / "actual size", no "fit to page". Each sticker is an 11 mm square
(DSA 1u top is ~12.7 mm with a dish); the thin grey outline is the cut line.
Yellow is pure process yellow (C0 M0 Y100 K0) for dark caps; black for grey or
light caps. Edit LEGENDS to match ~/.config/deckd/config.toml.
"""
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

FONT = "DejaVu Sans"
CUT = "#999999"
INKS = {"yellow": ("#FFFF00", "#222"), "black": ("#000000", "#9a9a9a")}  # ink, preview background

PAGE_W, PAGE_H = 210, 297
STICKER = 11.0
SIZES = [2.2, 1.9, 1.6, 1.3]  # mm, one set per size, side by side; 2.2: 5 letters is ~8 mm wide
SET_GAP = 8.0
GAP = 4.0
MARGIN = 15.0

# One line per row of text; as on the pad, K1 top left.
LEGENDS = [
    [["Caps", "Ctrl"], ["Snip"], ["Clip", "board"]],
    [["Calc"], ["Mic", "mute"], ["Audio", "out"]],
    [["Rec"], ["OCR"], ["Color", "pick"]],
    [["Voice"], ["DND"], ["Awake"]],
]


def sticker(x, y, lines, ink, size):
    out = [f'<rect x="{x}" y="{y}" width="{STICKER}" height="{STICKER}" rx="1.2" '
           f'fill="none" stroke="{CUT}" stroke-width="0.1"/>']
    lead = size * 1.15
    cx, cy = x + STICKER / 2, y + STICKER / 2
    top = cy - lead * (len(lines) - 1) / 2 + size * 0.36
    for i, s in enumerate(lines):
        out.append(f'<text x="{cx:.2f}" y="{top + i * lead:.2f}" font-family="{FONT}" '
                   f'font-weight="bold" font-size="{size:.2f}" fill="{ink}" '
                   f'text-anchor="middle">{escape(s)}</text>')
    return out


def main():
    here = Path(__file__).parent
    pitch = STICKER + GAP
    for name, (ink, bg) in INKS.items():
        body = []
        set_w = len(LEGENDS[0]) * pitch - GAP + SET_GAP
        for k, size in enumerate(SIZES):
            x0 = MARGIN + k * set_w
            body.append(f'<text x="{x0}" y="{MARGIN - 3}" font-family="{FONT}" font-size="2.5" '
                        f'fill="#000">{size} mm</text>')
            for r, row in enumerate(LEGENDS):
                for c, lines in enumerate(row):
                    body += sticker(x0 + c * pitch, MARGIN + r * pitch, lines, ink, size)
        body.append(f'<text x="{MARGIN}" y="{MARGIN + len(LEGENDS) * pitch + 4}" '
                    f'font-family="{FONT}" font-size="3" fill="#000">macropad legends. '
                    f'Print at 100%. Squares are {STICKER} mm.</text>')
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
               f'viewBox="0 0 {PAGE_W} {PAGE_H}">\n' + "\n".join(body) + "\n</svg>\n")
        stem = here / f"text_{name}"
        stem.with_suffix(".svg").write_text(svg)
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", f"{stem}.pdf", f"{stem}.svg"], check=True)
        subprocess.run(["rsvg-convert", "-d", "300", "-p", "300", "-b", bg,
                        "-o", f"{stem}.png", f"{stem}.svg"], check=True)
        print(f"wrote {stem.name}.svg/.pdf/.png")


if __name__ == "__main__":
    main()
