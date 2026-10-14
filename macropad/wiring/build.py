#!/usr/bin/env python3
"""Generate wiring.html for the tilted deck: everything under the plate, one
encoder close up, the BlackPill pinout with the buttons, a checklist and tests.

Geometry mirrors case/scad/deck.scad (key grid, slider pitch, screens, encoder
column) so the drawing matches the printed plate. Underside view = the deck plate lifted off
and turned over its front-back axis, back edge still away from you, so left and
right are swapped versus the top.
"""
from pathlib import Path

# ---- deck geometry, mm (case/scad/deck.scad, common.scad) ----
PITCH, SIDE_M = 21.0, 5.0
SLIDERS, KEY_COLS, ROWS = 3, 3, 4
POT_PITCH = 26.0
PAD_W = 177.2
BLOCK_B = 73.0          # sliders, centre along the slope
KEY_BLOCK_B = 62.3      # keys, centre along the slope
SCR_B = 27.5            # front screen row
SCR_PCB = (24.5, 26.8)
POT_BODY = (9.0, 60.0)
ENC_GAP, ENC_R = 1.0, 8.5
KEY_NAMES = [[f"K{r * KEY_COLS + c + 1}" for c in range(KEY_COLS)] for r in range(ROWS)]
TOP_B = 118.0           # the drawing shows the plate from the front edge up to here


def slider_a(i):
    return SIDE_M + SCR_PCB[0] / 2 + POT_PITCH * i


# encoder column right of the keys: S4, E1, S5, E2 from the front
ENC_A = PAD_W - SIDE_M - SCR_PCB[0] / 2


def key_a(c):
    """Keys centred between the slider screens and the knob column."""
    return (slider_a(SLIDERS - 1) + ENC_A) / 2 + PITCH * (c - (KEY_COLS - 1) / 2)


def key_b(r):
    return KEY_BLOCK_B + PITCH * ((ROWS - 1) / 2 - r)


# E1 just behind S4; E2 level with the top key row; S5 midway between them
ENC_B = {"E1": SCR_B + SCR_PCB[1] / 2 + ENC_GAP + ENC_R, "E2": key_b(0)}
S5_B = (ENC_B["E1"] + ENC_B["E2"]) / 2


def screens():
    """(a, b) of S1 S2 S3 (under the sliders), S4 (E1) and S5 (E2)."""
    return [(slider_a(i), SCR_B) for i in range(SLIDERS)] + [(ENC_A, SCR_B), (ENC_A, S5_B)]


# ---- BlackPill pin map ----
ROW_PIN = ["A4", "A5", "A6", "B14"]
COL_PIN = ["A7", "A8", "A15", "B0"]                        # COL 3: the two encoder pushes
PUSH_ROW = {"E2": 0, "E1": 2}                              # each push sits on the row nearest it, column 3
ENC_PINS = {"E1": ("B1", "B8"), "E2": ("B9", "A0")}      # (A, B)
POT_PIN = ["A1", "A2", "A3"]                               # wiper (pin 2) of slider 1, 2, 3
SCR_NAMES = ["S1", "S2", "S3", "S4", "S5"]
# 4-pin I2C screens, all at address 0x3C, so each sits on its own channel of a
# TCA9548A multiplexer in the lid; the mux is on I2C1
SCR_CH = [0, 1, 2, 3, 4]
MUX_PINS = {"SCL": "B6", "SDA": "B7"}

