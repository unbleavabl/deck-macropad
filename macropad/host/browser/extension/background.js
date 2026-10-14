// deckd tab volume: the macropad's "focused" slider sets the volume of the media in the active
// tab of the focused window, so every tab and window is separate (Chromium plays all of them
// through one audio stream). Talks to deckd through the native host com.deckd.bridge
// (host/browser/deckd_bridge.py); an open native port also keeps this worker alive.

let port = null;
let focus = null; // title of the focused window, from deckd (Hyprland knows focus; Chromium on Wayland doesn't reliably)
let busy = false;
let pending; // newest volume asked for while busy (undefined = none)

function connect() {
  port = chrome.runtime.connectNative("com.deckd.bridge");
  port.onMessage.addListener((m) => {
    if (m.title !== undefined) focus = m.title;
    if (m.type === "set") request(m.volume);
    else if (m.type === "get" || m.type === "focus") request(null);
    else if (m.type === "seek") seek(m.seconds, m.track);
    else if (m.type === "reload") chrome.runtime.reload(); // deckd.py reload-extension
  });
  port.onDisconnect.addListener(() => {
    port = null;
    setTimeout(connect, 5000);
  });
  request(null);
}

// Runs in the page. YouTube: its own player API, so its volume slider follows. Elsewhere every
// audio / video element. v = 0..1 to set, null to only read. Returns 0..1, or null without media.
function pageVolume(v) {
  const yt = document.getElementById("movie_player");
  if (yt && yt.setVolume) {
    if (v !== null) {
      yt.setVolume(Math.round(v * 100));
      if (v > 0 && yt.isMuted()) yt.unMute();
    }
    return yt.isMuted() ? 0 : yt.getVolume() / 100;
  }
  const media = [...document.querySelectorAll("video, audio")];
  if (!media.length) return null;
  if (v !== null)
    media.forEach((m) => {
      m.volume = v;
      if (v > 0) m.muted = false;
    });
  return media[0].muted ? 0 : media[0].volume;
}

// one page call at a time; slider bursts collapse to the newest value
async function request(v) {
  if (busy) {
    if (v !== null || pending === undefined) pending = v;
    return;
  }
  busy = true;
  try {
    await apply(v);
  } finally {
    busy = false;
  }
  if (pending !== undefined) {
    const next = pending;
    pending = undefined;
    request(next);
  }
}

// The tab shown in the focused window: a window's title is its active tab's title plus
// " - Chromium" (web app windows: the title alone).
async function focusedTab() {
  const tabs = await chrome.tabs.query({ active: true });
  if (focus) {
    // each profile runs its own copy of this extension; only the one owning the tab answers
    return tabs
      .filter((t) => t.title && focus.startsWith(t.title))
      .sort((a, b) => b.title.length - a.title.length)[0];
  }
  const win = await chrome.windows.getLastFocused({ populate: true }).catch(() => null);
  return win?.tabs?.find((t) => t.active);
}

async function apply(v) {
  const want = focus;
  const tab = await focusedTab();
  if (!tab) return;
  if (!/^https?:/.test(tab.url || "")) {
    port?.postMessage({ type: "tab", for: want, site: "", title: tab?.title || "", volume: null });
    return;
  }
  let volume = null;
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id, allFrames: true },
      world: "MAIN",
      func: pageVolume,
      args: [v],
    });
    volume = results.map((r) => r.result).find((x) => typeof x === "number") ?? null;
  } catch (e) {} // pages scripts can't run on (web store, error pages)
  const site = new URL(tab.url).hostname.replace(/^www\./, "");
  port?.postMessage({ type: "tab", for: want, site, title: tab.title, volume });
}

// E1: seek the tab playing `track` (the media title Omarchy shows), focused or not.
// YouTube through its player API, elsewhere the playing (or first) media element.
function pageSeek(seconds) {
  const yt = document.getElementById("movie_player");
  if (yt && yt.seekTo) {
    yt.seekTo(yt.getCurrentTime() + seconds, true);
    return true;
  }
  const media = [...document.querySelectorAll("video, audio")];
  const m = media.find((x) => !x.paused) || media[0];
  if (!m) return false;
  m.currentTime = Math.max(0, m.currentTime + seconds);
  return true;
}

async function seek(seconds, track) {
  const tabs = (await chrome.tabs.query({})).filter((t) => track && t.title && t.title.includes(track));
  tabs.sort((a, b) => b.audible - a.audible); // the one playing first
  if (!tabs.length) return;
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tabs[0].id, allFrames: true },
      world: "MAIN",
      func: pageSeek,
      args: [seconds],
    });
  } catch (e) {}
}

const report = () => request(null);
chrome.tabs.onUpdated.addListener((id, info) => {
  if (info.audible !== undefined || info.status === "complete") report();
});
chrome.runtime.onStartup.addListener(() => {}); // wakes the worker when the browser starts
connect();
