#!/usr/bin/env bash
# Render every printable STL and the preview images from scad/.
#
#   stl/fit-tests/   print these first: plate fit, screen fit, knob and slider-cap fit
#   stl/deck/        the 30 degree deck with sliders and phone holder
#   stl/knobs-caps/  encoder knobs, encoder spacers, slider caps
#   3mf/             Bambu Studio projects (P1S): keycaps, labels, keycap fit tests
#   stl/keycaps/     flat keycaps and their pressed-in labels (label_body black + label_legend white, one object, one colour swap)
set -euo pipefail
cd "$(dirname "$0")"

stl() {  # stl <scad> <part> <out>
    echo "== $3"
    mkdir -p "$(dirname "stl/$3")"
    openscad -q -D "part=\"$2\"" -o "stl/$3" "scad/$1"
}

stl parts.scad fit_switch_encoder fit-tests/fit_switch_encoder.stl
stl parts.scad fit_screen         fit-tests/fit_screen.stl
stl parts.scad fit_knob_caps      fit-tests/fit_knob_caps.stl
stl parts.scad fit_knob           fit-tests/fit_knob.stl
stl deck.scad  fit_bp_cradle      fit-tests/fit_bp_cradle.stl
stl keycaps.scad fit_keycap_caps   fit-tests/fit_keycap_caps.stl
stl keycaps.scad fit_keycap_labels fit-tests/fit_keycap_labels.stl
stl keycaps.scad fit_keycap_legend fit-tests/fit_keycap_legend.stl

stl deck.scad deck_plate deck/deck_plate.stl
stl deck.scad deck_dock  deck/deck_dock.stl
stl deck.scad deck_frame deck/deck_frame.stl
stl deck.scad deck_lid   deck/deck_lid.stl

stl parts.scad knob      knobs-caps/knob.stl
stl parts.scad enc_spacer knobs-caps/enc_spacer.stl
stl parts.scad fader_cap knobs-caps/fader_cap.stl

stl keycaps.scad keycap       keycaps/keycap.stl
stl keycaps.scad label_body   keycaps/label_body.stl
stl keycaps.scad label_legend keycaps/label_legend.stl
stl keycaps.scad label_blank  keycaps/label_blank.stl
stl keycaps.scad glue_body    glue/glue_body.stl
stl keycaps.scad glue_legend  glue/glue_legend.stl
python3 make_3mf.py   # 3mf/: Bambu Studio projects for the keycaps and labels
python3 make_stickers.py   # stickers/stickers.pdf: the key icons on A4 sticker paper

echo "== previews"
mkdir -p preview
png() {  # png <scad> <part> <camera> <out>
    openscad -q -D "part=\"$2\"" --imgsize=1200,900 --colorscheme=Tomorrow --camera="$3" -o "preview/$4" "scad/$1"
}
png deck.scad deck_all 89,75,50,55,0,25,560  deck.png
png deck.scad deck_all 89,75,50,60,0,205,560 deck_back.png
png parts.scad all 60,40,5,50,0,25,250  parts.png
openscad -q --imgsize=900,1150 --colorscheme=Tomorrow --viewall --autocenter -o preview/keycaps.png scad/keycaps.scad

echo "== assembly diagram"
python3 diagram.py >/dev/null
