#!/usr/bin/env python3
"""Generate deck.kicad_pcb: the plate PCB for the tilted deck.

One 2-layer board under the plate, parallel to it, top face 5 mm below the
plate's top (MX standard). Switches clip into the plate and solder to it; the
five screens drop their header pins straight through it; slide pots and
encoders keep their plate mounts and pass through cutouts, their pins joined to
pads beside the cutout by short wires. The multiplexer and BlackPill stay in
the lid: the plate's 27 harness wires solder into pad groups A-E along the
back edge, same plugs as wiring/build.py.

Geometry mirrors case/scad/deck.scad. Face coordinates: a = across from the
plate's left edge (seen from the top), b = up the slope from its front edge.
Board coordinates: x = a + X0, y = Y0 - b (KiCad y points down), top side
toward the plate.

    ./build_pcb.py          place parts, write deck-unrouted.kicad_pcb + deck.dsn
    ./route.sh              autoroute, fill, DRC, Gerbers (calls this first)
"""
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
LIB = Path("/usr/share/kicad/footprints")
X0, Y0 = 20.0, 140.0

# ---- deck geometry, mm (deck.scad, common.scad) ----
PAD_W = 177.2
SIDE_M = 5.0
POT_PITCH = 26.0
KEY_PITCH = 21.0
KEY_BLOCK_B = 62.3
BLOCK_B = 73.0                 # sliders, centre along the slope
SCR_B = 27.5
SCR_PCB = (24.5, 26.8)
SCR_HOLES = (20.1, 23.4)
POT_BODY = (9.0, 60.0)
ENC_GAP, ENC_R = 1.0, 8.5
ROWS, KEY_COLS, SLIDERS = 4, 3, 3


def slider_a(i):
    return SIDE_M + SCR_PCB[0] / 2 + POT_PITCH * i


ENC_A = PAD_W - SIDE_M - SCR_PCB[0] / 2


def key_a(c):
    return (slider_a(SLIDERS - 1) + ENC_A) / 2 + KEY_PITCH * (c - (KEY_COLS - 1) / 2)


def key_b(r):
    return KEY_BLOCK_B + KEY_PITCH * ((ROWS - 1) / 2 - r)


ENC_B = [SCR_B + SCR_PCB[1] / 2 + ENC_GAP + ENC_R, key_b(0)]        # E1, E2
S5_B = (ENC_B[0] + ENC_B[1]) / 2
SCREENS = [(slider_a(i), SCR_B) for i in range(SLIDERS)] + [(ENC_A, SCR_B), (ENC_A, S5_B)]
SCR_HDR_DB = SCR_PCB[1] / 2 - 1.3          # header pin row behind the screen's centre

# ---- board ----
FRONT_B, BACK_B = 5.0, 110.0               # front: as far as the frame's front wall allows; back: 3.4 mm off the phone slot wall at the board's underside
BOSS_A, BOSS_B = 12.5, 11.5                # notches round the frame's front screw bosses (plate_screws, boss_r 4.5): a from each side, b
LEFT_A, RIGHT_A = 4.0, 173.2               # inside the side walls
POT_CUT = (9.6, 61.0)
ENC_CUT = (13.6, 15.2)                     # EC11 body plus its pin rows (7 mm either side)
SCR_WIN = (17.0, -11.5, 9.5)               # relief under each screen's back-side parts: width, b from, b to (from its centre)
PEG_HOLE = 3.2                             # the plate's screen glue pegs (2.6) reach 0.4 mm into the board

# ---- nets (README "Matrix and pins") ----
ROW_PIN = ["A4", "A5", "A6", "B14"]
COL_PIN = ["A7", "A8", "A15", "B0"]
PUSH_ROW = [2, 0]                          # E1 push on row 2, E2 push on row 0, both column 3
ENC_PINS = [("B1", "B8"), ("B9", "A0")]    # (A, B) of E1, E2
POT_PIN = ["A1", "A2", "A3"]
NET_OF_PIN = {p: f"ROW{i}" for i, p in enumerate(ROW_PIN)}
NET_OF_PIN |= {p: f"COL{i}" for i, p in enumerate(COL_PIN)}
NET_OF_PIN |= {p: f"POT{i + 1}" for i, p in enumerate(POT_PIN)}
for e, (pa, pb) in enumerate(ENC_PINS):
    NET_OF_PIN[pa], NET_OF_PIN[pb] = f"E{e + 1}A", f"E{e + 1}B"
