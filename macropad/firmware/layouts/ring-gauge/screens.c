// Copyright 2026 unb
// SPDX-License-Identifier: GPL-2.0-or-later
#include <math.h>
#include <string.h>
#include "quantum.h"
#include "i2c_master.h"
#include "qp.h"
#include "qp_surface.h"
#include "screens.h"
// built by fonts/make_fonts.py
#include "fonts/font_small.qff.h"
#include "fonts/font_mid.qff.h"
#include "fonts/font_big.qff.h"

#define MUX_ADDR (0x70 << 1)
#define SCREEN_ADDR 0x3C
#define I2C_WAIT 10

// One painter device for all five: they share an address and the mux picks which one listens.
// It only does init and power. Frames are drawn into `frame` (text through the `canvas` surface,
// shapes straight into the bits) and sent by present(), which keeps a copy of what each panel
// shows and sends only the columns that changed in each 8-row page: an animated icon costs
// ~1 ms of I2C instead of the ~23 ms of a whole frame. (Painter devices per screen would do the
// same, but QMK's SH1106_NUM_I2C_DEVICES can't be raised: its header redefines it to 0.)
static painter_device_t dev;
static bool             ok[SCREEN_COUNT], full[SCREEN_COUNT];
static uint8_t          shown[SCREEN_COUNT][128 * 8]; // panel RAM: page by page, a byte a column
static painter_font_handle_t small, mid, big;
static uint8_t          frame[128 * 64 / 8];
static painter_device_t canvas;
// Titles are drawn into a wide strip first, so a scrolling one can be cut at any pixel.
#define STRIP_W 320
#define STRIP_H 16
static uint8_t          strip_buf[STRIP_W * STRIP_H / 8];
static painter_device_t strip;

// A ring gauge on the left (the bar, with the icon in its middle); right of it the title, the
// value big and a line of small text. y values are the tops of the font cells: each one puts that
// font's baseline where the layout wants it.
#define RING_X 27
#define RING_Y 32
#define RING_R 25
#define COL_X 58 // the text column, to the right edge
#define COL_W (128 - COL_X)
#define TITLE_Y 4  // baseline 15
#define BIG_Y 19   // baseline 41, digits from 22
#define MID_Y 25   // the same baseline in the smaller font, digits from 27
#define UNIT_DY -2 // unit cell top, from the value's digit top
#define SUB_Y 46   // baseline 57
#define SLIDE_MS 240    // a new icon drops into the ring
#define SCROLL_PAUSE 1500
#define SCROLL_SPEED 30 // px/s
#define SCROLL_GAP 32

typedef struct {
    char     title[SCREEN_TITLE_MAX + 1];
    uint8_t  icon;
    int16_t  bar_px, bar_target; // bar width shown / wanted; -1: no bar
    bool     scrolls;
    uint32_t title_at, icon_at;
} view_t;
static view_t views[SCREEN_COUNT];

static bool mux_select(uint8_t mask) {
    return i2c_transmit(MUX_ADDR, &mask, 1, I2C_WAIT) == I2C_STATUS_SUCCESS;
}

bool screen_ok(uint8_t i) {
    return i < SCREEN_COUNT && ok[i];
}

void screens_init(void) {
    i2c_init();
    small  = qp_load_font_mem(font_font_small);
    mid    = qp_load_font_mem(font_font_mid);
    big    = qp_load_font_mem(font_font_big);
    canvas = qp_make_mono1bpp_surface(128, 64, frame);
    strip  = qp_make_mono1bpp_surface(STRIP_W, STRIP_H, strip_buf);
    qp_init(canvas, QP_ROTATION_0);
    qp_init(strip, QP_ROTATION_0);
    dev = qp_sh1106_make_i2c_device(128, 64, SCREEN_ADDR);
    for (uint8_t i = 0; i < SCREEN_COUNT; i++) {
        // left dark: the keymap turns them on once the host has configured USB
        ok[i]               = mux_select(1 << i) && qp_init(dev, QP_ROTATION_0) && qp_power(dev, false);
        full[i]             = true; // panel RAM holds noise after power-up
        views[i].bar_px     = -1;
        views[i].bar_target = -1;
    }
    mux_select(0);
}

