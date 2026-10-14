// Small prints for the deck: encoder knobs and spacers, slide-pot caps, and the
// fit tests to print before anything else. Units mm.
//
//   fit_switch_encoder   one switch cutout + one encoder hole (plate fit)
//   fit_screen           one screen window + pocket, as in the deck plate
//   fit_knob_caps        4 slider caps with growing slots + 3 knob stubs with
//                        growing bores; keep the ones that grip, set below
//   fit_knob             just the 3 knobs from fit_knob_caps
//   knob                 encoder knob, print 2
//   enc_spacer           spacer ring on the encoder bushing, under the plate, print 2
//   fader_cap            slide-pot cap, print 3

include <common.scad>

part = "all"; // "fit_switch_encoder", "fit_screen", "fit_knob_caps", "fit_knob", "knob", "enc_spacer", "fader_cap", "all"

/* [Encoder knob, EC11 6 mm shaft] */
enc_shaft_l = 20;     // shaft length from the bushing base (15 or 20), uncut; measure yours
knob_gap = 1;         // knob bottom above the plate
knob_roof = 0.8;      // above the shaft tip: the knob is only as tall as the shaft needs
knob_skirt = 2;       // knob runs this much further down the shaft than knob_gap gives (user, 2026-10-07: cover more shaft, roof unchanged)
enc_shaft = "D";      // "D" = flatted shaft, "round" = no flat left after the cut
// Bore started from a Stream Deck+ knob model (6.16 round, 4.59 across the flat,
// plain, no ribs). Printed: 6.26 / 4.69 tight; 6.46 / 4.89 very loose; fit_knob
// 2026-10-08: 6.38 / 4.81 (3 dots) best.
shaft_bore = 6.38;
d_flat = 4.81;        // across the flat
fit_step = 0.04;      // bore step between the fit-test knobs (round and flat together)
knob_d = 17;          // 19.05 grid minus a keycap's half width leaves room for <= 18
// recess for washer + nut + bushing top: diameter, depth. With a spacer the
// bushing barely clears the plate and takes no nut, so only its top is cleared.
nut_clear = [12, enc_spacer > 0 ? max(0.6, enc_bush_l - clip_t - enc_spacer - knob_gap + 0.6) + knob_skirt : 5.2 + knob_skirt];
spacer_d = 12;        // fits the 13 mm relief pocket under the plate and the EC11's top
grip_n = 24;          // vertical grooves round the knob

// shaft tip 0.2 under the roof
knob_h = enc_shaft_l - clip_t - enc_spacer - knob_gap + 0.2 + knob_roof + knob_skirt;

/* [Slide-pot cap, Bourns PTA DP metal lever] */
lever = [4.0, 1.0];   // blade: along travel, across travel
lever_tol = 0.15;     // added to each side of the slot; tune with fit_knob_caps
fader = [8, 12, 10];  // cap: along travel, across travel, height
fader_slot_d = 6;     // how far the cap pushes onto the lever

// One switch cutout and one encoder hole: print this first to check tolerances.
module fit_switch_encoder() {
    difference() {
        union() {
            linear_extrude(clip_t) rrect([2 * u + 6, u + 6], 2);
            difference() {
                linear_extrude(4) rrect([2 * u + 6, u + 6], 2);
                translate([2, 2, -1]) cube([2 * u + 2, u + 2, 6]);
            }
        }
        translate([3 + u / 2 - switch_cut / 2, 3 + u / 2 - switch_cut / 2, -1])
            cube([switch_cut, switch_cut, clip_t + 2]);
        translate([3 + 1.5 * u, 3 + u / 2, -1]) cylinder(d = enc_hole, h = clip_t + 2);
    }
}

// One screen cut in a 3 mm plate, like the deck's: the module's glass should
// drop into the pocket, the lit area fill the window, and the 4 pegs go
// through the module's mounting holes.
// Printed top face down, as the deck plate is.
fit_plate_t = 3;
module fit_screen() {
    sz = scr_pcb + [8, 8];
    translate([0, 0, fit_plate_t]) rotate([180, 0, 0]) {
        difference() {
            translate([-sz[0] / 2, -sz[1] / 2, -fit_plate_t]) linear_extrude(fit_plate_t) rrect(sz, 2);
            screen_cut(fit_plate_t);
            // arrow on top pointing at the header end
            translate([sz[0] / 2 - 3, sz[1] / 2 - 4, -0.4]) linear_extrude(1) polygon([[-1.5, 0], [1.5, 0], [0, 2]]);
        }
        screen_pegs(fit_plate_t);
    }
}

// Encoder knob, modelled upright (bottom = z 0). Printed upside down so the
// bore and nut recess open upwards and need no supports.

// Spacer ring: slides over the bushing between the encoder body and the plate.
module enc_spacer() {
    difference() {
        cylinder(d = spacer_d, h = enc_spacer, $fn = 64);
        translate([0, 0, -1]) cylinder(d = enc_hole, h = enc_spacer + 2);
    }
}

// Shaft bore, opening at z = 0, `depth` deep, D flat (facing +x) the full
// depth. `d` = round part, the flat stays d_flat - shaft_bore from the far side.
module bore(d, depth) {
    difference() {
        cylinder(d = d, h = depth, $fn = 96);
        if (enc_shaft == "D")
            translate([d_flat - shaft_bore + d / 2, -d, -1]) cube([d, 2 * d, depth + 2]);
    }
    // lead-in chamfer
    cylinder(d1 = d + 1, d2 = d - 0.2, h = 0.6, $fn = 48);
}

