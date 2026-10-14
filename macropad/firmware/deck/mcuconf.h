// Copyright 2026 unb
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include_next <mcuconf.h>

#undef STM32_I2C_USE_I2C1
#define STM32_I2C_USE_I2C1 TRUE

#undef STM32_ADC_USE_ADC1
#define STM32_ADC_USE_ADC1 TRUE
