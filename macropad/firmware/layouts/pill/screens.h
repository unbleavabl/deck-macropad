// Copyright 2026 unb
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <stdbool.h>
#include <stdint.h>

#define SCREEN_COUNT 5
// longest title kept; longer than fits, it scrolls
#define SCREEN_TITLE_MAX 40

// Icons, drawn 16x16 in the top right corner, most of them animated. The numbers are part of the
// host protocol (deckd.py ICONS lists them in this order).
enum {
    ICON_NONE,
    ICON_SPEAKER,  // waves pulse outward
    ICON_MUTE,     // speaker, blinking X
    ICON_MIC,      // level bouncing inside
    ICON_MIC_MUTE, // blinking slash
    ICON_SUN,      // rays turn
    ICON_MOON,     // stars twinkle
    ICON_MOON_OFF, // still
    ICON_PLAY,     // equalizer
    ICON_PAUSE,    // breathes
    ICON_NOTE,     // bobs
    ICON_GLOBE,    // spins
    ICON_APP,      // window, text typing in
    ICON_GEAR,     // turns
    ICON_SLIDER,   // knob follows the bar
    ICON_WAIT,     // spinner
    ICON_UNPLUG,   // plug reaching for its socket
    ICON_COUNT
};

// The five 128x64 SH1106s all sit at 0x3C, each on its own TCA9548A channel (S1..S5 = 0..4).
// Each has its own framebuffer and only pixels that changed are sent, so animation frames are
// cheap. Screens start powered off.
void screens_init(void);
// Panel power for every screen that answered; contents are kept, so redraw after turning on.
void screens_power(bool on);
bool screen_ok(uint8_t i);
// Clear screen i and draw: its number top left, `value` in big digits, and a bar `fill` of 0..128 px.
void screen_draw(uint8_t i, int16_t value, uint8_t fill);
// Draw screen i: the title along the top (scrolling if too long) with the icon at its right,
// `text` big in black on a solid white pill across the middle (a number keeps what follows it,
// "%", "PM", "`C", as a small unit at its top right; ` is a degree sign), and under it the
// 0..100 bar as a thick run along a thin line (bar < 0: none). With `info` (idle): `info` on the
// pill instead, `tag` as the title and, with no bar, `text` small at the bottom. Call again to
// animate: the frame depends on the time and on how long the content has been showing. Returns
// false if the screen is missing or the I2C transfer failed.
bool screen_draw_text(uint8_t i, const char *title, const char *text, int8_t bar, uint8_t icon, const char *info, const char *tag);
// Whether screen i's next frame would differ from the last one (icon, scrolling, bar easing).
bool screen_animating(uint8_t i);
// Send every pixel of screen i on its next draw, not only the changed ones.
void screen_invalidate(uint8_t i);
// Re-send screen i's init sequence (after a failed draw); redraw it afterwards.
bool screen_reinit(uint8_t i);
// Print to the console which screens answer behind the mux.
void screens_scan(void);
