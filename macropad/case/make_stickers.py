#!/usr/bin/env python3
"""Sticker sheets with the key icons, A4, 600 dpi, print at 100% / actual size (PNG previews
beside them):

    stickers/stickers.pdf        white sticker paper, on any label
    stickers/stickers_clear.pdf  clear sticker film, on white labels (label_blank in white)

Each sticker is a black square with the white icon, the same icon and size as on the printed
labels, a little smaller than the label face so its edges don't lift. The paper is the
white: only the black is printed, so any printer does it. The black runs BLEED past
each cut line (marked by an unprinted hairline), so cutting slightly off the line still
leaves a black edge on the black cap. Sets are laid out like
the pad (K1 top left). Icons are read from the `legends` list in scad/keycaps.scad, so the
sheet follows any change there. A 50 mm bar at the bottom checks the print scale.

Clear film has no white, so the icon is left clear and the white label under it shows
through; the black ink covers the rest. Those stickers are oversized (the label face plus
CLEAR_BLEED each side, no cut line): stick one on, then trim it flush with the label's
edge with a craft knife, so no white ring is left round it in the black cap."""

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SCAD = HERE / "scad/keycaps.scad"
FONT = HERE / "scad/fonts/DeckIcons.ttf"
TEXT_FONT = "/usr/share/fonts/TTF/DejaVuSans.ttf"
OUT = HERE / "stickers"

DPI = 600
PAGE = (210, 297)       # A4, mm
MARGIN = 12
STICKER = 14.6          # label face is 15.1; a bit under so the edges don't lift
CORNER = 0.75           # the label's corner radius
ICON = 11               # Material Symbols live area (20/24 em), as icon_size in keycaps.scad
BLEED = 1.0             # black past the cut line, so a cut a little outside still has a black edge
GUIDE = 0.12            # unprinted hairline on the cut line
GAP = 4.0               # between cut lines: 2 x bleed + a little paper
SET_GAP = 8.0           # between sets
SETS = (3, 3)           # sets across, down
LABEL_FACE = 15.1       # label top: pocket 15.2 less label_tol each side
CLEAR_BLEED = 1.5       # clear-film stickers: black past the label edge, trimmed off on the label
CLEAR_GAP = 2.0
CLEAR_SETS = (3, 2)


def mm(v):
    return round(v * DPI / 25.4)


def legends():
    """The 12 legends from keycaps.scad: ("icon", char) or ("text", string)."""
    src = SCAD.read_text()
    block = src[src.index("legends = ["):]
    block = block[:block.index("];")]
    out = []
    for kind, val in re.findall(r'\["(icon|text|calc)",\s*"((?:[^"\\]|\\.)*)"\]', block):
        if kind == "icon":
            val = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), val)
        out.append((kind, val))
    assert len(out) == 12, out
    return out


def calc(d, cx, cy):
    """The calculator drawn like calc_2d in keycaps.scad (white square, black - x + =)."""
    src = SCAD.read_text()
    v = {k: float(re.search(rf"^{k} = ([0-9.]+);", src, re.M).group(1))
         for k in ("calc_slot", "calc_arm", "calc_bar", "calc_pos", "calc_r", "icon_size")}
    h = v["icon_size"] / 2
    d.rounded_rectangle((mm(cx - h), mm(cy - h), mm(cx + h), mm(cy + h)), radius=mm(v["calc_r"]), fill=255)
    w, L, p = v["calc_slot"], v["calc_arm"], v["calc_pos"]

    def bar(x, y, ang):
        import math
        dx, dy = math.cos(math.radians(ang)) * (L - w) / 2, math.sin(math.radians(ang)) * (L - w) / 2
        d.line((mm(x - dx), mm(y - dy), mm(x + dx), mm(y + dy)), fill=0, width=mm(w))
        for ex, ey in ((x - dx, y - dy), (x + dx, y + dy)):
            d.ellipse((mm(ex - w / 2), mm(ey - w / 2), mm(ex + w / 2), mm(ey + w / 2)), fill=0)

    bar(cx - p, cy - p, 0)                                   # -   (page y runs down)
    bar(cx + p, cy - p, 45), bar(cx + p, cy - p, -45)        # x
    bar(cx - p, cy + p, 0), bar(cx - p, cy + p, 90)          # +
    for s in (-1, 1):                                        # =
        bar(cx + p, cy + p + s * (w + v["calc_bar"]) / 2, 0)