# ---- the lid, mm (case/scad/deck.scad): the plate's wires plug onto header pins here ----
import math
DECK_D = 173.2 * math.cos(math.radians(30))
BP_X, BP_W = PAD_W / 2, 21.0
BP_Y1 = DECK_D - 3 - 0.3                # the BlackPill's USB-C end, at the back wall
BP_Y0 = BP_Y1 - 53.2
BTN_POS = [(BP_X + 7, BP_Y0 - 16), (BP_X - 7, BP_Y0 - 16)]    # B, R: B on the BOOT0 side, R on the R pin's side
LID_POSTS = [(7, 24), (PAD_W - 7, 24), (7, DECK_D - 12), (PAD_W - 7, DECK_D - 12)]
MUX = (118.2, 149.2, 112.0, 133.0)      # x0, x1, y0, y1: hot-glued right of the BlackPill (seen from above), near B6/B7
MUX_PAD_X0 = 122.2                      # first channel pad; the pads run along its back edge
MUX_CH = [f"S{d}{c}" for c in range(5) for d in "DC"]
# multi-pin Dupont plugs on the header pins: name, header ("L"/"R" BlackPill, "M" mux), pins in order
PLUGS = [("A", "R", ["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "B0", "B1"]),
         ("B", "M", MUX_CH),
         ("C", "L", ["B8", "B9", None, "G", "3V3"]),       # the 5V pin left empty
         ("D", "L", ["B14", None, "A8"]),                  # B15 left empty
         ("E", "L", ["A15"])]
PLUG_PINS = {n: p for n, _, p in PLUGS}
LID_CUT = 66            # the lid's empty front part, left out of the drawing
FOLD_MM = 30            # slack where the ribbons fold when the case opens
GATHER_MM = 36          # strip above the plate where the wires gather into ribbons
LEVEL_PX = 7
RIB = 1.8               # mm between wires in a ribbon (drawn a little wider than real ribbon, for the numbers)

S = 6.0                 # px per mm in view 1
OX, OY = 190, 210


def vx(a):
    """Plate x (mm from the left, seen from the top) to underside px: mirrored."""
    return OX + (PAD_W - a) * S


def vy(b):
    """Distance up the slope from the front edge to underside px: back at the top."""
    return OY + (TOP_B - b) * S


def f(v):
    return f"{v:.1f}"


def line(x1, y1, x2, y2, cls):
    return f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" class="{cls}"/>'


def poly(pts, cls):
    return f'<polyline points="{" ".join(f"{f(a)},{f(b)}" for a, b in pts)}" class="{cls}"/>'


def text(x, y, s, cls="lbl", anchor="middle"):
    return f'<text x="{f(x)}" y="{f(y)}" class="{cls}" text-anchor="{anchor}">{s}</text>'


def tag(x, y, s, kind, anchor="middle"):
    """Destination pill: a coloured label naming the BlackPill pin a wire goes to."""
    w = 7.2 * len(s) + 16
    x0 = {"middle": x - w / 2, "end": x - w, "start": x}[anchor]
    return (f'<rect x="{f(x0)}" y="{f(y - 11)}" width="{f(w)}" height="20" rx="10" class="tag tag-{kind}"/>'
            + text(x0 + w / 2, y + 3.5, s, f"tagtxt tt-{kind}"))


def dot(x, y, cls):
    return f'<circle cx="{f(x)}" cy="{f(y)}" r="3.4" class="{cls}"/>'


def wire(pts, kind, halo=True):
    """A wire drawn over whatever it crosses, with a gap round it so crossings read as 'not joined'."""
    return ([poly(pts, "halo")] if halo else []) + [poly(pts, f"w w-{kind}")]


def fan(ends, x_tag, y0, step, anchor):
    """Pills stacked `step` apart from y0, each joined by a short leader to its wire end (x, y)."""
    out = []
    for i, (x, y, s, kind) in enumerate(ends):
        ty = y0 + i * step
        out.append(poly([(x, y), (x_tag, ty)], f"w w-{kind}"))
        out.append(tag(x_tag, ty, s, kind, anchor))
    return out


def diode_v(x, y_pin, y_bus):
    """Vertical 1N4148 (px) from a pin to the row bus; band at the bus end."""
    out = [line(x, y_pin, x, y_bus, "w w-row")]
    top, bot = min(y_pin, y_bus), max(y_pin, y_bus)
    h = min(3.2 * S, bot - top - 4)
    y0 = (top + bot) / 2 - h / 2
    band_y = y0 if y_bus < y_pin else y0 + 0.6 * h
    out.append(f'<rect x="{f(x - 6)}" y="{f(y0)}" width="12" height="{f(h)}" rx="2" class="diode"/>')
    out.append(f'<rect x="{f(x - 6)}" y="{f(band_y)}" width="12" height="{f(0.4 * h)}" class="band"/>')
    out.append(f'<rect x="{f(x - 6)}" y="{f(y0)}" width="12" height="{f(h)}" rx="2" class="diode-edge"/>')
    return out


def diode_h(x_pin, y_pin, x_end, y_bus, h=12):
    """Horizontal 1N4148 (px) from a pin to x_end, band at x_end, then a leg up to the bus."""
    out = [poly([(x_pin, y_pin), (x_end, y_pin), (x_end, y_bus)], "w w-row")]
    left, right = min(x_pin, x_end), max(x_pin, x_end)
    w = min(3.6 * S, right - left - 10)
    x0 = (left + right) / 2 - w / 2
    bw = 0.4 * w
    bx = x0 if x_end < x_pin else x0 + w - bw
    out.append(f'<rect x="{f(x0)}" y="{f(y_pin - h / 2)}" width="{f(w)}" height="{f(h)}" rx="2" class="diode"/>')
    out.append(f'<rect x="{f(bx)}" y="{f(y_pin - h / 2)}" width="{f(bw)}" height="{f(h)}" class="band"/>')
    out.append(f'<rect x="{f(x0)}" y="{f(y_pin - h / 2)}" width="{f(w)}" height="{f(h)}" rx="2" class="diode-edge"/>')
    return out


def diode_key_svg():
    """Large 1N4148 as it looks in hand, upright: black band (cathode) at the top, toward the row."""
    cx = 200
    o = [line(cx, 20, cx, 80, "w w-row"), line(cx, 240, cx, 300, "w w-plain"),
         f'<rect x="{cx - 22}" y="80" width="44" height="160" rx="8" class="diode"/>',
         f'<rect x="{cx - 22}" y="80" width="44" height="48" rx="8" class="band"/>',
         f'<rect x="{cx - 22}" y="104" width="44" height="24" class="band"/>',
         f'<rect x="{cx - 22}" y="80" width="44" height="160" rx="8" class="diode-edge"/>',
         text(cx + 40, 108, "black band", "note", "start"),
         text(cx + 40, 190, "red glass body", "note", "start"),
         text(cx + 40, 34, "band end → row bus", "note", "start"),
         text(cx + 40, 294, "plain end → switch pin", "note", "start"),
         text(470, 140, "Current flows switch → row,", "note", "start"),
         text(470, 158, "so the black band is always", "note", "start"),
         text(470, 176, "on the row side.", "note", "start")]
    return ('<svg viewBox="0 0 820 320" role="img" aria-label="A 1N4148 diode standing upright: red glass body with a '
            'black band at the top. The plain end at the bottom goes to the switch pin, the black band end at the top '
            'goes to the row bus.">\n' + "\n".join(o) + "\n</svg>")


def grp(owner, net, items, w=None):
    """Wrap drawing items so the page can filter them: owner = the part they belong to
    ("bus" for the shared copper), net = the bus or signal(s) they carry, space separated,
    w = the harness wire number for wires that cross between plate and lid."""
    if not items:
        return []
    wa = f' data-w="{w}"' if w else ""
    return [f'<g data-o="{owner}" data-n="{net}"{wa}>'] + items + ['</g>']


def rail(x1, y1, x2, y2, kind):
    """A bare copper bus: thick line in the net's colour with a bright core."""
    return [line(x1, y1, x2, y2, f"bus bus-{kind}"), line(x1, y1, x2, y2, "bus-core")]


def sleeve(x, y, vertical):
    """Insulating sleeve where two bare buses cross: drawn on the upper (vertical) bus."""
    w, h = (10, 18) if vertical else (18, 10)
    return f'<rect x="{f(x - w / 2)}" y="{f(y - h / 2)}" width="{w}" height="{h}" rx="3" class="sleeve"/>'


def body(owner, items):
    return grp(owner, "body", items)


def badge(x, y, n, kind):
    """The wire's number, as written on the tape at both of its ends."""
    return (f'<circle cx="{f(x)}" cy="{f(y)}" r="10.5" class="badge badge-{kind}"/>'
            + text(x, y + 4, str(n), f"badgetxt tt-{kind}"))


# power buses, bare copper: a GND and a 3V3 pair across the front (just in front
# of the screens, clear of every board) and across the slider ends; joined by
# two insulated links up the slider-side edge. GND is the outer of each pair.
GND_FRONT, V_FRONT = 11.2, 12.8          # b
GND_BACK, V_BACK = 107.0, 105.8          # b, clear of the slider pins and the dock's screw blocks
GND_LEFT, V_LEFT = 4.0, 5.4              # a, the links' left ends
FRONT_END = ENC_A - 3.81 + 1.5           # a: front rails reach S4's GND and VCC pins
GND_BACK_END, V_BACK_END = 79.0, 80.5    # a: back rails stop past slider 3; their wires to the lid leave here
GAP_GND, GAP_V = 147.0, 146.2            # a: S5's power wires down the gap between keys and knobs


def row_bus_b(r):
    return key_b(r) + (11.5 if r == 1 else 9.5)


def col_a(c):
    return key_a(c) - 3.81


ROW_START = col_a(0) + 2.2
ROW_EXT = 145.4                          # rows 0 and 2 run on into the gap, for the knob pushes
ROW_END = {r: (ROW_EXT if r in PUSH_ROW.values() else key_a(KEY_COLS - 1) + 4.0) for r in range(ROWS)}
COL_WALL = 173.0                         # a: column 3 (an insulated wire) runs up the knob-column wall
GAP = 22          # px between neighbouring harness wires: room for a number badge


def plate_parts():
    """The plate underside: bare copper buses (rows, columns, GND, 3V3), the parts, and the
    insulated jumpers from each part to its buses. Wires that go on to the lid are returned as
    `exits`, each a path that ends at the plate's back edge, without crossing one another."""
    base, buses, over, dots = [], [], [], []
    exits = []
    left, right = vx(PAD_W), vx(0)
    yP = vy(TOP_B)

    def exit_(pts, kind, pin, owner, net, short, frm, to):
        exits.append(dict(x=pts[-1][0], pts=pts, kind=kind, pin=pin, owner=owner, net=net,
                          short=short, frm=frm, to=to))

    base.append(f'<rect x="{f(left)}" y="{f(yP)}" width="{f(PAD_W * S)}" height="{f(TOP_B * S)}" rx="14" class="case"/>')
    base.append(text((left + right) / 2, vy(0) + 34, "PLATE, UPSIDE DOWN · ITS FRONT EDGE", "edge"))
    # the phone dock's two screw blocks under the plate's back corners: keep wires clear
    for a0 in (4.0, PAD_W - 12.0):
        base.append(f'<rect x="{f(vx(a0 + 8))}" y="{f(vy(121.4))}" width="{f(8 * S)}" height="{f((121.4 - 109.0) * S)}" rx="3" class="keepout"/>')
        base.append(text(vx(a0 + 4), vy(113.5), "dock", "pinmini"))
        base.append(text(vx(a0 + 4), vy(111.5), "screw", "pinmini"))

    # ---- key matrix ----
    for r in range(ROWS):
        for c in range(KEY_COLS):
            name = KEY_NAMES[r][c]
            cx, cy = vx(key_a(c)), vy(key_b(r))
            base += body(name, [f'<rect x="{f(cx - 7 * S)}" y="{f(cy - 7 * S)}" width="{f(14 * S)}" height="{f(14 * S)}" rx="3" class="part"/>',
                                text(cx, cy + 4.2 * S, name, "keyname")])
            dx, dy = vx(key_a(c) + 2.54), vy(key_b(r) + 5.08)
            over += grp(name, f"row{r}", diode_v(dx, dy, vy(row_bus_b(r))) + [dot(dx, vy(row_bus_b(r)), "joint j-row")])
            dots += grp(name, f"row{r}", [dot(dx, dy, "joint j-row")])
            dots += grp(name, f"col{c}", [dot(vx(col_a(c)), vy(key_b(r) + 2.54), "joint j-col")])
    for name, b in ENC_B.items():
        cx, cy = vx(ENC_A), vy(b)
        base += body(name, [f'<rect x="{f(cx - 6 * S)}" y="{f(cy - 6 * S)}" width="{f(12 * S)}" height="{f(12 * S)}" rx="3" class="part"/>',
                            f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(3.5 * S)}" class="shaft"/>',
                            text(cx, cy + 0.9 * S, name, "keyname"), text(cx, cy - 4.0 * S, "push", "pinlbl")])

    # row buses; each one's wire to the lid leaves from its end by column 0
    for r in range(ROWS):
        y = vy(row_bus_b(r))
        buses += grp("bus", f"row{r}", rail(vx(ROW_START), y, vx(ROW_END[r]), y, "row")
                     + [text(vx(ROW_END[r]) - 4, y - 6, f"ROW {r}", "busname", "end")])
        lane = vx(col_a(0) - 3.0 - 0.9 * r)
        exit_([(vx(ROW_START), y), (lane, y), (lane, yP)], "row", ROW_PIN[r], "bus", f"row{r}",
              f"Row {r}", f"Row {r} bus, its end by column 0", ROW_PIN[r])
    # column buses, from the front row's pins to the back row's: the switch pins solder straight on
    col_top, col_bot = key_b(0) + 2.54, key_b(ROWS - 1) + 2.54
    for c in range(KEY_COLS):
        x = vx(col_a(c))
        buses += grp("bus", f"col{c}", rail(x, vy(col_top), x, vy(col_bot), "col")
                     + [text(x + 6, vy(col_bot) + 14, f"COL {c}", "busname", "start")])
        exit_([(x, vy(col_top)), (x, yP)], "col", COL_PIN[c], "bus", f"col{c}",
              f"Col {c}", f"Column {c} bus, its back end", COL_PIN[c])
        for r in range(ROWS):
            if col_bot < row_bus_b(r) < col_top:
                buses += grp("bus", f"row{r} col{c}", [sleeve(x, vy(row_bus_b(r)), True)])

    # ---- knob pushes: a diode from the pin nearer the keys to its row bus; the
    # other pin on column 3, an insulated wire up the knob-column wall ----
    xw = vx(COL_WALL)
    ys = {name: vy(b + 7) for name, b in ENC_B.items()}
    over += grp("bus", "col3", wire([(vx(ENC_A + 2.5), ys["E1"]), (xw, ys["E1"]), (xw, ys["E2"]), (vx(ENC_A + 2.5), ys["E2"])], "col")
                + [dot(xw, ys["E2"], "joint j-col")])
    for name, b in ENC_B.items():
        r = PUSH_ROW[name]
        px_row, px_col, py = vx(ENC_A - 2.5), vx(ENC_A + 2.5), ys[name]
        over += grp(name, f"row{r}", diode_h(px_row, py, vx(ROW_EXT), vy(row_bus_b(r))) + [dot(vx(ROW_EXT), vy(row_bus_b(r)), "joint j-row")])
        dots += grp(name, f"row{r}", [dot(px_row, py, "joint j-row")]) + grp(name, "col3", [dot(px_col, py, "joint j-col")])

    # ---- power buses ----
    for net, kind, bf, bb, al, be, lab_b in (("gnd", "gnd", GND_FRONT, GND_BACK, GND_LEFT, GND_BACK_END, GND_FRONT - 2.2),
                                             ("3v3", "pwr", V_FRONT, V_BACK, V_LEFT, V_BACK_END, V_FRONT + 2.6)):
        label = "GND BUS" if net == "gnd" else "3V3 BUS"
        buses += grp("bus", net, rail(vx(al), vy(bf), vx(FRONT_END + (0 if net == "gnd" else 1.0)), vy(bf), kind)
                     + rail(vx(al), vy(bb), vx(be), vy(bb), kind)
                     + [text(vx(118), vy(lab_b) + 4, label, "busname")])
        # the link between the front and back pair: insulated, up the slider-side edge
        over += grp("bus", net, wire([(vx(al), vy(bf)), (vx(al), vy(bb))], kind) + [dot(vx(al), vy(bf), f"joint j-{kind}"), dot(vx(al), vy(bb), f"joint j-{kind}")])
        pin = "G" if net == "gnd" else "3V3"
        exit_([(vx(be), vy(bb)), (vx(be), yP)], kind, pin, "bus", net,
              f"{label[:3]} bus", f"{label[:3]} bus, its back end by slider 3", pin)

    # ---- encoders: C to its screen's GND pin; A and B up the knob-column wall ----
    side = []   # (source height b, path start pts, kind, pin, owner, net, short, frm)
    scr_gnd_a = ENC_A - 0.5 * 2.54           # the GND pin of the screen in front of each knob
    for name, b in ENC_B.items():
        cx, pb = vx(ENC_A), b - 7
        pin_y = vy(pb)
        a_pin, b_pin = ENC_PINS[name]
        sb = SCR_B if name == "E1" else S5_B
        hdr = vy(sb + SCR_PCB[1] / 2 - 1.3)
        dots += body(name, [text(cx + dx * S, pin_y - 8, lab, "pinlbl") for dx, lab in ((-2.5, "B"), (0, "C"), (2.5, "A"))])
        over += grp(name, "gnd", wire([(cx, pin_y), (cx, vy(pb - 1.2)), (vx(scr_gnd_a), vy(pb - 1.2)), (vx(scr_gnd_a), hdr)], "gnd")
                    + [dot(vx(scr_gnd_a), hdr, "joint j-gnd")])
        dots += grp(name, "gnd", [dot(cx, pin_y, "joint j-gnd")])
        for dx, rise, sig, pin in ((-2.5, 0.0, "b", b_pin), (2.5, 0.5, "a", a_pin)):
            x0 = cx + dx * S
            dots += grp(name, f"{name.lower()}{sig}", [dot(x0, pin_y, "joint j-enc")])
            side.append((pb + rise, [(x0, pin_y), (x0, vy(pb + rise))], "enc", pin, name, f"{name.lower()}{sig}",
                         f"{name} {sig.upper()}", f"{name} pin {sig.upper()}"))
    side.append((ENC_B["E2"] + 7, [(xw, ys["E2"])], "col", COL_PIN[3], "bus", "col3", "Col 3",
                 "Column 3 wire (knob pushes), at the wall by E2"))

    # ---- slide pots: pins 1 and 2 at the back end, pin 3 alone at the front end. Pin 1 to 3V3 (back
    # rails), pin 2 straight to the back edge and across to a 100 nF right of the body, its other leg to the GND back rail, pin 3 to the GND pin of
    # the slider's own screen, just in front of it ----
    pot_top = vy(BLOCK_B + POT_BODY[1] / 2)
    p_pin = pot_top - 1.5 * S
    for i in range(SLIDERS):
        name = f"Slider {i + 1}"
        cx = vx(slider_a(i))
        base += body(name, [f'<rect x="{f(cx - POT_BODY[0] / 2 * S)}" y="{f(pot_top)}" width="{f(POT_BODY[0] * S)}" '
                            f'height="{f(POT_BODY[1] * S)}" rx="4" class="part"/>',
                            f'<rect x="{f(cx - 3)}" y="{f(pot_top + 8 * S)}" width="6" height="{f((POT_BODY[1] - 16) * S)}" rx="3" class="shaft"/>',
                            text(cx, vy(BLOCK_B), name, "keyname vert").replace(
                                "<text ", f'<text transform="rotate(-90 {f(cx)} {f(vy(BLOCK_B))})" ', 1)])
        xs = {1: cx - 2.5 * S, 2: cx}             # seen from below
        cap_x = cx + (POT_BODY[0] / 2 + 3) * S    # the capacitor, standing right of the slider body
        cap_t, cap_b = p_pin + 4 * S, p_pin + 11 * S   # its two legs' solder joints
        gnd_x, gnd_y = cap_x + 3 * S, cap_b + 2 * S    # its GND wire: round and up to the GND back rail
        dots += body(name, [text(x, p_pin + 16, str(n), "pinlbl") for n, x in xs.items()])
        net = f"pot{i + 1}"
        over += grp(name, "3v3", wire([(xs[1], p_pin), (xs[1], vy(V_BACK))], "pwr") + [dot(xs[1], vy(V_BACK), "joint j-pwr")])
        over += grp(name, net, wire([(xs[2], p_pin), (cap_x, p_pin), (cap_x, cap_t)], "pot") + [dot(cap_x, cap_t, "joint j-pot")])
        over += grp(name, "gnd", wire([(cap_x, cap_b), (cap_x, gnd_y), (gnd_x, gnd_y), (gnd_x, vy(GND_BACK))], "gnd")
                    + [dot(cap_x, cap_b, "joint j-gnd"), dot(gnd_x, vy(GND_BACK), "joint j-gnd")])
        over += grp(name, net + " gnd", [poly([(cap_x, cap_t), (cap_x, cap_t + 1.5 * S)], "w w-pot"),
                                         poly([(cap_x, cap_b - 1.5 * S), (cap_x, cap_b)], "w w-gnd"),
                                         f'<rect x="{f(cap_x - 1.6 * S)}" y="{f(cap_t + 1.5 * S)}" width="{f(3.2 * S)}" '
                                         f'height="{f(cap_b - cap_t - 3 * S)}" rx="2" class="cap"/>',
                                         text(cap_x + 0.5 * S, gnd_y + 16, "100 nF", "port")])
        exit_([(xs[2], p_pin), (xs[2], yP)], "pot", POT_PIN[i], name, net, f"Slider {i + 1}", f"Slider {i + 1} pin 2", POT_PIN[i])
        dots += grp(name, "3v3", [dot(xs[1], p_pin, "joint j-pwr")]) + grp(name, net, [dot(xs[2], p_pin, "joint j-pot")])
        # pin 3, alone at the front end: a short jumper to its screen's GND pin (the third header pin from below)
        p3_b = BLOCK_B - POT_BODY[1] / 2 + 1.5
        scr_gnd_x = cx + 0.5 * 2.54 * S
        scr_hdr_y = vy(SCR_B + SCR_PCB[1] / 2 - 1.3)
        dots += body(name, [text(cx - 12, vy(p3_b) + 4, "3", "pinlbl", "end")])
        over += grp(name, "gnd", wire([(cx, vy(p3_b)), (cx, vy(42.2)), (scr_gnd_x, vy(42.2)), (scr_gnd_x, scr_hdr_y)], "gnd")
                    + [dot(cx, vy(p3_b), "joint j-gnd")])

    # ---- screens: VCC / GND to the power buses; SDA / SCL to the back edge, for the multiplexer ----
    order = ["SDA", "SCL", "GND", "VCC"]          # seen from below, left to right
    kinds = {"SDA": "scr", "SCL": "scr", "VCC": "pwr", "GND": "gnd"}
    for i, (a, b) in enumerate(screens()):
        name = SCR_NAMES[i]
        cx = vx(a)
        top_y = vy(b + SCR_PCB[1] / 2)
        hdr_b = b + SCR_PCB[1] / 2 - 1.3
        hdr_y = vy(hdr_b)
        base += body(name, [f'<rect x="{f(cx - SCR_PCB[0] / 2 * S)}" y="{f(top_y)}" width="{f(SCR_PCB[0] * S)}" '
                            f'height="{f(SCR_PCB[1] * S)}" rx="3" class="part"/>',
                            text(cx - 9.2 * S, top_y + 14 * S, name, "keyname")])
        ch = SCR_CH[i]
        for k, pin in enumerate(order):
            x = cx + (k - 1.5) * 2.54 * S
            kind = kinds[pin]
            net = {"SDA": f"sd{ch}", "SCL": f"sc{ch}", "VCC": "3v3", "GND": "gnd"}[pin]
            dest = {"SDA": f"SD{ch}", "SCL": f"SC{ch}", "VCC": "3V3", "GND": "G"}[pin]
            dots += grp(name, net, [text(x, hdr_y + 16, pin, "pinmini"), dot(x, hdr_y, f"joint j-{kind}")])
            if pin in ("VCC", "GND"):
                if i == 4:
                    # S5: a step forward, across to the gap beside the keys, down it to the front pair
                    jb = hdr_b - (2.0 if pin == "GND" else 1.0)
                    xl = vx(GAP_GND if pin == "GND" else GAP_V)
                    yb = vy(GND_FRONT if pin == "GND" else V_FRONT)
                    over += grp(name, net, wire([(x, hdr_y), (x, vy(jb)), (xl, vy(jb)), (xl, yb)], kind) + [dot(xl, yb, f"joint j-{kind}")])
                else:
                    yb = vy(V_FRONT if pin == "VCC" else GND_FRONT)
                    over += grp(name, net, wire([(x, hdr_y), (x, yb)], kind) + [dot(x, yb, f"joint j-{kind}")])
                continue
            short, frm = f"{name} {pin}", f"{name} {pin}"
            if i < 3:
                # slider screens: a step back, then up the gap beside the slider to the back edge
                jb = hdr_b + (0.9 if pin == "SDA" else 1.7)
                lane = vx(a + (7.0 if pin == "SDA" else 6.0))
                exit_([(x, hdr_y), (x, vy(jb)), (lane, vy(jb)), (lane, yP)], "scr", dest, name, net, short, frm, f"mux {dest}")
            elif i == 3:
                # S4: a step back, under E1's pins, then out to the knob-column wall
                jb = hdr_b + (0.7 if pin == "SDA" else 1.3)
                side.append((jb, [(x, hdr_y), (x, vy(jb))], "scr", dest, name, net, short, frm))
            else:
                # S5: a step forward over its own board, then out to the wall
                jb = hdr_b - (1.0 if pin == "SDA" else 2.0)
                side.append((jb, [(x, hdr_y), (x, vy(jb))], "scr", dest, name, net, short, frm))

    # the knob-column wall: lowest source outermost, so the wires never cross
    side.sort(key=lambda s: -s[0])
    for j, (_, pts, kind, pin, owner, net, short, frm) in enumerate(side):
        xt = left - 14 - j * 8
        y = pts[-1][1]
        exit_(pts + [(xt, y), (xt, yP)], kind, pin, owner, net, short, frm, f"mux {pin}" if net[:2] in ("sd", "sc") else pin)

    return base, buses, over, dots, exits, left, right


def main_svg():
    """The case opened up for wiring, to scale: lid on top (inside up, turned round), plate below
    (upside down), their back edges meeting at the fold. The plate's wires gather along its back
    edge into five ribbons that cross the fold and end in plugs A-E on the header pins."""
    base, buses, over, dots, exits, left, right = plate_parts()
    yP = vy(TOP_B)

    # ---- number the harness wires: rows, columns, power, knobs, sliders, screens ----
    def wkey(e):
        n = e["net"]
        if n[:3] in ("row", "col"):
            return (0 if n[:3] == "row" else 1, n)
        if n in ("gnd", "3v3"):
            return (2, n == "3v3")
        if n.startswith("pot"):
            return (4, n)
        if n[0] == "e":
            return (3, n)
        return (5, int(n[2]), n[:2] == "sc")
    exits.sort(key=wkey)
    for i, e in enumerate(exits):
        e["w"] = i + 1

    # ---- the lid, to the same scale as the plate, turned round so its back edge meets the plate's ----
    # Both halves are mirrored the same way (vx), so a lid point sits straight above the plate
    # point under it in the closed case. LY: lid y (mm from its front edge) to px, back edge at the fold.
    FOLD = FOLD_MM * S
    y_bb = yP - GATHER_MM * S            # bottom of the fold band (plate side)
    y_bt = y_bb - FOLD                   # top of the fold band (lid side)

    def LY(y):
        return y_bt - (DECK_D - y) * S

    lid, wires_lid, harness, ribbons = [], [], [], []
    lid.append(f'<path d="M{f(vx(PAD_W))} {f(LY(LID_CUT))} V{f(LY(DECK_D) - 6 * S)} Q{f(vx(PAD_W))} {f(LY(DECK_D))} {f(vx(PAD_W - 6))} {f(LY(DECK_D))} '
               f'H{f(vx(6))} Q{f(vx(0))} {f(LY(DECK_D))} {f(vx(0))} {f(LY(DECK_D) - 6 * S)} V{f(LY(LID_CUT))} Z" class="case"/>')
    lid.append(line(vx(PAD_W), LY(LID_CUT), vx(0), LY(LID_CUT), "cutline"))
    lid.append(text((left + right) / 2, LY(LID_CUT) - 30, "LID, INSIDE FACING UP, TURNED ROUND · ITS BACK EDGE (USB-C) AT THE FOLD · BLACKPILL UPSIDE DOWN · TO SCALE", "edge"))
    lid.append(text((left + right) / 2, LY(LID_CUT) - 12, f"its front {LID_CUT:.0f} mm, empty, not shown", "hingesub"))
    for px_, py_ in LID_POSTS:
        if py_ > LID_CUT:
            lid.append(f'<circle cx="{f(vx(px_))}" cy="{f(LY(py_))}" r="{f(4 * S)}" class="boss"/>')

    # BlackPill upside down (chips, its buttons and USB-C face the lid, long pins up), USB-C at the back wall.
    # Seen from above, its left-hand header (B12 at the USB end) is on the right.
    lid.append(f'<rect x="{f(vx(BP_X + BP_W / 2))}" y="{f(LY(BP_Y0))}" width="{f(BP_W * S)}" height="{f((BP_Y1 - BP_Y0) * S)}" rx="5" class="board"/>')
    lid.append(f'<rect x="{f(vx(BP_X + 4.5))}" y="{f(LY(DECK_D) - 3 * S)}" width="{f(9 * S)}" height="{f(3 * S)}" rx="5" class="usb"/>')
    lid.append(text(vx(BP_X), LY(DECK_D) - 3 * S - 6, "USB-C", "port"))
    b0x, b0y = BP_X + 3.0, BP_Y1 - 15          # the board's own BOOT0 button, underneath it
    lid.append(f'<rect x="{f(vx(b0x) - 1.5 * S)}" y="{f(LY(b0y) - 1.5 * S)}" width="{f(3 * S)}" height="{f(3 * S)}" rx="2" class="part" stroke-dasharray="4 3"/>')

    def bp_pin(side, name):          # side "L" / "R": the board's left / right header (chips up); upside down, L is on +x
        names = BP_LEFT if side == "L" else BP_RIGHT
        return (BP_X + (7.62 if side == "L" else -7.62), BP_Y1 - 2.6 - 2.54 * names.index(name))

    def mux_pad(name):
        return MUX_PAD_X0 + MUX_CH.index(name) * 2.54, MUX[3] - 2.0

    def where(pin):
        if pin in MUX_CH:
            return mux_pad(pin)
        return bp_pin("L" if pin in BP_LEFT else "R", pin)       # G and 3V3: the left-hand header, plug C

    def arrive(x, y, x_from):        # a wire's end, stopping just short of a pin it comes to from x_from
        return (vx(x) + (4 if x_from < x else -4), LY(y))

    used = {e["pin"] for e in exits} | {"B6", "B7", "R"}
    for side, names in (("L", BP_LEFT), ("R", BP_RIGHT)):
        for name in names:
            x, y = bp_pin(side, name)
            avoid = BP_USE.get(name, "").startswith("avoid")
            cls = "pad pad-avoid" if avoid else ("pad pad-used" if name in used else "pad pad-off")
            lid.append(f'<circle cx="{f(vx(x))}" cy="{f(LY(y))}" r="4.2" class="{cls}"/>')
            # names inside the board, where no wire arrives
            lid.append(text(vx(x) + (9 if side == "L" else -9), LY(y) + 3, name, "padmini", "start" if side == "L" else "end"))

    # multiplexer
    mx0, mx1, my0, my1 = MUX
    lid += body("MUX", [f'<rect x="{f(vx(mx1))}" y="{f(LY(my0))}" width="{f((mx1 - mx0) * S)}" height="{f((my1 - my0) * S)}" rx="5" class="board"/>',
                        text(vx((mx0 + mx1) / 2), LY((my0 + my1) / 2) + 2, "TCA9548A mux", "port"),
                        text(vx((mx0 + mx1) / 2), LY((my0 + my1) / 2) + 16, "A0–A2, RST free", "pinmini")])
    for name in MUX_CH:
        x, y = mux_pad(name)
        lid += grp("MUX", name.lower(), [f'<circle cx="{f(vx(x))}" cy="{f(LY(y))}" r="4.2" class="pad pad-used"/>',
                                         f'<text x="{f(vx(x) + 3)}" y="{f(LY(y) - 8)}" class="padmini" text-anchor="end" '
                                         f'transform="rotate(90 {f(vx(x) + 3)} {f(LY(y) - 8)})">{name}</text>'])
    # mux I2C and power (L1-L4), from pads on its front edge, in front of the B button and up over the middle
    # of the board: SCL and SDA to B6 and B7 on the near header, GND and VIN on to G and 3V3 at the far header's USB end
    (bbx, bby), (brx, bry) = BTN_POS
    for j, (pad, side, pin, kind, net, xv, yh) in enumerate((
            ("SCL", "L", "B6", "scr", "mux-scl", BP_X + 1.2, bby - 4.0),
            ("SDA", "L", "B7", "scr", "mux-sda", BP_X + 0.4, bby - 5.0),
            ("GND", "R", "G", "gnd", "mux-gnd", BP_X - 0.4, bby - 6.0),
            ("VIN", "R", "3V3", "pwr", "mux-vin", BP_X - 1.2, bby - 7.0))):
        ux = mx1 - 3 - (3 - j) * 2.54
        uy = my0 + 2.0
        x, y = bp_pin(side, pin)
        pts = [(vx(ux), LY(uy)), (vx(ux), LY(yh)), (vx(xv), LY(yh)), (vx(xv), LY(y)), arrive(x, y, xv)]
        wires_lid += grp("MUX", net, wire(pts, kind) + [f'<circle cx="{f(vx(ux))}" cy="{f(LY(uy))}" r="3.6" class="pad pad-used"/>',
                                                         text(vx(ux), LY(uy) - 7, pad, "padmini"), dot(vx(x), LY(y), f"joint j-{kind}")], w=f"L{j + 1}")

    # B and R buttons, in front of the BlackPill
    for bxx, byy, lab in ((bbx, bby, "B"), (brx, bry, "R")):
        lid += body("Buttons", [f'<rect x="{f(vx(bxx + 3))}" y="{f(LY(byy - 3))}" width="{f(6 * S)}" height="{f(6 * S)}" rx="4" class="part"/>',
                                text(vx(bxx), LY(byy) + 5, lab, "port")])
    # B: two wires from the board's own BOOT0 button, soldered on before the board goes in, out under its
    # front edge (dashed: under the board)
    under = wire([(vx(b0x - 1.0), LY(b0y - 1.5)), (vx(b0x - 1.0), LY(bby + 4.5)), (vx(bbx - 1.0), LY(bby + 4.5)), (vx(bbx - 1.0), LY(bby + 3))], "rst") \
        + wire([(vx(b0x - 0.2), LY(b0y - 1.5)), (vx(b0x - 0.2), LY(bby + 5.7)), (vx(bbx + 1.0), LY(bby + 5.7)), (vx(bbx + 1.0), LY(bby + 3))], "rst")
    under = [u.replace("<polyline ", '<polyline stroke-dasharray="7 5" ', 1).replace("<path ", '<path stroke-dasharray="7 5" ', 1) for u in under]
    wires_lid += grp("Buttons", "rst", under + [dot(vx(b0x - 1.0), LY(b0y - 1.5), "joint j-rst"), dot(vx(b0x - 0.2), LY(b0y - 1.5), "joint j-rst")], w="L5")
    # R: one leg up over the board to the R pin, the other to G, joining the mux's GND wire at the pin
    rx_, ry_ = bp_pin("R", "R")
    gx_, gy_ = bp_pin("R", "G")
    wires_lid += grp("Buttons", "rst",
                     wire([arrive(rx_, ry_, BP_X - 2.8), (vx(BP_X - 2.8), LY(ry_)), (vx(BP_X - 2.8), LY(BP_Y0 - 2.0)), (vx(brx - 1.2), LY(BP_Y0 - 2.0)), (vx(brx - 1.2), LY(bry + 3))], "rst")
                     + wire([(vx(brx + 1.2), LY(bry + 3)), (vx(brx + 1.2), LY(BP_Y0 - 3.0)), (vx(BP_X - 2.0), LY(BP_Y0 - 3.0)), (vx(BP_X - 2.0), LY(gy_))], "gnd")
                     + [dot(vx(rx_), LY(ry_), "joint j-rst"), dot(vx(BP_X - 2.0), LY(gy_), "joint j-gnd")], w="L6")

    # ---- plugs A-E and their ribbons ----
    # each plug: its header pins in order (None = an empty slot), and which side its ribbon leaves
    by_pin = {e["pin"]: e for e in exits}
    lanes = {}                    # pin -> lane x (mm, lid/plate x)
    plug_of = {}
    for name, side, pins in PLUGS:
        for p in pins:
            if p:
                plug_of[p] = name
    # right-hand header (-x seen from above, the board upside down): plug A, lanes outside the board,
    # pin nearest the USB end innermost
    xr = BP_X - BP_W / 2 - 2.0
    for k, p in enumerate(sorted([p for p in PLUG_PINS["A"] if p], key=BP_RIGHT.index)):
        lanes[p] = xr - k * RIB
    # left-hand header (+x): D, E, C from the USB end, farthest pin outermost
    xl = BP_X + BP_W / 2 + 2.0
    k = 0
    for name in ("D", "E", "C"):
        for p in PLUG_PINS[name]:
            if p:
                lanes[p] = xl + k * RIB
                k += 1
        k += 1                    # a gap between ribbons
    # mux: straight down from its pads
    for p in PLUG_PINS["B"]:
        lanes[p] = mux_pad(p)[0]

    # plug housings
    for name, side, pins in PLUGS:
        pos = [where(p) if p else None for p in pins]
        real = [q for q in pos if q]
        if name == "B":
            xs_ = [q[0] for q in real]
            x0, x1 = min(xs_) - 1.27, max(xs_) + 1.27
            y0 = real[0][1] - 1.27
            lid.append(f'<rect x="{f(vx(x1))}" y="{f(LY(y0))}" width="{f((x1 - x0) * S)}" height="{f(2.54 * S)}" rx="2" class="plug"/>')
            lid.append(text(vx(x1) - 10, LY(y0) - 3, f"plug {name}", "plugname", "end"))
        else:
            hx = where(next(p for p in pins if p))[0]
            ys_ = [bp_pin(side, p)[1] if p else None for p in pins]
            first = min((BP_LEFT if side == "L" else BP_RIGHT).index(p) for p in pins if p)
            ya = BP_Y1 - 2.6 - 2.54 * first + 1.27
            yb = ya - 2.54 * len(pins)
            lid.append(f'<rect x="{f(vx(hx + 1.27))}" y="{f(LY(yb))}" width="{f(2.54 * S)}" height="{f((ya - yb) * S)}" rx="2" class="plug"/>')
            lid.append(text(vx(hx), LY(yb) - 6, name, "plugname"))

    # the band where the ribbons fold
    hx0, hx1 = left - 20, right + 20
    band = [f'<rect x="{f(hx0)}" y="{f(y_bt)}" width="{f(hx1 - hx0)}" height="{f(FOLD)}" rx="10" class="hinge"/>',
            text(hx1 - 16, y_bt + FOLD / 2 - 2, f"FOLD · {FOLD_MM:.0f} mm OF SLACK", "hingetxt", "end"),
            text(hx1 - 16, y_bt + FOLD / 2 + 15, "five flat ribbons, one per plug", "hingesub", "end")]

    # every wire: plate exit -> up to its gathering level -> along the back edge to its lane -> up the ribbon
    lane_px = {e["w"]: vx(lanes[e["pin"]]) for e in exits}

    def crossings(order):
        lvl = {w: i for i, w in enumerate(order)}
        n = 0
        for a in exits:
            for b in exits:
                if a is b:
                    continue
                wa, wb = a["w"], b["w"]
                lo, hi = sorted((b["x"], lane_px[wb]))
                if lvl[wb] < lvl[wa] and lo < a["x"] < hi:         # b's run crosses a's rise from the plate
                    n += 1
                if lvl[wb] > lvl[wa] and lo < lane_px[wa] < hi:    # b's run crosses a's rise into its ribbon
                    n += 1
        return n
    order = [e["w"] for e in sorted(exits, key=lambda e: abs(lane_px[e["w"]] - e["x"]))]
    best = crossings(order)
    improved = True
    while improved:
        improved = False
        for i in range(len(order)):
            for j in range(i + 1, len(order)):
                order[i], order[j] = order[j], order[i]
                c = crossings(order)
                if c < best:
                    best, improved = c, True
                else:
                    order[i], order[j] = order[j], order[i]
    lv = {w: i for i, w in enumerate(order)}
    assert len(order) * LEVEL_PX < GATHER_MM * S - 14, "gathering band too short"
    rib_x = {}
    for e in exits:
        n, pin, kind = e["w"], e["pin"], e["kind"]
        lx_ = vx(lanes[pin])
        rib_x.setdefault(plug_of[pin], []).append(lx_)
        ylv = yP - 10 - lv[n] * LEVEL_PX
        tx_, ty_ = where(pin)
        if plug_of[pin] == "B":
            lid_pts = [(lx_, y_bt), (lx_, LY(ty_))]
        else:
            lid_pts = [(lx_, y_bt), (lx_, LY(ty_)), (vx(tx_) + (4 if lanes[pin] < tx_ else -4), LY(ty_))]
        pts = e["pts"] + [(e["x"], ylv), (lx_, ylv), (lx_, y_bb), (lx_, y_bt)] + lid_pts[1:]
        mid = y_bt + FOLD / 2
        items = wire(pts, kind) + [dot(vx(tx_), LY(ty_), f"joint j-{kind}"),
                                   f'<text x="{f(lx_ + 3)}" y="{f(mid)}" class="lanenum tt-{kind}" text-anchor="middle" '
                                   f'transform="rotate(-90 {f(lx_ + 3)} {f(mid)})">{n}</text>']
        harness += grp(e["owner"], e["net"], items, w=str(n))
        e["to"] = f"{'mux ' + pin if pin in MUX_CH else pin} · plug {plug_of[pin]}"
    # ribbon sleeves across the fold, with the plug letter at both ends
    for name, xs_ in rib_x.items():
        x0, x1 = min(xs_) - 5, max(xs_) + 5
        ribbons.append(f'<rect x="{f(x0)}" y="{f(y_bt + 4)}" width="{f(x1 - x0)}" height="{f(FOLD - 8)}" rx="4" class="ribbon"/>')
        ribbons.append(text((x0 + x1) / 2, y_bt + 22, name, "plugname"))

    labels = [r for r in ribbons if r.startswith("<text")]
    sleeves = [r for r in ribbons if not r.startswith("<text")]
    body_ = "\n".join(lid + wires_lid + band + sleeves + base + buses + over + dots + harness + labels)
    x_min = min(hx0, left - 30) - 20
    x_max = max(hx1, right + 60) + 20
    y_min = LY(LID_CUT) - 50
    y_max = vy(0) + 56
    return (f'<svg class="wiring" viewBox="{f(x_min)} {f(y_min)} {f(x_max - x_min)} {f(y_max - y_min)}" role="img" '
            'aria-label="The case opened up for wiring, to scale: the lid at the top, turned round, with the BlackPill, the TCA9548A '
            'multiplexer and the B and R buttons; the plate below it, upside down, with its bare copper buses and every part. '
            f'{len(exits)} numbered wires leave the plate, gather along its back edge into five flat ribbons, cross the fold and '
            'end in five plugs, A to E, on the BlackPill and multiplexer header pins.">\n' + body_ + "\n</svg>"), exits

def harness_html(exits):
    """The wires between plate and lid, in number order, plus the few that stay in the lid."""
    rows = []
    for e in sorted(exits, key=lambda e: e["w"]):
        rows.append((str(e["w"]), e["kind"], e["owner"], e["net"], e["frm"], e["to"]))
    lid_only = [("L1", "scr", "MUX", "mux-scl", "Mux SCL", "B6"), ("L2", "scr", "MUX", "mux-sda", "Mux SDA", "B7"),
                ("L3", "gnd", "MUX", "mux-gnd", "Mux GND", "G (right-hand header, USB end)"),
                ("L4", "pwr", "MUX", "mux-vin", "Mux VIN", "3V3 (right-hand header, USB end)"),
                ("L5", "rst", "Buttons", "rst", "B button, both legs", "the board's own BOOT0 button, two legs (solder before the board goes in)"),
                ("L6", "rst", "Buttons", "rst", "R button, both legs", "R and G (right-hand header; G shared with L3)")]
    out = []
    for group, items in (("Between plate and lid", rows), ("Inside the lid", lid_only)):
        out.append(f'<tr class="grouprow"><th colspan="4">{group}</th></tr>')
        for w, kind, owner, net, frm, to in items:
            out.append(f'<tr data-w="{w}" data-o="{owner}" data-n="{net}" tabindex="0">'
                       f'<td><span class="numbadge nb-{kind}">{w}</span></td><td>{frm}</td><td class="to">{to}</td>'
                       f'<td><input type="checkbox" aria-label="Wire {w} done" data-done="{w}"></td></tr>')
    return "\n".join(out)


def encoder_mount_svg():
    """Side section of one EC11 in the plate with the printed spacer, z up, mm scaled by k."""
    k, cx, z0 = 10.0, 230, 200

    def px(v):
        return cx + v * k

    def pz(v):
        return z0 - v * k

    def box(x0, x1, z_lo, z_hi, cls, rx=0):
        return (f'<rect x="{f(px(x0))}" y="{f(pz(z_hi))}" width="{f((x1 - x0) * k)}" '
                f'height="{f((z_hi - z_lo) * k)}" rx="{rx}" class="{cls}"/>')

    sp = 3.0   # spacer thickness
    o = [box(-22, -3.9, -1.5, 0, "plate"), box(3.9, 22, -1.5, 0, "plate"),
         box(-6, -3.9, -1.5 - sp, -1.5, "spacer"), box(3.9, 6, -1.5 - sp, -1.5, "spacer"),
         box(-6, 6, -1.5 - sp - 6.5, -1.5 - sp, "part", 2),
         box(-3.5, 3.5, -1.5 - sp, 1.0, "metal"),
         box(-3, 3, 1.0, 15.0, "metal"),
         box(-4.75, 4.75, 0, 2.0, "metal"),
         box(-8.5, 8.5, 1.0, 17.0, "knob", 6)]
    for x in (-5, 5):
        o.append(box(x - 0.4, x + 0.4, -1.5 - sp - 11, -1.5 - sp - 6.5, "metal"))
    o.append(text(px(-22), pz(0) - 10, "OUTSIDE (TOP)", "edge", "start"))
    o.append(text(px(-22), pz(-1.5) + 22, "INSIDE THE CASE", "edge", "start"))

    lx = px(22) + 30
    labels = [
        (8.5, 12, "Knob (15.5 mm tall), pushed onto the shaft"),
        (4.75, 1.0, "Nut, no washer: only ~2.5 mm of thread is left"),
        (3.5, 0.5, "Threaded M7 bushing up through the 7.8 mm hole"),
        (22, -0.75, "Plate, 1.5 mm thin round the encoder"),
        (6, -3.0, "Printed 3 mm spacer ring (enc_spacer.stl)"),
        (6, -7.5, "EC11 body hangs 3 mm lower than without it"),
        (5.4, -13, "Pins point down: solder wires here"),
    ]
    for i, (ax, az, s) in enumerate(labels):
        ty = 40 + i * 34
        o.append(poly([(px(ax) + 3, pz(az)), (lx - 14, ty - 4), (lx - 6, ty - 4)], "leader"))
        o.append(text(lx, ty, s, "note", "start"))
    return ('<svg viewBox="0 0 820 340" role="img" aria-label="Side view: a printed 3 mm spacer ring sits on the EC11 '
            'bushing under the plate; the bushing comes up through the 7.8 mm hole and the nut, without its washer, '
            'clamps it from the top; the body and pins hang below; the knob goes on the shaft.">\n'
            + "\n".join(o) + "\n</svg>")


def encoder_pins_svg():
    """One EC11 from below, 5 pins, with where each pin goes."""
    k, cx, cy = 14.0, 410, 235

    def px(v):
        return cx + v * k

    def py(v):
        return cy + v * k

    o = [text(cx, 22, "BACK ↑ · push pins on this side", "edge"),
         f'<rect x="{f(px(-6))}" y="{f(py(-6))}" width="{f(12 * k)}" height="{f(12 * k)}" rx="5" class="part"/>',
         f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(3.5 * k)}" class="shaft"/>',
         text(cx, cy + 6, "EC11", "keyname"),
         text(cx, py(-4.4), "push switch", "pinlbl"),
         text(cx, py(4.9), "encoder", "pinlbl")]
    wires, dots = [], []
    # the push pin nearer the keys (right, seen from below) takes the diode; the other goes to column 3
    wires += diode_v(px(2.5), py(-7.5), py(-12))
    wires.append(poly([(px(2.5), py(-12)), (px(10), py(-12)), (px(10), py(-12) - 5)], "w w-row"))
    wires.append(tag(px(10) + 40, py(-12) - 16, f"E1: ROW 2 → {ROW_PIN[2]} · E2: ROW 0 → {ROW_PIN[0]}", "row"))
    o.append(text(px(2.5) + 14, py(-9.75) + 4, "black band toward row", "pinlbl", "start"))
    wires.append(poly([(px(-2.5), py(-7.5)), (px(-2.5), py(-10)), (px(-10), py(-10)), (px(-10), py(-12))], "w w-col"))
    wires.append(tag(px(-10), py(-12) - 16, f"COL 3 → {COL_PIN[3]} (both)", "col"))
    dots += [dot(px(2.5), py(-7.5), "joint j-row"), dot(px(-2.5), py(-7.5), "joint j-col")]
    e1, e2 = ENC_PINS["E1"], ENC_PINS["E2"]
    for dx, lab, dest, kind in ((-2.5, "B", f"B → {e1[1]} (E1) · {e2[1]} (E2)", "enc"),
                                (0, "C", "C → screen GND", "gnd"),
                                (2.5, "A", f"A → {e1[0]} (E1) · {e2[0]} (E2)", "enc")):
        o.append(text(px(dx), py(7.5) - 12, lab, "pinbig"))
        tx = dx * 4.8
        wires.append(poly([(px(dx), py(7.5)), (px(dx), py(10.5)), (px(tx), py(10.5)), (px(tx), py(13))], f"w w-{kind}"))
        wires.append(tag(px(tx), py(13) + 16, dest, kind))
        dots.append(dot(px(dx), py(7.5), f"joint j-{kind}"))
    o.append(text(cx, 470, "FRONT ↓ · 3 turning pins on this side, toward its screen", "edge"))
    return ('<svg viewBox="0 0 820 490" role="img" aria-label="One EC11 seen from below. Back side: two push pins; '
            f'the right one (nearer the keys) goes through a diode, band toward the row, to row 2 ({ROW_PIN[2]}) for E1 or row 0 '
            f'({ROW_PIN[0]}) for E2; the left one goes to column 3 ({COL_PIN[3]}) for both. Front side, left to right: B to {e1[1]} or {e2[1]}, C to its screen’s GND pin, '
            f'A to {e1[0]} or {e2[0]}.">\n' + "\n".join(o + wires + dots) + "\n</svg>")


