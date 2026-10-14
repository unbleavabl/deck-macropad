# TinyUF2 bootloader

Installed on the pad (since 2026-10-13): `tinyuf2-porfix.*`, TinyUF2 0.35.0 for
stm32f411ce_blackpill with `porfix.patch` applied.

The patch: stock TinyUF2 writes a double-tap magic to the end of RAM at power-up and waits
500 ms. Plugging in USB can bounce the supply and reset the chip inside that window; RAM keeps
the magic, so the pad stayed in the bootloader (STMF411BOOT drive) instead of starting QMK.
Patched `board_init` clears the magic after a power-on or brown-out reset (RCC->CSR
PORRSTF/BORRSTF). Reset-pin double tap and QMK's jump to the bootloader still work.

Install / reinstall: put the pad in the bootloader, copy `update-tinyuf2-porfix.uf2` to the
drive (it erases the QMK app), then `firmware/flash.sh`. Back to stock: same with
`update-tinyuf2.uf2`. Rescue: ST-Link, `st-flash --freq=1M write tinyuf2-porfix.bin 0x08000000`.

Rebuild: clone adafruit/tinyuf2 at tag 0.35.0, `git apply porfix.patch`,
`git submodule update --init --depth 1 lib/tinyusb lib/uf2`,
`python3 tools/get_deps.py --board stm32f411ce_blackpill`, then in `ports/stm32f4`:
`CFLAGS=-Wno-unterminated-string-initialization make BOARD=stm32f411ce_blackpill all self-update`
(GCC 16 trips over a string in ghostfat.c otherwise).
