# Ring gauge layout (backup, 2026-10-09)

The screen layout as it was before the pill: ring gauge on the left (bar as a 270 degree arc,
icon in the middle), title / value / small text in a column on the right.

Restore: copy `screens.c`, `screens.h`, `rules.mk` into `../../deck/` and `fonts/*` into
`../../deck/fonts/` (delete fonts there that aren't in this folder), then `../../flash.sh`.
Or flash `handwired_deck_default.uf2` as it is (the default keymap of that day).