void screens_power(bool on) {
    for (uint8_t i = 0; i < SCREEN_COUNT; i++)
        if (ok[i]) ok[i] = mux_select(1 << i) && qp_power(dev, on);
    mux_select(0);
}

void screen_invalidate(uint8_t i) {
    if (i < SCREEN_COUNT) full[i] = true;
}

static bool send(const uint8_t *buf, uint8_t len) {
    return i2c_transmit(SCREEN_ADDR << 1, buf, len, I2C_WAIT) == I2C_STATUS_SUCCESS;
}

// Send screen i what changed between `frame` and what it shows (everything, after
// screen_invalidate). A failed transfer leaves the panel unknown, so it gets everything next time.
static bool present(uint8_t i) {
    bool sent = mux_select(1 << i);
    for (uint8_t page = 0; sent && page < 8; page++) {
        uint8_t  buf[1 + 128] = {0x40}; // data
        uint8_t *col = buf + 1, *was = shown[i] + page * 128;
        for (uint8_t x = 0; x < 128; x++)
            for (uint8_t y = 0; y < 8; y++) {
                uint16_t n = (page * 8 + y) * 128 + x;
                col[x] |= (frame[n / 8] >> (n % 8) & 1) << y;
            }
        int16_t l = 0, r = 127;
        if (!full[i]) {
            while (l < 128 && col[l] == was[l]) l++;
            if (l == 128) continue;
            while (col[r] == was[r]) r--;
        }
        uint8_t cmd[] = {0x00, 0xB0 | page, 0x00 | (l & 0x0F), 0x10 | l >> 4};
        buf[l]        = 0x40;
        sent          = send(cmd, sizeof cmd) && send(buf + l, r - l + 2);
        memcpy(was + l, col + l, r - l + 1);
    }
    mux_select(0);
    full[i] = !sent;
    return sent;
}

// ---- pixels into `frame`; icon drawing adds the icon's origin

static int16_t org_x, org_y;

static void pset(int16_t x, int16_t y, bool on) {
    if ((uint16_t)x >= 128 || (uint16_t)y >= 64) return;
    uint16_t n = y * 128 + x;
    if (on) frame[n / 8] |= 1 << (n % 8);
    else frame[n / 8] &= ~(1 << (n % 8));
}

static void box(int16_t x0, int16_t y0, int16_t x1, int16_t y1, bool on) {
    for (int16_t y = y0; y <= y1; y++)
        for (int16_t x = x0; x <= x1; x++) pset(org_x + x, org_y + y, on);
}

static void dot(int16_t x, int16_t y, bool on) {
    pset(org_x + x, org_y + y, on);
}

static void line(int16_t x0, int16_t y0, int16_t x1, int16_t y1) {
    int16_t dx = abs(x1 - x0), dy = -abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1, e = dx + dy;
    for (;;) {
        dot(x0, y0, true);
        if (x0 == x1 && y0 == y1) return;
        int16_t e2 = 2 * e;
        if (e2 >= dy) e += dy, x0 += sx;
        if (e2 <= dx) e += dx, y0 += sy;
    }
}

static void disc(int16_t cx, int16_t cy, int16_t r, bool on) {
    for (int16_t y = -r; y <= r; y++)
        for (int16_t x = -r; x <= r; x++)
            if (x * x + y * y <= r * r + r) dot(cx + x, cy + y, on);
}

static void ring(int16_t cx, int16_t cy, int16_t r) {
    for (int16_t y = -r; y <= r; y++)
        for (int16_t x = -r; x <= r; x++) {
            int16_t d = x * x + y * y;
            if (d >= r * r - r && d <= r * r + r) dot(cx + x, cy + y, true);
        }
}

