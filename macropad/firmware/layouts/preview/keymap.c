// Copyright 2026 unb
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Default keymap: the pad only reports. Every key, knob push and knob click goes to the host
// daemon (macropad/host/deckd.py), which runs whatever its config.toml says, so keys change
// without reflashing. The daemon also sets volumes and brightness from the sliders and
// draws all five screens. Without the daemon the keys do nothing and S1-S3 show the sliders.
//
//   K1  K2  K3   E2
//   K4  K5  K6
//   K7  K8  K9   E1
//   K10 K11 K12
//
// Hold both knob pushes for a second to flash (deck.c), or run `deckd.py boot`.
#include QMK_KEYBOARD_H
#include <stdio.h>
#include <string.h>
#include "analog.h"
#include "raw_hid.h"
#include "screens.h"
#include "usb_device_state.h"

// clang-format off
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT(
        KC_NO, KC_NO, KC_NO,     KC_NO,
        KC_NO, KC_NO, KC_NO,
        KC_NO, KC_NO, KC_NO,     KC_NO,
        KC_NO, KC_NO, KC_NO
    )
};
// clang-format on

// ---------------------------------------------------------------------------------------------
// Host link (raw HID, 32-byte reports). Protocol, shared with macropad/host/deckd.py:
//   host -> pad  0x01 screen: [1, screen 0-4, bar (int8, -1 = none), title[12], text[12], icon]
//                     icon: ICON_* from screens.h, 0 = none
//                0x02 long title, sent just before its 0x01: [2, screen, title chars 12..39 [28]]
//                0x04 idle info, sent just before its 0x01: [4, screen, info[12], tag[16]]
//                     (the screen then shows info big, its text small; no 0x04: text big)
//                0x03 ping, once a second: [3]   pad answers [0x83, 7 (protocol version)]
//                0x06 frame chunk: [6, screen, chunk 0-36, 28 bytes] (layout preview, see screens.h)
//                0x07 show frame:  [7, screen]: the screen shows the host's frame instead of its
//                     own drawing; with no 0x07 for FRAME_TIMEOUT it goes back to its own
//                0x05 jump to the bootloader
//   pad -> host  0x81 slider: [0x81, slider 0-2, permille low, permille high] (0..1000)
//                0x82 key:    [0x82, row, col, pressed]
//                0x84 knob:   [0x84, knob (0 = E1, 1 = E2), clockwise]
// No ping for 3 s: the host is gone; the screens fall back to local.

#define HOST_TIMEOUT 3000
#define FRAME_TIMEOUT 2000
// Sliders: read every 5 ms, 16 ADC reads averaged, smoothed while resting; the ends (SLIDER_LO / SLIDER_HI of 1023) count
// as 0 / 1000 so a slider pushed all the way gets there. Position is in permille; a new value is
// sent once it is SLIDER_DEADBAND permille away from the last one sent, so noise can't make the
// value flicker, while a real move of 0.3 % already counts.
#define SLIDER_LO 20
#define SLIDER_HI 1003
#define SLIDER_DEADBAND 3
#define SLIDER_JUMP 12 // ADC counts: a change bigger than this is a real move, skip smoothing

#define ANIM_MS 100 // animated screens get a new frame this often

typedef struct {
    char    title[SCREEN_TITLE_MAX + 1];
    char    text[13];
    int8_t  bar;
    uint8_t icon;
    char    info[13];
    char    tag[17];
} screen_t;

static const pin_t SLIDER[] = SLIDER_PINS;
static int32_t     slider_f[3] = {-1, -1, -1}; // smoothed reading, x16
static int16_t     slider_pm[3]; // permille last taken
static screen_t    host_screen[SCREEN_COUNT];
static uint32_t    host_seen;
static bool        host_alive;
static uint8_t     host_got; // one bit per screen the host has sent since it came up
static char        host_tail[SCREEN_COUNT][SCREEN_TITLE_MAX - 12 + 1]; // from 0x02, for the next 0x01
static uint8_t     tail_got; // one bit per screen with a 0x02 waiting
static char        host_info[SCREEN_COUNT][12 + 16]; // from 0x04, for the next 0x01
static uint8_t     info_got; // one bit per screen with a 0x04 waiting
static uint8_t     dirty; // one bit per screen
static bool        screens_on;
static uint8_t     framed; // one bit per screen showing host frames
static uint32_t    framed_at[SCREEN_COUNT];

