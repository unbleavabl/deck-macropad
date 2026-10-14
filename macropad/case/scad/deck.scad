// Tilted macropad: 3 slide pots, 12 MX keys, 2 EC11 encoders and 5 OLED
// screens on a 30 degree wedge, with a phone slot across the back. Wired only:
// STM32F411 BlackPill, USB-C in the back wall.
//
//   +---------------------------------------------+
//   | ========== phone slot (recessed) ========== |   back, ~100 mm tall
//   |                                             |
//   |  ||   ||   ||   [K1]  [K2]  [K3]           |
//   |  ||   ||   ||   [K4]  [K5]  [K6]    (E2)   |
//   |  ||   ||   ||   [K7]  [K8]  [K9]    [S5]   |
//   |  ||   ||   ||   [K10] [K11] [K12]   (E1)   |
//   | [S1] [S2] [S3]                      [S4]   |   front, 13 mm tall
//   +---------------------------------------------+
//
// Each screen sits in front of its control: S1-S3 under the sliders, S4 under
// E1 and S5 under E2 in a column right of the keys.
//
// Prints: `deck_plate` (the sloped top in front of the phone slot, printed
// flat), `deck_dock` (the phone slot: its walls, floor and the strip of top
// behind it, printed standing on the slot floor), `deck_frame` (walls, printed
// upright), `deck_lid` (flat bottom carrying the BlackPill and the BOOT0 /
// reset buttons). The dock drops into notches in the frame's side walls and
// screws to it through its strip (2 screws); the plate screws to the frame at
// its front corners and into the dock's front wall at its back corners (4
// screws), so its back edge is clamped too; the lid screws on from below.
//
// Units mm. Origin = front-left-bottom corner of each part, z = 0 on the desk.
// "Face" coordinates: a = across (x), b = up the slope from the front edge,
// n = out of the face; the top surface is n = 0.

include <common.scad>

part = "deck_all"; // "deck_plate", "deck_dock", "deck_frame", "deck_lid", "fit_bp_cradle", "deck_all"

/* [Shared wedge] */
tilt = 30;            // face angle from the desk
front_h = 13;         // height of the face's front edge
face_l = 173.2;       // face length along the slope: screens, keys, sliders and the phone slot
wall = 3;
corner_r = 6;         // the four vertical corners of the case
edge_r = 2.5;         // every other outside edge: top, front, back, sides, bottom
lip_r_front = 1.5;    // the phone slot's front lip (the plate's back edge, a 40 degree corner)
lip_r_back = 2.5;     // the phone slot's back lip (the dock strip's front edge)
slot_chamfer = 1.5;   // where the slot comes out of the side walls

/* [Macropad face] */
margin = 7;
slider_cols = 3;
key_pitch = 21;       // key spacing, both ways: 19.05 + 2 for a ~3 mm gap between caps
block_b = 73;         // centre of the sliders along the slope; just behind the screens (further back and their pins meet the dock's screw blocks)
key_block_b = 62.3;   // centre of the key block along the slope: centred with the sliders and knobs, and high
                      // enough that E2 (level with the top row) clears S5 under the plate
side_m = 5;           // plate edge to the slider screens and to the knob column, each side
enc_gap = 1;          // knob edge to the screen in front of it
enc_r = 8.5;          // knob radius (knob_d / 2 in parts.scad)
plate_t = 3;          // plate thickness
switch_relief = 15.6; // underside pocket round each switch
enc_relief = 13;

/* [Slide pots, Bourns PTA4543 (45 mm travel)] */
pot_travel = 45;
pot_pitch = 26;              // slider spacing: a screen module (24.5) + gap
pot_body = [9.0, 60];        // width, length
pot_screw_pitch = 56;        // M2 threaded holes in the body ends
pot_slot_w = 2.0;            // lever blade is 1 mm thick across the slot
pot_lever_along = 4.0;
pot_peg_d = 1.4;             // into the M2 threaded holes in the body ends (minor dia ~1.57)
pot_peg_h = 2.0;

