#!/usr/bin/env python3
"""Draw preview/assembly.png: the deck exploded, every part labelled with its STL.

Renders scad/exploded.scad once for the picture, then once per part
with the same camera to find where that part lands, and puts its file name in
the margin with a line to it. Run from anywhere; needs openscad and Pillow.
"""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SCAD = HERE / "scad" / "exploded.scad"
OUT = HERE / "preview" / "assembly.png"
SIZE = 1000
MARGIN = 400
FONT = "/usr/share/fonts/TTF/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/TTF/DejaVuSansMono.ttf"

PANELS = [
    {
        "view": "deck", "title": "Tilted deck",
        "camera": "89,35,60,60,0,30,700",
        "parts": [
            ("fader_cap", "knobs-caps/fader_cap.stl", "x3", "slider caps", "left"),
            ("knob", "knobs-caps/knob.stl", "x2", "encoder knobs", "left"),
            ("deck_plate", "deck/deck_plate.stl", "x1", "top plate, 4 screws", "right"),
            ("deck_dock", "deck/deck_dock.stl", "x1", "phone dock: slot + strip, 2 screws", "right"),
            ("deck_frame", "deck/deck_frame.stl", "x1", "walls, notched for the dock", "right"),
            ("deck_lid", "deck/deck_lid.stl", "x1", "lid: BlackPill, BOOT0 + reset buttons", "right"),
        ],
    },
]


def render(view, camera, only, path):
    subprocess.run(["openscad", "-q", "--render", "-D", f'view="{view}"', "-D", f'only="{only}"',
                    f"--imgsize={SIZE},{SIZE}", "--colorscheme=Tomorrow", f"--camera={camera}",
                    "-o", str(path), str(SCAD)], check=True)
    return Image.open(path).convert("RGB")


def part_anchors(part, scene, count):
    """One point per visible copy of the part: its pixels that the full scene
    still shows (not hidden behind other parts), split into connected blobs,
    biggest `count` blobs, each as its list of inner points."""
    bg = part.getpixel((2, 2))
    pp, sp = part.load(), scene.load()
    g = 3
    vis = {(x, y) for y in range(0, SIZE, g) for x in range(0, SIZE, g)
           if sum(abs(a - b) for a, b in zip(pp[x, y], bg)) > 30
           and sum(abs(a - b) for a, b in zip(pp[x, y], sp[x, y])) < 12}
    blobs, seen = [], set()
    for start in vis:
        if start in seen:
            continue
        blob, todo = [], [start]
        seen.add(start)
        while todo:
            x, y = todo.pop()
            blob.append((x, y))
            for n in ((x + g, y), (x - g, y), (x, y + g), (x, y - g)):
                if n in vis and n not in seen:
                    seen.add(n)
                    todo.append(n)
        blobs.append(blob)
    blobs.sort(key=len, reverse=True)
    out = []
    for blob in blobs[:count]:
        # keep points at least 3 grid steps inside the blob, so a line never ends on an edge
        inner = set(blob)
        for _ in range(3):
            inner = {(x, y) for x, y in inner
                     if all(q in inner for q in ((x + g, y), (x - g, y), (x, y + g), (x, y - g)))}
        out.append(sorted(inner or blob))
    return out


def main():
    f_title = ImageFont.truetype(BOLD, 40)
    f_file = ImageFont.truetype(MONO, 24)
    f_note = ImageFont.truetype(FONT, 21)
    f_foot = ImageFont.truetype(FONT, 22)
    top, foot = 110, 190
    W, H = len(PANELS) * SIZE + (len(PANELS) + 1) * MARGIN, SIZE + top + foot  # a margin each side of each panel
    canvas = Image.new("RGB", (W, H), (248, 248, 248))
    d = ImageDraw.Draw(canvas)

    with tempfile.TemporaryDirectory() as tmp:
        for i, panel in enumerate(PANELS):
            ox = MARGIN + i * (SIZE + MARGIN)
            scene = render(panel["view"], panel["camera"], "all", Path(tmp) / "scene.png")
            canvas.paste(scene, (ox, top))
            d.text((ox + SIZE / 2, 45), panel["title"], font=f_title, fill=(30, 30, 30), anchor="mm")

            anchors = []  # per part: one list of candidate points per visible copy
            for prt in panel["parts"]:
                only, count = prt[0], prt[2]
                pieces = prt[5] if len(prt) > 5 else int(count[1:])  # separate pieces to point at
                part = render(panel["view"], panel["camera"], only, Path(tmp) / f"{only}.png")
                pts = part_anchors(part, scene, pieces)
                anchors.append([[(ox + x, top + y) for x, y in blob] for blob in pts])

            # labels stacked in the margin beside the panel, each side in the
            # same top-to-bottom order as its parts
            for side in ("left", "right"):
                ks = [k for k, prt in enumerate(panel["parts"]) if prt[4] == side]
                mid = lambda k: sum(y for blob in anchors[k] for _, y in blob) / sum(len(b) for b in anchors[k])
                ks.sort(key=mid)
                step = SIZE / (len(ks) + 1)
                for slot, k in enumerate(ks):
                    _, fname, count, note = panel["parts"][k][:4]
                    ly = top + step * (slot + 1)
                    if side == "left":
                        tx, end_x, anchor = ox - MARGIN + 30, ox - 20, "la"
                    else:
                        tx, end_x, anchor = ox + SIZE + MARGIN - 30, ox + SIZE + 20, "ra"
                    head = f"{fname}  {count}"
                    d.text((tx, ly - 30), head, font=f_file, fill=(20, 20, 20), anchor=anchor)
                    d.text((tx, ly + 2), note, font=f_note, fill=(90, 90, 90), anchor=anchor)
                    # the line starts just past the label text
                    tw = max(d.textlength(head, font=f_file), d.textlength(note, font=f_note)) + 14
                    end_x = tx + tw if side == "left" else tx - tw
                    for blob in anchors[k]:
                        # the point of this copy nearest the label: short lines, few crossings
                        ax, ay = min(blob, key=lambda q: (q[0] - end_x) ** 2 + (q[1] - ly) ** 2)
                        d.line([(end_x, ly - 14), (ax, ay)], fill=(60, 60, 60), width=3)
                        d.ellipse([ax - 7, ay - 7, ax + 7, ay + 7], fill=(255, 255, 255), outline=(60, 60, 60), width=3)

    lines = [
        "Every STL is in case/stl/. Exploded along the direction each part goes on; screws and electronics not shown.",
        "Made from: scad/deck.scad -> deck/*   scad/parts.scad -> knobs-caps/*, fit-tests/*   (scad/common.scad: shared sizes)",
        "Print first: fit-tests/fit_switch_encoder.stl, fit_screen.stl, fit_knob_caps.stl. Also print knobs-caps/enc_spacer.stl x2.",
    ]
    for j, line in enumerate(lines):
        d.text((W / 2, top + SIZE + 45 + j * 42), line, font=f_foot, fill=(60, 60, 60), anchor="mm")

    OUT.parent.mkdir(exist_ok=True)
    canvas.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
