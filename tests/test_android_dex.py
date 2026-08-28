import actions.android_dex as dex


def test_android_dex_tool_registered_in_main():
    from pathlib import Path
    main_text = Path("main.py").read_text(encoding="utf-8")
    assert '"name": "android_dex"' in main_text


def test_android_dex_dispatch_routes_actions(monkeypatch):
    calls = []

    def fake_adb(args, serial=None, timeout=25):
        calls.append((tuple(args), serial))
        if args[:2] == ["devices"]:
            return True, "List of devices attached\nABC123\tdevice\n"
        if args[:3] == ["shell", "pm", "list"]:
            return True, "package:com.whatsapp\npackage:com.instagram\n"
        return True, "ok"

    monkeypatch.setattr(dex, "_adb", fake_adb)

    out = dex.android_dex({"action": "apps"})
    assert "com.whatsapp" in out and "com.instagram" in out

    out = dex.android_dex({"action": "launch", "app_name": "whatsapp"})
    assert "com.whatsapp" in out
    assert any(a[:4] == ("shell", "monkey", "-p", "com.whatsapp") for a, _ in calls)

    out = dex.android_dex({"action": "media", "control": "next"})
    assert "next" in out.lower()

    out = dex.android_dex({"action": "status"})
    assert "ABC123" in out


def test_android_dex_no_device_message(monkeypatch):
    monkeypatch.setattr(dex, "_adb", lambda args, serial=None, timeout=25: (True, "List of devices attached\n"))
    out = dex.android_dex({"action": "apps"})
    assert "No Android device connected" in out


def test_android_dex_connect_needs_ip(monkeypatch):
    monkeypatch.setattr(dex, "_adb", lambda args, serial=None, timeout=25: (True, ""))
    out = dex.android_dex({"action": "connect"})
    assert "IP" in out