/* [Phone slot, behind the keys] */
phone_t = 11;         // phone thickness with case: iPhone 16 Plus is 7.8 bare
phone_slot = phone_t + 2.5;
phone_angle = 70;     // phone lean, from the desk
phone_b = 125;        // slot's front edge on the plate, along the slope from the front
phone_depth = 15;     // how far the phone sinks in, along its front face; below 15 the plate's back screw blocks get too short
trough_t = 2.4;       // slot walls and floor
dock_ledge = 8;       // the dock's front wall thickens to this (from the slot face) where the plate screws in
dock_ledge_d = 9;     // ...and reaches this far below the plate's underside
dock_pilot = 6;       // pilot depth for the plate's back screws: deeper would break into the slot

/* [Screens, one below each slider and encoder] */
scr_b = 27.5;         // screen centres along the slope; clear of the front plate screws

/* [STM32F411 BlackPill] */
bp_w = 21.0;
bp_l = 53.2;
bp_t = 1.6;
// Mounted upside down: chips, buttons and USB-C face the lid, long header pins
// point up for the plugs. The board rests on its header solder stubs on two rails.
bp_usb_h = 3.2;       // USB-C receptacle height off the board; check with calipers
bp_stub_h = 2.0;      // header pin stubs + solder on the chip side; check with calipers
bp_usb_z = 5.2;       // USB-C centre above the lid: kept from the chips-up cradle so the frame needs no reprint
bp_raise = 0.8;       // extra height on every cradle part: fit_bp_cradle +0.8 fit best (2026-10-08)
bp_lift = bp_usb_z + bp_usb_h / 2;   // board's chip-side face above the lid, before bp_raise
bp_row = 7.62;        // header rows, either side of the board's centre line
bp_stop_t = 3;        // wall across the board's front edge: takes the USB-C plug's push
bp_side_w = 2;        // cradle side walls, run forward to brace the front wall
bp_notch_w = 8;       // gap at the front wall's foot for the BOOT0 wires

/* [Fasteners] */
boss_r = 4.5;


// ---- derived ----
deck_d = face_l * cos(tilt);                 // footprint depth
back_h = front_h + face_l * sin(tilt);
pad_w = 177.2;        // plate width, kept from the 10-key layout

bp_x = pad_w / 2;
bp_y1 = deck_d - wall - 0.3;
bp_y0 = bp_y1 - bp_l;
btn_pos = [[bp_x + 7, bp_y0 - 16], [bp_x - 7, bp_y0 - 16]];  // BOOT0 (on the side of the board's BOOT0 button), reset (on the R pin's side)

lid_posts = [[wall + 4, 24], [pad_w - wall - 4, 24],
             [wall + 4, deck_d - 12], [pad_w - wall - 4, deck_d - 12]];
plate_screws = [[margin, 6], [pad_w - margin, 6]];           // plate front corners into the frame; kept forward, clear of the front power bus
dock_screws = [[8, 112], [pad_w - 8, 112]];                     // plate back corners into the dock's front wall
strip_screws = [[margin, face_l - 14], [pad_w - margin, face_l - 14]];   // dock strip into the frame

// Place children in face coordinates (a, b, n).
module on_face() {
    translate([0, 0, front_h]) rotate([tilt, 0, 0]) children();
}

// The full wedge of width w: vertical front and back, flat bottom, sloped top.
module wedge(w) {
    rotate([90, 0, 90]) linear_extrude(w)
        polygon([[0, 0], [deck_d, 0], [deck_d, back_h], [0, front_h]]);
}