// Low knob with a solid hub: the shaft pushes into a plain D bore that starts
// above the nut recess and stops under the roof.
module knob(bore_d = shaft_bore, marks = 0) {
    z0 = nut_clear[1];
    difference() {
        intersection() {
            cylinder(d = knob_d, h = knob_h, $fn = 96);
            // soft top edge
            cylinder(d1 = knob_d + 2 * knob_h - 2, d2 = knob_d - 2, h = knob_h, $fn = 96);
        }
        for (i = [0 : grip_n - 1])
            rotate(i * 360 / grip_n) translate([knob_d / 2, 0, -1]) cylinder(d = 1.2, h = knob_h - 1, $fn = 12);
        translate([0, 0, -0.01]) cylinder(d = nut_clear[0], h = z0 + 0.01, $fn = 64);
        translate([0, 0, z0 - 0.01]) bore(bore_d, knob_h - knob_roof - z0 + 0.01);
        // fit-test marks: dots on the top face (none on the real knob)
        if (marks > 0) for (j = [1 : marks]) rotate(-35 - j * 22) translate([knob_d / 2 - 3, 0, knob_h - 0.6]) cylinder(d = 1.6, h = 1, $fn = 16);
    }
}

// Slide-pot cap, modelled upright, slot opening at the bottom. Printed upside
// down. x = along the travel (the way you push it), y = across.
module fader_cap(slot = lever + [2, 2] * lever_tol, marks = 0) {
    difference() {
        hull() for (x = [-1, 1], y = [-1, 1])
            translate([x * (fader[0] / 2 - 1.5), y * (fader[1] / 2 - 1.5), 0]) cylinder(r = 1.5, h = fader[2], $fn = 24);
        // finger dip: shallow saddle along the travel
        translate([0, -fader[1], fader[2] + 16 - 1.2]) rotate([-90, 0, 0]) cylinder(r = 16, h = 2 * fader[1], $fn = 120);
        // grip ribs across the top
        for (x = [-2, 0, 2]) translate([x, 0, fader[2]]) cube([0.6, fader[1] + 1, 3], center = true);
        translate([-slot[0] / 2, -slot[1] / 2, -0.01]) cube([slot[0], slot[1], fader_slot_d]);
        // fit-test size marks: small notches in one side
        if (marks > 0) for (i = [1 : marks]) translate([-fader[0] / 2 + 1 + i * 1.4, -fader[1] / 2 - 0.5, 2]) cube([0.6, 1, fader[2] - 5]);
    }
}

// Fit test: 4 fader caps with slots growing 0.1 mm a step (notches = step + 1),
// and 3 full knobs with bores shaft_bore -fit_step / 0 / +fit_step (1, 2, 3 dots
// on top). All printed upside down, like the real parts.
module fit_knob_caps() {
    for (i = [0 : 3]) translate([i * (fader[0] + 4), 0, fader[2]]) rotate([180, 0, 0])
        fader_cap(lever + [1, 1] * (0.1 * i), i + 1);
    for (i = [0 : 2]) translate([i * (knob_d + 3) + knob_d / 2, -fader[1] - knob_d / 2, knob_h]) rotate([180, 0, 0])
        knob(shaft_bore - fit_step + fit_step * i, i + 1);
}

// 3 short test hubs, bores shaft_bore -fit_step / 0 / +fit_step (1, 2, 3 dots
// in the roof): just the top 8 mm of the knob's bore, so they print in minutes.
// Printed roof down, as the knob is.
module fit_knob() {
    for (i = [0 : 2]) translate([i * 15, 0, 0]) difference() {
        cylinder(d = 11, h = 8 + knob_roof, $fn = 64);
        translate([0, 0, 8 + knob_roof + 0.01]) rotate([180, 0, 0]) bore(shaft_bore - fit_step + fit_step * i, 8 + 0.01);
        for (j = [1 : i + 1]) rotate(j * 30) translate([4, 0, -0.01]) cylinder(d = 1.2, h = 0.4, $fn = 16);
    }
}

if (part == "fit_switch_encoder") {
    fit_switch_encoder();
} else if (part == "fit_screen") {
    fit_screen();
} else if (part == "fit_knob_caps") {
    fit_knob_caps();
} else if (part == "fit_knob") {
    fit_knob();
} else if (part == "knob") {
    translate([0, 0, knob_h]) rotate([180, 0, 0]) knob();
} else if (part == "enc_spacer") {
    enc_spacer();
} else if (part == "fader_cap") {
    translate([0, 0, fader[2]]) rotate([180, 0, 0]) fader_cap();
} else {
    // everything laid out side by side, as printed (preview only)
    fit_switch_encoder();
    translate([-scr_pcb[0] / 2 - 10, u / 2 + 3, 0]) fit_screen();
    translate([0, u + 6 + fader[1] + knob_d + 8, 0]) fit_knob_caps();
    translate([2 * u + 34, 10, 0]) for (i = [0, 1]) translate([i * (knob_d + 4), 0, knob_h]) rotate([180, 0, 0]) knob();
    translate([2 * u + 34, knob_d + 20, 0]) for (i = [0 : 2]) translate([i * (fader[0] + 4), 0, fader[2]]) rotate([180, 0, 0]) fader_cap();
}