# WeAct BlackPill V2/V3, each header from the USB-C end. Component side up with USB-C at the top, BP_LEFT is
# the left-hand row; in the lid the board is upside down, so seen from above BP_LEFT is on the right.
BP_LEFT = ["B12", "B13", "B14", "B15", "A8", "A9", "A10", "A11", "A12", "A15",
           "B3", "B4", "B5", "B6", "B7", "B8", "B9", "5V", "G", "3V3"]
BP_RIGHT = ["5V", "G", "3V3", "B10", "B2", "B1", "B0", "A7", "A6", "A5",
            "A4", "A3", "A2", "A1", "A0", "R", "C15", "C14", "C13", "VB"]
BP_USE = {
    "A4": "row:ROW 0", "A5": "row:ROW 1", "A6": "row:ROW 2", "B14": "row:ROW 3",
    "A7": "col:COL 0", "A8": "col:COL 1", "A15": "col:COL 2", "B0": "col:COL 3 (knob pushes)",
    "B1": "enc:E1 A", "B8": "enc:E1 B", "B9": "enc:E2 A", "A0": "enc:E2 B",
    "A1": "pot:Slider 1 pin 2", "A2": "pot:Slider 2 pin 2", "A3": "pot:Slider 3 pin 2",
    "B6": "scr:Mux SCL (I2C1)", "B7": "scr:Mux SDA (I2C1)",
    "R": "rst:",
    "A9": "avoid:avoid (USB sense)", "A10": "avoid:avoid (DFU)", "A11": "avoid:USB", "A12": "avoid:USB",
    "B2": "avoid:BOOT1", "C13": "avoid:LED", "C14": "avoid:32 kHz crystal", "C15": "avoid:32 kHz crystal",
}


