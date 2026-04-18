# ScreenshotStretchTo16by9

A lightweight Windows system-tray application that monitors the clipboard for new screenshots and **automatically stretches them to a 16:9 aspect ratio**. Runs silently in the background — take a screenshot and paste it already in 16:9.

## How It Works

1. Launch the app — a tray icon appears in your system tray
2. Take a screenshot (Win+Shift+S, Snipping Tool, Print Screen, etc.)
3. The app detects the image on the clipboard
4. If it's not already 16:9, it stretches it to 16:9 and puts it back on the clipboard
5. Paste (Ctrl+V) anywhere — the image is now 16:9

Images that are already 16:9 are left untouched.

## Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.12+ | Runtime language |
| **Pillow** | >=10.0 | Image processing and Lanczos resampling |
| **pywin32** | >=306 | Windows clipboard access (CF_DIB format) |
| **pystray** | >=0.19 | System tray icon and menu |

**Platform:** Windows only (10/11)

## Architecture

Single-file application (`main.py`) with a two-thread model:

```
┌─────────────────────────────┐
│        Main Thread          │
│   pystray event loop        │
│   (system tray icon)        │
│                             │
│   ┌─── Tray Icon ───┐      │
│   │ Stretch16by9     │      │
│   │ └─ Quit          │      │
│   └─────────────────┘      │
└──────────┬──────────────────┘
           │
           │ spawns daemon thread
           ▼
┌─────────────────────────────┐
│     Monitor Thread          │
│                             │
│  poll clipboard (250ms)     │
│       │                     │
│       ▼                     │
│  new image detected?        │
│       │                     │
│    ┌──┴──┐                  │
│    │yes  │ no → sleep       │
│    └──┬──┘                  │
│       ▼                     │
│  already 16:9?              │
│    ┌──┴──┐                  │
│    │no   │ yes → cache hash │
│    └──┬──┘                  │
│       ▼                     │
│  stretch → write CF_DIB     │
│  debounce 600ms             │
└─────────────────────────────┘
```

### Components

| Component | Responsibility |
|-----------|---------------|
| `get_clipboard_image()` | Read image from clipboard via `PIL.ImageGrab.grabclipboard()` |
| `set_clipboard_image(img)` | Write PIL Image back as CF_DIB (24bpp RGB or 32bpp BGRA) |
| `image_hash(img)` | MD5 fingerprint of downscaled 64x64 bytes for change detection |
| `monitor_loop()` | Background thread: poll → detect → stretch → write-back loop |
| `create_icon_image()` | Generate tray icon programmatically (no external assets) |
| `on_quit()` | Graceful shutdown handler |

### Threading Model

- **Main thread** runs the pystray event loop (tray icon)
- **Daemon thread** runs `monitor_loop()`
- Shared state (`last_hash`) protected by `threading.Lock()`
- Debounce timer (`DEBOUNCE_SECONDS` = 0.6s) prevents re-processing own output

## Getting Started

### Prerequisites

- Windows 10 or 11
- Python 3.12+

### Installation

```bash
git clone https://github.com/Ian-bug/ScreenshotStretchTo16by9.git
cd ScreenshotStretchTo16by9
pip install -r requirements.txt
```

### Usage

```bash
python main.py
```

The app starts as a system-tray icon. Right-click the icon and select **Quit** to stop.

No configuration needed — works out of the box.

## Project Structure

```
ScreenshotStretchTo16by9/
├── main.py            # Entry point — entire application
├── requirements.txt   # Python dependencies
├── AGENTS.md          # Development guidelines & architecture docs
├── LICENSE            # MIT License
├── README.md          # This file
└── .gitignore         # Git ignore rules
```

## Key Features

- **Automatic detection** — polls clipboard every 250ms for new screenshots
- **Smart stretching** — resizes to 16:9 using high-quality Lanczos resampling
- **Alpha channel support** — preserves transparency (RGBA) from Snipping Tool screenshots via 32bpp DIB
- **Change detection** — MD5 fingerprinting avoids re-processing unchanged images
- **Debounce protection** — 600ms cooldown after writing prevents infinite loops
- **Zero config** — no arguments, settings files, or setup required
- **Graceful shutdown** — right-click tray icon → Quit; daemon thread exits cleanly

## Development Workflow

### Running

```bash
python main.py
```

### Linting / Type Checking

```bash
pip install ruff
ruff check main.py

pip install mypy
mypy main.py
```

> **Note:** The codebase uses `try/except` guards around optional Windows-only imports (`win32clipboard`, `pystray`). These produce static-analysis false positives that are expected and should not be removed.

### Testing

No test suite exists yet. When creating tests:

```bash
pip install pytest pytest-mock
python -m pytest tests/
```

Tests must mock `win32clipboard` and `ImageGrab` since this is a Windows-clipboard tool.

## Coding Standards

### Style

- **Indent:** 4 spaces (no tabs)
- **Line length:** prefer under 120 characters
- **Naming:** `snake_case` for functions/variables, `UPPER_SNAKE_CASE` for constants, `PascalCase` for classes
- **No comments** unless asked — keep code self-documenting

### Imports

Standard library first, then third-party, then local. Windows-only imports wrapped in `try/except ImportError` with fallback to `None`.

### Error Handling

- Never use bare `except:` — always catch specific types
- Always log caught exceptions (never swallow silently)
- Clipboard operations must have fallback `CloseClipboard()` in finally/except paths
- Monitor loop body fully wrapped in try/except so the daemon thread never crashes

### Struct Packing (DIB)

The most error-prone part of this codebase. Rules:
- BITMAPINFOHEADER: `<IiiHHIIiiII` = 11 fields = 40 bytes
- Pixel rows are bottom-up (iterate `range(h-1, -1, -1)`)
- 24bpp rows padded to 4-byte boundaries: `stride = (w * 3 + 3) & ~3`
- Always little-endian (`<`)
- Verify `len(hdr)` equals `biSize` (40) after packing

## Contributing

Contributions are welcome! Key guidelines:

1. Follow the coding standards outlined above and in [AGENTS.md](AGENTS.md)
2. Windows-only — do not attempt cross-platform support
3. Maintain the threading safety patterns (lock on shared state, monotonic timing, debounce)
4. Test clipboard operations carefully — a hung clipboard can lock the entire OS session
5. Preserve alpha channel handling for RGBA images

## License

This project is licensed under the [MIT License](LICENSE).

Copyright (c) 2026 Ian-bug
