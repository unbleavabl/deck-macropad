// Flat, blank MX keycaps with a press-in label. Units mm.
//
// The cap is black and plain, printed upright (skirt on the bed, stem post
// from the bed up) so nothing needs supports: the label pocket opens upward and
// the only bridge is the cavity ceiling between the skirt and the post. The
// label is printed separately and pressed into the pocket from the top, flush
// with the cap, held by friction. To change one, pull the cap and push a
// paperclip up through the eject hole in the pocket floor.
//
// Labels are black with a raised white legend, printed face up so the AMS
// swaps colour once per print: the black body first, then the white legend
// standing legend_d proud of it, its top flush with the cap. Load label_body
// (black) and label_legend (white) as two parts of one object. Caps and blank
// labels are single colour; print them separately.
//
//   keycap         one cap, printed upright; print 12
//   label_body     black part of the label set (the 12 keys)
//   label_legend   white part of the label set, same placement
//   label_blank    one plain black label (single colour, full height)
//   glue_body / glue_legend   glue-on labels for a bought flat cap (KeyCap v4: flat 18.4 mm
//                  top, r 1.5): 12 thin plates, black base + raised white legend, laid out as
//                  on the pad; print both as one object, ironing on, then glue on the caps
//   fit_keycap_caps    3 caps, stem cross -0.1 / 0 / +0.1 (dots on the skirt's front edge). Black.
//   fit_keycap_labels  3 labels, clearance -0.05 / 0 / +0.05 (dots underneath): black body
//   fit_keycap_legend  their white legends: load with fit_keycap_labels as one object
//   all            preview: the 12 caps with their labels, as on the pad

include <common.scad>
use <fonts/DeckIcons.ttf>

part = "all"; // "keycap", "label_body", "label_legend", "label_blank", "glue_body", "glue_legend", "fit_keycap_caps", "fit_keycap_labels", "fit_keycap_legend", "all"

/* [Cap] */
cap = 18;             // square; the deck's key_pitch 21 leaves a 3 mm gap
cap_h = 6.8;          // skirt bottom (= post bottom) to top face
cap_r = 1.5;          // vertical corners
cap_chamfer = 0.4;    // top edge
wall_t = 1.2;         // skirt

/* [MX stem socket] */
stem_d = 5.5;         // post round the cross, from the bed up
cross = [4.1, 1.3];   // cross arm length, width; tune with fit_keycap_caps
cross_depth = 4.0;    // how far the switch stem goes in
cross_step = 0.1;     // between the fit-test caps

/* [Label pocket] */
label_t = 1.8;        // label thickness = pocket depth
legend_d = 0.8;       // white legend height on the black body: 4 layers at 0.2, enough to hide the black under it
rim = 1.4;            // cap top left round the label, each side
pocket_r = 0.8;       // pocket corners
label_tol = 0.05;     // clearance each side between label and pocket (press fit); tune with fit_keycap_labels
lead_in = 0.3;        // chamfer round the pocket mouth, so the label starts in straight
eject_d = 1.6;        // eject hole through the pocket floor, beside the post
eject_x = 4.6;

/* [Legends] */
icon_size = 11;       // Material Symbols' 20/24 live area, the size of a round icon
icon_font = "Deck Icons";   // Material Symbols Rounded, filled, weight 600 (fonts/DeckIcons.ttf)
// One per key, K1..K12 as on the pad (from ~/.config/deckd/config.toml).
// An icon is a Material Symbols codepoint as "\uXXXX"; text is printed as is (keep it to 2-4 characters);
// "calc" is the calculator drawn by calc_2d. Keep every white stroke >= 0.8 mm and every
// gap >= 0.6 mm or the 0.4 nozzle loses it (Material's calculate and document_scanner failed).
legends = [
    ["icon", "\ue318"],   // K1  Caps <> Ctrl         keyboard_capslock
    ["icon", "\uf7d2"],   // K2  region screenshot    screenshot_region
    ["icon", "\ue14f"],   // K3  clipboard            content_paste
    ["calc", ""],         // K4  calculator           drawn here (calc_2d): Material's calculate has slots too fine to print
    ["icon", "\ue02b"],   // K5  mic mute             mic_off
    ["icon", "\ue310"],   // K6  switch output        headphones
    ["icon", "\uf679"],   // K7  screen record        screen_record
    ["icon", "\ue262"],   // K8  copy text (OCR)      text_fields (document_scanner's inner lines were too thin to print)
    ["icon", "\ue3b8"],   // K9  color picker         colorize
    ["icon", "\ue91f"],   // K10 voice typing         record_voice_over
    ["icon", "\ue15c"],   // K11 do not disturb       do_not_disturb_on
    ["icon", "\uefef"],   // K12 keep awake           coffee
];
text_size = 4.5;
text_font = "Liberation Sans:style=Bold";

