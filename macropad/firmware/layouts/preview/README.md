# Layout preview (backup, 2026-10-09)

deckd drew the screens itself and sent whole frames (firmware protocol 7: 0x06 frame chunk,
0x07 show; 2 s timeout back to the pad's drawing), so layouts could be tried without flashing.
E1 stepped through the layouts. Removed once wedge / scope / flask / sprout went into the
firmware as themes.

Here: `preview.py` (the layouts in Python, incl. all the rejected ones) and `deckd.py` with its
hooks, plus the firmware of that day (`screens.c/h`, default `keymap.c`, built `.uf2`). To bring
it back, put those files back in place (`host/`, `deck/`, `deck/keymaps/default/`) and flash.
