"""Layout preview: deckd draws the five screens itself and sends them as whole frames, so layouts
can be tried without reflashing. Temporary: it costs USB traffic all the time it runs.

On:  deckd.py preview on [layout]      Off: deckd.py preview off
While on, turning E1 (the media knob) steps through the layouts; its screen names the new one for
a moment. The last entry, "pad", hands the screens back to the firmware's own drawing.

The flag file (~/.config/deckd/preview, holding the layout name) is how the CLI talks to the
running daemon. Frames go out as 28-byte chunks (only the ones that changed) and a "show" report
per screen (firmware protocol 7, 0x06 / 0x07); a screen that hears nothing for 2 s goes back to
the firmware's drawing, so stopping the daemon can't leave a screen frozen.

Icons are the firmware's own: the icon code is cut out of deck/screens.c and built with gcc."""
import ctypes
import math
import subprocess
import threading
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
SCREENS_C = HERE.parent / "firmware/deck/screens.c"
FLAG = Path.home() / ".config/deckd/preview"
CACHE = Path.home() / ".cache/deckd"
FPS = 8
CHUNK = 28
BUDGET = 60  # chunk reports per frame at most (~480/s); screens over it wait their turn
NAME_S = 1.5  # how long E1 shows a new layout's name
HIST_S = 0.5  # history: a sample this often

T = "/usr/share/fonts/TTF/"
FONTS = {"s": (T + "RobotoCondensed-Bold.ttf", 13), "sb": (T + "RobotoCondensed-Bold.ttf", 16),
         "b": (T + "Roboto-Bold.ttf", 26), "m": (T + "Roboto-Bold.ttf", 19), "n": (T + "Roboto-Bold.ttf", 16),
         "x44": (T + "Roboto-Black.ttf", 44), "x36": (T + "Roboto-Black.ttf", 36), "x30": (T + "Roboto-Black.ttf", 30)}
_fonts = {}


def font(k):
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(*FONTS[k])
    return _fonts[k]


def icon_lib():
    """The firmware's icon drawing as a shared library: render(icon, t_ms, value, out[32*32])
    draws the icon centred on (16, 16), as screens.c centres it."""
    so = CACHE / "libicons.so"
    if so.exists() and so.stat().st_mtime > SCREENS_C.stat().st_mtime:
        return ctypes.CDLL(str(so))
    src = SCREENS_C.read_text()
    body = src[src.index("// ---- pixels into"):src.index("// ---- text")]
    CACHE.mkdir(parents=True, exist_ok=True)
    c = CACHE / "libicons.c"
    c.write_text(f'''#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "{SCREENS_C.parent}/screens.h"
static uint8_t frame[128 * 64 / 8];
{body}
void render(int ic, unsigned t, int value, unsigned char *out) {{
    memset(frame, 0, sizeof frame);
    org_x = 8 + ICON_NUDGE[ic][0];
    org_y = 8 + ICON_NUDGE[ic][1];
    draw_icon(ic, t, value);
    for (int y = 0; y < 32; y++)
        for (int x = 0; x < 32; x++) {{
            int n = y * 128 + x;
            out[y * 32 + x] = frame[n / 8] >> (n % 8) & 1;
        }}
}}
''')
    subprocess.run(["gcc", "-O1", "-w", "-shared", "-fPIC", "-o", str(so), str(c), "-lm"], check=True)
    return ctypes.CDLL(str(so))