pocket_w = cap - 2 * rim;                  // square pocket
label_w = pocket_w - 2 * label_tol;

// Label, modelled face up: bottom at z = 0, top face at z = label_t.
module label_shape(tol = label_tol) {
    w = pocket_w - 2 * tol;
    r = max(0.1, pocket_r - tol);
    // small chamfer round the bottom edge: helps it into the pocket, hides elephant foot
    hull() {
        translate([0, 0, 0.3]) linear_extrude(label_t - 0.3) offset(r = r) square(w - 2 * r, center = true);
        linear_extrude(label_t) offset(r = r) square(w - 2 * r - 0.6, center = true);
    }
}

module legend_2d(i, size = icon_size) {
    L = legends[i];
    // text size 1 draws the icon grid 1.4 mm square, off the font's centre by (0.016, 0.071)
    k = size * 24 / 20 / 1.4;
    if (L[0] == "icon")
        translate(-[0.016, 0.071] * k) text(L[1], size = k, font = icon_font, halign = "center", valign = "center");
    else if (L[0] == "calc")
        scale(size / icon_size) calc_2d();
    else
        text(L[1], size = text_size, font = text_font, halign = "center", valign = "center");
}

// Calculator in Material's calculate style, sized to print: a white rounded square,
// icon_size across, with - x + = cut in as calc_slot wide slots; the = bars have
// calc_bar of white between them. make_stickers.py draws the same shape.
calc_slot = 0.9;
calc_arm = 3.0;       // symbol size
calc_bar = 1.0;       // white between the = bars
calc_pos = 2.4;       // symbol centres from the middle
calc_r = 2;           // square's corners

module calc_2d() {
    module bar(a = 0) rotate(a) hull() for (s = [-1, 1]) translate([s * (calc_arm - calc_slot) / 2, 0]) circle(d = calc_slot, $fn = 24);
    difference() {
        offset(r = calc_r) square(icon_size - 2 * calc_r, center = true);
        translate([-calc_pos, calc_pos]) bar();                                   // -
        translate([calc_pos, calc_pos]) { bar(45); bar(-45); }                    // x
        translate([-calc_pos, -calc_pos]) { bar(); bar(90); }                     // +
        for (y = [-1, 1]) translate([calc_pos, -calc_pos + y * (calc_slot + calc_bar) / 2]) bar();   // =
    }
}

// The legend volume: the top legend_d of the label, kept inside the visible face.
module legend(i) {
    vis = [label_w - 0.8, label_w - 0.8];
    translate([0, 0, label_t - legend_d]) linear_extrude(legend_d + 0.01)
        intersection() {
            legend_2d(i);
            square(vis, center = true);
        }
}

// Black part: with a legend, the label minus its top legend_d (the legend stands
// on it); i = -1 is a plain label, full height.
module label_body(i = -1, tol = label_tol) {
    difference() {
        label_shape(tol);
        if (i >= 0) translate([-cap, -cap, label_t - legend_d]) cube([2 * cap, 2 * cap, legend_d + 1]);
    }
}

// White part: the legend, standing on the body.
module label_legend(i, tol = label_tol) {
    intersection() { label_shape(tol); legend(i); }
}

// Keycap, modelled upright as printed: skirt and post bottom at z = 0, top face at z = cap_h, back toward +y.
module keycap(cross_sz = cross, marks = 0) {
    ceil_z = cross_depth;
    difference() {
        // body with a chamfered top edge
        hull() {
            linear_extrude(cap_h - cap_chamfer) offset(r = cap_r) square(cap - 2 * cap_r, center = true);
            linear_extrude(cap_h) offset(r = cap_r - cap_chamfer) square(cap - 2 * cap_r, center = true);
        }
        // hollow skirt, minus the stem post
        difference() {
            ri = max(0.1, cap_r - wall_t);
            translate([0, 0, -0.01]) linear_extrude(ceil_z + 0.01)
                offset(r = ri) square(cap - 2 * wall_t - 2 * ri, center = true);
            translate([0, 0, -0.02]) cylinder(d = stem_d, h = ceil_z + 0.04);
        }
        // MX cross, with a small lead-in
        translate([0, 0, -0.01]) for (a = [0, 90]) rotate(a) {
            translate([-cross_sz[0] / 2, -cross_sz[1] / 2, 0]) cube([cross_sz[0], cross_sz[1], cross_depth]);
            hull() {
                translate([-cross_sz[0] / 2 - 0.3, -cross_sz[1] / 2 - 0.3, 0]) cube([cross_sz[0] + 0.6, cross_sz[1] + 0.6, 0.01]);
                translate([-cross_sz[0] / 2, -cross_sz[1] / 2, 0.3]) cube([cross_sz[0], cross_sz[1], 0.01]);
            }
        }
        // label pocket with a chamfered mouth
        translate([0, 0, cap_h - label_t]) linear_extrude(label_t + 1)
            offset(r = pocket_r) square(pocket_w - 2 * pocket_r, center = true);
        translate([0, 0, cap_h - lead_in]) hull() {
            linear_extrude(0.01) offset(r = pocket_r) square(pocket_w - 2 * pocket_r, center = true);
            translate([0, 0, lead_in]) linear_extrude(0.01) offset(r = pocket_r + lead_in) square(pocket_w - 2 * pocket_r, center = true);
        }
        // eject hole: pocket floor to the cavity, clear of the post
        translate([eject_x, 0, ceil_z - 1]) cylinder(d = eject_d, h = cap_h, $fn = 16);
        // fit-test marks: dots in the skirt's front edge
        if (marks > 0) for (j = [1 : marks]) translate([(j - (marks + 1) / 2) * 2, -cap / 2 + wall_t / 2, -0.01]) cylinder(d = 0.8, h = 0.4, $fn = 12);
    }
}

