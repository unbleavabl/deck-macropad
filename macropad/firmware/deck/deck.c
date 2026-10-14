// Copyright 2026 unb
// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"

// Hold both knob pushes (E2 = row 0, E1 = row 2, column 3) for three seconds to jump to the
// TinyUF2 bootloader.
#define BOOT_HOLD_MS 3000

void housekeeping_task_kb(void) {
    static uint16_t held_since;
    static bool     held;
    bool            all = matrix_is_on(0, 3) && matrix_is_on(2, 3)
                   && !matrix_is_on(1, 3) && !matrix_is_on(3, 3); // not column 3 glitching (keymap.c)
    if (!all) {
        held = false;
    } else if (!held) {
        held       = true;
        held_since = timer_read();
    } else if (timer_elapsed(held_since) > BOOT_HOLD_MS) {
        reset_keyboard();
    }
    housekeeping_task_user();
}

// Encoders are read from pin-change interrupts, not the main loop: a screen flush blocks the
// loop for ~23 ms (1 KB over 400 kHz I2C), long enough to miss quadrature steps, which showed
// up as dropped and doubled clicks.
extern void encoder_quadrature_handle_read(uint8_t index, uint8_t pin_a_state, uint8_t pin_b_state);

static const pin_t ENC_A[] = {B1, B9};
static const pin_t ENC_B[] = {B8, A0};

static void encoder_isr(void *arg) {
    uint8_t i = (uint32_t)arg;
    encoder_quadrature_handle_read(i, gpio_read_pin(ENC_A[i]), gpio_read_pin(ENC_B[i]));
}

void encoder_quadrature_post_init_kb(void) {
    for (uint32_t i = 0; i < 2; i++) {
        palEnableLineEvent(ENC_A[i], PAL_EVENT_MODE_BOTH_EDGES);
        palSetLineCallback(ENC_A[i], encoder_isr, (void *)i);
        palEnableLineEvent(ENC_B[i], PAL_EVENT_MODE_BOTH_EDGES);
        palSetLineCallback(ENC_B[i], encoder_isr, (void *)i);
    }
}

// the interrupts do the reading; polling as well would race them
void encoder_driver_task(void) {}
