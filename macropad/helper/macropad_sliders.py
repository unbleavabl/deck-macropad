#!/usr/bin/env python3
"""Turn the macropad's 3 slide pots into volume (or anything else) on Linux.

The firmware sends the pots as joystick axes X, Y, Z over USB. This reads them with evdev and
runs the action configured for each slider in sliders.toml.

    ./macropad_sliders.py               run with ./sliders.toml
    ./macropad_sliders.py --list        show input devices and which one matches
    ./macropad_sliders.py --dry-run     print actions instead of running them
    ./macropad_sliders.py --apps        list programs playing audio (for app names)

Needs python-evdev (pacman -S python-evdev), and pactl/wpctl for audio.
"""
import argparse
import json
import select
import shlex
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import evdev
from evdev import ecodes

AXES = {"x": ecodes.ABS_X, "y": ecodes.ABS_Y, "z": ecodes.ABS_Z}
HERE = Path(__file__).resolve().parent


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- actions

def sh(cmd, dry):
    if dry:
        log("would run:", cmd if isinstance(cmd, str) else shlex.join(cmd))
        return
    try:
        subprocess.run(cmd, shell=isinstance(cmd, str), check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
    except subprocess.TimeoutExpired:
        log("timed out:", cmd)


def sink_inputs():
    """Streams currently playing audio, from pactl's JSON output."""
    try:
        out = subprocess.run(["pactl", "-f", "json", "list", "sink-inputs"],
                             capture_output=True, text=True, timeout=2).stdout
        return json.loads(out or "[]")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []


def stream_names(si):
    p = si.get("properties", {})
    return [p.get(k, "") for k in ("application.name", "application.process.binary",
                                     "application.id", "media.name")]


def matches(si, wanted):
    wanted = [w.lower() for w in wanted]
    return any(w and w in n.lower() for n in stream_names(si) for w in wanted)


def do_action(slider, pct, dry):
    kind = slider["action"]
    if kind == "master":
        sh(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{pct}%"], dry)
    elif kind == "mic":
        sh(["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", f"{pct}%"], dry)
    elif kind == "app":
        apps = slider["apps"] if isinstance(slider["apps"], list) else [slider["apps"]]
        hit = [si for si in sink_inputs() if matches(si, apps)]
        if not hit and dry:
            log(f"no stream playing for {apps}")
        for si in hit:
            sh(["pactl", "set-sink-input-volume", str(si["index"]), f"{pct}%"], dry)
    elif kind == "brightness":
        sh(["brightnessctl", "-q", "set", f"{max(pct, slider.get('min', 1))}%"], dry)
    elif kind == "command":
        sh(slider["command"].format(percent=pct, value=pct / 100), dry)
    else:
        log(f"unknown action {kind!r}")


# ---------------------------------------------------------------- input

def find_device(name):
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue
        abs_codes = {c for c, _ in dev.capabilities().get(ecodes.EV_ABS, [])}
        if name.lower() in dev.name.lower() and set(AXES.values()) <= abs_codes:
            return dev
        dev.close()
    return None


def to_percent(raw, info, snap):
    span = info.max - info.min
    pct = round(100 * (raw - info.min) / span) if span else 0
    if pct <= snap:
        return 0
    if pct >= 100 - snap:
        return 100
    return pct


def run(cfg, dry):
    sliders = cfg["slider"]
    name = cfg.get("device_name", "Macropad")
    min_gap = 1 / cfg.get("max_rate_hz", 20)
    snap = cfg.get("end_snap_percent", 2)
    invert = cfg.get("invert", False)

    while True:
        dev = find_device(name)
        if dev is None:
            log(f"waiting for a '{name}' joystick device (is the firmware with the sliders loaded?)")
            while (dev := find_device(name)) is None:
                time.sleep(2)
        log(f"using {dev.path}: {dev.name}")
        info = {axis: dev.absinfo(code) for axis, code in AXES.items()}
        by_code = {AXES[s["axis"]]: s for s in sliders}
        last_pct, last_sent = {}, {}
        pending = {}

        def flush(now):
            for code, pct in list(pending.items()):
                if pct == last_pct.get(code):
                    pending.pop(code)
                    continue
                if now - last_sent.get(code, 0) < min_gap:
                    continue  # too soon; stays pending for the next flush
                s = by_code[code]
                if dry:
                    log(f"{s.get('name', s['axis'])}: {pct}%")
                do_action(s, pct, dry)
                last_pct[code], last_sent[code] = pct, now
                pending.pop(code)

        try:
            while True:
                # wake up for new events, or in time to send a held-back value
                r, _, _ = select.select([dev.fd], [], [], min_gap if pending else None)
                if r:
                    for ev in dev.read():
                        if ev.type == ecodes.EV_ABS and ev.code in by_code:
                            pct = to_percent(ev.value, info[by_code[ev.code]["axis"]], snap)
                            pending[ev.code] = 100 - pct if invert else pct
                flush(time.monotonic())
        except OSError:
            log("device gone, waiting for it to come back")
            time.sleep(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--config", default=str(HERE / "sliders.toml"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--apps", action="store_true")
    args = ap.parse_args()

    if args.apps:
        for si in sink_inputs():
            print(" | ".join(n for n in stream_names(si) if n))
        return
    cfg = tomllib.loads(Path(args.config).read_text())
    if args.list:
        want = cfg.get("device_name", "Macropad")
        hit = find_device(want)
        for path in evdev.list_devices():
            d = evdev.InputDevice(path)
            mark = "  <- sliders" if hit and d.path == hit.path else ""
            print(f"{d.path}  {d.name}{mark}")
        if not hit:
            print(f"\nno device named like '{want}' with axes X/Y/Z")
        return
    try:
        run(cfg, args.dry_run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
