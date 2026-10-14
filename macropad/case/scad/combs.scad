// Harness combs: printed sleeves that hold the single-pin Dupont housings of
// the plate-to-lid wires side by side, in header order, so each group plugs
// on and off its header as one block and stays in order when unplugged.
//
// Slide each wire sideways into its slot in the comb lip (front face), then
// pull its housing up into the sleeve until it stops under the lip. The wire
// number is engraved on the back face above each slot; the plug letter is on
// the end face at the first pin of the list. A solid block fills each empty
// header pin (5V in C, B15 in D), so a comb only goes on one way along the row.
//
// Print standing as modelled (lip up), no supports. Print fit_comb first and
// set `fit` to the slot that holds a housing snugly but lets it slide.
// Units mm.

part = "all"; // "comb_A", "comb_B", "comb_C", "comb_D", "fit_comb", "all"

/* [Dupont housing] */
pitch = 2.54;
housing = 2.5;        // square housing cross-section
fit = 0.3;            // clearance added to the cavity; tune with fit_comb

/* [Comb] */
wall = 1.2;
body_h = 9;           // sleeve height around the housing (a housing is ~14 long)
lip = 1.2;            // comb lip on top that the housings stop against
wire_slot = 1.7;      // slot per wire in the lip; wider than the wire, narrower than the housing
text_size = 1.5;
text_depth = 0.4;
letter_size = 3.5;

// Wire numbers in header order (0 = empty pin, filled solid). See wiring.html, harness table.
COMBS = [
    ["A", [14, 15, 16, 17, 1, 2, 3, 5, 8, 11]],      // BlackPill A0 A1 A2 A3 A4 A5 A6 A7 B0 B1
    ["B", [18, 19, 20, 21, 22, 23, 24, 25, 26, 27]], // mux SD0 SC0 SD1 SC1 ... SD4 SC4
    ["C", [12, 13, 0, 9, 10]],                       // BlackPill B8 B9 (5V) G 3V3
    ["D", [4, 0, 6]],                                // BlackPill B14 (B15) A8
];                                                   // E (A15, wire 7) is a single plug: no comb

$fn = 24;

function depth(f) = housing + f + 2 * wall;
function length(n) = n * pitch + 2 * wall;

module comb(letter, nums, f = fit) {
    n = len(nums);
    D = depth(f);
    L = length(n);
    H = body_h + lip;
    difference() {
        cube([L, D, H]);
        for (i = [0 : n - 1]) if (nums[i] > 0) {
            cx = wall + (i + 0.5) * pitch;
            // housing cavity; neighbouring cavities merge into one run
            translate([wall + i * pitch - f / 2, wall, -1])
                cube([pitch + f, housing + f, body_h + 1]);
            // the comb slot: in from the front face, through the lip, to the cavity centre
            translate([cx - wire_slot / 2, -1, body_h - 0.01])
                cube([wire_slot, 1 + wall + (housing + f + wire_slot) / 2, lip + 1]);
            // wire number on the back face, reading upward
            translate([cx, D + 0.01, body_h / 2])
                rotate([90, 0, 0]) linear_extrude(text_depth + 0.01)
                    mirror([1, 0]) rotate(90)
                        text(str(nums[i]), size = text_size, font = "Liberation Sans:style=Bold",
                             halign = "center", valign = "center");
        }
        // plug letter on the end face at the first pin
        translate([-0.01, D / 2, body_h / 2])
            rotate([90, 0, 90]) linear_extrude(text_depth + 0.01)
                mirror([1, 0])
                    text(letter, size = min(letter_size, D - 1), font = "Liberation Sans:style=Bold",
                         halign = "center", valign = "center");
    }
}

// three 2-slot combs at fit - 0.1, fit, fit + 0.1; the notches on the end count 1, 2, 3
module fit_comb() {
    for (k = [0 : 2]) translate([k * (length(2) + 3), 0, 0]) difference() {
        comb("", [1, 2], fit + (k - 1) * 0.1);
        for (j = [0 : k]) translate([length(2) - 0.6, 0.6 + j * 1.2, -1]) cube([1, 0.6, body_h + lip + 2]);
    }
}

module all_combs() {
    for (k = [0 : len(COMBS) - 1]) translate([0, k * (depth(fit) + 4), 0]) comb(COMBS[k][0], COMBS[k][1]);
}

if (part == "fit_comb") fit_comb();
else if (part == "all") all_combs();
else for (c = COMBS) if (part == str("comb_", c[0])) comb(c[0], c[1]);