/* [Glue-on labels, for a bought flat cap] */
// KeyCap v4 (~/Downloads/KeyCap+v4.stl, measured 2026-10-08): flat top 18.4 mm square,
// square edges, corners ~r 1.5, 6 mm tall.
glue_w = 17.8;        // 0.3 mm of the cap's top left round it, so a slightly-off placement doesn't show
glue_r = 1.2;
glue_base = 1.2;      // black, 6 layers (0.8 curled on the bed, 2026-10-08); the white legend (legend_d) stands on it
glue_icon = 13;       // icons scaled to the bigger face (11 on the 15.1 mm press-in labels)
glue_gap = 8;         // between labels on the plate: room for each one's 3 mm brim

module glue_body() {
    linear_extrude(glue_base) offset(r = glue_r) square(glue_w - 2 * glue_r, center = true);
}

module glue_legend(i) {
    translate([0, 0, glue_base]) linear_extrude(legend_d)
        intersection() {
            legend_2d(i, glue_icon);
            offset(r = glue_r - 0.4) square(glue_w - 0.8 - 2 * (glue_r - 0.4), center = true);
        }
}

// The label set laid out face up for printing, as on the pad (K1 top left).
// `what` = "body" or "legend": print both as parts of one object.
set_cols = 3;
set_gap = 3;
module label_set(what) {
    for (i = [0 : len(legends) - 1])
        translate([(i % set_cols) * (label_w + set_gap), -floor(i / set_cols) * (label_w + set_gap), 0]) {
            if (what == "body") label_body(i);
            else label_legend(i);
        }
}

// Fit-test labels carry real icons, so the test also tries the AMS: calculator
// (finest detail), region screenshot (thin strokes), do not disturb (big fill).
fit_icons = [3, 1, 10];

module fit_keycap_caps() {
    for (i = [0 : 2]) translate([i * (cap + 4), 0, 0])
        keycap(cross + [1, 1] * (cross_step * (i - 1)), i + 1);
}

// what = "body" (black) or "legend" (white); face up, like the label set
module fit_keycap_labels(what) {
    for (i = [0 : 2]) translate([i * (label_w + set_gap), 0, 0]) {
        t = label_tol + 0.05 * (i - 1);
        if (what == "legend") label_legend(fit_icons[i], t);
        else difference() {
            label_body(fit_icons[i], t);
            // dots on the label's underside
            for (j = [1 : i + 1]) translate([(j - (i + 2) / 2) * 2, 0, -0.01]) cylinder(d = 1, h = 0.4, $fn = 12);
        }
    }
}

if (part == "keycap") {
    keycap();
} else if (part == "label_body") {
    label_set("body");
} else if (part == "label_legend") {
    label_set("legend");
} else if (part == "glue_body" || part == "glue_legend") {
    for (i = [0 : len(legends) - 1])
        translate([(i % set_cols) * (glue_w + glue_gap), -floor(i / set_cols) * (glue_w + glue_gap), 0])
            if (part == "glue_body") glue_body(); else glue_legend(i);
} else if (part == "label_blank") {
    label_body(-1);
} else if (part == "fit_keycap_caps") {
    fit_keycap_caps();
} else if (part == "fit_keycap_labels") {
    fit_keycap_labels("body");
} else if (part == "fit_keycap_legend") {
    fit_keycap_labels("legend");
} else {
    // the 12 caps with their labels as on the pad, K1 top left, back toward +y
    for (i = [0 : len(legends) - 1]) translate([(i % 3) * 21, -floor(i / 3) * 21, 0]) {
        color("#222") render() keycap();
        translate([0, 0, cap_h - label_t]) {
            color("#222") render() label_body(i);
            color("white") render() label_legend(i);
        }
    }
}
