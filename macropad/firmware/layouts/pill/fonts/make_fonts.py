#!/usr/bin/env python3
"""Build the screen fonts (fonts/font_*.qff.c/.h):
  small  Roboto Condensed Bold 13 px: title, unit, bottom line. Has a degree sign besides ASCII.
  big    Roboto Bold 26 px: the value.
  mid    Roboto Bold 19 px: the value when it doesn't fit big.
Run from anywhere: python3 make_fonts.py (needs qmk and Pillow)."""
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = {  # name: (file, px, extra unicode glyphs)
    "small": ("/usr/share/fonts/TTF/RobotoCondensed-Bold.ttf", 13, "°"),
    "big": ("/usr/share/fonts/TTF/Roboto-Bold.ttf", 26, ""),
    "mid": ("/usr/share/fonts/TTF/Roboto-Bold.ttf", 19, ""),
}


def convert(png, glyphs):
    subprocess.run(["qmk", "painter-convert-font-image", "-i", str(png), "-f", "mono2", "-u", glyphs, "-o", str(HERE)],
                   check=True, capture_output=True)
    for f in HERE.glob(f"{png.stem}.qff.*"):  # the generated header names the output dir
        f.write_text(f.read_text().replace(f"| {HERE}", "| fonts"))


with tempfile.TemporaryDirectory() as tmp:
    for name, (ttf, px, glyphs) in FONTS.items():
        png = Path(tmp) / f"font_{name}.png"
        subprocess.run(["qmk", "painter-make-font-image", "-f", ttf, "-s", str(px), "-u", glyphs, "-o", str(png)],
                       check=True, capture_output=True)
        convert(png, glyphs)