class Canvas:
    """128x64, 0 / 255. XOR draws invert what is under them (the liquid fill)."""

    def __init__(self, lib, t):
        self.im = Image.new("L", (128, 64))
        self.d = ImageDraw.Draw(self.im)
        self.lib, self.t = lib, t

    def _put(self, m, mode):
        if mode == "xor":
            self.im = ImageChops.difference(self.im, m)
            self.d = ImageDraw.Draw(self.im)
        else:
            self.im.paste(255 if mode == "on" else 0, (0, 0), m)

    def text(self, k, s, x, y, anchor="ls", mode="on"):
        m = Image.new("L", (128, 64))
        ImageDraw.Draw(m).text((x, y), s, font=font(k), fill=255, anchor=anchor)
        m = m.point(lambda v: 255 if v > 127 else 0)
        self._put(m, mode)
        return m.getbbox() or (x, y, x, y)

    def tw(self, k, s):
        return font(k).getbbox(s, anchor="ls")[2] if s else 0

    def icon(self, ic, cx, cy, scale=1, mode="on", value=0):
        if not ic:
            return
        buf = (ctypes.c_ubyte * 1024)()
        self.lib.render(ic, self.t, value, buf)
        m = Image.new("L", (128, 64))
        for y in range(32):
            for x in range(32):
                if buf[y * 32 + x]:
                    for a in range(scale):
                        for b in range(scale):
                            X, Y = cx + (x - 16) * scale + a, cy + (y - 16) * scale + b
                            if 0 <= X < 128 and 0 <= Y < 64:
                                m.putpixel((X, Y), 255)
        self._put(m, mode)

    def px(self, x, y):
        if 0 <= x < 128 and 0 <= y < 64:
            self.im.putpixel((x, y), 255)

    def rect(self, x0, y0, x1, y1, fill=True, on=True):
        self.d.rectangle((x0, y0, x1, y1), fill=(255 if on else 0) if fill else None, outline=255 if on else 0)

    def rrect(self, x0, y0, x1, y1, r, fill=True, on=True):
        self.d.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=(255 if on else 0) if fill else None,
                                 outline=255 if on else 0)


def trunc(c, k, t, w):
    while t and c.tw(k, t) > w:
        t = t[:-1]
    return t.rstrip(" -")


def pick(c, st, w):
    """Biggest value font that fits value + unit in w px."""
    for k in ("b", "m", "n"):
        if c.tw(k, st["value"]) + (c.tw("s", st["unit"]) + 2 if st["unit"] else 0) <= w:
            return k
    return "n"


def value_unit(c, st, k, x, y, anchor="l", mode="on"):
    v, u = st["value"], st["unit"]
    w = c.tw(k, v) + (c.tw("s", u) + 2 if u else 0)
    x = x - w // 2 if anchor == "c" else x - w if anchor == "r" else x
    b = c.text(k, v, x, y, mode=mode)
    if u:
        c.text("s", u, x + c.tw(k, v) + 2, b[1], anchor="lt", mode=mode)


# ---- layouts: each draws one screen from st (label, value, unit, bar 0..100 or < 0, icon, sub);
# c.t is the time in ms, for the ones that move on their own

def wedge(c, st):
    """Rising bars like a signal meter, the value big on the left."""
    c.text("s", trunc(c, "s", st["label"], 106), 0, 10)
    c.icon(st["icon"], 119, 7, value=st["bar"])
    value_unit(c, st, pick(c, st, 70), 0, 44)
    if st["sub"]:
        c.text("s", st["sub"], 0, 62)
    n = 10
    on = round(max(st["bar"], 0) * n / 100)
    for k in range(n):
        x, h = 72 + k * 5, 6 + k * 4
        if st["bar"] >= 0 and k < on:
            c.rect(x, 62 - h, x + 3, 62)
        else:
            c.rect(x + 1, 61, x + 2, 62)


def top(c, st, w=106):
    """Title top left, icon top right: the header most layouts share."""
    c.text("s", trunc(c, "s", st["label"], w), 0, 10)
    c.icon(st["icon"], 119, 7, value=max(st["bar"], 0))


def scope(c, st):
    """An oscilloscope trace along the bottom; its height is the value."""
    top(c, st)
    value_unit(c, st, pick(c, st, 80), 0, 38)
    if st["sub"]:
        c.text("s", st["sub"], 127, 38, anchor="rs")
    for x in range(0, 128, 4):
        c.px(x, 54)
    for y in range(44, 64, 4):
        c.px(0, y), c.px(127, y)
    a = max(st["bar"], 0) / 100 * 9
    pts = [(x, 54 - a * math.sin(x * 2 * math.pi / 32 + c.t * 0.006)) for x in range(0, 128, 2)]
    c.d.line(pts, fill=255, width=1)