// The whole case, lid included, with every outside edge rounded: the wedge
// shrunk by edge_r and grown back with a sphere (a hull of 8 spheres, since the
// wedge is convex), then its vertical corners rounded to corner_r. Every part
// is cut from it, so the rounding runs on unbroken across the seams.
module envelope() {
    r = edge_r;
    zt = front_h - r / cos(tilt);                     // top face, moved in by r
    pts = [[r, -lid_t + r], [deck_d - r, -lid_t + r],
           [deck_d - r, zt + (deck_d - r) * tan(tilt)], [r, zt + r * tan(tilt)]];
    intersection() {
        hull() for (x = [r, pad_w - r], p = pts) translate([x, p[0], p[1]]) sphere(r = r, $fn = 24);
        translate([0, 0, -lid_t - 1]) linear_extrude(back_h + lid_t + 2) rrect([pad_w, deck_d], corner_r);
    }
}

// What the rounding takes off round the phone slot: both lips, and a chamfer
// where the slot comes out of each side wall.
module slot_rounding() {
    across(-1, pad_w + 1) {
        lip_cutter(ph_pf, -[cos(tilt), sin(tilt)], -ph_u, lip_r_front);
        lip_cutter(ph_pb, [cos(tilt), sin(tilt)], -ph_u, lip_r_back);
    }
    for (e = [[0, 1], [pad_w, -1]]) hull() {
        across(e[0] - 0.01, e[0] + 0.01) offset(delta = slot_chamfer) slot_profile();
        across(e[0] + e[1] * slot_chamfer - 0.01, e[0] + e[1] * slot_chamfer + 0.01) slot_profile();
    }
}

// 2D: the material in the corner at p (between directions d1 and d2, unit
// vectors along its two faces) that a fillet of radius r removes.
module lip_cutter(p, d1, d2, r) {
    th = acos(d1 * d2);                    // the material's angle at the corner
    l = r / tan(th / 2);                   // corner to where the fillet meets each face
    bis = (d1 + d2) / norm(d1 + d2);
    difference() {
        polygon([p - (d1 + d2) * 0.01, p + d1 * l, p + bis * (r / sin(th / 2)), p + d2 * l]);
        translate(p + bis * (r / sin(th / 2))) circle(r = r, $fn = 48);
    }
}

// Everything above the face plane shifted down by `depth` (n > -depth).
module above_face(w, depth) {
    on_face() translate([-1, -50, -depth]) cube([w + 2, face_l + 100, 100]);
}

function slider_a(i) = side_m < 0 ? margin + pot_pitch * (i + 0.5) : side_m + scr_pcb[0] / 2 + pot_pitch * i;
// keys centred in the space between the slider screens and the knob column
function key_a(c) = side_m < 0 ? margin + slider_cols * pot_pitch + key_pitch * (c + 0.5)
    : (slider_a(slider_cols - 1) + enc_a()) / 2 + key_pitch * (c - (key_cols - 1) / 2);
function key_b(r) = key_block_b + key_pitch * ((rows - 1) / 2 - r);
function slider_b() = block_b;
// encoder column, right of the keys: S4, E1, S5, E2 from the front, packed
// against the side wall
function enc_a() = side_m < 0 ? pad_w - wall - 0.5 - scr_pcb[0] / 2 : pad_w - side_m - scr_pcb[0] / 2;
// E1 just behind S4; E2 level with the top key row; S5 midway between E1's
// back pins and E2's front pins (the pin rows sit 7 mm either side of a knob)
function enc_b(i) = i == 0 ? scr_b + scr_pcb[1] / 2 + enc_gap + enc_r : key_b(0);
function s5_b() = (enc_b(0) + enc_b(1)) / 2;
// screens [a, b]: S1 S2 S3 under the sliders, then S4 (E1) and S5 (E2)
function screens() = concat([for (i = [0 : slider_cols - 1]) [slider_a(i), scr_b]],
    [for (i = [0, 1]) [enc_a(), i == 0 ? scr_b : s5_b()]]);

// ---------------- macropad wedge ----------------