// Screens are lit only while the host has USB configured: with the PC off (or asleep) but
// still feeding 5 V they go dark instead of showing "no deckd".
static void set_screens(bool on) {
    if (on == screens_on) return;
    screens_on = on;
    screens_power(on);
    if (on) dirty = 0x1F;
}

// housekeeping doesn't run while suspended, so this is where they go off on sleep
void suspend_power_down_user(void) {
    set_screens(false);
}

static void send3(uint8_t type, uint8_t a, uint8_t b, uint8_t c) {
    uint8_t r[32] = {type, a, b, c};
    raw_hid_send(r, sizeof r);
}

static void send_slider(uint8_t i) {
    send3(0x81, i, slider_pm[i] & 0xFF, slider_pm[i] >> 8);
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (host_alive) send3(0x82, record->event.key.row, record->event.key.col, record->event.pressed);
    return false;
}

bool encoder_update_user(uint8_t index, bool clockwise) {
    if (host_alive) send3(0x84, index, clockwise, 0);
    return false;
}

void raw_hid_receive(uint8_t *data, uint8_t length) {
    host_seen = timer_read32();
    if (!host_alive) {
        host_alive = true;
        for (uint8_t i = 0; i < 3; i++) send_slider(i);
    }
    switch (data[0]) {
        case 0x01:
            if (data[1] < SCREEN_COUNT) {
                screen_t *s = &host_screen[data[1]];
                s->bar      = (int8_t)data[2];
                memcpy(s->title, data + 3, 12);
                memcpy(s->text, data + 15, 12);
                s->title[12] = s->text[12] = 0;
                if (tail_got & (1 << data[1])) strcat(s->title, host_tail[data[1]]);
                tail_got &= ~(1 << data[1]);
                s->icon = data[27];
                s->info[0] = s->tag[0] = 0;
                if (info_got & (1 << data[1])) {
                    memcpy(s->info, host_info[data[1]], 12);
                    memcpy(s->tag, host_info[data[1]] + 12, 16);
                    s->info[12] = s->tag[16] = 0;
                }
                info_got &= ~(1 << data[1]);
                host_got |= 1 << data[1];
                dirty |= 1 << data[1];
            }
            break;
        case 0x02:
            if (data[1] < SCREEN_COUNT) {
                memcpy(host_tail[data[1]], data + 2, SCREEN_TITLE_MAX - 12);
                host_tail[data[1]][SCREEN_TITLE_MAX - 12] = 0;
                tail_got |= 1 << data[1];
            }
            break;
        case 0x04:
            if (data[1] < SCREEN_COUNT) {
                memcpy(host_info[data[1]], data + 2, 12 + 16);
                info_got |= 1 << data[1];
            }
            break;
        case 0x06:
            if (data[1] < SCREEN_COUNT) screen_frame_chunk(data[1], data[2], data + 3);
            break;
        case 0x07:
            if (data[1] < SCREEN_COUNT) {
                framed |= 1 << data[1];
                framed_at[data[1]] = timer_read32();
                dirty |= 1 << data[1];
            }
            break;
        case 0x03:
            send3(0x83, 7, 0, 0);
            break;
        case 0x05:
            reset_keyboard();
            break;
    }
}

