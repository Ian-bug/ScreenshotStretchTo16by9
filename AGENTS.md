# AGENTS.md — ScreenshotStretchTo16by9

## Project Overview

Lightweight Windows system-tray application that monitors the clipboard for new screenshots and automatically stretches them to a **16:9 aspect ratio**, replacing the clipboard content with the result. Runs silently in the background; triggers instantly on screenshot capture.

**Language:** Python 3.12+ | **Platform:** Windows only | **Entry point:** `main.py`

---

## Commands

### Run

```bash
python main.py
```

Launches the tray app. No arguments or config files. To stop: right-click tray icon → Quit.

### Install Dependencies

```bash
pip install -r requirements.txt
```

Dependencies: `Pillow>=10.0`, `pywin32>=306`, `pystray>=0.19`

### Lint / Type Check

No formal linter or type checker is configured. If adding one:

```bash
# Ruff (recommended for this project — fast, Python-native)
pip install ruff
ruff check main.py

# Or mypy for strict type checking
pip install mypy
mypy main.py
```

**Note:** The codebase intentionally uses `try/except` guards around optional imports (`win32clipboard`, `pystray`) which produce static-analysis false positives. These are expected and should not be "fixed" by removing the guards.

### Test

No test suite exists yet. When creating tests:

```bash
# Run all tests (once they exist)
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_clipboard.py

# Run a single test function
python -m pytest tests/test_clipboard.py::test_stretch_to_16by9 -v
```

Recommended test framework: `pytest` + `pytest-mock`. Tests must mock `win32clipboard` and `ImageGrab` since this is a Windows-clipboard tool.

---

## Architecture

Single-file application (`main.py`). Structure:

| Component | Responsibility |
|-----------|---------------|
| `get_clipboard_image()` | Read image from clipboard via `PIL.ImageGrab.grabclipboard()` |
| `set_clipboard_image(img)` | Write PIL Image back as CF_DIB (raw bitmap) |
| `dib_encode()` / inline | Convert PIL Image → Windows DIB byte string (BITMAPINFOHEADER + pixel data) |
| `image_hash(img)` | MD5 of downscaled 64x64 bytes for change detection |
| `monitor_loop()` | Background thread: poll clipboard → detect new image → stretch if not 16:9 → write back |
| `create_icon_image()` | Generate tray icon programmatically (no external assets) |
| `on_quit()` | Graceful shutdown handler |

**Threading model:** Main thread runs the pystray event loop (tray icon). A daemon thread runs `monitor_loop()`. Shared state (`last_hash`) protected by `threading.Lock()`.

**Clipboard format:** Reads any image format via PIL. Writes as **CF_DIB only** (24bpp RGB or 32bpp BGRA). This is critical — Snipping Tool, browsers, and most apps accept DIB.

---

## Code Style Guidelines

### Imports

- Standard library imports first, then third-party, then local
- Optional/Windows-only imports wrapped in `try/except ImportError` with fallback to `None`
- Never use `from module import *`
- Import inside functions only when needed for lazy loading (e.g., `hashlib` in `image_hash`)

```python
import logging
import struct
import sys
import threading
import time
from PIL import Image, ImageDraw, ImageGrab

try:
    import win32clipboard
except ImportError:
    win32clipboard = None
```

### Formatting

- **Indent:** 4 spaces (no tabs)
- **Line length:** no strict limit, but prefer under 120 chars
- **Blank lines:** 2 between top-level definitions, 1 between methods in a class
- **Trailing whitespace:** avoid
- **No comments in code** unless asked — keep code self-documenting

### Naming Conventions

| Category | Style | Example |
|----------|-------|---------|
| Functions/modules | `snake_case` | `get_clipboard_image()`, `monitor_loop()` |
| Variables | `snake_case` | `last_hash`, `pixel_data` |
| Constants | `UPPER_SNAKE_CASE` | `TARGET_RATIO`, `POLL_INTERVAL`, `DEBOUNCE_SECONDS` |
| Classes | `PascalCase` | (none currently) |
| Private/internal | leading underscore | `_internal_helper()` |