// cos of k * 22.5 degrees, times 7; sin(k) = COS7[(k + 12) % 16]
static const int8_t COS7[16] = {7, 6, 5, 3, 0, -3, -5, -6, -7, -6, -5, -3, 0, 3, 5, 6};
#define SIN7(k) COS7[((k) + 12) % 16]
// v (from COS7) scaled to radius r, rounded
static int16_t at(int8_t v, int16_t r) {
    return (v * r + (v < 0 ? -3 : 3)) / 7;
}
// half widths of a radius-7 circle, by row distance from the centre
static const uint8_t ROW7[8] = {7, 7, 7, 6, 6, 5, 4, 0};

// ---- icons, 16x16, in local coordinates 0..15; t: ms since boot, value: bar 0..100

static void speaker(void) {
    box(1, 5, 3, 10, true);
    for (int16_t x = 4; x < 8; x++) box(x, 9 - x, x, x + 6, true);
}

static void icon_speaker(uint32_t t) {
    speaker();
    uint8_t p = t / 300 % 3;
    if (p >= 1) {
        dot(9, 5, true), dot(9, 10, true);
        box(10, 6, 10, 9, true);
    }
    if (p == 2) {
        dot(12, 2, true), dot(12, 13, true);
        box(13, 3, 13, 4, true), box(13, 11, 13, 12, true);
        box(14, 5, 14, 10, true);
    }
}

static void icon_mute(uint32_t t) {
    speaker();
    if (t % 1000 < 700) line(10, 5, 15, 10), line(10, 10, 15, 5);
}

static void mic(void) {
    box(6, 0, 9, 0, true), box(6, 9, 9, 9, true); // capsule
    box(5, 1, 5, 8, true), box(10, 1, 10, 8, true);
    box(3, 6, 3, 8, true), box(12, 6, 12, 8, true); // holder
    dot(4, 9, true), dot(11, 9, true);
    box(5, 10, 10, 10, true);
    box(7, 11, 8, 13, true), box(4, 14, 11, 14, true); // stand
}

static void icon_mic(uint32_t t) {
    static const uint8_t LEVEL[8] = {2, 5, 8, 4, 6, 3, 7, 1};
    mic();
    uint8_t h = LEVEL[t / 120 % 8];
    box(6, 9 - h, 9, 8, true);
}

static void icon_mic_mute(uint32_t t) {
    mic();
    if (t % 1000 < 700) {
        for (int16_t k = 0; k < 15; k++) dot(k + 1, 15 - k, false), dot(k, 14 - k, true);
    }
}

static void icon_sun(uint32_t t) {
    disc(7, 7, 3, true);
    uint8_t ph = t / 250 % 2;
    for (uint8_t k = 0; k < 8; k++) {
        uint8_t d = (2 * k + ph) % 16;
        line(7 + at(COS7[d], 5), 7 + at(SIN7(d), 5), 7 + COS7[d], 7 + SIN7(d));
    }
}

static void moon(void) {
    disc(7, 8, 7, true);
    disc(11, 5, 6, false);
}

static void icon_moon(uint32_t t) {
    moon();
    bool a = t / 500 % 2;
    dot(13, 2, true);
    if (a) dot(13, 1, true), dot(12, 2, true), dot(14, 2, true), dot(13, 3, true);
    dot(14, 11, !a);
    dot(10, 13, true);
}

static void icon_play(uint32_t t) {
    static const uint8_t H[16] = {4, 9, 14, 10, 6, 12, 15, 7, 3, 11, 8, 13, 5, 15, 9, 6};
    for (uint8_t k = 0; k < 4; k++) {
        uint8_t h = H[(t / 110 + k * 5) % 16];
        box(4 * k, 16 - h, 4 * k + 2, 15, true);
    }
}

static void icon_pause(uint32_t t) {
    box(3, 2, 6, 13, true), box(9, 2, 12, 13, true);
    if (t % 1400 >= 1000) box(4, 3, 5, 12, false), box(10, 3, 11, 12, false); // breathe out
}