NET_OF_PIN |= {"G": "GND", "3V3": "3V3"}
NET_OF_PIN |= {f"S{d}{c}": f"S{d}{c}" for c in range(5) for d in "DC"}
# harness pad groups: two columns in the channels between the key columns (nothing above them),
# pad 1 (square) at the front end; None = empty position, keeping the plug's spacing
HARNESS = [("A", ["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "B0", "B1"]),
           ("D", ["B14", None, "A8"]),
           ("E", ["A15"]),
           ("C", ["B8", "B9", None, "G", "3V3"]),
           ("B", [f"S{d}{c}" for c in range(5) for d in "DC"])]
HARNESS_COLS = [(key_a(0) + KEY_PITCH / 2, 62.0, ["E", "D", "A"]),      # (a, b of the first pad, groups front to back)
                (key_a(1) + KEY_PITCH / 2, 62.0, ["B", "C"])]
GROUP_GAP = 3.0
SCREEN_PINS = ["GND", "VCC", "SCL", "SDA"]     # left to right seen from the top (user's modules, 2026-10-07)

board = pcbnew.BOARD()
nets = {}


def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    return nets[name]


def P(a, b):
    return pcbnew.VECTOR2I(pcbnew.FromMM(X0 + a), pcbnew.FromMM(Y0 - b))


def add_fp(lib, name, ref, a, b, rot=0, bottom=False, value=None):
    fp = pcbnew.FootprintLoad(str(LIB / f"{lib}.pretty"), name)
    if fp is None:
        sys.exit(f"footprint {lib}:{name} not found")
    fp.SetReference(ref)
    fp.SetValue(value or name)
    fp.Value().SetVisible(False)
    board.Add(fp)
    fp.SetPosition(P(a, b))
    fp.SetOrientationDegrees(rot)
    if bottom:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    return fp


def peg_hole(ref, a, b):
    """Bare NPTH hole for one of the plate's glue pegs (no courtyard: the screen's header is close)."""
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("deck", "PegHole_3.2mm"))      # freerouting's SES needs a name
    fp.SetReference(ref)
    fp.Reference().SetVisible(False)
    fp.SetValue("peg")
    fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    h = pcbnew.PAD(fp)
    h.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    h.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    d = pcbnew.FromMM(PEG_HOLE)
    h.SetSize(pcbnew.VECTOR2I(d, d))
    h.SetDrillSize(pcbnew.VECTOR2I(d, d))
    h.SetLayerSet(h.UnplatedHoleMask())
    fp.Add(h)
    board.Add(fp)
    fp.SetPosition(P(a, b))


def pad(fp, num):
    return [p for p in fp.Pads() if p.GetNumber() == str(num)][0]


def pad_ab(p):
    v = p.GetPosition()
    return pcbnew.ToMM(v.x) - X0, Y0 - pcbnew.ToMM(v.y)


def connect(fp, num, name):
    pad(fp, num).SetNet(net(name))


def place_centred(fp, a, b):
    """Move fp so the midpoint of its pads lands on (a, b)."""
    pts = [pad_ab(p) for p in fp.Pads() if p.GetNumber()]
    ca = sum(x for x, _ in pts) / len(pts)
    cb = sum(y for _, y in pts) / len(pts)
    fp.Move(pcbnew.VECTOR2I(pcbnew.FromMM(a - ca), pcbnew.FromMM(cb - b)))


def header(ref, n, a, b, along_a, names, bottom=False):
    """1xN 2.54 header, pad 1 at (a, b), running +a (along_a) or +b; names[i] = net or None."""
    fp = add_fp("Connector_PinHeader_2.54mm", f"PinHeader_1x{n:02d}_P2.54mm_Vertical", ref, a, b,
                rot=90 if along_a else 180, bottom=bottom)
    for i, nm in enumerate(names):
        p = pad(fp, i + 1)
        want = (a + 2.54 * i, b) if along_a else (a, b + 2.54 * i)
        got = pad_ab(p)
        assert abs(got[0] - want[0]) < 0.01 and abs(got[1] - want[1]) < 0.01, (ref, i, got, want)
        if nm:
            p.SetNet(net(nm))
    fp.Reference().SetVisible(False)      # labelled by hand instead
    return fp


def text(s, a, b, size=1.0, layer=pcbnew.F_SilkS, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(P(a, b))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(size * 0.15))
    t.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


def both_silk(s, a, b, size=1.0, rot=0):
    text(s, a, b, size, pcbnew.F_SilkS, rot)
    text(s, a, b, size, pcbnew.B_SilkS, rot)


def edge_poly(pts):
    for (a1, b1), (a2, b2) in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(a1, b1))
        s.SetEnd(P(a2, b2))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)


def edge_rect(a, b, w, h):
    """Rectangle centred on (a, b), w across, h along."""
    edge_poly([(a - w / 2, b - h / 2), (a + w / 2, b - h / 2), (a + w / 2, b + h / 2), (a - w / 2, b + h / 2)])


