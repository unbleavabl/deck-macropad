#!/usr/bin/env python3
"""deckd: the PC side of the macropad.

The pad's default keymap only reports: keys, knob clicks and slider moves come here, and this
daemon runs what config.toml says and draws all five screens. Change the config and restart the
service; no reflashing.

  deckd.py         run (the systemd user service does this)
  deckd.py boot    put the pad in its bootloader for flashing
  deckd.py reload-extension   reload the browser extension after editing it

Protocol: keymaps/default/keymap.c. Config: ~/.config/deckd/config.toml, else config.toml next
to this file. Needs python-hidapi, pactl, hyprctl; ddcutil for the brightness slider.
"""

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import tomllib
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import hid

VID, PID = 0xFEED, 0x4D50
USAGE_PAGE = 0xFF60  # QMK raw HID
# Screen icons, in the order of screens.h's ICON_* (the index goes to the pad); animated on the pad
ICONS = ["", "speaker", "mute", "mic", "mic-mute", "sun", "moon", "moon-off", "play", "pause", "note",
         "globe", "app", "gear", "slider", "wait", "unplug"]
TITLE_MAX = 40  # longer than fits, the pad scrolls it
IDLE_S = 3  # a screen untouched and unchanged this long shows its `info` big, its value small

HERE = Path(__file__).resolve().parent
CONFIG = Path.home() / ".config/deckd/config.toml"
THEME = Path.home() / ".local/state/deckd/theme"  # the pad's screen theme (K10 + K12 picks it there)
THEMES = ["wedge", "scope", "flask", "sprout"]  # screens.h THEME_*

# matrix position -> key name (keyboard.json)
KEY_NAMES = {(r, c): f"K{r * 3 + c + 1}" for r in range(4) for c in range(3)}
KEY_NAMES[(0, 3)] = "E2"
KEY_NAMES[(2, 3)] = "E1"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def load_config():
    path = CONFIG if CONFIG.exists() else HERE / "config.toml"
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    log(f"config: {path}")
    return cfg


def run(cmd, notify=None):
    """Start a shell command in the background, detached from the daemon. With notify (the
    headline) the command's last line of output becomes a notification once it exits; no
    output, no notification (a cancelled picker, say)."""
    log(f"run: {cmd}")
    p = subprocess.Popen(cmd, shell=True, start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE if notify else subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, text=True)
    if notify:
        def wait():
            lines = p.communicate()[0].strip().splitlines()
            if lines:
                notify_send(notify, lines[-1])
        threading.Thread(target=wait, daemon=True).start()