def sheet(clear):
    """clear=False: white paper, cut on the hairlines. clear=True: clear film, oversized."""
    img = Image.new("L", (mm(PAGE[0]), mm(PAGE[1])), 255)
    d = ImageDraw.Draw(img)
    em = mm(ICON * 24 / 20)                       # icon font size: the live area is 20/24 em
    icon_font = ImageFont.truetype(str(FONT), em)
    small = ImageFont.truetype(TEXT_FONT, mm(2.6))
    text_font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", mm(4.5))
    # centre icons on the font's em square, as the printed labels do: a round icon
    # (do_not_disturb_on fills 20/24 of it) sets the offset for all of them
    bx = d.textbbox((0, 0), "", font=icon_font)
    off = ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)

    if clear:
        face, bleed, gap, sets = LABEL_FACE, CLEAR_BLEED, CLEAR_GAP, CLEAR_SETS
        note = "Clear film: stick on a white label, trim flush with its edge."
    else:
        face, bleed, gap, sets = STICKER, BLEED, GAP, SETS
        note = "Cut on the thin white lines."
    pitch = face + 2 * bleed + gap
    set_w, set_h = 3 * pitch - gap, 4 * pitch - gap + 4    # + room for the caption
    total_w = sets[0] * set_w + (sets[0] - 1) * SET_GAP
    x0 = (PAGE[0] - total_w) / 2
    y0 = MARGIN + 8
    d.text((mm(PAGE[0] / 2), mm(MARGIN)), f"Macropad key stickers: print at 100% (actual size), check the 50 mm bar. {note}",
           font=small, fill=0, anchor="mt")
    items = legends()
    n = 0
    for sy in range(sets[1]):
        for sx in range(sets[0]):
            n += 1
            ox = x0 + sx * (set_w + SET_GAP)
            oy = y0 + sy * (set_h + SET_GAP)
            d.text((mm(ox), mm(oy)), f"set {n}   K1 top left, as on the pad", font=small, fill=110, anchor="lt")
            for i, (kind, val) in enumerate(items):
                cx = ox + bleed + (i % 3) * pitch + face / 2
                cy = oy + 4 + bleed + (i // 3) * pitch + face / 2
                h = face / 2 + bleed
                d.rectangle((mm(cx - h), mm(cy - h), mm(cx + h), mm(cy + h)), fill=0)
                if not clear:
                    h = face / 2
                    d.rounded_rectangle((mm(cx - h), mm(cy - h), mm(cx + h), mm(cy + h)),
                                        radius=mm(CORNER), outline=255, width=max(1, mm(GUIDE)))
                if kind == "icon":
                    d.text((mm(cx) - off[0], mm(cy) - off[1]), val, font=icon_font, fill=255)
                elif kind == "calc":
                    calc(d, cx, cy)
                else:
                    d.text((mm(cx), mm(cy)), val, font=text_font, fill=255, anchor="mm")
    # scale check
    by = PAGE[1] - MARGIN - 4
    bx0 = (PAGE[0] - 50) / 2
    d.rectangle((mm(bx0), mm(by), mm(bx0 + 50), mm(by + 1)), fill=0)
    for t in (0, 10, 20, 30, 40, 50):
        d.rectangle((mm(bx0 + t) - 2, mm(by - 1.5), mm(bx0 + t) + 2, mm(by + 1)), fill=0)
    d.text((mm(PAGE[0] / 2), mm(by + 2)), "50 mm", font=small, fill=0, anchor="mt")

    name = "stickers_clear" if clear else "stickers"
    img.save(OUT / f"{name}.pdf", resolution=DPI)
    img.resize((img.width // 6, img.height // 6), Image.LANCZOS).save(OUT / f"{name}.png")
    print(f"== stickers/{name}.pdf: {sets[0] * sets[1]} sets of 12, {face} mm + {bleed} bleed")


def main():
    OUT.mkdir(exist_ok=True)
    sheet(False)
    sheet(True)


if __name__ == "__main__":
    main()
