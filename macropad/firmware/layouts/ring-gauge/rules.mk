QUANTUM_PAINTER_ENABLE = yes
QUANTUM_PAINTER_DRIVERS += sh1106_i2c
ANALOG_DRIVER_REQUIRED = yes
SRC += screens.c fonts/font_small.qff.c fonts/font_mid.qff.c fonts/font_big.qff.c

# TinyUF2 sits in the first 64k; the firmware starts after it
MCU_LDSCRIPT = STM32F411xE_tinyuf2