module plate_holes() {
    // keys
    for (r = [0 : rows - 1], c = [0 : key_cols - 1])
        on_face() translate([key_a(c), key_b(r), 0]) {
            translate([-switch_cut / 2, -switch_cut / 2, -plate_t - 1]) cube([switch_cut, switch_cut, plate_t + 2]);
            translate([-switch_relief / 2, -switch_relief / 2, -plate_t - 1])
                cube([switch_relief, switch_relief, plate_t - clip_t + 1]);
        }
    // encoders
    for (i = [0, 1])
        on_face() translate([enc_a(), enc_b(i), 0]) {
            translate([0, 0, -plate_t - 1]) cylinder(d = enc_hole, h = plate_t + 2);
            translate([-enc_relief / 2, -enc_relief / 2, -plate_t - 1])
                cube([enc_relief, enc_relief, plate_t - clip_t + 1]);
        }
    // slide pots: lever slot, body pocket underneath
    for (i = [0 : slider_cols - 1])
        on_face() translate([slider_a(i), block_b, 0]) {
            translate([0, 0, -plate_t - 1]) linear_extrude(plate_t + 2)
                rotate(90) stadium(pot_travel + pot_lever_along + 1, pot_slot_w);
            translate([-pot_body[0] / 2 - 0.3, -pot_body[1] / 2 - 0.5, -plate_t - 1])
                cube([pot_body[0] + 0.6, pot_body[1] + 1, plate_t - clip_t + 1]);
        }
    // screens
    for (p = screens()) on_face() translate([p[0], p[1], 0]) screen_cut(plate_t);
    // plate screws, countersunk from the top
    countersinks(concat(plate_screws, dock_screws));
}

module countersinks(pts) {
    for (p = pts) on_face() translate([p[0], p[1], 0]) {
        translate([0, 0, -plate_t - 1]) cylinder(d = screw_d, h = plate_t + 2);
        translate([0, 0, -(screw_head_d - screw_d) / 2 + 0.01])
            cylinder(d1 = screw_d, d2 = screw_head_d, h = (screw_head_d - screw_d) / 2);
    }
}

// Glue pegs under the plate: 4 per screen, 2 per slide pot (into its
// mounting holes, from the pocket's ceiling).
module plate_pegs() {
    for (p = screens()) on_face() translate([p[0], p[1], 0]) screen_pegs(plate_t);
    for (i = [0 : slider_cols - 1], s = [-1, 1])
        on_face() translate([slider_a(i), block_b + s * pot_screw_pitch / 2, -clip_t - pot_peg_h])
            cylinder(d = pot_peg_d, h = pot_peg_h + 0.01);
}

// Plate in place (sloped). Its edges are vertical so it lines up with the frame;
// its back edge is the slot's front face.
module deck_plate() {
    difference() {
        intersection() {
            envelope();
            above_face(pad_w, plate_t);
        }
        plate_holes();
        across(-1, pad_w + 1) behind(ph_pf);
        slot_rounding();
    }
    plate_pegs();
}

// The phone dock in place: slot walls and floor, the strip of top behind the
// slot, and two thick blocks on the front wall that take the plate's back screws.
module deck_dock() {
    difference() {
        union() {
            // the strip: the top layer behind the slot
            intersection() {
                envelope();
                above_face(pad_w, plate_t);
                across(0, pad_w) behind(ph_pb);
            }
            intersection() {
                envelope();
                union() {
                    // walls and floor; in front of the slot they stop under the plate
                    difference() {
                        across(0, pad_w) trough_profile();
                        intersection() { above_face(pad_w, plate_t); across(-1, pad_w + 1) in_front(ph_pf); }
                    }
                    // screw blocks under the plate's back corners
                    for (p = dock_screws) intersection() {
                        across(p[0] - 4, p[0] + 4) polygon([ph_pf - ph_u * 60, ph_pf + ph_u * 60,
                            ph_pf + ph_n * dock_ledge + ph_u * 60, ph_pf + ph_n * dock_ledge - ph_u * 60]);
                        on_face() translate([-1, -50, -plate_t - dock_ledge_d]) cube([pad_w + 2, face_l + 100, dock_ledge_d]);
                        across(-1, pad_w + 1) above_floor();    // no lower than the floor, so it prints flat
                    }
                }
            }
        }
        across(-1, pad_w + 1) slot_profile();
        slot_rounding();
        for (p = dock_screws) on_face() translate([p[0], p[1], -plate_t - dock_pilot]) cylinder(d = pilot_d, h = dock_pilot + 0.01);
        countersinks(strip_screws);
    }
}

