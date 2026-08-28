# actions/phone_camera.py
"""
Rahul AI — Phone Camera Holographic Viewer
===========================================
Mirrors the connected phone's camera (streamed over Rahul Connect as
`camera_frame` messages) into a desktop window with:

  • Holographic render mode (cyan scanlines, tint, glow frame, HUD brackets)
  • Hand-gesture control from the PHONE camera itself:
      - Pinch (thumb+index distance)  → zoom in / out  (1.0x – 4.0x)
      - Open palm position            → pan / move the view
  • Manual controls: hologram on/off, zoom +/-, reset, stop

Voice entry points (tool `phone_camera`):
  "show my phone camera" / "phone camera hologram on" / "stop phone camera"
"""

from __future__ import annotations

import base64
import threading
import time
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "config" / "models" / "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-assets/hand_landmarker.task"

_ACCENT = QColor(34, 211, 238)          # Rahul AI cyan
_BG = QColor(4, 6, 10)


class _CameraBridge(QObject):
    """Cross-thread bridge: gateway thread → Qt main thread (queued signals)."""

    frame_ready = pyqtSignal(bytes)
    open_requested = pyqtSignal(str)
    close_requested = pyqtSignal()


bridge = _CameraBridge()


class _GestureThread(threading.Thread):
    """Runs MediaPipe hand detection on the latest frame (~5 fps)."""

    def __init__(self):
        super().__init__(daemon=True, name="PhoneCameraGestures")
        self._lock = threading.Lock()
        self._latest: bytes | None = None
        self._stop = threading.Event()
        self._landmarker = None
        # outputs (read by UI):
        self.hand_visible = False
        self.pinch_norm = 0.35      # 0..1 (thumb-index distance)
        self.palm_x = 0.5           # 0..1
        self.palm_y = 0.5           # 0..1

    def feed(self, jpeg: bytes) -> None:
        with self._lock:
            self._latest = jpeg

    def stop(self) -> None:
        self._stop.set()

    def _ensure_landmarker(self):
        if self._landmarker is not None:
            return True
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
            if not MODEL_PATH.exists():
                MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
                import urllib.request
                tmp = MODEL_PATH.with_suffix(".download")
                with urllib.request.urlopen(MODEL_URL, timeout=60) as r, open(tmp, "wb") as out:
                    while True:
                        chunk = r.read(8192)
                        if not chunk:
                            break
                        out.write(chunk)
                tmp.replace(MODEL_PATH)
            self._landmarker = mp_vision.HandLandmarker.create_from_model_path(str(MODEL_PATH))
            return True
        except Exception:
            self._landmarker = None
            return False

    def run(self):
        while not self._stop.wait(0.2):
            with self._lock:
                data = self._latest
                self._latest = None
            if not data:
                continue
            if not self._ensure_landmarker():
                continue
            try:
                import mediapipe as mp
                from mediapipe.tasks.python import vision as mp_vision
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=_jpeg_to_rgb(data))
                if img is None:
                    continue
                res = self._landmarker.detect(img)
                hands = res.hand_landmarks or []
                if not hands:
                    self.hand_visible = False
                    continue
                lm = hands[0]
                self.hand_visible = True
                # pinch: thumb tip (4) ↔ index tip (8)
                dx = lm[4].x - lm[8].x
                dy = lm[4].y - lm[8].y
                dist = (dx * dx + dy * dy) ** 0.5          # ~0.03 closed … ~0.35 open
                self.pinch_norm = max(0.0, min(1.0, (dist - 0.03) / 0.30))
                # palm centroid: middle finger MCP (9)
                self.palm_x = max(0.0, min(1.0, lm[9].x))
                self.palm_y = max(0.0, min(1.0, lm[9].y))
            except Exception:
                continue


def _jpeg_to_rgb(data: bytes):
    """JPEG bytes → numpy RGB array (H, W, 3)."""
    import numpy as np
    from PIL import Image
    import io as _io
    try:
        img = Image.open(_io.BytesIO(data)).convert("RGB")
        return np.asarray(img)
    except Exception:
        return None


class PhoneCameraWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rahul AI — Phone Camera Hologram")
        self.setWindowFlag(Qt.WindowType.Tool, False)
        self.resize(720, 980)
        self._image: QImage | None = None
        self._zoom = 1.0
        self._target_zoom = 1.0
        self._pan_x = 0.0      # -1..1
        self._pan_y = 0.0
        self._hologram = True
        self._frames = 0
        self._fps = 0
        self._last_fps_t = time.time()
        self._last_frame_t = 0.0

        self._gestures = _GestureThread()
        self._gestures.start()

        self._status = QLabel("waiting for camera…")
        self._status.setStyleSheet("color: rgba(34,211,238,0.85); background: transparent; font-size: 11px;")
        self._view = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._view.setMinimumSize(320, 420)

        btn_row = QHBoxLayout()
        self._btn_holo = QPushButton("Hologram: ON")
        self._btn_zoom_in = QPushButton("Zoom +")
        self._btn_zoom_out = QPushButton("Zoom −")
        self._btn_reset = QPushButton("Reset")
        self._btn_stop = QPushButton("Stop")
        for b in (self._btn_holo, self._btn_zoom_in, self._btn_zoom_out, self._btn_reset, self._btn_stop):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { background: rgba(34,211,238,0.10); color: #a5f3fc; border: 1px solid rgba(34,211,238,0.35);"
                " border-radius: 8px; padding: 6px 12px; font-size: 11px; font-weight: bold; }"
                "QPushButton:hover { background: rgba(34,211,238,0.22); }"
            )
            btn_row.addWidget(b)
        self._btn_holo.clicked.connect(self._toggle_holo)
        self._btn_zoom_in.clicked.connect(lambda: self._nudge_zoom(0.25))
        self._btn_zoom_out.clicked.connect(lambda: self._nudge_zoom(-0.25))
        self._btn_reset.clicked.connect(self._reset_view)
        self._btn_stop.clicked.connect(self.close)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)
        lay.addWidget(self._view, 1)
        lay.addLayout(btn_row)
        lay.addWidget(self._status)

        self._render_timer = QTimer(self)
        self._render_timer.timeout.connect(self._tick)
        self._render_timer.start(66)  # ~15 fps UI

    # ── slots ─────────────────────────────────────────────────────────
    def on_frame(self, data: bytes) -> None:
        self._last_frame_t = time.time()
        img = QImage.fromData(data, "JPEG")
        if not img.isNull():
            self._image = img
            self._frames += 1
            try:
                self._gestures.feed(data)
            except Exception:
                pass

    def _tick(self) -> None:
        now = time.time()
        if now - self._last_fps_t >= 1.0:
            self._fps = self._frames
            self._frames = 0
            self._last_fps_t = now
        self._apply_gestures()
        self._render()
        stale = " · NO SIGNAL" if now - self._last_frame_t > 2.5 and self._last_frame_t else ""
        hand = "hand ✓" if self._gestures.hand_visible else "no hand"
        self._status.setText(
            f"fps {self._fps} · zoom {self._zoom:.2f}x · {hand} · pinch {self._gestures.pinch_norm:.2f}"
            f" · hologram {'ON' if self._hologram else 'OFF'}{stale}"
        )

    def _apply_gestures(self) -> None:
        g = self._gestures
        if not g.hand_visible:
            return
        # pinch distance → target zoom (1.0 closed-ish … 3.5 open)
        self._target_zoom = 1.0 + g.pinch_norm * 2.5
        # open palm (pinch relaxed) pans the view toward the palm position
        if g.pinch_norm > 0.6:
            self._pan_x = (g.palm_x - 0.5) * 1.2
            self._pan_y = (0.5 - g.palm_y) * 1.2
        # smooth zoom
        self._zoom += (self._target_zoom - self._zoom) * 0.25

    def _nudge_zoom(self, delta: float) -> None:
        self._target_zoom = max(1.0, min(4.0, self._target_zoom + delta))
        self._zoom = max(1.0, min(4.0, self._zoom + delta))

    def _reset_view(self) -> None:
        self._target_zoom = self._zoom = 1.0
        self._pan_x = self._pan_y = 0.0

    def _toggle_holo(self) -> None:
        self._hologram = not self._hologram
        self._btn_holo.setText(f"Hologram: {'ON' if self._hologram else 'OFF'}")

    # ── painting ──────────────────────────────────────────────────────
    def _render(self) -> None:
        if self._image is None:
            self._view.setText("waiting for the phone camera stream…")
            return
        cw, ch = self._view.width(), self._view.height()
        if cw <= 0 or ch <= 0:
            return
        canvas = QImage(cw, ch, QImage.Format.Format_ARGB32_Premultiplied)
        canvas.fill(_BG)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # base rect (contain)
        iw, ih = self._image.width(), self._image.height()
        scale = min(cw / iw, ch / ih)
        bw, bh = int(iw * scale), int(ih * scale)
        bx, by = (cw - bw) // 2, (ch - bh) // 2

        # zoom + pan transform
        zw, zh = int(bw * self._zoom), int(bh * self._zoom)
        max_off_x = max(0, (zw - bw) // 2)
        max_off_y = max(0, (zh - bh) // 2)
        zx = bx - max_off_x - int(self._pan_x * max_off_x)
        zy = by - max_off_y - int(self._pan_y * max_off_y)
        painter.drawImage(int(zx), int(zy), int(zw), int(zh), self._image, 0, 0, iw, ih)

        if self._hologram:
            # cyan tint
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            overlay = QColor(_ACCENT)
            overlay.setAlpha(26)
            painter.fillRect(zx, zy, zw, zh, overlay)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            # scanlines
            pen = QPen(QColor(0, 0, 0, 60))
            pen.setWidth(1)
            painter.setPen(pen)
            for y in range(zy, zy + zh, 4):
                painter.drawLine(zx, y, zx + zw, y)
            # glow frame
            pen = QPen(QColor(_ACCENT))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(zx, zy, zw, zh)
            # HUD corner brackets
            pen.setWidth(3)
            painter.setPen(pen)
            L = 26
            for cx, cy, dx, dy in ((zx, zy, 1, 1), (zx + zw, zy, -1, 1), (zx, zy + zh, 1, -1), (zx + zw, zy + zh, -1, -1)):
                painter.drawLine(cx, cy, cx + dx * L, cy)
                painter.drawLine(cx, cy, cx, cy + dy * L)
            # label
            painter.setPen(QColor(_ACCENT))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(zx + 8, zy + 18, f"RAHUL AI · HOLOGRAM · {self._zoom:.1f}x")

        painter.end()
        from PyQt6.QtGui import QPixmap
        self._view.setPixmap(QPixmap.fromImage(canvas))

    def closeEvent(self, event):
        try:
            self._gestures.stop()
        except Exception:
            pass
        try:
            _close_stream()
        except Exception:
            pass
        super().closeEvent(event)


# ── module-level window management (Qt main thread via bridge) ────────────

_window: PhoneCameraWindow | None = None
_device_name = ""


def _open_window(device: str = ""):
    global _window, _device_name
    _device_name = device or _device_name
    if _window is None:
        _window = PhoneCameraWindow()
    _window.show()
    _window.raise_()
    _window.activateWindow()


def _close_window():
    global _window
    if _window is not None:
        try:
            _window.close()
        except Exception:
            pass
        _window = None


def _on_frame_main(data: bytes):
    if _window is None:
        _open_window()
    if _window is not None:
        _window.on_frame(data)


bridge.open_requested.connect(lambda d="": _open_window(d))
bridge.close_requested.connect(_close_window)
bridge.frame_ready.connect(_on_frame_main)


# ── public API (called from gateway thread / tools) ───────────────────────

def push_frame(device_id: str, jpeg_b64: str) -> None:
    try:
        data = base64.b64decode(jpeg_b64)
        bridge.frame_ready.emit(data)   # queued → Qt main thread
    except Exception:
        pass


def open_viewer(device: str = "") -> None:
    bridge.open_requested.emit(device)


def close_viewer() -> None:
    bridge.close_requested.emit()


def _close_stream() -> None:
    """Window closed by user → tell the phone to stop streaming."""
    try:
        from actions.rahul_connect import connect_execute
        connect_execute({"action": "stop_camera_stream"})
    except Exception:
        pass


# ── tool entry ─────────────────────────────────────────────────────────────

def phone_camera(parameters: dict, player=None, session_memory=None, speak=None) -> str:
    params = dict(parameters or {})
    action = str(params.get("action") or "start").lower()

    if action in ("start", "mirror", "show", "open"):
        target = params.get("target") or params.get("device") or ""
        from actions.rahul_connect import connect_execute
        res = connect_execute({"action": "start_camera_stream", **({"target": target} if target else {})})
        open_viewer(str(target or "phone"))
        if '"success": true' in res.replace(" ", "").lower() or '"success":true' in res.replace(" ", "").lower():
            return ("Phone camera mirror started. The holographic viewer is open — "
                    "show a hand to the phone camera: pinch to zoom, open palm to move.")
        return ("Camera request sent, but the phone did not confirm streaming. "
                "Make sure the latest Rahul Connect app is installed and the camera permission is granted.")

    if action in ("stop", "close"):
        from actions.rahul_connect import connect_execute
        try:
            connect_execute({"action": "stop_camera_stream"})
        except Exception:
            pass
        close_viewer()
        return "Phone camera mirror stopped."

    if action in ("hologram_on", "hologram"):
        if _window is not None:
            _window._hologram = True
            _window._btn_holo.setText("Hologram: ON")
            return "Holographic mode on."
        return "Open the phone camera mirror first."

    if action == "hologram_off":
        if _window is not None:
            _window._hologram = False
            _window._btn_holo.setText("Hologram: OFF")
            return "Holographic mode off — plain camera view."
        return "Open the phone camera mirror first."

    if action == "status":
        if _window is None:
            return "Phone camera mirror is not running."
        return (f"Mirror running · zoom {_window._zoom:.2f}x · hologram "
                f"{'ON' if _window._hologram else 'OFF'} · hand "
                f"{'detected' if _window._gestures.hand_visible else 'not visible'}.")

    return "Unknown action. Use: start | stop | hologram_on | hologram_off | status."


PLUGIN = {
    "name": "phone_camera",
    "description": "Mirror the connected phone's camera as a hologram with gesture zoom/move control.",
}