def notify_send(headline, text=""):
    """Omarchy's own action toast: shown even with do not disturb on."""
    subprocess.Popen(["omarchy-notification-send", "-t", "2500", headline, text],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def out(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


class Latest:
    """Runs fn(value) in its own thread with the newest value put(); older ones are dropped.
    With add=True the values are summed instead (knob clicks)."""

    def __init__(self, fn, add=False):
        self.fn, self.add = fn, add
        self.value = None
        self.cond = threading.Condition()
        threading.Thread(target=self.loop, daemon=True).start()

    def put(self, v):
        with self.cond:
            self.value = self.value + v if self.add and self.value is not None else v
            self.cond.notify()

    def loop(self):
        while True:
            with self.cond:
                while self.value is None:
                    self.cond.wait()
                v, self.value = self.value, None
            try:
                self.fn(v)
            except Exception as e:  # keep the worker alive
                log(f"worker: {e!r}")


# --------------------------------------------------------------------------- audio (pactl)


def pactl_json(*args):
    try:
        return json.loads(out("pactl", "-f", "json", *args) or "null") or []
    except json.JSONDecodeError:
        return []


def percent(entry):
    """Average channel volume of a pactl json sink/source/sink-input, in %."""
    vals = [int(c["value_percent"].rstrip("%")) for c in entry.get("volume", {}).values()]
    return round(sum(vals) / len(vals)) if vals else 0


def output_sink():
    """The sink the volume keys change: Omarchy's resolver looks through DSP sinks (EasyEffects)."""
    name = out("omarchy-audio-output-sink").strip()
    return name or out("pactl", "get-default-sink").strip()


class Audio:
    def __init__(self):
        self.sink_name = self.source_name = ""
        self.sinks, self.inputs, self.sources = [], [], []

    def refresh(self, devices_changed):
        if devices_changed or not self.sink_name:
            self.sink_name = output_sink()
            self.source_name = out("pactl", "get-default-source").strip()
        self.sinks = pactl_json("list", "sinks")
        self.inputs = pactl_json("list", "sink-inputs")
        self.sources = pactl_json("list", "sources")

    def sink(self):
        return next((s for s in self.sinks if s["name"] == self.sink_name), None)

    def source(self):
        return next((s for s in self.sources if s["name"] == self.source_name), None)

    def streams(self, slider, window):
        """Sink inputs a slider of target "apps" or "focused" controls."""
        found = []
        for s in self.inputs:
            p = s.get("properties", {})
            name = (p.get("application.name") or "").lower()
            binary = (p.get("application.process.binary") or "").lower()
            if slider["target"] == "apps":
                if any(a.lower() in name or a.lower() in binary for a in slider.get("apps", [])):
                    found.append(s)
            elif slider["target"] == "focused" and window["pid"]:
                cls = window["class"].lower()
                if str(window["pid"]) == p.get("application.process.id") or (cls and (cls in name or cls == binary)):
                    found.append(s)
        return found


# --------------------------------------------------------------------------- monitors (ddcutil)


class Brightness:
    """All DDC/CI monitors together, VCP 0x10. ddcutil takes ~0.3 s a call, so the value shown is
    the last one set (read from the first monitor once at start)."""

    def __init__(self, buses=None):
        self.buses = buses
        self.value = None
        threading.Thread(target=self.detect, daemon=True).start()

    def detect(self):
        if not self.buses:
            self.buses = [int(b) for b in re.findall(r"/dev/i2c-(\d+)", out("ddcutil", "detect", "--brief"))]
        log(f"ddc buses: {self.buses}")
        if self.buses:
            m = re.search(r"VCP 10 C (\d+) (\d+)", out("ddcutil", "--bus", str(self.buses[0]), "getvcp", "10", "--brief"))
            if m:
                self.value = round(int(m[1]) * 100 / int(m[2]))

    def set(self, pct):
        if pct == self.value:
            return
        self.value = pct
        with ThreadPoolExecutor() as ex:
            for b in self.buses or []:
                ex.submit(out, "ddcutil", "--bus", str(b), "--noverify", "setvcp", "10", str(pct))


# --------------------------------------------------------------------------- browsers


class Bridges:
    """deckd.sock: the browser extension's native host (browser/deckd_bridge.py) connects here,
    one per running browser. Chromium plays every tab through one audio stream, so for browser
    windows the "focused" slider goes to the extension, which sets the volume of the media in
    the active tab of the focused window."""

    PATH = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "deckd.sock"

    def __init__(self, on_change):
        self.on_change = on_change
        self.conns = {}  # browser ("chromium", "chrome") -> sockets, one per profile
        self.tabs = {}  # browser -> last report {site, title, volume}
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        self.PATH.unlink(missing_ok=True)
        srv = socket.socket(socket.AF_UNIX)
        srv.bind(str(self.PATH))
        srv.listen()
        while True:
            c, _ = srv.accept()
            threading.Thread(target=self.client, args=(c,), daemon=True).start()

    def client(self, c):
        name = None
        try:
            for line in c.makefile():
                m = json.loads(line)
                if m["type"] == "hello":
                    name = m["browser"]
                    self.conns.setdefault(name, []).append(c)
                    log(f"browser bridge: {name}")
                elif m["type"] == "reload-extension":  # from `deckd.py reload-extension`
                    for b in list(self.conns):
                        self.send(b, {"type": "reload"})
                elif m["type"] == "tab" and name:
                    self.tabs[name] = m
                    self.on_change()
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        if name and c in self.conns.get(name, []):
            self.conns[name].remove(c)
            if not self.conns[name]:
                del self.conns[name]
            log(f"browser bridge gone: {name}")

    def for_window(self, cls):
        """The connected browser that owns a window class, if any."""
        c = cls.lower()
        if c.startswith("google-chrome"):
            want = "chrome"
        elif c == "chromium" or c.startswith("chrome-"):  # chrome-* = Omarchy web apps (Chromium)
            want = "chromium"
        else:
            return None
        return want if self.conns.get(want) else None

    def send(self, browser, msg):
        for c in list(self.conns.get(browser, [])):
            try:
                c.sendall((json.dumps(msg) + "\n").encode())
            except OSError:
                pass


# --------------------------------------------------------------------------- knobs


MPRIS = "/org/mpris/MediaPlayer2"


def mpris_player():
    """D-Bus name of the player to seek: the one playing, else the first one."""
    names = re.findall(r"^(org\.mpris\.MediaPlayer2\.\S+)", out("busctl", "--user", "list", "--no-legend"), re.M)
    for n in names:
        if "Playing" in out("gdbus", "call", "--session", "--dest", n, "--object-path", MPRIS, "--method",
                            "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2.Player", "PlaybackStatus"):
            return n
    return names[0] if names else None


class Media:
    """Turn: seek (`seek` seconds a click; in browsers through the extension, see Bridges).
    Hold the push and turn: previous / next track.
    Push alone: play / pause (Omarchy's media service, same player as the media keys).
    The screen shows the track title and the elapsed time, or PAUSE."""

    def __init__(self, k):
        self.seek = k.get("seek", 5)
        self.bridges = None  # set by Deck

    def status(self):
        try:
            return json.loads(out("omarchy-shell", "media", "status") or "{}")
        except json.JSONDecodeError:
            return {}

    def turn(self, clicks):
        n = mpris_player()
        if not n:
            return
        if re.search(r"chromium|chrome|brave|vivaldi|edge", n):
            # Chromium accepts MPRIS Seek but YouTube ignores it. With the extension: seek inside
            # the page, wherever the tab is. Without: the player's arrow keys (5 s each), sent to
            # the window showing the track (only works while that tab is its window's active one).
            browser = "chrome" if "chrome" in n and "chromium" not in n else "chromium"
            if self.bridges and self.bridges.conns.get(browser):
                track = self.status().get("title")
                self.bridges.send(browser, {"type": "seek", "seconds": clicks * self.seek, "track": track})
                return
            window = self.browser_window()
            if window:
                for _ in range(abs(clicks)):
                    key = "Right" if clicks > 0 else "Left"
                    for state in ("down", "up"):
                        out("hyprctl", "eval", f'hl.dispatch(hl.dsp.send_key_state({{ mods = "", key = "{key}", '
                            f'state = "{state}", window = "address:{window}" }}))')
                return
        out("gdbus", "call", "--session", "--dest", n, "--object-path", MPRIS, "--method",
            "org.mpris.MediaPlayer2.Player.Seek", str(int(clicks * self.seek * 1_000_000)))

    def browser_window(self):
        """Address of the browser window whose title (its active tab) is the playing track."""
        try:
            title = json.loads(out("omarchy-shell", "media", "status") or "{}").get("title")
            clients = json.loads(out("hyprctl", "clients", "-j") or "[]")
        except json.JSONDecodeError:
            return None
        return next((c["address"] for c in clients if title and title in c["title"]), None)

    def turn_held(self, clicks):
        for _ in range(abs(clicks)):
            out("omarchy-shell", "media", "next" if clicks > 0 else "previous")

    def push(self):
        out("omarchy-shell", "media", "playPause")

    def screen(self):
        try:
            m = json.loads(out("omarchy-shell", "media", "status") or "{}")
        except json.JSONDecodeError:
            m = {}
        if not m.get("hasMedia"):
            return "MEDIA", "--", -1, "note"
        title = m.get("title") or m.get("identity") or "MEDIA"
        if not m.get("playing"):
            return title, "PAUSE", -1, "pause"
        n = mpris_player()
        pos = re.search(r"int64 (\d+)", out("gdbus", "call", "--session", "--dest", n or "", "--object-path", MPRIS, "--method",
                                            "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2.Player", "Position"))
        if not pos:
            return title, "PLAY", -1, "play"
        sec = int(pos[1]) // 1_000_000
        return title, f"{sec // 60}:{sec % 60:02d}", -1, "play"


class NightLight:
    """hyprsunset colour temperature. Turn clockwise: warmer. Push: Omarchy's on/off toggle."""

    OFF = 6500

    def __init__(self, k):
        self.step, self.min = k.get("step", 250), k.get("min", 2500)

    def get(self):
        m = re.fullmatch(r"\s*(\d+)\s*", out("hyprctl", "hyprsunset", "temperature"))
        return int(m[1]) if m else None  # None: hyprsunset not running

    def turn(self, clicks):
        t = self.get()
        if t is None:  # not running: start it; it needs a moment before it takes commands
            subprocess.Popen("uwsm-app -- hyprsunset", shell=True, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
            t = self.OFF
        t = min(max(t - clicks * self.step, self.min), self.OFF)
        for _ in range(5):  # a fresh hyprsunset overrides the first value it gets
            out("hyprctl", "hyprsunset", "temperature", str(t))
            if self.get() == t:
                break
            time.sleep(0.2)

    def push(self):
        out("omarchy-toggle-nightlight")
        t = self.get()
        notify_send("Night light", "on" if t is not None and t < 6000 else "off")

    def screen(self):
        t = self.get()
        if t is None or t >= 6000:
            return "NIGHT LIGHT", "OFF", -1, "moon-off"
        return "NIGHT LIGHT", f"{t}K", round((self.OFF - t) * 100 / (self.OFF - self.min)), "moon"


class CommandKnob:
    """Shell commands per click: cw, ccw, push."""

    def __init__(self, k):
        self.k = k

    def turn(self, clicks):
        for _ in range(abs(clicks)):
            run(self.k["cw"] if clicks > 0 else self.k["ccw"])

    def push(self):
        if "push" in self.k:
            run(self.k["push"])

    def screen(self):
        return self.k.get("label", ""), self.k.get("text", ""), -1, self.k.get("icon", "gear")


KNOB_TYPES = {"media": Media, "nightlight": NightLight, "command": CommandKnob}


class Info:
    """What a screen shows big while idle (`info` in config.toml), as (big text, small tag):
      { time = "Asia/Kolkata", tag = "INDIA" }   clock in that time zone, 12 h
      { date = true }                             day and month; the weekday as the tag
      { weather = "18.52,73.94" }                 temperature; the sky as the tag (Open-Meteo,
                                                  every 15 min; "lat,lon", or a place name)"""

    WEATHER_EVERY = 900
    # WMO weather codes, as Open-Meteo reports them
    SKY = {0: "CLEAR", 1: "MOSTLY CLEAR", 2: "PARTLY CLOUDY", 3: "OVERCAST", 45: "FOG", 48: "FOG",
           51: "LIGHT DRIZZLE", 53: "DRIZZLE", 55: "HEAVY DRIZZLE", 56: "FREEZING DRIZZLE",
           57: "FREEZING DRIZZLE", 61: "LIGHT RAIN", 63: "RAIN", 65: "HEAVY RAIN", 66: "FREEZING RAIN",
           67: "FREEZING RAIN", 71: "LIGHT SNOW", 73: "SNOW", 75: "HEAVY SNOW", 77: "SNOW GRAINS",
           80: "SHOWERS", 81: "SHOWERS", 82: "HEAVY SHOWERS", 85: "SNOW SHOWERS", 86: "SNOW SHOWERS",
           95: "THUNDERSTORM", 96: "THUNDER + HAIL", 99: "THUNDER + HAIL"}

    def __init__(self, k):
        self.k = k
        self.weather = None
        if "weather" in k:
            threading.Thread(target=self.weather_loop, daemon=True).start()

    def get(self):
        k = self.k
        if "time" in k:
            # 12 h without the space: "12:44PM" is the widest that fits the big font
            return datetime.now(ZoneInfo(k["time"])).strftime("%-I:%M%p"), k.get("tag", "")
        if k.get("date"):
            now = datetime.now()
            return f"{now.day} {now:%b}", now.strftime("%A").upper()
        if "weather" in k:
            return self.weather or ("--", "WEATHER")
        return None

    @staticmethod
    def fetch(url):
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())

    def weather_loop(self):
        place, coords = self.k["weather"], None
        while True:
            try:
                if not coords:
                    m = re.fullmatch(r"\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*", place)
                    if m:
                        coords = m[1], m[2]
                    else:
                        g = self.fetch("https://geocoding-api.open-meteo.com/v1/search?count=1&name="
                                       + urllib.parse.quote(place))["results"][0]
                        coords = g["latitude"], g["longitude"]
                c = self.fetch(f"https://api.open-meteo.com/v1/forecast?latitude={coords[0]}&longitude={coords[1]}"
                               "&current=temperature_2m,weather_code")["current"]
                # the pad's fonts are ASCII: no degree sign
                # ` is the screens' degree sign
                self.weather = f"{round(c['temperature_2m'])}`C", self.SKY.get(c["weather_code"], "")
            except (OSError, ValueError, KeyError, IndexError) as e:
                log(f"weather: {e}")
            time.sleep(self.WEATHER_EVERY)


# --------------------------------------------------------------------------- the daemon


class Deck:
    def __init__(self, cfg):
        self.keys = cfg.get("keys", {})
        self.sliders = cfg.get("slider", [])[:3]
        knobs = cfg.get("knob", {})
        self.knobs = [KNOB_TYPES[knobs[n]["type"]](knobs[n]) if n in knobs else None for n in ("E1", "E2")]
        self.audio = Audio()
        self.bridges = Bridges(lambda: self.dirty.set())
        for k in self.knobs:
            if isinstance(k, Media):
                k.bridges = self.bridges
        self.brightness = Brightness(next((s.get("buses") for s in self.sliders if s["target"] == "brightness"), None))
        self.window = {"class": "", "pid": 0, "title": ""}
        self.dev = None
        self.dev_lock = threading.Lock()
        self.connected = threading.Event()
        self.sent_screens = {}
        self.slider_seen = set()  # first report after connect is the position, not a move
        self.slider_moved = {}  # slider -> when it last moved
        self.dirty = threading.Event()  # screens need recomputing
        self.audio_dirty = self.devices_dirty = True
        self.slider_workers = [Latest(lambda v, i=i: self.set_slider(i, v)) for i in range(len(self.sliders))]
        # [knob][held]: clicks while the push is held go to their own worker
        self.knob_workers = [[Latest(lambda v, i=i, h=h: self.turn_knob(i, v, h), add=True) for h in (False, True)] for i in range(2)]
        self.knob_held, self.knob_turned = [False, False], [False, False]
        # idle info per screen (sliders 0-2, E1 3, E2 4)
        self.infos = {i: Info(s["info"]) for i, s in enumerate(self.sliders) if "info" in s}
        self.infos.update({3 + i: Info(knobs[n]["info"]) for i, n in enumerate(("E1", "E2")) if "info" in knobs.get(n, {})})
        self.active_until = [0.0] * 5  # screen -> until when it shows its value big
        self.last_sig = {}  # screen -> what counted as its content last time

    # ---- pad I/O

    def send(self, report):
        with self.dev_lock:
            if self.dev:
                self.dev.write(b"\0" + report.ljust(32, b"\0"))  # leading 0 = report id

    def device_loop(self):
        while True:
            path = next((d["path"] for d in hid.enumerate(VID, PID) if d["usage_page"] == USAGE_PAGE), None)
            if not path:
                time.sleep(0.25)
                continue
            dev = hid.device()
            try:
                dev.open_path(path)
                with self.dev_lock:
                    self.dev = dev
                log("pad connected")
                # put the last known screens back at once; the refresh below corrects them
                self.send(bytes([0x08, self.theme()]))
                last, self.sent_screens = self.sent_screens, {}
                for i, scr in last.items():
                    self.draw(i, *scr)
                self.slider_seen.clear()
                self.connected.set()
                self.dirty.set()
                last_ping = 0
                while True:
                    if time.monotonic() - last_ping > 1:
                        self.send(b"\x03")
                        last_ping = time.monotonic()
                    data = dev.read(32, 200)
                    if data:
                        self.on_report(bytes(data))
            except OSError as e:
                log(f"pad gone ({e})")
            finally:
                self.connected.clear()
                with self.dev_lock:
                    self.dev = None
                dev.close()
            time.sleep(0.25)

    def on_report(self, r):
        if r[0] == 0x81 and r[1] < len(self.sliders):
            i = r[1]
            if i in self.slider_seen:
                pct = min(r[2] | r[3] << 8, 1000) / 10  # permille -> %
                self.slider_workers[i].put(pct)
                self.touch(i)
                self.show_slider_now(i, pct)
            self.slider_seen.add(i)
        elif r[0] == 0x82:
            name = KEY_NAMES.get((r[1], r[2]), f"row {r[1]} col {r[2]}")
            log(f"{name} {'down' if r[3] else 'up'}")
            if name in ("E1", "E2"):  # push acts on release, unless the knob turned while held
                i = int(name[1]) - 1
                if r[3]:
                    self.knob_held[i], self.knob_turned[i] = True, False
                    return
                self.knob_held[i] = False
                self.touch(3 + i)
                if self.knobs[i] and not self.knob_turned[i]:
                    threading.Thread(target=self.push_knob, args=(self.knobs[i],), daemon=True).start()
                return
            key = self.keys.get(name, {})
            if r[3] and key.get("run"):
                run(key["run"], key.get("label", name) if key.get("notify") else None)
        elif r[0] == 0x85 and r[1] < len(THEMES):
            log(f"theme {THEMES[r[1]]}")
            THEME.parent.mkdir(parents=True, exist_ok=True)
            THEME.write_text(THEMES[r[1]] + "\n")
        elif r[0] == 0x84 and r[1] < 2:
            i = r[1]
            if self.knob_held[i]:
                self.knob_turned[i] = True
            self.touch(3 + i)
            self.knob_workers[i][self.knob_held[i]].put(1 if r[2] else -1)

    @staticmethod
    def theme():
        try:
            return THEMES.index(THEME.read_text().strip())
        except (FileNotFoundError, ValueError):
            return 0

    def show_slider_now(self, i, pct):
        """Put the slider's new value on its screen at once, before pactl / ddcutil have caught
        up; the regular refresh leaves that screen alone for a moment so it doesn't flick back."""
        prev = self.sent_screens.get(i) or (self.sliders[i].get("label", ""), "", -1, "")
        title, icon = prev[0], prev[3]
        if icon == "mute":  # moving it doesn't unmute, but the number shown is the volume
            icon = "speaker"
        self.slider_moved[i] = time.monotonic()
        self.draw(i, title, f"{round(pct)}%", round(pct), icon)

    def touch(self, i):
        """Screen i shows its value big for the next IDLE_S seconds."""
        self.active_until[i] = time.monotonic() + IDLE_S
        threading.Timer(IDLE_S + 0.05, self.dirty.set).start()

    def draw(self, i, title, text, bar, icon="", info=None):
        key = (title, text, bar, icon, info)
        if self.sent_screens.get(i) == key:
            return
        self.sent_screens[i] = key
        t = title.encode("ascii", "replace")[:TITLE_MAX]
        x = text.encode("ascii", "replace")[:12].ljust(12, b"\0")
        if len(t) > 12:  # the rest of a long title goes first, the 0x01 report completes it
            self.send(bytes([0x02, i]) + t[12:].ljust(TITLE_MAX - 12, b"\0"))
        if info:  # idle: info big, text small; the 0x01 report picks it up
            big, tag = (v.encode("ascii", "replace") for v in info)
            self.send(bytes([0x04, i]) + big[:12].ljust(12, b"\0") + tag[:16].ljust(16, b"\0"))
        ic = ICONS.index(icon) if icon in ICONS else 0
        self.send(bytes([0x01, i, bar & 0xFF]) + t[:12].ljust(12, b"\0") + x + bytes([ic]))

    # ---- actions

    def set_slider(self, i, pct):
        s = self.sliders[i]
        t = s["target"]
        if t == "master":
            out("pactl", "set-sink-volume", self.audio.sink_name or output_sink(), f"{pct:.1f}%")
        elif t == "mic":
            out("pactl", "set-source-volume", "@DEFAULT_SOURCE@", f"{pct:.1f}%")
        elif t == "brightness":
            self.brightness.set(round(pct))
            self.dirty.set()
        elif t == "focused" and (b := self.bridges.for_window(self.window["class"])):
            self.bridges.send(b, {"type": "set", "volume": round(pct / 100, 3), "title": self.window["title"]})
        else:
            for st in self.audio.streams(s, self.window):
                out("pactl", "set-sink-input-volume", str(st["index"]), f"{pct:.1f}%")

    def turn_knob(self, i, clicks, held):
        k = self.knobs[i]
        if k:
            (k.turn_held if held and hasattr(k, "turn_held") else k.turn)(clicks)
            self.dirty.set()

    def push_knob(self, knob):
        knob.push()
        time.sleep(0.3)
        self.dirty.set()

    # ---- screens

    def slider_screen(self, s):
        t = s["target"]
        label = s.get("label", t.upper())
        if t == "brightness":
            v = self.brightness.value
            return (label, "--", -1, "sun") if v is None else (label, f"{v}%", v, "sun")
        if t in ("master", "mic"):
            d = self.audio.sink() if t == "master" else self.audio.source()
            icon, muted = ("speaker", "mute") if t == "master" else ("mic", "mic-mute")
            if not d:
                return label, "--", -1, icon
            v = percent(d)
            return (label, "MUTE", min(v, 100), muted) if d.get("mute") else (label, f"{v}%", min(v, 100), icon)
        if t == "focused" and (b := self.bridges.for_window(self.window["class"])):
            tab = self.bridges.tabs.get(b, {})
            if tab.get("for") != self.window["title"]:
                return "BROWSER", "...", -1, "globe"  # the extension hasn't answered for this window yet
            label = tab.get("site", "").upper() or label
            v = tab.get("volume")
            return (label, "--", -1, "globe") if v is None else (label, f"{round(v * 100)}%", round(v * 100), "globe")
        streams = self.audio.streams(s, self.window)
        if t == "focused":
            label = self.window["class"].split(".")[-1].upper() or label
        if not streams:
            return label, "--", -1, "app"
        v = percent(streams[0])
        return (label, "MUTE", min(v, 100), "mute") if streams[0].get("mute") else (label, f"{v}%", min(v, 100), "app")

    def screen_loop(self):
        while True:
            self.dirty.wait()
            time.sleep(0.15)  # let bursts settle; at most ~6 updates a second
            self.dirty.clear()
            if not self.connected.is_set():
                continue
            if self.audio_dirty:
                devices, self.audio_dirty, self.devices_dirty = self.devices_dirty, False, False
                self.audio.refresh(devices)
            now = time.monotonic()
            for i, s in enumerate(self.sliders):
                if now - self.slider_moved.get(i, 0) < 0.5:
                    threading.Timer(0.5, self.dirty.set).start()  # catch up once it stops
                    continue
                self.draw_idle(i, self.slider_screen(s))
            for i, k in enumerate(self.knobs):
                scr = k.screen() if k else ("", "", -1, "")
                # media: the elapsed time ticking doesn't count as a change, a new track does
                self.draw_idle(3 + i, scr, (scr[0], scr[3]) if isinstance(k, Media) else scr)

    def draw_idle(self, i, scr, sig=None):
        """Draw a screen, with its idle info once nothing has touched or changed it for IDLE_S."""
        sig = scr if sig is None else sig
        if i in self.last_sig and self.last_sig[i] != sig:
            self.touch(i)
        self.last_sig[i] = sig
        info = self.infos[i].get() if i in self.infos and time.monotonic() >= self.active_until[i] else None
        self.draw(i, *scr, info)

    def audio_loop(self):
        while True:
            p = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                if "on sink" in line or "on source" in line or "on server" in line:
                    if "'change'" not in line or "on server" in line:
                        self.devices_dirty = True  # added / removed / default changed
                    self.audio_dirty = True
                    self.dirty.set()
            p.wait()
            time.sleep(1)

    # ---- Hyprland: focused window (for the "focused" slider)

    def update_window(self):
        try:
            w = json.loads(out("hyprctl", "activewindow", "-j") or "{}")
        except json.JSONDecodeError:
            w = {}
        self.window = {"class": w.get("class", ""), "pid": w.get("pid", 0), "title": w.get("title", "")}
        if b := self.bridges.for_window(self.window["class"]):
            self.bridges.send(b, {"type": "focus", "title": self.window["title"]})
        self.dirty.set()

    def hypr_socket(self):
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "hypr"
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        if sig and (runtime / sig / ".socket2.sock").exists():
            return runtime / sig / ".socket2.sock"
        # Hyprland restarted, or started outside its environment: take the newest instance
        socks = sorted(runtime.glob("*/.socket2.sock"), key=lambda p: p.stat().st_mtime)
        if socks:
            os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = socks[-1].parent.name  # for hyprctl
            return socks[-1]
        return None

    def hypr_loop(self):
        while True:
            path = self.hypr_socket()
            if not path:
                time.sleep(2)
                continue
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.connect(str(path))
                    self.update_window()
                    buf = b""
                    while chunk := s.recv(4096):
                        buf += chunk
                        *lines, buf = buf.split(b"\n")
                        if any(l.startswith(b"activewindow>>") for l in lines):
                            self.update_window()
            except OSError as e:
                log(f"hyprland socket: {e}")
            time.sleep(2)

    def tick_loop(self):
        while True:  # knob screens (track title, night light) have no change events
            time.sleep(2)
            self.dirty.set()

    def run(self):
        for loop in (self.screen_loop, self.audio_loop, self.hypr_loop, self.tick_loop):
            threading.Thread(target=loop, daemon=True).start()
        self.device_loop()


def boot():
    """Jump the pad to its bootloader (works while the daemon runs: hidraw allows two openers)."""
    path = next((d["path"] for d in hid.enumerate(VID, PID) if d["usage_page"] == USAGE_PAGE), None)
    if not path:
        sys.exit("pad not found")
    dev = hid.device()
    dev.open_path(path)
    dev.write(b"\0\x05" + bytes(31))
    dev.close()
    print("pad is in its bootloader: qmk flash -kb handwired/deck -km default")


def reload_extension():
    """Make the browser extension reload itself from disk (after editing it)."""
    s = socket.socket(socket.AF_UNIX)
    s.connect(str(Bridges.PATH))
    s.sendall(b'{"type": "reload-extension"}\n')
    s.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["boot"]:
        boot()
    elif sys.argv[1:] == ["reload-extension"]:
        reload_extension()
    else:
        Deck(load_config()).run()