# ---------------- outline ----------------
# slider 1's cutout opens to the left edge and E2's to the back edge: nothing needs
# the board beside them, and it keeps clear of the dock's screw blocks in the back corners
pot1_l = slider_a(0) - POT_CUT[0] / 2
pot1_r = slider_a(0) + POT_CUT[0] / 2
pot_f = BLOCK_B - POT_CUT[1] / 2
e2_l = ENC_A - ENC_CUT[0] / 2
e2_f = ENC_B[1] - ENC_CUT[1] / 2
edge_poly([(LEFT_A, BOSS_B), (BOSS_A, BOSS_B), (BOSS_A, FRONT_B), (PAD_W - BOSS_A, FRONT_B), (PAD_W - BOSS_A, BOSS_B),
           (RIGHT_A, BOSS_B), (RIGHT_A, e2_f), (e2_l, e2_f), (e2_l, BACK_B),
           (pot1_r, BACK_B), (pot1_r, pot_f), (LEFT_A, pot_f)])
for i in (1, 2):
    edge_rect(slider_a(i), BLOCK_B, *POT_CUT)
edge_rect(ENC_A, ENC_B[0], *ENC_CUT)
for a, b in SCREENS:
    edge_rect(a, b + (SCR_WIN[1] + SCR_WIN[2]) / 2, SCR_WIN[0], SCR_WIN[2] - SCR_WIN[1])

# ---------------- keys and their diodes ----------------
for r in range(ROWS):
    for c in range(KEY_COLS):
        k = r * KEY_COLS + c + 1
        a, b = key_a(c), key_b(r)
        # footprint origin is its pad 1; the switch centre is at (-2.54, +5.08) from it
        sw = add_fp("Button_Switch_Keyboard", "SW_Cherry_MX_1.00u_PCB", f"K{k}", a + 2.54, b + 5.08, value="MX")
        gi = sw.GraphicalItems()
        for g in [gi[j] for j in range(len(gi))]:         # (iterating it directly fails on Python 3.14)
            if g.GetLayer() == pcbnew.F_SilkS:      # outline sits under the switch; frees the channel for harness labels
                sw.Remove(g)
        connect(sw, 1, f"COL{c}")
        connect(sw, 2, f"K{k}D")
        d = add_fp("Diode_THT", "D_DO-35_SOD27_P7.62mm_Horizontal", f"D{k}", 0, 0, bottom=True, value="1N4148")
        place_centred(d, a, b - KEY_PITCH / 2)
        connect(d, 1, f"ROW{r}")          # pad 1 = cathode (band)
        connect(d, 2, f"K{k}D")

# ---------------- encoders: cutout, 5 lead pads left of it, push diode ----------------
for e in range(2):
    b = ENC_B[e]
    pa = e2_l - 2.55 if e else ENC_A - ENC_CUT[0] / 2 - 2.55
    names = [f"E{e + 1}A", "GND", f"E{e + 1}B", f"E{e + 1}P", "COL3"]
    header(f"J_E{e + 1}", 5, pa, b - 5.08, False, names)
    for i, lab in enumerate(["A", "C", "B", "SW", "SW"]):
        text(lab, pa - 2.9, b - 5.08 + 2.54 * i, 0.8)     # top only: the push diode sits here underneath
    both_silk(f"E{e + 1}", ENC_A, b, 2.0)
    d = add_fp("Diode_THT", "D_DO-35_SOD27_P7.62mm_Horizontal", f"D{13 + e}", 0, 0, rot=90, bottom=True, value="1N4148")
    place_centred(d, (key_a(2) + 7.0 + ENC_A - SCR_PCB[0] / 2) / 2, b)
    connect(d, 1, f"ROW{PUSH_ROW[e]}")
    connect(d, 2, f"E{e + 1}P")

# ---------------- slide pots: cutout, lead pads right of it, 100 nF ----------------
for i in range(SLIDERS):
    a = slider_a(i)
    pa = a + POT_CUT[0] / 2 + 2.6
    back = BLOCK_B + POT_BODY[1] / 2 - 1.5      # pins 1 and 2 at the back end
    front = BLOCK_B - POT_BODY[1] / 2 + 1.5     # pin 3 alone at the front end
    header(f"J_P{i + 1}", 2, pa, back - 2.54, False, [f"POT{i + 1}", "3V3"])
    header(f"J_P{i + 1}G", 1, pa, front, False, ["GND"])
    both_silk("2", pa + 1.9, back - 2.54, 0.8)
    both_silk("1", pa + 1.9, back, 0.8)
    both_silk("3", pa + 1.9, front, 0.8)
    both_silk(f"SLIDER {i + 1}", pa, BLOCK_B, 1.2, rot=90)
    cap = add_fp("Capacitor_THT", "C_Disc_D3.0mm_W1.6mm_P2.50mm", f"C{i + 1}", 0, 0, rot=90, bottom=True, value="100n")
    place_centred(cap, pa + 4.5, back - 6.5)
    connect(cap, 1, f"POT{i + 1}")
    connect(cap, 2, "GND")

