// Copyright 2026 unb
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

// I2C1 on B6 (SCL) / B7 (SDA): the TCA9548A, with the five screens behind it
#define I2C_DRIVER I2CD1
#define I2C1_SCL_PIN B6
#define I2C1_SDA_PIN B7
#define I2C1_CLOCK_SPEED 400000
#define I2C1_DUTY_CYCLE FAST_DUTY_CYCLE_2
// two drawing surfaces (screens.c)
#define SURFACE_NUM_DEVICES 2


// slider wipers (pin 2)
#define SLIDER_PINS { A1, A2, A3 }

// One detent = a full quadrature cycle (4 edges). 2 looked right while the encoders were polled,
// because screen flushes made the poll miss edges; with interrupt reads it gave 2 steps a click.
#define ENCODER_RESOLUTION 4
// both knobs counted the wrong way round as wired (A/B swapped relative to QMK's idea of clockwise)
#define ENCODER_DIRECTION_FLIP