def blackpill_svg():
    """The board as it sits in the lid: upside down (back side up, long pins up), USB-C at the top."""
    s = 11.0
    bw, bl = 21 * s, 53 * s
    bx, by = 300, 70
    cx = bx + bw / 2
    out = [f'<rect x="{bx}" y="{by}" width="{f(bw)}" height="{f(bl)}" rx="6" class="board"/>',
           f'<rect x="{f(cx - 4.5 * s)}" y="{f(by - 12)}" width="{f(9 * s)}" height="{f(3 * s)}" rx="6" class="usb"/>',
           text(cx, by - 24, "USB-C · TOWARD THE BACK WALL", "edge")]
    # the board's own buttons, underneath it (dashed)
    btns = {"NRST": (-4.0, 15), "BOOT0": (3.0, 15), "KEY": (1.0, 43)}
    for name, (dx, d) in btns.items():
        xx, yy = cx + dx * s, by + d * s
        out.append(f'<rect x="{f(xx - 2 * s)}" y="{f(yy - 2 * s)}" width="{f(4 * s)}" height="{f(4 * s)}" rx="3" class="part" stroke-dasharray="5 4"/>')
        out.append(text(xx, yy + 4, name, "pinmini"))
    out.append(text(cx, by + bl - 14, "chips underneath", "port"))
    pads = {}
    for side, pins in ((1, BP_LEFT), (-1, BP_RIGHT)):        # upside down: the left-hand header is on the right
        px = cx + side * 7.62 * s
        for i, name in enumerate(pins):
            py = by + (2.6 + 2.54 * i) * s
            pads[(name, side)] = (px, py)
            use = BP_USE.get(name)
            if name == "3V3":
                use = "pwr:3V3 (plug C: sliders, screens)" if side == 1 else "pwr:3V3 (mux VIN)"
            if name == "G":
                use = "gnd:G (plug C: GND bus)" if side == 1 else "gnd:G (mux GND, R button)"
            kind, what = (use.split(":", 1) if use else ("off", ""))
            pad_kind = kind if kind not in ("avoid",) else "avoid"
            out.append(f'<circle cx="{f(px)}" cy="{f(py)}" r="7" class="pad pad-{pad_kind}"/>')
            out.append(text(px - side * 14, py + 4, name, "padname", "start" if side < 0 else "end"))
            if what:
                lx = px + side * 22
                anchor = "end" if side < 0 else "start"
                if kind == "avoid":
                    out.append(line(px + side * 7, py, lx, py, "w w-off"))
                    out.append(tag(lx, py, what, "avoid", anchor))
                elif kind == "off":
                    out.append(text(lx, py + 4, what, "port", anchor))
                else:
                    out.append(line(px + side * 7, py, lx, py, f"w w-{kind}"))
                    out.append(tag(lx, py, what, kind, anchor))
    # external buttons in the lid: R on the left under the R pin, B on the right
    ey = by + bl + 70
    rpad = pads[("R", -1)]
    rx_ = rpad[0] - 190                # clear of the pills on the left
    out.append(f'<rect x="{f(rx_ - 30)}" y="{f(ey - 30)}" width="60" height="60" rx="6" class="part"/>')
    out.append(text(rx_, ey + 5, "R", "keyname"))
    out.append(text(rx_, ey + 50, "reset button (lid)", "port"))
    out.append(poly([(rpad[0] - 7, rpad[1]), (rx_, rpad[1]), (rx_, ey - 30)], "w w-rst"))
    out.append(poly([(rx_ - 30, ey + 22), (rx_ - 70, ey + 22), (rx_ - 70, ey + 60)], "w w-gnd"))
    out.append(tag(rx_ - 70, ey + 72, "to G", "gnd"))
    lx_ = bx + bw + 120
    out.append(f'<rect x="{f(lx_ - 30)}" y="{f(ey - 30)}" width="60" height="60" rx="6" class="part"/>')
    out.append(text(lx_, ey + 5, "B", "keyname"))
    out.append(text(lx_, ey + 50, "BOOT0 button (lid)", "port"))
    b0x, b0y = cx + btns["BOOT0"][0] * s, by + btns["BOOT0"][1] * s
    out.append(poly([(b0x - 1.2 * s, b0y + 2 * s), (b0x - 1.2 * s, by + bl + 36), (lx_ - 14, by + bl + 36), (lx_ - 14, ey - 30)], "w w-rst"))
    out.append(poly([(b0x + 1.2 * s, b0y + 2 * s), (b0x + 1.2 * s, by + bl + 22), (lx_ + 14, by + bl + 22), (lx_ + 14, ey - 30)], "w w-rst"))
    out.append(dot(b0x - 1.2 * s, b0y + 2 * s, "joint j-rst"))
    out.append(dot(b0x + 1.2 * s, b0y + 2 * s, "joint j-rst"))
    out.append(text(lx_ - 42, ey - 2, "two thin wires on the board's own", "port", "end"))
    out.append(text(lx_ - 42, ey + 12, "BOOT0 button, under the board", "port", "end"))
    vw, vh = 840, int(ey + 100)
    return (f'<svg viewBox="0 0 {vw} {vh}" role="img" aria-label="WeAct BlackPill as it sits in the lid: upside down, back side up, '
            'USB-C at the top. Right header, from the USB end: B12 to B9, then 5V, G, 3V3. B14 row 3, A8 column 1, A15 column 2, '
            'B6 multiplexer SCL, B7 multiplexer SDA, B8 E1 B, B9 E2 A. Left header, from the USB end: 5V, G, 3V3, B10, B2, B1 E1 A, '
            'B0 column 3 (knob pushes), A7 column 0, A6 to A4 rows 2 to 0, A3 to A1 sliders, A0 E2 B, R to the reset button, '
            'C15, C14, C13, VB. A9, A10, A11, A12, B2, C13, C14 and C15 are avoided. '
            'The B button is wired across the board\'s own BOOT0 button, underneath.">\n' + "\n".join(out) + "\n</svg>")


