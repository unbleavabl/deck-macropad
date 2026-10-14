// Exploded view of the deck, for the assembly diagram (case/diagram.py).
// Not a print. `only` renders a single part so the diagram script can find
// where it lands in the picture.

use <deck.scad>
use <parts.scad>
include <common.scad>

only = "all";    // "all" or one part name below

// values the view needs (use<> shares modules and functions, not variables)
tilt = 30;
deck_n = [0, -sin(tilt), cos(tilt)]; // out of the deck's face

module show(name, c) {
    if (only == "all" || only == name) color(c) children();
}

show("deck_lid", "SlateGray") translate([0, 0, -45]) deck_lid();
show("deck_frame", "SteelBlue") deck_frame();
show("deck_plate", "LightSteelBlue") translate(deck_n * 40) deck_plate();
show("deck_dock", "CadetBlue") translate([0, 0, 0] + [0, cos(70), sin(70)] * 40) deck_dock();
show("knob", "Orange") for (i = [0, 1]) on_face() translate([enc_a(), enc_b(i), 85]) knob();
show("fader_cap", "Tomato") for (i = [0 : 2]) on_face() translate([slider_a(i), slider_b(), 85]) rotate(90) fader_cap();