# ---------------- screens: header pins through the board, peg holes ----------------
for s, (a, b) in enumerate(SCREENS):
    hb = b + SCR_HDR_DB
    nm = {"GND": "GND", "VCC": "3V3", "SCL": f"SC{s}", "SDA": f"SD{s}"}
    header(f"S{s + 1}", 4, a - 1.5 * 2.54, hb, True, [nm[p] for p in SCREEN_PINS])
    for k, p in enumerate(SCREEN_PINS):
        both_silk(p, a + (k - 1.5) * 2.54, hb - 2.0, 0.8)
    both_silk(f"S{s + 1}", a, b + (SCR_WIN[1] + SCR_WIN[2]) / 2, 2.0)
    for x in (-1, 1):
        for y in (-1, 1):
            peg_hole(f"H{s + 1}{'LR'[x > 0]}{'FB'[y > 0]}", a + x * SCR_HOLES[0] / 2, b + y * SCR_HOLES[1] / 2)

# ---------------- harness pads, between the key columns ----------------
groups = dict(HARNESS)
for a, b, names in HARNESS_COLS:
    for g in names:
        pins = groups[g]
        header(f"J{g}", len(pins), a, b, False, [NET_OF_PIN.get(p) if p else None for p in pins])
        both_silk(g, a - 2.4, b, 1.2)
        for i, p in enumerate(pins):
            if p:
                both_silk(p, a + 2.6, b + 2.54 * i, 0.8)
        b += 2.54 * len(pins) + GROUP_GAP

# ---------------- labels ----------------
# harness legend in the free strip between slider 3 and the keys (no room for a label per pad)
for i, (g, pins) in enumerate(HARNESS):
    both_silk(f"{g}: " + " ".join(p or "-" for p in pins), 81.0 + 1.3 * i, 70, 0.8, rot=90)
text("deck plate PCB v1 - TOP: toward the plate", 114.6, 15.2, 1.0)
text("deck plate PCB v1 - BOTTOM: toward the lid", 114.6, 15.2, 1.0, pcbnew.B_SilkS)

# ---------------- rules (JLCPCB 2-layer) and GND pours ----------------
ds = board.GetDesignSettings()
ds.SetCopperLayerCount(2)
ds.m_TrackMinWidth = pcbnew.FromMM(0.15)          # freerouting necks down to 0.15 at a few pads; JLCPCB does 0.127
ds.m_MinClearance = pcbnew.FromMM(0.2)
ds.m_ViasMinSize = pcbnew.FromMM(0.6)
ds.m_MinThroughDrill = pcbnew.FromMM(0.3)
ds.m_CopperEdgeClearance = pcbnew.FromMM(0.25)

nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetTrackWidth(pcbnew.FromMM(0.25))
nc.SetClearance(pcbnew.FromMM(0.25))
nc.SetViaDiameter(pcbnew.FromMM(0.7))
nc.SetViaDrill(pcbnew.FromMM(0.35))


def add_pours(board):
    """GND pour on both layers, over the whole board."""
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(net("GND"))
        z.SetLocalClearance(pcbnew.FromMM(0.3))
        z.SetMinThickness(pcbnew.FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        ol = z.Outline()
        ol.NewOutline()
        for pa_, pb_ in [(LEFT_A, FRONT_B), (RIGHT_A, FRONT_B), (RIGHT_A, BACK_B), (LEFT_A, BACK_B)]:
            ol.Append(P(pa_, pb_))
        board.Add(z)


if __name__ == "__main__":
    # GND is routed as tracks like every other net (freerouting would treat a pour as a
    # plane and leave pads stranded in islands); route.sh adds the pours afterwards
    pcbnew.ExportSpecctraDSN(board, str(HERE / "deck.dsn"))
    add_pours(board)
    # GND is routed as tracks too, so a pad joined to the pour by a single spoke is fine
    rules = '(version 1)\n(rule "one spoke is enough" (constraint min_resolved_spokes 1))\n'
    for stem in ("deck", "deck-unrouted"):
        (HERE / f"{stem}.kicad_dru").write_text(rules)
    out = HERE / "deck-unrouted.kicad_pcb"
    board.Save(str(out))
    print(f"{len(board.GetFootprints())} footprints, {len(nets)} nets -> {out.name}, deck.dsn")