def flask(c, st):
    """A round flask filling up, its surface rippling."""
    cx, cy, R = 30, 32, 28
    c.d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=255)
    lvl = max(st["bar"], 0) / 100
    surf = cy + R - 2 * (R - 2) * lvl
    if st["bar"] > 0:
        for x in range(cx - R + 2, cx + R - 1):
            ys = surf + 1.6 * math.sin(x * 0.35 + c.t * 0.008)
            for y in range(int(ys), cy + R):
                if (x - cx) ** 2 + (y - cy) ** 2 <= (R - 2) ** 2:
                    c.px(x, y)
    c.icon(st["icon"], cx, cy, mode="xor", value=max(st["bar"], 0))
    X = 64
    c.text("s", trunc(c, "s", st["label"], 127 - X), X, 14)
    value_unit(c, st, pick(c, st, 127 - X), X, 42)
    if st["sub"]:
        c.text("s", st["sub"], X, 58)


def left_col(c, st, w):
    """Title, value and small text down the left, `w` px wide; the icon bottom left if no text."""
    c.text("s", trunc(c, "s", st["label"], w), 0, 12)
    value_unit(c, st, pick(c, st, w), 0, 40)
    if st["sub"]:
        c.text("s", trunc(c, "s", st["sub"], w), 0, 60)
    else:
        c.icon(st["icon"], 8, 54, value=max(st["bar"], 0))


def right_col(c, st, x):
    """Title, value and small text in a column from x to the right edge."""
    c.text("s", trunc(c, "s", st["label"], 127 - x), x, 14)
    value_unit(c, st, pick(c, st, 127 - x), x, 42)
    if st["sub"]:
        c.text("s", trunc(c, "s", st["sub"], 127 - x), x, 58)


def knockout(c, k, s, x, y, anchor="ls"):
    """Text with a dark margin round it, readable over anything."""
    m = Image.new("L", (128, 64))
    ImageDraw.Draw(m).text((x, y), s, font=font(k), fill=255, anchor=anchor)
    m = m.point(lambda v: 255 if v > 127 else 0)
    c._put(m.filter(ImageFilter.MaxFilter(5)), "off")
    c._put(m, "on")


