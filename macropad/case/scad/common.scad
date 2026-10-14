// Sizes shared by every model: the switch and encoder holes, the fasteners,
// and the parts that sit inside the case. Change them here, not in the
// models. Included by deck.scad and parts.scad. Units mm.

/* [Key grid] */
u = 19.05;            // standard key unit; the fit test uses it, the deck has its own key_pitch
rows = 4;
key_cols = 3;

/* [Plate cutouts] */
clip_t = 1.5;         // plate thickness at every switch, encoder and pot; MX clips need 1.5
switch_cut = 14.0;    // tune with fit_switch_encoder.stl
enc_hole = 7.8;       // EC11 M7 bushing; 7.3 printed too small for the thread (fit test, 2026-10-05)
enc_spacer = 3;       // printed spacer on the bushing under the plate: lowers the encoder (and its
                      // shaft) by this much. 0 = no spacer, encoder against the plate
enc_bush_l = 7;       // threaded bushing height above the encoder body; measure yours

/* [Fasteners] */
pilot_d = 2.8;        // M3 screws cut their own thread in this hole, no inserts. Holes print
                      // ~0.4 small here, so this comes out ~2.4-2.5; open it up if the screws bind
pilot_depth = 8;
screw_d = 3.4;
screw_head_d = 6.4;   // M3 flat head, 90 deg countersink

/* [Glue pegs: slide pots and screens] */
// Printed pins under the plate that drop through a part's mounting holes to
// place it; a dab of hot glue over each tip holds it.
peg_d = 2.6;          // 3.0 mm holes on the screen modules

/* [Screen, 0.96" SSD1306 128x64 4-pin I2C module; measured 2026-10-06, check with fit_screen.stl] */
// Mounted under the plate, glass up in a pocket, seen through a window in the
// skin left above it, placed by 4 glue pegs through its mounting holes.
// "along" runs from the flex cable (front) to the header (back).
scr_pcb = [24.5, 26.8];     // across, along (measured)
scr_glass = [24.5, 16.6];   // across, along (measured)
scr_glass_off = -0.6;       // glass centre from the PCB centre, toward the header: 5.6 gap header side, 4.4 flex side
scr_glass_t = 2.2;          // pocket depth: 2.0 glass (measured) + tape
scr_aa = [24.5, 14];         // lit area, across, along: full glass width, 14 down from the glass's header edge (measured)
scr_aa_off = 1.3;           // lit area centre from the glass centre, toward the header
scr_win_inset = 1;          // window edge inside the lit area, each side: a border of plate over the glass edge
scr_fpc = [14, 4.5];        // flex cable folded round the glass's front edge: width, reach
scr_holes = [20.1, 23.4];   // mounting hole pitch, across, along: across from 3.0 holes 0.7 in from each edge; along +1 after fit_screen (2026-10-06)
scr_peg_h = 2.4;            // PCB 1.6 + a tip for the glue
scr_hdr = [11, 3.2];        // header solder joints along the back edge: 4 pins at 2.54 (GND VDD SCK SDA)
scr_hdr_t = 1.5;
scr_tol = 0.3;

/* [Lid] */
lid_t = 2.5;
tol = 0.25;           // sliding fit between lid lip and walls
lip_h = 1.5;
lip_w = 1.2;

/* [USB-C cutout in the back wall] */
usb_cut = [10, 5];

/* [BOOT0 and reset buttons, 6x6 tactile, stem down through the lid] */
rst_body = 6.0;
rst_stem_d = 3.5;
rst_wall_h = 3.5;

$fn = 48;

// Cut for one screen module, centred on the module, plate top at z = 0,
// header toward +y. `t` = plate thickness.
module screen_cut(t) {
    skin = t - scr_glass_t;
    g = scr_glass + [2, 2] * scr_tol;
    gy = scr_glass_off;
    // glass pocket and the flex cable below it
    translate([-g[0] / 2, gy - g[1] / 2, -t - 1]) cube([g[0], g[1], scr_glass_t + 1]);
    translate([-scr_fpc[0] / 2, -scr_pcb[1] / 2 - scr_tol, -t - 1])
        cube([scr_fpc[0], gy - g[1] / 2 + scr_pcb[1] / 2 + scr_tol + 0.01, scr_glass_t + 1]);
    // header solder joints
    translate([-scr_hdr[0] / 2, scr_pcb[1] / 2 - scr_hdr[1], -t - 1]) cube([scr_hdr[0], scr_hdr[1] + scr_tol, scr_hdr_t + 1]);
    // window over the lit area, 45 degree bevel outwards
    w = scr_aa - [2, 2] * scr_win_inset;
    translate([0, gy + scr_aa_off, 0]) hull() {
        translate([0, 0, -skin - 0.01]) linear_extrude(0.01) square(w, center = true);
        translate([0, 0, 0]) linear_extrude(0.01) square(w + [2, 2] * skin, center = true);
    }
}

// The 4 glue pegs for one screen, hanging from the plate's underside; same
// placement as screen_cut.
module screen_pegs(t) {
    for (x = [-1, 1], y = [-1, 1]) translate([x * scr_holes[0] / 2, y * scr_holes[1] / 2, -t - scr_peg_h])
        cylinder(d = peg_d, h = scr_peg_h + 0.01);
}

module rrect(size, r) {
    offset(r = r) offset(delta = -r) square(size);
}

module stadium(w, h) {
    hull() for (s = [-1, 1]) translate([s * (w - h) / 2, 0]) circle(d = h);
}