CHECKLIST = [
    ("Plate", "Switches clipped in; encoders with spacer ring and nut; sliders and screens pegged and glued", "plate"),
    ("Buses", "Column buses: bare copper along each key column, front-row pin to back-row pin, switch pins soldered on", "col"),
    ("Buses", "Row buses: bare copper across each key row, rows 0 and 2 on into the gap by the knobs; sleeve every crossing", "row"),
    ("Buses", "GND and 3V3 pairs: across the front (in front of the screens) and across the slider ends; 2 insulated links up the slider side", "gnd"),
    ("Keys", "Diode from each key's free pin to its row bus, black band at the bus", "row"),
    ("Knobs", "Push: diode from the pin nearer the keys to row 0 (E2) or row 2 (E1) · column 3 wire up the wall, E1 to E2 · C: to its screen's GND pin", "enc"),
    ("Sliders", "Pins 1 and 2 at the back end, pin 3 at the front · pin 1 → 3V3 back bus · pin 3 → its screen's GND pin · 100 nF right of the slider body (from the back): one leg to pin 2, the other to the GND back bus", "pwr"),
    ("Screens", "VCC → 3V3 · GND → GND, jumpers down to the front pair; S5's down the gap by the keys", "pwr"),
    ("Lid", "Male header pins on the BlackPill and multiplexer (long pins up); L5 soldered to the BlackPill's BOOT0 button; BlackPill upside down in its cradle (chips down, USB-C at the back), multiplexer glued right of it, B and R buttons in their pockets", "plate"),
    ("Lid", "Lid wires L1–L6: mux to BlackPill, and the two buttons (harness table)", "rst"),
    ("Harness", "Wires 1–27: soldered at the plate end, gathered into ribbons A–E along the back edge, crimped into plugs A–E (harness table)", "scr"),
]