def hourglass(c, st):
    """Sand runs down; the bottom bulb holds the value."""
    cx, top_, neck, bot, hw = 22, 4, 31, 59, 18
    c.rect(2, 1, 42, 2), c.rect(2, 60, 42, 61)
    c.d.line((cx - hw, top_, cx - 1, neck, cx - hw, bot), fill=255)
    c.d.line((cx + hw, top_, cx + 1, neck, cx + hw, bot), fill=255)
    v = max(st["bar"], 0) / 100
    if st["bar"] >= 0:
        yl = bot - 1 - round((bot - neck - 4) * v)  # bottom sand surface
        w = hw * (yl - neck) / (bot - neck) - 1
        c.d.polygon([(cx - w, yl), (cx + w, yl), (cx + hw - 2, bot - 1), (cx - hw + 2, bot - 1)], fill=255)
        yt = neck - 2 - round((neck - top_ - 6) * (1 - v))  # top sand surface
        w = hw * (neck - yt) / (neck - top_) - 1
        if w > 0:
            c.d.polygon([(cx - w, yt), (cx + w, yt), (cx, neck - 1)], fill=255)
        if 0 < v < 1:
            for y in range(neck, yl, 3):
                if (y + c.t // 40) % 3 == 0:
                    c.px(cx, y)
    right_col(c, st, 50)


def ecg(c, st):
    """A heart monitor: the trace is drawn by a sweeping cursor; beats grow with the value."""
    c.icon(st["icon"], 8, 8, value=max(st["bar"], 0))
    vw = c.tw("m", st["value"]) + (c.tw("s", st["unit"]) + 2 if st["unit"] else 0)
    c.text("s", trunc(c, "s", st["label"], 127 - 19 - vw - 4), 19, 13)
    value_unit(c, st, "m", 127, 22, anchor="r")
    if st["sub"]:
        c.text("s", st["sub"], 19, 27)
    A = 4 + 22 * max(st["bar"], 0) / 100 if st["bar"] >= 0 else 0
    base, P = 54, 44

    def y(x):
        p = x % P
        if 4 <= p < 9:
            return base - 2 * math.sin((p - 4) / 5 * math.pi)  # P wave
        if 12 <= p < 14:
            return base + 2 * (p - 12) / 2  # Q
        if 14 <= p < 17:
            return base + 2 - (A + 2) * (p - 14) / 3  # R up
        if 17 <= p < 21:
            return base - A + (A + A / 4) * (p - 17) / 4  # down past the line (S)
        if 21 <= p < 23:
            return base + A / 4 - A / 4 * (p - 21) / 2
        if 28 <= p < 36:
            return base - 3 * math.sin((p - 28) / 8 * math.pi)  # T wave
        return base
    cur = int(c.t * 0.05) % 128
    pts = [(x, y(x)) for x in range(128) if not (cur < x < cur + 10 or cur + 10 - 128 > x)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x1 == x0 + 1:
            c.d.line((x0, y0, x1, y1), fill=255)
    c.rect(cur - 1, int(y(cur)) - 1, cur + 1, int(y(cur)) + 1)


def rain(c, st):
    """Rain falls into a pool as deep as the value."""
    v = max(st["bar"], 0) / 100
    pool = 63 - round(22 * v) if st["bar"] >= 0 else 62
    for x in range(128):
        ys = pool + 1.2 * math.sin(x * 0.25 + c.t * 0.006)
        c.rect(x, int(ys), x, 63)
    n = 8 + round(16 * v)
    for k in range(n):
        x = (k * 53 + 11) % 128
        y = (c.t * 0.06 + k * 37) % (pool + 10) - 6
        c.rect(x, int(y), x, int(y) + 3)
    knockout(c, "s", trunc(c, "s", st["label"], 104), 0, 10)
    c.rect(109, 0, 127, 16, on=False)
    c.icon(st["icon"], 119, 7, value=max(st["bar"], 0))
    vw = c.tw(pick(c, st, 124), st["value"])
    k = pick(c, st, 124)
    knockout(c, k, st["value"], 64 - (vw + (c.tw("s", st["unit"]) + 2 if st["unit"] else 0)) // 2, 38)
    if st["unit"]:
        knockout(c, "s", st["unit"], 64 - (vw + c.tw("s", st["unit"]) + 2) // 2 + vw + 2, 26)
    if st["sub"]:
        c.text("s", st["sub"], 64, 62, anchor="ms", mode="xor")


def orbit(c, st):
    """A moon circles the icon, trailing an arc as long as the value."""
    cx, cy, R = 30, 32, 24
    for a in range(0, 360, 15):
        t = math.radians(a)
        c.px(round(cx + R * math.cos(t)), round(cy + R * math.sin(t)))
    head = (c.t * 0.09) % 360
    if st["bar"] > 0:
        c.d.arc((cx - R, cy - R, cx + R, cy + R), head - 3.4 * st["bar"], head, fill=255, width=2)
    t = math.radians(head)
    mx, my = cx + R * math.cos(t), cy + R * math.sin(t)
    c.d.ellipse((mx - 4, my - 4, mx + 4, my + 4), fill=0)
    c.d.ellipse((mx - 3, my - 3, mx + 3, my + 3), fill=255)
    c.icon(st["icon"], cx, cy, value=max(st["bar"], 0))
    right_col(c, st, 64)


def tide(c, st):
    """Waves fill the screen from the bottom to the value; text turns dark under water."""
    if st["bar"] > 0:
        lvl = 63 - 60 * st["bar"] / 100
        for x in range(128):
            ys = lvl + 2 * math.sin(x * 0.09 + c.t * 0.004) + 1.2 * math.sin(x * 0.23 - c.t * 0.007)
            c.rect(x, max(0, int(ys)), x, 63)
    c.text("s", trunc(c, "s", st["label"], 106), 0, 10, mode="xor")
    c.icon(st["icon"], 119, 7, mode="xor", value=max(st["bar"], 0))
    sw = c.tw("s", st["sub"]) + 6 if st["sub"] else 0
    value_unit(c, st, pick(c, st, 124 - sw), 0, 44, mode="xor")
    if st["sub"]:
        c.text("s", st["sub"], 127, 44, anchor="rs", mode="xor")


def history(c, st):
    """The value over the last 30 s as an area chart, newest on the right."""
    top(c, st)
    sw = c.tw("s", st["sub"]) + 6 if st["sub"] else 0
    value_unit(c, st, pick(c, st, 124 - sw), 0, 32)
    if st["sub"]:
        c.text("s", st["sub"], 127, 32, anchor="rs")
    h = st.get("hist") or []
    for x in range(0, 128, 4):
        c.px(x, 63)
    for k, v in enumerate(h[-64:][::-1]):
        x = 126 - k * 2
        y = 63 - round(25 * v / 100)
        for yy in range(y, 64):
            if yy == y or (x + yy) % 2 == 0:
                c.px(x, yy), c.px(x + 1, yy)


def vu(c, st):
    """An analog needle meter; the needle swings to the value and settles."""
    px_, py_, R = 64, 76, 60
    lo, hi = -140, -40  # degrees, screen y up
    c.text("s", trunc(c, "s", st["label"], 106), 0, 10)
    c.icon(st["icon"], 119, 7, value=max(st["bar"], 0))

    def at(deg, r):
        t = math.radians(deg)
        return px_ + r * math.cos(t), py_ + r * math.sin(t)
    c.d.arc((px_ - R, py_ - R, px_ + R, py_ + R), lo, hi, fill=255)
    c.d.arc((px_ - R, py_ - R, px_ + R, py_ + R), lo + 80, hi, fill=255, width=3)  # the hot end
    for k in range(11):
        d = lo + (hi - lo) * k / 10
        c.d.line((*at(d, R), *at(d, R + (5 if k % 5 == 0 else 3))), fill=255)
    if st["bar"] >= 0:
        d = lo + (hi - lo) * max(0, min(st["needle"], 104)) / 100
        c.d.line((*at(d, 20), *at(d, R + 4)), fill=255, width=1)
    c.rect(0, 47, 127, 63, on=False)
    c.rect(20, 47, 107, 47)
    k = "m" if c.tw("m", st["value"]) + (c.tw("s", st["unit"]) + 2 if st["unit"] else 0) <= 84 else "n"
    value_unit(c, st, k, 64, 63, anchor="c")
    if st["sub"]:
        c.text("s", st["sub"], 127, 63, anchor="rs")


def radar(c, st):
    """A sweeping radar; the blip's distance from the centre is the value."""
    cx, cy, R = 30, 32, 28
    c.d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=255)
    for r in (R // 3, 2 * R // 3):
        for a in range(0, 360, 20):
            t = math.radians(a)
            c.px(round(cx + r * math.cos(t)), round(cy + r * math.sin(t)))
    for k in range(-R, R + 1, 3):
        c.px(cx + k, cy), c.px(cx, cy + k)
    sweep = (c.t * 0.18) % 360
    for k, back in enumerate((0, 6, 12, 18)):
        t = math.radians(sweep - back)
        x1, y1 = cx + R * math.cos(t), cy + R * math.sin(t)
        if k == 0:
            c.d.line((cx, cy, x1, y1), fill=255)
        else:
            for f in range(0, R, 2 + k):
                c.px(round(cx + f * math.cos(t)), round(cy + f * math.sin(t)))
    if st["bar"] >= 0:
        bearing = -50
        age = (sweep - bearing) % 360  # degrees since the beam passed it
        r = 3 if age < 60 else 2 if age < 200 else 1
        t = math.radians(bearing)
        bx, by = cx + R * st["bar"] / 100 * math.cos(t), cy + R * st["bar"] / 100 * math.sin(t)
        c.d.ellipse((bx - r, by - r, bx + r, by + r), fill=255)
    right_col(c, st, 64)


def sprout(c, st):
    """A plant in a pot, as tall as the value, swaying."""
    left_col(c, st, 80)
    c.d.polygon([(92, 53), (120, 53), (116, 63), (96, 63)], fill=255)
    c.rect(90, 51, 122, 53)
    if st["bar"] <= 0:
        return
    h = 4 + 44 * st["bar"] / 100
    sway = 3 * math.sin(c.t * 0.0025) * h / 48
    pts = [(106 + sway * (k / 10) ** 2, 51 - h * k / 10) for k in range(11)]
    c.d.line(pts, fill=255, width=2)
    for k in range(2, 11, 2):
        x, y = pts[k]
        side = 1 if k % 4 else -1
        c.d.ellipse((x + (1 if side > 0 else -8), y - 2, x + (8 if side > 0 else -1), y + 2), fill=255)
    if st["bar"] >= 80:
        x, y = pts[-1]
        for a in range(0, 360, 60):
            t = math.radians(a + c.t * 0.05)
            c.d.ellipse((x + 4 * math.cos(t) - 2, y + 4 * math.sin(t) - 2, x + 4 * math.cos(t) + 2, y + 4 * math.sin(t) + 2), fill=255)
        c.d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=0)


def lissajous(c, st):
    """A Lissajous figure turning in a box; the higher the value, the more knots it ties."""
    left_col(c, st, 62)
    x0, y0, S = 66, 2, 60
    for k in range(0, S + 1, 4):
        c.px(x0 + k, y0), c.px(x0 + k, y0 + S), c.px(x0, y0 + k), c.px(x0 + S, y0 + k)
    v = max(st["bar"], 0)
    a, b = (1, 2) if v < 20 else (2, 3) if v < 45 else (3, 4) if v < 70 else (4, 5) if v < 90 else (5, 6)
    amp = (S / 2 - 3) * (0.3 + 0.7 * v / 100) if st["bar"] >= 0 else 4
    ph = c.t * 0.0012
    pts = [(x0 + S / 2 + amp * math.sin(a * u + ph), y0 + S / 2 + amp * math.sin(b * u))
           for u in [k * 2 * math.pi / 160 for k in range(161)]]
    c.d.line(pts, fill=255)


LAYOUTS = {"wedge": wedge, "scope": scope, "flask": flask, "hourglass": hourglass, "ecg": ecg, "rain": rain,
           "orbit": orbit, "tide": tide, "history": history, "vu": vu, "radar": radar, "sprout": sprout,
           "lissajous": lissajous, "pad": None}
NAMES = list(LAYOUTS)


def split(text):
    """As the firmware does: a number keeps what follows it as a small unit; ` is a degree sign."""
    i = 0
    if text[:1].isdigit() or (text[:1] == "-" and text[1:2].isdigit()):
        i = 1
        while i < len(text) and (text[i].isdigit() or text[i] in ":."):
            i += 1
        return text[:i], text[i:].strip().replace("`", "°")
    return text, ""


class Preview:
    def __init__(self, deck, icons):
        self.deck = deck
        self.icons = icons  # name -> firmware icon number
        self.lib = None
        self.layout = None  # name, or None when off
        self.sent = {}  # screen -> frame bytes the pad has
        self.shown = {}  # screen -> when it last got a "show"
        self.bar = {}  # screen -> eased bar 0..100
        self.named_at = 0.0
        self.hist = {}  # screen -> recent values, one per HIST_S
        self.hist_at = {}
        self.needle = {}  # screen -> [position, speed] (vu)
        self.t0 = time.monotonic()

    @staticmethod
    def set_flag(name):
        FLAG.parent.mkdir(parents=True, exist_ok=True)
        if name:
            FLAG.write_text(name + "\n")
        else:
            FLAG.unlink(missing_ok=True)

    def read_flag(self):
        try:
            name = FLAG.read_text().strip() or NAMES[0]
        except FileNotFoundError:
            return None
        return name if name in LAYOUTS else NAMES[0]

    def step(self, clicks):
        """E1 turned while the preview is on."""
        i = (NAMES.index(self.layout) + clicks) % len(NAMES)
        self.layout = NAMES[i]
        self.set_flag(self.layout)
        self.named_at = time.monotonic()
        self.sent.clear()  # resend everything: the pad may have drawn its own frames meanwhile

    def content(self, i):
        scr = self.deck.sent_screens.get(i)
        if not scr:
            return None
        title, text, bar, icon, info = scr
        if info:
            label, (value, unit), sub = info[1], split(info[0]), text
        else:
            label, (value, unit), sub = title, split(text), ""
        return {"label": label, "value": value, "unit": unit, "bar": bar, "icon": self.icons.get(icon, 0), "sub": sub}

    def frame(self, i, fn, now):
        st = self.content(i)
        if i == 3 and now - self.named_at < NAME_S:
            st = {"label": "LAYOUT %d/%d" % (NAMES.index(self.layout) + 1, len(NAMES)),
                  "value": self.layout.upper(), "unit": "", "bar": -1, "icon": 0, "sub": ""}
            fn = fn or wedge
        if not st:
            return None
        # the bar eases halfway to its value each frame, as on the pad
        if st["bar"] < 0:
            self.bar.pop(i, None)
        else:
            b = self.bar.get(i, 0)
            b += (st["bar"] - b) / 2
            self.bar[i] = b if abs(st["bar"] - b) > 0.5 else st["bar"]
            st["bar"] = round(self.bar[i])
        if st["bar"] >= 0:
            h = self.hist.setdefault(i, [])
            if not h or now - self.hist_at.get(i, 0) >= HIST_S:
                h.append(st["bar"])
                del h[:-64]
                self.hist_at[i] = now
            n = self.needle.setdefault(i, [0.0, 0.0])
            n[1] = (n[1] + (st["bar"] - n[0]) * 0.35) * 0.62  # a spring, damped
            n[0] += n[1]
            st["needle"] = n[0]
        st["hist"] = self.hist.get(i)
        c = Canvas(self.lib, int((now - self.t0) * 1000))
        fn(c, st)
        return c.im.point(lambda v: 255 if v > 127 else 0).convert("1").tobytes("raw", "1;R")

    def changed(self, i, data):
        old = self.sent.get(i)
        return [k for k in range(0, len(data), CHUNK) if old is None or old[k:k + CHUNK] != data[k:k + CHUNK]]

    def push(self, i, data, chunks):
        """Send the chunks of screen i that changed, then show it."""
        for k in chunks:
            self.deck.send(bytes([0x06, i, k // CHUNK]) + data[k:k + CHUNK])
        self.deck.send(bytes([0x07, i]))
        self.sent[i] = data

    def loop(self):
        while True:
            time.sleep(1 / FPS)
            flag = self.read_flag()
            if flag != self.layout:  # set from the CLI
                self.layout = flag
                self.sent.clear()
                self.deck.log_preview(flag)
            if not self.layout or not self.deck.connected.is_set():
                continue
            if self.lib is None:
                try:
                    self.lib = icon_lib()
                except (OSError, subprocess.CalledProcessError) as e:
                    self.deck.log_preview(None, f"icons: {e}")
                    self.set_flag(None)
                    continue
            fn, now = LAYOUTS[self.layout], time.monotonic()
            budget = BUDGET
            self.first = (getattr(self, "first", 0) + 1) % 5  # who goes first rotates, so none starves
            for i in [(self.first + n) % 5 for n in range(5)]:
                data = self.frame(i, fn, now) if fn or (i == 3 and now - self.named_at < NAME_S) else None
                if data is None:
                    continue
                chunks = self.changed(i, data)
                if chunks and len(chunks) > budget and i in self.sent:
                    chunks = []  # over budget: this one keeps its frame until a later turn
                    data = self.sent[i]
                # unchanged frames still get a "show" now and then, so the pad keeps them
                if chunks or now - self.shown.get(i, 0) > 0.5:
                    self.push(i, data, chunks)
                    self.shown[i] = now
                    budget -= len(chunks)
