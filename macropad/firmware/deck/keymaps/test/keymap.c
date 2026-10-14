// Copyright 2026 unb
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Wiring test: every key types its own name, the knobs type "e1>" / "e1<" per click,
// each screen shows its number and its slider (S1-S3) or knob count (S4 = E1, S5 = E2),
// and `qmk console` prints which screens answer, the raw slider values and a pull-up/down
// probe of the slider pins every 5 s.
#include QMK_KEYBOARD_H
#include <stdlib.h>
#include "analog.h"
#include "screens.h"

enum { T_K1 = SAFE_RANGE, T_K2, T_K3, T_K4, T_K5, T_K6, T_K7, T_K8, T_K9, T_K10, T_K11, T_K12, T_E1, T_E2 };

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT(
        T_K1,  T_K2,  T_K3,         T_E2,
        T_K4,  T_K5,  T_K6,
        T_K7,  T_K8,  T_K9,         T_E1,
        T_K10, T_K11, T_K12
    )
};

static const pin_t SLIDER[] = SLIDER_PINS;
static int16_t     slider_raw[3] = {-100, -100, -100};
static int16_t     knob[2];
static bool        pushed[2];
static uint8_t     dirty; // one bit per screen

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    if (keycode < T_K1 || keycode > T_E2) return true;
    uprintf("row %u col %u %s\n", record->event.key.row, record->event.key.col, record->event.pressed ? "down" : "up");
    if (keycode >= T_E1) {
        uint8_t e = keycode - T_E1;
        pushed[e] = record->event.pressed;
        dirty |= 1 << (3 + e);
        if (record->event.pressed) send_string(e ? "e2push " : "e1push ");
        return false;
    }
    if (record->event.pressed) {
        char name[6] = "k";
        uint8_t n = keycode - T_K1 + 1;
        if (n >= 10) { name[1] = '1'; name[2] = '0' + n - 10; name[3] = ' '; }
        else { name[1] = '0' + n; name[2] = ' '; }
        send_string(name);
    }
    return false;
}

bool encoder_update_user(uint8_t index, bool clockwise) {
    knob[index] += clockwise ? 1 : -1;
    if (knob[index] > 99 || knob[index] < -99) knob[index] = 0;
    dirty |= 1 << (3 + index);
    send_string(index ? (clockwise ? "e2> " : "e2< ") : (clockwise ? "e1> " : "e1< "));
    return false;
}

void keyboard_post_init_user(void) {
    screens_init();
    screens_power(true);
    dirty = 0x1F;
}

void housekeeping_task_user(void) {
    static uint32_t read_at, draw_at, scan_at = 3000;
    uint32_t now = timer_read32();

    if (timer_expired32(now, read_at)) {
        read_at = now + 30;
        for (uint8_t i = 0; i < 3; i++) {
            int16_t raw = analogReadPin(SLIDER[i]);
            if (abs(raw - slider_raw[i]) > 6) { slider_raw[i] = raw; dirty |= 1 << i; }
        }
    }
    // redraw at most one screen per 20 ms, so the matrix keeps scanning
    if (dirty && timer_expired32(now, draw_at)) {
        draw_at = now + 20;
        uint8_t i = 0;
        while (!(dirty & (1 << i))) i++;
        dirty &= ~(1 << i);
        if (i < 3) screen_draw(i, (int32_t)slider_raw[i] * 100 / 1023, (uint32_t)slider_raw[i] * 128 / 1023);
        else screen_draw(i, knob[i - 3], pushed[i - 3] ? 128 : 0);
    }
    // knob pins: print A/B levels of E1 (B1, B8) and E2 (B9, A0) whenever one changes; 1 = open, 0 = touching C
    static uint8_t last_pins = 0xFF;
    uint8_t        pins      = gpio_read_pin(B1) | gpio_read_pin(B8) << 1 | gpio_read_pin(B9) << 2 | gpio_read_pin(A0) << 3;
    if (pins != last_pins) {
        last_pins = pins;
        uprintf("knob pins  E1 A=%u B=%u   E2 A=%u B=%u\n", pins & 1, pins >> 1 & 1, pins >> 2 & 1, pins >> 3 & 1);
    }
    if (timer_expired32(now, scan_at)) {
        scan_at = now + 5000;
        screens_scan();
        uprintf("sliders raw: %d %d %d\n", slider_raw[0], slider_raw[1], slider_raw[2]);
        // wiper probe: read each slider pin as a digital input with the weak pull-down,
        // then the pull-up. Driven pin: both the same. Open pin: down 0, up 1.
        uint8_t down = 0, up = 0;
        for (uint8_t i = 0; i < 3; i++) {
            gpio_set_pin_input_low(SLIDER[i]);
            wait_ms(20);
            down |= gpio_read_pin(SLIDER[i]) << i;
            gpio_set_pin_input_high(SLIDER[i]);
            wait_ms(20);
            up |= gpio_read_pin(SLIDER[i]) << i;
        }
        uprintf("slider pins pull-down: %u %u %u   pull-up: %u %u %u\n", down & 1, down >> 1 & 1, down >> 2 & 1, up & 1, up >> 1 & 1, up >> 2 & 1);
    }
}