static bool draw(uint8_t i) {
    if (framed & (1 << i)) return screen_draw_frame(i);
    // each screen keeps its local view until the host has sent it something
    if (host_alive && host_got & (1 << i)) {
        return screen_draw_text(i, host_screen[i].title, host_screen[i].text, host_screen[i].bar, host_screen[i].icon, host_screen[i].info, host_screen[i].tag);
    } else if (i < 3) {
        uint8_t pct = (slider_pm[i] + 5) / 10;
        char    title[10], text[6];
        snprintf(title, sizeof title, "SLIDER %u", i + 1);
        snprintf(text, sizeof text, "%u%%", pct);
        return screen_draw_text(i, title, text, pct, ICON_SLIDER, NULL, NULL);
    } else {
        // the daemon takes a few seconds to find a freshly plugged pad
        bool waiting = timer_read32() < 8000;
        return screen_draw_text(i, i == 3 ? "E1" : "E2", waiting ? "..." : "no deckd", -1, waiting ? ICON_WAIT : ICON_UNPLUG, NULL, NULL);
    }
}

void keyboard_post_init_user(void) {
    screens_init();
    dirty = 0x1F;
}

void housekeeping_task_user(void) {
    static uint32_t read_at, draw_at, refresh_at, anim_at;
    static uint8_t  refresh_next;
    uint32_t        now = timer_read32();

    set_screens(usb_device_state_get_configure_state() == USB_DEVICE_STATE_CONFIGURED);
    if (host_alive && timer_elapsed32(host_seen) > HOST_TIMEOUT) {
        host_alive = false;
        host_got   = 0;
        dirty      = 0x1F;
    }
    for (uint8_t i = 0; i < SCREEN_COUNT; i++)
        if (framed & (1 << i) && timer_elapsed32(framed_at[i]) > FRAME_TIMEOUT) {
            framed &= ~(1 << i);
            dirty |= 1 << i;
        }
    if (timer_expired32(now, read_at)) {
        read_at = now + 5;
        for (uint8_t i = 0; i < 3; i++) {
            int32_t sum = 0;
            for (uint8_t n = 0; n < 16; n++) sum += analogReadPin(SLIDER[i]);
            // x16 fixed point (sum of 16 reads). Moving: follow at once. Resting: 1/16 of the way
            // per 5 ms, which irons out the few counts of noise the wipers pick up.
            int32_t d = sum - slider_f[i];
            slider_f[i] = slider_f[i] < 0 || abs(d) > SLIDER_JUMP * 16 ? sum : slider_f[i] + d / 16;
            int32_t pm = (slider_f[i] - SLIDER_LO * 16) * 1000 / ((SLIDER_HI - SLIDER_LO) * 16);
            if (pm < 0) pm = 0;
            if (pm > 1000) pm = 1000;
            if (abs(pm - slider_pm[i]) >= SLIDER_DEADBAND || ((pm == 0 || pm == 1000) && pm != slider_pm[i])) {
                slider_pm[i] = pm;
                if (host_alive) send_slider(i);
                else dirty |= 1 << i;
            }
        }
    }
    // redraw at most one screen per 20 ms, so the matrix keeps scanning
    if (screens_on && dirty && timer_expired32(now, draw_at)) {
        draw_at   = now + 20;
        uint8_t i = 0;
        while (!(dirty & (1 << i))) i++;
        dirty &= ~(1 << i);
        // a failed transfer can leave a screen garbled: re-init it and draw again next time
        if (!draw(i) && screen_reinit(i)) dirty |= 1 << i;
    }
    // animation frames: these only send the pixels that moved, a few hundred bytes at most
    if (screens_on && timer_expired32(now, anim_at)) {
        anim_at = now + ANIM_MS;
        for (uint8_t i = 0; i < SCREEN_COUNT; i++)
            if (!(framed & (1 << i)) && screen_animating(i)) dirty |= 1 << i;
    }
    // and send one whole screen a second anyway, so a screen whose content stopped changing can't
    // keep a corrupted frame (every flush re-sends the page addresses too)
    if (timer_expired32(now, refresh_at)) {
        refresh_at = now + 1000;
        screen_invalidate(refresh_next);
        dirty |= 1 << refresh_next;
        refresh_next = (refresh_next + 1) % SCREEN_COUNT;
    }
}