static void icon_note(uint32_t t) {
    org_y += t / 350 % 2;
    disc(3, 12, 2, true), disc(11, 10, 2, true);
    box(5, 3, 5, 12, true), box(13, 1, 13, 10, true);
    line(5, 3, 13, 1), line(5, 4, 13, 2);
}

static void icon_globe(uint32_t t) {
    ring(7, 7, 7);
    box(0, 7, 14, 7, true);
    int8_t off = COS7[t / 150 % 16];
    for (int16_t y = -7; y <= 7; y++) dot(7 + off * ROW7[abs(y)] / 7, 7 + y, true);
}

static void icon_app(uint32_t t) {
    box(0, 1, 15, 3, true), box(0, 14, 15, 14, true); // frame, title bar
    box(0, 4, 0, 13, true), box(15, 4, 15, 13, true);
    dot(12, 2, false), dot(14, 2, false);
    // lines of text typing in, cursor blinking at the end
    static const uint8_t LEN[3] = {11, 8, 5};
    int16_t p = t / 90 % 40, x = 2, y = 6;
    for (uint8_t l = 0; l < 3 && p > 0; l++) {
        int16_t n = p < LEN[l] ? p : LEN[l];
        box(2, 6 + 3 * l, 1 + n, 6 + 3 * l, true);
        x = 2 + n, y = 6 + 3 * l;
        p -= n;
    }
    if (t % 600 < 300) box(x, y - 2, x, y, true);
}

static void icon_gear(uint32_t t) {
    disc(7, 7, 4, true);
    disc(7, 7, 1, false);
    uint8_t ph = t / 150 % 2;
    for (uint8_t k = 0; k < 8; k++) {
        uint8_t d = (2 * k + ph) % 16;
        disc(7 + at(COS7[d], 6), 7 + at(SIN7(d), 6), 1, true);
    }
}

static void icon_slider(uint8_t value) {
    box(0, 7, 15, 8, true);
    int16_t k = 1 + value * 13 / 100;
    box(k - 2, 2, k + 2, 13, false);
    box(k - 1, 3, k + 1, 12, true);
}

static void icon_wait(uint32_t t) {
    uint8_t head = t / 90 % 8;
    for (uint8_t k = 0; k < 8; k++) {
        int16_t x = 7 + at(COS7[2 * k], 6), y = 7 + at(SIN7(2 * k), 6);
        uint8_t d = (head - k + 8) % 8;
        if (d == 0) disc(x, y, 1, true);
        else if (d <= 2) dot(x, y, true), dot(x + 1, y, true), dot(x, y + 1, true), dot(x - 1, y, true), dot(x, y - 1, true);
        else dot(x, y, true);
    }
}

static void icon_unplug(uint32_t t) {
    static const uint8_t SHIFT[4] = {0, 1, 2, 1};
    int16_t s = SHIFT[t / 250 % 4];
    box(0, 7, 2 + s, 8, true); // cable
    box(3 + s, 4, 7 + s, 11, true);
    box(8 + s, 5, 10 + s, 5, true), box(8 + s, 10, 10 + s, 10, true);
    box(13, 3, 15, 12, true); // socket
    dot(13, 5, false), dot(13, 10, false);
    if (s == 2) dot(11, 2, true), dot(11, 13, true), dot(10, 1, true), dot(10, 14, true);
}

static bool icon_moves(uint8_t icon) {
    return icon != ICON_NONE && icon != ICON_MOON_OFF && icon != ICON_SLIDER;
}

// Each icon's shift from (8, 8) so that the box round everything it draws, over its whole
// animation, has its centre on the icon's centre pixel (to within half a pixel). Measured by
// running the icon code on the host.
static const int8_t ICON_NUDGE[ICON_COUNT][2] = {
    [ICON_MIC] = {0, 1},      [ICON_MIC_MUTE] = {1, 1}, [ICON_SUN] = {1, 1},  [ICON_MOON] = {1, 0},
    [ICON_MOON_OFF] = {1, 0}, [ICON_PLAY] = {1, 0},     [ICON_NOTE] = {1, 0}, [ICON_GLOBE] = {1, 1},
    [ICON_GEAR] = {1, 1},     [ICON_WAIT] = {1, 1},
};