### Types

- No type annotations required currently (small codebase, no mypy config)
- If adding types, use `from __future__ import annotations` and modern syntax (`Image | None`)
- Always validate types at runtime when reading from external sources (clipboard, filesystem)

### Error Handling Rules

1. **Never use bare `except:`** — always catch `Exception` or a specific type
2. **Always log caught exceptions** — never swallow silently in production paths:
   ```python
   except Exception as e:
       log.error("Operation failed: %s", e)
   ```
3. **Clipboard operations** must always have a fallback `CloseClipboard()` in the finally/except path — Windows clipboard lock can otherwise hang the entire OS session
4. **Optional-import guards** (`win32clipboard is None`, `Icon is None`) are checked once at startup in `main()` — fail fast with a clear error message
5. **Monitor loop** must never crash — wrap the entire body in try/except so the daemon thread stays alive
6. Use `log.warning()` for recoverable issues, `log.error()` for failures, `log.info()` for normal operations

### Threading

- Shared mutable state (`last_hash`) **must** be protected by `state_lock` (a `threading.Lock()`)
- Use `time.monotonic()` for all timing comparisons (not `time.time()`)
- Monitor loop uses a **debounce pattern**: after writing to clipboard, skip processing for `DEBOUNCE_SECONDS` (0.6s) to avoid re-processing our own output
- The monitor thread is a **daemon thread** — it will be killed when the main (tray) thread exits

### Struct Packing (DIB / Binary Formats)

This is the #1 source of bugs in this codebase. Follow these rules religiously:

- **Always count format characters and values manually before writing a `struct.pack()` call**
- BITMAPINFOHEADER (40-byte): `<IiiHHIIiiII` = **11 fields** = biSize(4), biWidth(4), biHeight(4), biPlanes(2), biBitCount(2), biCompression(4), biSizeImage(4), biXPelsPerMeter(4), biYPelsPerMeter(4), biClrUsed(4), biClrImportant(4)
- Pixel rows are **bottom-up** (flip Y): iterate `range(h-1, -1, -1)`
- 24bpp rows are **padded to 4-byte boundaries**: `stride = (w * 3 + 3) & ~3`
- Endianness: always little-endian (`<`)
- After packing, verify: `len(hdr)` should equal `biSize` value (40)

### Logging

- Use the `log` instance (not `logging.getLogger` inline or `print()`)
- Logger name: `"stretch16by9"`
- Format: `%(asctime)s [%(levelname)s] %(message)s`
- Level: `INFO` by default
- Log every meaningful event: image detected, stretch applied, skipped (already 16:9), errors, shutdown

---

## Critical Gotchas

1. **DIB struct mismatch = silent failure** — if format string doesn't match value count, `struct.pack` raises `struct.error`. Since this is inside a try/except, it logs an error but the clipboard write simply doesn't happen. **Always verify field counts.**

2. **`ImageGrab.grabclipboard()` return types** — returns `PIL.Image`, `str` (filepath), `list[str]` (file list), or `None`. Always check `isinstance(result, Image.Image)` before using.

3. **Clipboard contention** — our own writes trigger re-detection. The debounce timer (`skip_until`) prevents infinite loops, but the duration must be long enough for the clipboard to settle.

4. **Alpha channel handling** — screenshots from Snipping Tool may have RGBA (rounded corners). Detect `img.mode == "RGBA"` and write 32bpp DIB to preserve transparency. Don't blindly `.convert("RGB")`.

5. **`hash()` is not deterministic across processes** — use `hashlib.md5` for image fingerprinting, never Python's built-in `hash()`.

6. **Windows-only** — `win32clipboard` and `pystray` (Win32 backend) have no Linux/macOS equivalent. Do not attempt cross-platform support.

7. **pystray import may fail in some environments** — even when installed, the `_util.win32` sub-module can cause import errors. Only import `Icon, Menu, MenuItem` from `pystray` top-level.