module deck_frame() {
    difference() {
        union() {
            difference() {
                envelope();
                above_face(pad_w, plate_t);
                translate([0, 0, -lid_t - 1]) cube([pad_w, deck_d, lid_t + 1]);     // the lid's share
                translate([wall, wall, -1]) linear_extrude(back_h + 2) rrect([pad_w - 2 * wall, deck_d - 2 * wall], corner_r - wall);
            }
            // plate and strip bosses hang from the top, square to it, tied into the walls
            intersection() {
                wedge(pad_w);
                for (p = concat(plate_screws, strip_screws)) on_face() translate([p[0], p[1], -plate_t - 9]) {
                    cylinder(r = boss_r, h = 9);
                    translate([0, 0, -boss_r]) cylinder(r1 = 0.5, r2 = boss_r, h = boss_r);
                }
            }
            // lid posts
            for (p = lid_posts) translate([p[0], p[1], 0]) cylinder(r = 4, h = 12);
        }
        // trim anything poking above the plate seat
        above_face(pad_w, plate_t);
        // notches in the side walls for the dock, which slides in along the slot
        across(-1, pad_w + 1) offset(delta = tol) trough_outer();
        slot_rounding();
        for (p = concat(plate_screws, strip_screws)) on_face() translate([p[0], p[1], -plate_t - pilot_depth]) cylinder(d = pilot_d, h = pilot_depth + 0.01);
        for (p = lid_posts) translate([p[0], p[1], -0.01]) cylinder(d = pilot_d, h = pilot_depth);
        // USB-C in the back wall
        translate([bp_x, deck_d - wall / 2, bp_usb_z]) rotate([90, 0, 0])
            linear_extrude(wall + 2, center = true) stadium(usb_cut[0], usb_cut[1]);
    }
}

module deck_lid() {
    inset = wall + tol;
    difference() {
        union() {
            intersection() {
                envelope();
                translate([0, 0, -lid_t]) linear_extrude(lid_t) square([pad_w, deck_d]);
            }
            difference() {
                translate([inset, inset, 0]) linear_extrude(lip_h) rrect([pad_w - 2 * inset, deck_d - 2 * inset], corner_r - inset);
                translate([inset + lip_w, inset + lip_w, -1])
                    linear_extrude(lip_h + 2) rrect([pad_w - 2 * (inset + lip_w), deck_d - 2 * (inset + lip_w)], corner_r - inset - lip_w);
                for (p = lid_posts) translate([p[0], p[1], -1]) cylinder(r = 4.5, h = lip_h + 2);
                translate([bp_x - bp_w / 2 - 2, bp_y0, -1]) cube([bp_w + 4, deck_d, lip_h + 2]);
            }
            bp_cradle(bp_raise);
            // BOOT0 and reset button pockets
            for (p = btn_pos)
                translate([p[0] - rst_body / 2 - tol - lip_w, p[1] - rst_body / 2 - tol - lip_w, 0])
                    difference() {
                        cube([rst_body + 2 * tol + 2 * lip_w, rst_body + 2 * tol + 2 * lip_w, rst_wall_h]);
                        translate([lip_w, lip_w, -1]) cube([rst_body + 2 * tol, rst_body + 2 * tol, rst_wall_h + 2]);
                        translate([-1, lip_w + 1.5, 1.5]) cube([rst_body + 2 * lip_w + 4, rst_body - 3, rst_wall_h]);
                    }
        }
        for (p = btn_pos) translate([p[0], p[1], -lid_t - 1]) cylinder(d = rst_stem_d + 0.4, h = lid_t + 2);
        // B / R next to the button holes, so the two can be told apart from below
        for (i = [0, 1]) translate([btn_pos[i][0] + sign(btn_pos[i][0] - bp_x) * 7, btn_pos[i][1], -lid_t - 0.01])
            linear_extrude(0.6) mirror([1, 0, 0]) text(i == 0 ? "B" : "R", size = 5, halign = "center", valign = "center");
        for (p = lid_posts) {
            translate([p[0], p[1], -lid_t - 1]) cylinder(d = screw_d, h = lid_t + 2);
            translate([p[0], p[1], -lid_t - 0.01]) cylinder(d1 = screw_head_d, d2 = screw_d, h = (screw_head_d - screw_d) / 2);
        }
    }
}