def checklist_html():
    rows = []
    for i, (grp, what, kind) in enumerate(CHECKLIST):
        rows.append(f'<li><label><input type="checkbox" id="chk{i}"><span class="swatch sw-{kind}"></span>'
                    f'<span class="grp">{grp}</span><span class="what">{what}</span></label></li>')
    return "\n".join(rows)


PICK_PARTS = ([f"K{i}" for i in range(1, 13)] + ["E1", "E2"] + [f"Slider {i}" for i in (1, 2, 3)]
              + SCR_NAMES + ["MUX", "Buttons"])
PICK_BUSES = [(f"row{r}", f"Row {r}") for r in range(ROWS)] + [(f"col{c}", f"Col {c}") for c in range(4)] \
    + [("gnd", "GND"), ("3v3", "3V3")]


def picker_html():
    parts = "".join(f'<button type="button" data-pick="{p}" aria-pressed="false">{p}</button>' for p in PICK_PARTS)
    buses = "".join(f'<button type="button" data-bus="{n}" aria-pressed="false">{lab}</button>' for n, lab in PICK_BUSES)
    return parts, buses


TEMPLATE = Path(__file__).with_name("template.html").read_text()
MAIN, EXITS = main_svg()
html = (TEMPLATE.replace("{{MAIN}}", MAIN)
        .replace("{{HARNESS}}", harness_html(EXITS))
        .replace("{{HARNESS_N}}", str(len(EXITS)))
        .replace("{{DIODE}}", diode_key_svg())
        .replace("{{ENC_MOUNT}}", encoder_mount_svg())
        .replace("{{ENC_PINS}}", encoder_pins_svg())
        .replace("{{BLACKPILL}}", blackpill_svg())
        .replace("{{CHECKLIST}}", checklist_html())
        .replace("{{PICK_PARTS}}", picker_html()[0])
        .replace("{{PICK_BUSES}}", picker_html()[1])
        .replace("{{CHECK_N}}", str(len(CHECKLIST))))
Path(__file__).with_name("wiring.html").write_text(html)
print("wrote wiring.html")