static void draw_icon(uint8_t icon, uint32_t t, uint8_t value) {
    switch (icon) {
        case ICON_SPEAKER: icon_speaker(t); break;
        case ICON_MUTE: icon_mute(t); break;
        case ICON_MIC: icon_mic(t); break;
        case ICON_MIC_MUTE: icon_mic_mute(t); break;
        case ICON_SUN: icon_sun(t); break;
        case ICON_MOON: icon_moon(t); break;
        case ICON_MOON_OFF: moon(); break;
        case ICON_PLAY: icon_play(t); break;
        case ICON_PAUSE: icon_pause(t); break;
        case ICON_NOTE: icon_note(t); break;
        case ICON_GLOBE: icon_globe(t); break;
        case ICON_APP: icon_app(t); break;
        case ICON_GEAR: icon_gear(t); break;
        case ICON_SLIDER: icon_slider(value); break;
        case ICON_WAIT: icon_wait(t); break;
        case ICON_UNPLUG: icon_unplug(t); break;
    }
}

// ---- text

// Copy `s` into `buf`, dropping characters from the end until it fits in `w` px.
static const char *fit(char *buf, uint8_t size, painter_font_handle_t font, const char *s, int16_t w) {
    strncpy(buf, s, size - 1);
    buf[size - 1] = 0;
    for (uint8_t n = strlen(buf); n && qp_textwidth(font, buf) > w;) buf[--n] = 0;
    return buf;
}

// Title at (x0, y0), at most `w` px wide. Too wide: it pauses, scrolls round, pauses again.
// Returns its width on screen and whether it scrolls.
static int16_t draw_title(const char *title, int16_t x0, int16_t y0, int16_t w, uint32_t shown_ms, bool *scrolls) {
    memset(strip_buf, 0, sizeof strip_buf);
    qp_drawtext(strip, 0, 0, small, title);
    int16_t tw = qp_textwidth(small, title), off = 0, loop = tw + SCROLL_GAP;
    if (tw > STRIP_W) tw = STRIP_W;
    *scrolls = tw > w;
    if (*scrolls) {
        uint32_t e = shown_ms % (SCROLL_PAUSE + (uint32_t)loop * 1000 / SCROLL_SPEED);
        off        = e < SCROLL_PAUSE ? 0 : (e - SCROLL_PAUSE) * SCROLL_SPEED / 1000;
    }
    for (int16_t x = 0; x < w; x++) {
        int16_t sx = *scrolls ? (off + x) % loop : x;
        if (sx >= tw) continue;
        for (int16_t y = 0; y < STRIP_H; y++) {
            uint16_t n = y * STRIP_W + sx;
            if (strip_buf[n / 8] & (1 << (n % 8))) pset(x0 + x, y0 + y, true);
        }
    }
    return *scrolls ? w : tw;
}

// ---- screens

// seven-segment digit, segments a..g in bits 0..6
static const uint8_t SEGS[10] = {0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F};
#define MINUS 0x40

static void fill(int x0, int y0, int x1, int y1) {
    box(x0, y0, x1, y1, true);
}

static void seg_digit(int x, int y, int w, int h, int t, uint8_t s) {
    int m = y + h / 2;
    if (s & 0x01) fill(x, y, x + w - 1, y + t - 1);
    if (s & 0x02) fill(x + w - t, y, x + w - 1, m);
    if (s & 0x04) fill(x + w - t, m, x + w - 1, y + h - 1);
    if (s & 0x08) fill(x, y + h - t, x + w - 1, y + h - 1);
    if (s & 0x10) fill(x, m, x + t - 1, y + h - 1);
    if (s & 0x20) fill(x, y, x + t - 1, m);
    if (s & 0x40) fill(x, m - t / 2, x + w - 1, m - t / 2 + t - 1);
}