// BlackPill cradle, board upside down: a rail under each header row carries the
// pin stubs, so pushing a plug on presses straight down. The USB-C plug pushes
// the board forward, so its front edge bears on a solid wall across the cradle,
// braced by the side walls; the wall stops flush with the board's top so L1-L4
// lie over it, and a notch at its foot lets the BOOT0 wires (L5) out from under
// the board. `raise` lifts the board (and the walls with it).
module bp_cradle(raise) {
    lift = bp_lift + raise;
    for (s = [-1, 1]) {
        translate([bp_x + s * bp_row - 1.3, bp_y0 - tol, 0]) cube([2.6, bp_l + tol - 1, lift - bp_stub_h]);
        translate([bp_x + s * (bp_w / 2 + tol) + (s < 0 ? -bp_side_w : 0), bp_y0 - tol - bp_stop_t, 0])
            cube([bp_side_w, bp_l - 8 + tol + bp_stop_t, lift + bp_t + 1]);
    }
    difference() {
        translate([bp_x - bp_w / 2 - tol - bp_side_w, bp_y0 - tol - bp_stop_t, 0])
            cube([bp_w + 2 * (tol + bp_side_w), bp_stop_t, lift + bp_t]);
        translate([bp_x - bp_notch_w / 2, bp_y0 - tol - bp_stop_t - 1, -1])
            cube([bp_notch_w, bp_stop_t + 2, lift - 1.5 + 1]);
    }
}

// Fit test: the two ends of the cradle 4 times, raised by fit_raises. Front
// end: front wall, its braces and the rails' first 10 mm; back end: the rails'
// last 8 mm and a slice of the frame's back wall with its USB-C hole, where the
// frame has them. The ends are tied by two bars under the rails, so the middle
// prints almost nothing. Drop the board in, plug a cable in: keep the one where
// the plug goes in straight and the board doesn't move, set bp_raise to its number.
fit_raises = [0.4, 0.8, 1.2, 1.6];
module fit_bp_cradle() {
    x0 = bp_x - bp_w / 2 - tol - bp_side_w - 1;
    yf = bp_y0 - tol - bp_stop_t;          // front wall's front face
    y0 = yf - 6;                           // room for the number
    w = bp_w + 2 * (tol + bp_side_w + 1);
    ends = [[y0, bp_y0 + 10], [bp_y1 - 8, deck_d]];   // back end starts where the side walls stop
    for (i = [0 : len(fit_raises) - 1]) translate([i * (w + 3), 0, 0]) translate([-x0, -y0, 1.2]) {
        difference() {
            union() {
                for (e = ends) translate([x0, e[0], -1.2]) cube([w, e[1] - e[0], 1.2]);
                for (s = [-1, 1]) translate([bp_x + s * bp_row - 1.3, y0, -1.2]) cube([2.6, deck_d - y0, 1.2]);
                translate([x0, deck_d - wall, -1.2]) cube([w, wall, bp_usb_z + usb_cut[1] / 2 + 2 + 1.2]);
                intersection() {
                    bp_cradle(fit_raises[i]);
                    for (e = ends) translate([x0 - 1, e[0], -1]) cube([w + 2, e[1] - e[0], 50]);
                }
            }
            translate([bp_x, deck_d - wall / 2, bp_usb_z]) rotate([90, 0, 0])
                linear_extrude(wall + 2, center = true) stadium(usb_cut[0], usb_cut[1]);
            translate([bp_x, y0 + 3, -0.6]) linear_extrude(1)
                text(str("+", fit_raises[i]), size = 4, halign = "center", valign = "center");
        }
    }
}


