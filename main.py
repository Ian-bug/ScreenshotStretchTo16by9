import logging
import struct
import sys
import threading
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageGrab

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("stretch16by9")

try:
    import win32clipboard
except ImportError:
    win32clipboard = None

try:
    from pystray import Icon, Menu, MenuItem
except ImportError:
    Icon = None

TARGET_RATIO = 16 / 9
POLL_INTERVAL = 0.25
DEBOUNCE_SECONDS = 0.6
LANCZOS = getattr(Image.Resampling, "LANCZOS", getattr(Image, "LANCZOS", 1))

state_lock = threading.Lock()
last_hash = None
running = True


def get_clipboard_image():
    try:
        result = ImageGrab.grabclipboard()
        if isinstance(result, Image.Image):
            return result
        return None
    except Exception as e:
        log.warning("Failed to read clipboard: %s", e)
        return None


def set_clipboard_image(img):
    if img.mode == "RGBA":
        raw = img.tobytes("raw", "BGRA")
        bpp = 32
    else:
        rgb = img.convert("RGB")
        raw = rgb.tobytes("raw", "BGR")
        bpp = 24
    w, h = img.size
    if bpp == 24:
        stride = (w * 3 + 3) & ~3
        pad = stride - w * 3
        rows = []
        for y in range(h - 1, -1, -1):
            off = y * w * 3
            rows.append(raw[off:off + w * 3] + b"\x00" * pad)
        pixel_data = b"".join(rows)
    else:
        stride = w * 4
        rows = []
        for y in range(h - 1, -1, -1):
            off = y * stride
            rows.append(raw[off:off + stride])
        pixel_data = b"".join(rows)

    hdr = struct.pack("<IiiHHIIiiII",
                      40,
                      w,
                      h,
                      1,
                      bpp,
                      0,
                      len(pixel_data),
                      0,
                      0,
                      0,
                      0)
    dib = hdr + pixel_data
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib)
        win32clipboard.CloseClipboard()
    except Exception as e:
        log.error("Failed to write clipboard: %s", e)
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def image_hash(img):
    import hashlib
    data = img.resize((64, 64), LANCZOS).tobytes()
    return hashlib.md5(data).hexdigest()


def monitor_loop():
    global last_hash
    skip_until = 0.0
    while running:
        now = time.monotonic()
        if now < skip_until:
            time.sleep(POLL_INTERVAL)
            continue
        try:
            img = get_clipboard_image()
            if img is None:
                time.sleep(POLL_INTERVAL)
                continue
            h = image_hash(img)
            with state_lock:
                cached = last_hash
            if h == cached:
                time.sleep(POLL_INTERVAL)
                continue
            w, h_dim = img.size
            ratio = w / h_dim
            log.info("Detected image: %dx%d (ratio %.3f)", w, h_dim, ratio)
            if abs(ratio - TARGET_RATIO) > 0.02:
                new_h = int(w / TARGET_RATIO)
                stretched = img.resize((w, new_h), LANCZOS)
                set_clipboard_image(stretched)
                with state_lock:
                    last_hash = image_hash(stretched)
                skip_until = time.monotonic() + DEBOUNCE_SECONDS
                log.info("Stretched to %dx%d (16:9)", w, new_h)
            else:
                with state_lock:
                    last_hash = h
                log.info("Already 16:9, skipped")
        except Exception as e:
            log.error("Monitor loop error: %s", e, exc_info=True)
        time.sleep(POLL_INTERVAL)


def create_icon_image():
    icon_file = Path(__file__).parent / "assets" / "icon.ico"
    if icon_file.exists():
        return Image.open(icon_file).convert("RGBA")
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([8, 14, 56, 50], fill="#4A90D9", outline="#2E6CB5", width=2)
    draw.rectangle([12, 18, 52, 46], fill="#87CEEB")
    draw.line([20, 30, 32, 42, 44, 26], fill="white", width=3)
    return img


def on_quit(icon, item):
    global running
    log.info("Shutting down...")
    running = False
    icon.stop()


def main():
    if win32clipboard is None:
        log.error("pywin32 required. Run: pip install pywin32")
        return
    if Icon is None:
        log.error("pystray required. Run: pip install pystray")
        return

    log.info("Starting Screenshot Stretch to 16:9...")
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()

    menu = Menu(MenuItem("Quit", on_quit))
    icon = Icon("Stretch16by9", create_icon_image(), "Screenshot Stretch to 16:9", menu)
    icon.run()


if __name__ == "__main__":
    main()