void screen_draw(uint8_t i, int16_t value, uint8_t bar) {
    if (!screen_ok(i)) return;
    memset(frame, 0, sizeof frame);
    org_x = org_y = 0;

    // screen number, small, in a box
    box(0, 0, 19, 0, true), box(0, 25, 19, 25, true), box(0, 0, 0, 25, true), box(19, 0, 19, 25, true);
    seg_digit(4, 4, 12, 18, 2, SEGS[(i + 1) % 10]);

    // value, big, right-aligned
    bool neg = value < 0;
    int  v   = neg ? -value : value, x = 127 - 22;
    do {
        seg_digit(x, 2, 22, 38, 4, SEGS[v % 10]);
        v /= 10;
        x -= 28;
    } while (v);
    if (neg) seg_digit(x, 2, 22, 38, 4, MINUS);

    // bar
    box(0, 48, 127, 48, true), box(0, 63, 127, 63, true), box(0, 48, 0, 63, true), box(127, 48, 127, 63, true);
    if (bar > 4) fill(2, 50, bar > 125 ? 125 : bar - 1, 61);

    present(i);
}

bool screen_draw_text(uint8_t i, const char *title, const char *text, int8_t bar, uint8_t icon, const char *info, const char *tag) {
    if (!screen_ok(i)) return false;
    view_t  *v   = &views[i];
    uint32_t now = timer_read32();
    if (!title) title = "";
    if (info && *info && tag && *tag) title = tag; // idle: the tag names what the value is
    if (icon >= ICON_COUNT) icon = ICON_NONE;
    if (strncmp(v->title, title, SCREEN_TITLE_MAX)) {
        strncpy(v->title, title, SCREEN_TITLE_MAX);
        v->title_at = now;
    }
    if (icon != v->icon) {
        v->icon    = icon;
        v->icon_at = now;
    }
    // the bar eases halfway to its value each frame (and grows in from 0 when it appears)
    if (bar < 0) {
        v->bar_px = v->bar_target = -1;
    } else {
        v->bar_target = (int16_t)(bar > 100 ? 100 : bar) * 124 / 100;
        if (v->bar_px < 0) v->bar_px = 0;
        int16_t d = v->bar_target - v->bar_px;
        v->bar_px += d > 0 ? (d + 1) / 2 : -((1 - d) / 2);
    }

    memset(frame, 0, sizeof frame);
    org_x = org_y = 0;

    // ring: a dotted track through 270 degrees from bottom left, clockwise, and the bar over it
    // as a 4 px arc. Angles are screen degrees (y down), 0 = right.
    for (int16_t a = 135; a <= 405; a += 9) {
        float r = (a % 360) * (float)M_PI / 180;
        dot(RING_X + lroundf((RING_R - 2) * cosf(r)), RING_Y + lroundf((RING_R - 2) * sinf(r)), true);
    }
    if (v->bar_px > 0) {
        float end = 270.0f * v->bar_px / 124;
        for (int16_t y = -RING_R; y <= RING_R; y++)
            for (int16_t x = -RING_R; x <= RING_R; x++) {
                int16_t d = x * x + y * y;
                if (d < (RING_R - 4) * (RING_R - 4) || d > RING_R * RING_R + RING_R) continue;
                float a = atan2f(y, x) * 180 / (float)M_PI - 135;
                if (a < 0) a += 360;
                if (a <= end) dot(RING_X + x, RING_Y + y, true);
            }
    }
    if (icon) {
        uint32_t since = timer_elapsed32(v->icon_at);
        org_x          = RING_X - 8 + ICON_NUDGE[icon][0];
        org_y          = RING_Y - 8 + ICON_NUDGE[icon][1] - (since < SLIDE_MS ? 6 - (int16_t)(since * 6 / SLIDE_MS) : 0);
        draw_icon(icon, now, v->bar_px < 0 ? 0 : v->bar_px * 100 / 124);
        org_x = org_y = 0;
    }

    // title (idle: the tag)
    bool scrolls = false;
    if (*v->title) draw_title(v->title, COL_X, TITLE_Y, COL_W, timer_elapsed32(v->title_at), &scrolls);
    v->scrolls = scrolls;

    // value: a number keeps what follows it ("%", "PM", "`C") as a small unit at its top right.
    // Too wide big, it goes mid; still too wide, it's cut.
    char val[16], unit[16] = "";
    strncpy(val, info && *info ? info : text ? text : "", sizeof val - 1);
    val[sizeof val - 1] = 0;
    if ((*val >= '0' && *val <= '9') || (*val == '-' && val[1] >= '0' && val[1] <= '9')) {
        char *u = val + 1;
        while ((*u >= '0' && *u <= '9') || *u == ':' || *u == '.') u++;
        char *t = u, *o = unit;
        while (*t == ' ') t++;
        for (; *t && o < unit + sizeof unit - 3; t++) // ` is the degree sign
            if (*t == '`') *o++ = 0xC2, *o++ = 0xB0;
            else *o++ = *t;
        *o = 0, *u = 0;
    }
    int16_t                uw = *unit ? qp_textwidth(small, unit) + 2 : 0;
    painter_font_handle_t  f  = qp_textwidth(big, val) + uw <= COL_W ? big : mid;
    int16_t                y  = f == big ? BIG_Y : MID_Y;
    char                   buf[32];
    fit(buf, sizeof buf, f, val, COL_W - uw);
    qp_drawtext(canvas, COL_X, y, f, buf);
    if (*unit) qp_drawtext(canvas, COL_X + qp_textwidth(f, buf) + 2, y + (f == big ? 3 : 2) + UNIT_DY, small, unit);

    // idle: the text small under the value
    if (info && *info && text && *text) {
        fit(buf, sizeof buf, small, text, COL_W);
        qp_drawtext(canvas, COL_X, SUB_Y, small, buf);
    }
    return present(i);
}

