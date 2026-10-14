#!/usr/bin/env python3
"""Native messaging host com.deckd.bridge: the browser starts it for the deckd extension and
talks over stdin/stdout (4-byte length + JSON); it relays to deckd's socket as JSON lines.
Keeps retrying deckd, so the extension's port (and its worker) stay up while deckd restarts."""

import json
import os
import socket
import struct
import sys
import threading
import time

SOCK = os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "deckd.sock")
browser = open(f"/proc/{os.getppid()}/comm").read().strip()  # "chromium", "chrome", ...
conn = None
lock = threading.Lock()


def to_browser(msg):
    data = json.dumps(msg).encode()
    sys.stdout.buffer.write(struct.pack("<I", len(data)) + data)
    sys.stdout.buffer.flush()


def to_deckd(msg):
    with lock:
        if conn:
            try:
                conn.sendall((json.dumps(msg) + "\n").encode())
            except OSError:
                pass


def deckd_loop():
    global conn
    while True:
        try:
            s = socket.socket(socket.AF_UNIX)
            s.connect(SOCK)
            with lock:
                conn = s
            to_deckd({"type": "hello", "browser": browser})
            to_browser({"type": "get"})
            for line in s.makefile():
                to_browser(json.loads(line))
        except (OSError, json.JSONDecodeError):
            pass
        with lock:
            conn = None
        time.sleep(2)


threading.Thread(target=deckd_loop, daemon=True).start()
while header := sys.stdin.buffer.read(4):
    to_deckd(json.loads(sys.stdin.buffer.read(struct.unpack("<I", header)[0])))