// ---------------- phone slot ----------------
// A slot across the full width behind the keys, open at both side walls so a
// phone wider than the deck fits in landscape. The phone sinks phone_depth in
// and leans on the slot's back wall at phone_angle; the floor is square to the
// walls, so the phone sits flat on it and the dock prints standing on it.
// Profiles in world (y, z), extruded across the width.

function fpt(b) = [b * cos(tilt), front_h + b * sin(tilt)];      // point on the face
ph_u = [cos(phone_angle), sin(phone_angle)];                       // up the phone
ph_n = [-sin(phone_angle), cos(phone_angle)];                      // toward the user
ph_open = phone_slot / sin(phone_angle - tilt);                    // opening along the face
ph_pf = fpt(phone_b);                                              // opening, front edge
ph_pb = fpt(phone_b + ph_open);                                    // opening, back edge
ph_f = ph_pf - ph_u * phone_depth;                                 // floor, front corner
ph_bk = ph_f - ph_n * phone_slot;                                  // floor, back corner

module slot_profile() {
    polygon([ph_f, ph_bk, ph_bk + ph_u * 200, ph_f + ph_u * 200]);
}

// the slot plus its walls and floor
module trough_outer() {
    polygon([ph_f + (ph_n - ph_u) * trough_t, ph_bk - (ph_n + ph_u) * trough_t,
             ph_bk - ph_n * trough_t + ph_u * 200, ph_f + ph_n * trough_t + ph_u * 200]);
}

module trough_profile() {
    difference() { trough_outer(); slot_profile(); }
}

// everything above the slot floor's underside (along the walls)
module above_floor() {
    base = ph_f - ph_u * trough_t;
    polygon([base - ph_n * 300, base + ph_n * 300, base + ph_n * 300 + ph_u * 300, base - ph_n * 300 + ph_u * 300]);
}

// half-planes bounded by the wall line through p: behind it (away from the user) / in front
module behind(p) { polygon([p - ph_u * 300, p + ph_u * 300, p + ph_u * 300 - ph_n * 400, p - ph_u * 300 - ph_n * 400]); }
module in_front(p) { polygon([p - ph_u * 300, p + ph_u * 300, p + ph_u * 300 + ph_n * 400, p - ph_u * 300 + ph_n * 400]); }

module across(x0, x1) {
    translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(x1 - x0) children();
}

// ---------------- output ----------------

if (part == "deck_plate") {
    // printed top face down: the underside pockets open upwards, no supports
    translate([0, face_l, 0]) rotate([180, 0, 0])
        rotate([-tilt, 0, 0]) translate([0, 0, -front_h]) deck_plate();
} else if (part == "deck_dock") {
    // standing on the slot floor: the walls go straight up, no supports
    translate([0, 0, -(ph_f[0] * sin(90 - phone_angle) + ph_f[1] * cos(90 - phone_angle)) + trough_t])
        rotate([90 - phone_angle, 0, 0]) deck_dock();
} else if (part == "deck_frame") {
    deck_frame();
} else if (part == "fit_bp_cradle") {
    fit_bp_cradle();
} else if (part == "deck_lid") {
    translate([0, 0, lid_t]) deck_lid();
} else {
    color("SteelBlue") deck_frame();
    color("LightSteelBlue") deck_plate();
    color("CadetBlue") deck_dock();
    color("SlateGray") deck_lid();
}
