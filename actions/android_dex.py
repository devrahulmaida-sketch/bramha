# actions/android_dex.py
r"""
Android DEX Control for Rahul AI
================================
Inspired by the Android DEX project (github.com/Shrey113/Android-Dex):
desktop-grade Android control — mirroring, app management, notifications,
media control, and keyboard/mouse game input — delivered through open
ADB + scrcpy instead of the closed-source companion APK.

Capabilities (tool: android_dex, parameter `action`):
  devices          — list connected ADB devices (USB + Wi-Fi)
  connect          — wireless ADB connect (ip[:port]) / switch device to TCP/IP
  apps             — list installed (third-party) apps, with fuzzy search
  launch           — launch an app by name or package
  stop_app         — force-stop an app
  install          — install an APK (adb install -r)
  mirror           — scrcpy mirror window (fullscreen / view-only / record)
  stop_mirror      — close running mirror windows
  screenshot       — capture device screen to Downloads/Rahul DEX/
  media            — play/pause/next/previous/volume/mute media control
  notifications    — latest notification titles + packages (dumpsys)
  input            — tap / swipe / type / key / back / home / recents / wake
  status           — battery, model, android version, screen state

Setup (one-time):
  • Install Android platform-tools (adb) — https://developer.android.com/tools/releases/platform-tools
  • Optional mirroring: install scrcpy — https://github.com/Genymobile/scrcpy
  • Enable USB debugging on the phone (Developer options) and plug it in,
    or use `action=connect` with the phone's Wi-Fi IP for wireless.
  • Optional paths can be pinned in config/app_settings.json:
      { "adb_path": "C:\platform-tools\adb.exe", "scrcpy_path": "C:\scrcpy\scrcpy.exe" }
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = BASE_DIR / "config" / "app_settings.json"
OUTPUT_DIR = Path.home() / "Downloads" / "Rahul DEX"

_MEDIA_KEYS = {
    "play_pause": 85, "play": 85, "pause": 85,
    "next": 87, "previous": 88, "prev": 88,
    "volume_up": 24, "volume_down": 25, "mute": 164,
}
_NAV_KEYS = {
    "back": 4, "home": 3, "recents": 187, "menu": 82,
    "wake": 224, "sleep": 223, "power": 26, "enter": 66,
    "delete": 67, "volume_up": 24, "volume_down": 25, "mute": 164,
    "up": 19, "down": 20, "left": 21, "right": 22,
}

# running scrcpy processes (so we can stop them later)
_mirrors: list[subprocess.Popen] = []
_mirror_lock = threading.Lock()


# ── helpers ────────────────────────────────────────────────────────────────

def _settings() -> dict:
    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _find_tool(name: str, settings_key: str, extra_candidates: tuple[str, ...] = ()) -> str | None:
    """Locate adb/scrcpy: setting → PATH → common install locations."""
    configured = str(_settings().get(settings_key, "") or "").strip()
    if configured and Path(configured).exists():
        return configured
    on_path = shutil.which(name)
    if on_path:
        return on_path
    candidates = [
        r"C:\platform-tools\{0}.exe".format(name),
        r"C:\adb\{0}.exe".format(name),
        r"C:\Android\platform-tools\{0}.exe".format(name),
        r"C:\Program Files\scrcpy\{0}.exe".format(name),
        str(BASE_DIR / "tools" / "{0}.exe".format(name)),
        *extra_candidates,
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def _adb_path() -> str:
    return _find_tool("adb", "adb_path") or ""


def _scrcpy_path() -> str:
    return _find_tool("scrcpy", "scrcpy_path") or ""


def _run(cmd: list[str], timeout: int = 25) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return False, f"'{cmd[0]}' not found."
    except subprocess.TimeoutExpired:
        return False, f"Command timed out: {' '.join(cmd[:3])}…"
    except Exception as exc:
        return False, f"Command failed: {exc}"


def _adb(args: list[str], serial: str | None = None, timeout: int = 25) -> tuple[bool, str]:
    adb = _adb_path()
    if not adb:
        return False, (
            "ADB not found. Install Android platform-tools and (optionally) set "
            "'adb_path' in config/app_settings.json. "
            "https://developer.android.com/tools/releases/platform-tools"
        )
    cmd = [adb]
    if serial:
        cmd += ["-s", serial]
    return _run(cmd + args, timeout=timeout)


def _first_serial(explicit: str | None = None) -> tuple[str | None, str]:
    """Return (serial, error). Uses explicit target or the single connected device."""
    if explicit:
        return explicit, ""
    ok, out = _adb(["devices"])
    if not ok:
        return None, out
    serials = [
        line.split()[0]
        for line in out.splitlines()[1:]
        if line.strip() and line.split()[-1] == "device" and not line.startswith("*")
    ]
    if not serials:
        return None, "No Android device connected. Plug in with USB debugging on, or use action=connect for Wi-Fi."
    return serials[0], ""


def _speak(player, message: str) -> None:
    try:
        if player and hasattr(player, "write_log"):
            player.write_log(f"DEX: {message}")
    except Exception:
        pass


# ── actions ────────────────────────────────────────────────────────────────

def _act_devices() -> str:
    ok, out = _adb(["devices"])
    if not ok:
        return out
    lines = [l.strip() for l in out.splitlines()[1:] if l.strip() and not l.startswith("*")]
    if not lines:
        return "No ADB devices connected."
    rows = []
    for l in lines:
        parts = l.split()
        rows.append(f"• {parts[0]} — {parts[1] if len(parts) > 1 else 'unknown'}")
    return "Connected devices:\n" + "\n".join(rows)


def _act_connect(ip: str) -> str:
    if not ip:
        return "Give the phone's IP address (Settings → About → Status). Example: 192.168.0.105:5555"
    if ":" not in ip:
        ip = f"{ip}:5555"
    # If a USB device is attached, first switch it to TCP/IP mode
    serial, err = _first_serial()
    if serial and "." not in serial:
        _adb(["tcpip", "5555"], serial=serial)
        time.sleep(1.5)
    ok, out = _adb(["connect", ip])
    if not ok or "connected" not in out.lower():
        return f"Could not connect to {ip}: {out.strip()}"
    return f"Connected to {ip} over Wi-Fi. Device is now controllable wirelessly."


def _list_packages(serial: str, third_party_only: bool = True) -> list[str]:
    args = ["shell", "pm", "list", "packages"]
    if third_party_only:
        args.append("-3")
    ok, out = _adb(args, serial=serial)
    if not ok:
        return []
    return sorted(l.replace("package:", "").strip() for l in out.splitlines() if l.startswith("package:"))


def _act_apps(serial: str, query: str | None) -> str:
    pkgs = _list_packages(serial)
    if not pkgs:
        return "No apps listed (is the device authorized?)."
    if query:
        q = query.lower()
        matched = [p for p in pkgs if q in p.lower()]
        if not matched:
            return f"No app matches '{query}'. {len(pkgs)} apps installed."
        pkgs = matched
    shown = pkgs[:60]
    body = "\n".join(f"• {p}" for p in shown)
    extra = f"\n…and {len(pkgs) - 60} more." if len(pkgs) > 60 else ""
    return f"{len(pkgs)} app(s):\n{body}{extra}"


def _resolve_package(serial: str, app: str) -> str | None:
    app = (app or "").strip().lower().replace(" ", "")
    if not app:
        return None
    pkgs = _list_packages(serial)
    # exact → suffix match → substring
    for p in pkgs:
        if p.lower() == app:
            return p
    for p in pkgs:
        if p.lower().split(".")[-1] == app:
            return p
    for p in pkgs:
        if app in p.lower():
            return p
    return None


def _act_launch(serial: str, app: str) -> str:
    pkg = _resolve_package(serial, app)
    if not pkg:
        return f"App '{app}' not found. Use action=apps to list installed apps."
    ok, out = _adb(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"], serial=serial)
    if not ok:
        return f"Launch failed: {out.strip()[:200]}"
    return f"Launched {pkg}."


def _act_stop_app(serial: str, app: str) -> str:
    pkg = _resolve_package(serial, app)
    if not pkg:
        return f"App '{app}' not found."
    ok, out = _adb(["shell", "am", "force-stop", pkg], serial=serial)
    return f"Stopped {pkg}." if ok else f"Stop failed: {out.strip()[:200]}"


def _act_install(serial: str, path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"APK not found: {path}"
    ok, out = _adb(["install", "-r", str(p)], serial=serial, timeout=180)
    if ok and "success" in out.lower():
        return f"Installed {p.name}."
    return f"Install failed: {out.strip()[:300]}"


def _act_mirror(serial: str, mode: str, record: str | None) -> str:
    scrcpy = _scrcpy_path()
    if not scrcpy:
        return ("scrcpy not found. Install it from https://github.com/Genymobile/scrcpy "
                "or set 'scrcpy_path' in config/app_settings.json.")
    cmd = [scrcpy]
    if serial:
        cmd += ["-s", serial]
    cmd += ["--window-title", "Rahul AI — Android DEX"]
    if mode == "fullscreen":
        cmd.append("--fullscreen")
    if mode in ("view", "view_only", "no_control"):
        cmd.append("--no-control")
    if record:
        rec = Path(record).expanduser()
        rec.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["--record", str(rec)]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
        )
    except Exception as exc:
        return f"Mirror failed to start: {exc}"
    with _mirror_lock:
        _mirrors.append(proc)
    extra = " (recording)" if record else ""
    return f"Mirror started{extra}. Close the scrcpy window or use action=stop_mirror."


def _act_stop_mirror() -> str:
    with _mirror_lock:
        procs = list(_mirrors)
        _mirrors.clear()
    stopped = 0
    for p in procs:
        try:
            if p.poll() is None:
                p.terminate()
                stopped += 1
        except Exception:
            pass
    # Also catch any stray scrcpy the user started manually
    ok, out = _run(["taskkill", "/IM", "scrcpy.exe", "/F"]) if sys.platform == "win32" else (True, "")
    return f"Stopped {stopped} mirror window(s)."


def _act_screenshot(serial: str) -> str:
    ok, out = _adb(["exec-out", "screencap", "-p"], serial=serial, timeout=30)
    if not ok:
        # text-mode fallback: some setups mangle exec-out
        return f"Screenshot failed: {out.strip()[:200]}"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
    path.write_bytes(out.encode("latin-1", errors="ignore") if isinstance(out, str) else out)
    return f"Screenshot saved: {path}"


def _act_media(serial: str, control: str) -> str:
    control = (control or "").lower().strip()
    code = _MEDIA_KEYS.get(control)
    if code is None:
        return "control must be: play_pause | next | previous | volume_up | volume_down | mute"
    ok, out = _adb(["shell", "input", "keyevent", str(code)], serial=serial)
    return f"Media: {control.replace('_', ' ')}." if ok else f"Media command failed: {out.strip()[:150]}"


def _act_notifications(serial: str) -> str:
    ok, out = _adb(["shell", "dumpsys", "notification", "--noredact"], serial=serial, timeout=30)
    if not ok:
        return f"Could not read notifications: {out.strip()[:200]}"
    items: list[str] = []
    seen: set[str] = set()
    for line in out.splitlines():
        m = re.search(r"NotificationRecord\(.*?pkg=(\S+).*?android\.title=(String\)?\s*)?(.*?)(/|\)|$)", line)
        if m:
            pkg, title = m.group(1), m.group(3).strip().strip('"')
            if title and (pkg, title) not in seen:
                seen.add((pkg, title))
                items.append(f"• [{pkg}] {title}")
    if not items:
        for line in out.splitlines():
            m = re.match(r"\s{2}(\S+).*?", line)
            if "NotificationRecord" in line:
                pm = re.search(r"pkg=(\S+)", line)
                if pm:
                    items.append(f"• [{pm.group(1)}] (notification active)")
    if not items:
        return "No notifications found (or lockscreen privacy hides them)."
    return "Latest notifications:\n" + "\n".join(items[:20])


def _act_input(serial: str, parameters: dict) -> str:
    kind = str(parameters.get("input_type") or parameters.get("gesture") or "tap").lower()
    if kind in ("tap", "click"):
        x, y = parameters.get("x"), parameters.get("y")
        if x is None or y is None:
            return "tap needs x and y coordinates."
        ok, out = _adb(["shell", "input", "tap", str(int(x)), str(int(y))], serial=serial)
        return f"Tapped ({x}, {y})." if ok else f"Tap failed: {out.strip()[:150]}"
    if kind == "swipe":
        pts = [parameters.get(k) for k in ("x", "y", "x2", "y2")]
        if any(v is None for v in pts):
            return "swipe needs x, y, x2, y2."
        dur = int(parameters.get("duration", 300))
        ok, out = _adb(["shell", "input", "swipe", *[str(int(v)) for v in pts], str(dur)], serial=serial)
        return "Swiped." if ok else f"Swipe failed: {out.strip()[:150]}"
    if kind in ("type", "text"):
        text = str(parameters.get("text") or "")
        if not text:
            return "type needs text."
        safe = text.replace(" ", "%s").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>")
        ok, out = _adb(["shell", "input", "text", safe], serial=serial)
        return f"Typed {len(text)} characters." if ok else f"Typing failed: {out.strip()[:150]}"
    if kind == "key":
        key = str(parameters.get("key") or "").lower()
        code = _NAV_KEYS.get(key)
        if code is None and key.isdigit():
            code = int(key)
        if code is None:
            return f"Unknown key '{key}'. Use: {', '.join(sorted(_NAV_KEYS))} or an Android keycode number."
        ok, out = _adb(["shell", "input", "keyevent", str(code)], serial=serial)
        return f"Key: {key}." if ok else f"Key failed: {out.strip()[:150]}"
    return "input_type must be: tap | swipe | type | key"


def _act_status(serial: str) -> str:
    _, model = _adb(["shell", "getprop", "ro.product.model"], serial=serial)
    _, version = _adb(["shell", "getprop", "ro.build.version.release"], serial=serial)
    _, batt = _adb(["shell", "dumpsys", "battery"], serial=serial)
    level = re.search(r"level:\s*(\d+)", batt or "")
    temp = re.search(r"temperature:\s*(\d+)", batt or "")
    temp_c = f"{int(temp.group(1)) / 10:.1f}°C" if temp else "n/a"
    _, power = _adb(["shell", "dumpsys", "power"], serial=serial, timeout=20)
    awake = "awake" if (power and "mWakefulness=Awake" in power) else "asleep"
    return (
        f"Device: {model.strip() or 'unknown'} (Android {version.strip() or '?'})\n"
        f"Battery: {level.group(1) + '%' if level else 'n/a'} · Temp: {temp_c} · Screen: {awake}\n"
        f"Serial: {serial}"
    )


# ── main entry ─────────────────────────────────────────────────────────────

def android_dex(parameters: dict, player=None, session_memory=None, speak=None) -> str:
    params   = parameters or {}
    action   = str(params.get("action") or "devices").lower().strip()
    target   = params.get("target") or params.get("device") or params.get("serial")

    if action == "connect":
        return _act_connect(str(params.get("ip") or params.get("address") or ""))
    if action == "stop_mirror":
        return _act_stop_mirror()

    serial, err = _first_serial(str(target) if target else None)
    if err:
        return err

    if action in ("devices", "list_devices"):
        return _act_devices()
    if action in ("apps", "list_apps", "app_list"):
        return _act_apps(serial, params.get("query") or params.get("app_name"))
    if action == "launch":
        return _act_launch(serial, str(params.get("app_name") or params.get("package") or params.get("app") or ""))
    if action in ("stop_app", "close_app"):
        return _act_stop_app(serial, str(params.get("app_name") or params.get("package") or params.get("app") or ""))
    if action == "install":
        return _act_install(serial, str(params.get("path") or params.get("apk_path") or ""))
    if action == "mirror":
        return _act_mirror(serial, str(params.get("mode") or "window").lower(), params.get("record"))
    if action == "screenshot":
        return _act_screenshot(serial)
    if action == "media":
        return _act_media(serial, str(params.get("control") or params.get("media_control") or ""))
    if action in ("notifications", "notify"):
        return _act_notifications(serial)
    if action == "input":
        return _act_input(serial, params)
    if action in ("status", "info", "device_info"):
        return _act_status(serial)

    return (
        "Unknown action. Available: devices, connect, apps, launch, stop_app, install, "
        "mirror, stop_mirror, screenshot, media, notifications, input, status."
    )


PLUGIN = {
    "name": "android_dex",
    "description": "Android DEX control — mirror, apps, notifications, media, and touch/key input on a connected Android device via ADB/scrcpy.",
}