bool screen_animating(uint8_t i) {
    if (!screen_ok(i)) return false;
    view_t *v = &views[i];
    return icon_moves(v->icon) || v->scrolls || v->bar_px != v->bar_target || (v->icon && timer_elapsed32(v->icon_at) < SLIDE_MS + 100);
}

// Send screen i its init sequence again (after a failed flush; also revives one that was missing
// at boot). Its content has to be drawn again afterwards.
bool screen_reinit(uint8_t i) {
    if (i >= SCREEN_COUNT) return false;
    ok[i]   = mux_select(1 << i) && qp_init(dev, QP_ROTATION_0) && qp_power(dev, true);
    full[i] = true;
    mux_select(0);
    return ok[i];
}

void screens_scan(void) {
    uint8_t zero = 0;
    if (!mux_select(0)) {
        uprintf("mux 0x70: no answer (check B6/B7, 3V3, GND on the mux)\n");
        return;
    }
    uprintf("mux 0x70: ok. Screens are wanted at 0x3C on channels 0-4 (S1-S5).\n");
    for (uint8_t ch = 0; ch < 8; ch++) {
        mux_select(1 << ch);
        for (uint8_t addr = 0x3C; addr <= 0x3D; addr++) {
            if (i2c_transmit(addr << 1, &zero, 1, I2C_WAIT) == I2C_STATUS_SUCCESS)
                uprintf("  channel %u: device at 0x%02X%s\n", ch, addr, ch < SCREEN_COUNT && addr == SCREEN_ADDR ? (ok[ch] ? " (S ok)" : " (was missing at boot: replug USB)") : "  <- unexpected");
        }
    }
    mux_select(0);
    // anything answering with no channel selected sits on the BlackPill side of the mux
    for (uint8_t addr = 0x3C; addr <= 0x3D; addr++)
        if (i2c_transmit(addr << 1, &zero, 1, I2C_WAIT) == I2C_STATUS_SUCCESS) uprintf("  no channel: device at 0x%02X <- on the main bus\n", addr);
    uprintf("scan done\n");
}
