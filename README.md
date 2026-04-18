# ScreenshotStretchTo16by9

A lightweight Windows system-tray application that monitors the clipboard for new screenshots and **automatically stretches them to 16:9 aspect ratio**. Runs silently in the background — just take a screenshot and paste it already in 16:9.

## How It Works

1. Launch the app — a tray icon appears in your system tray
2. Take a screenshot (Win+Shift+S, Snipping Tool, Print Screen, etc.)
3. The app detects the image on the clipboard
4. If it's not already 16:9, it stretches it to 16:9 and puts it back on the clipboard
5. Paste (Ctrl+V) anywhere — the image is now 16:9

Images that are already 16:9 are left untouched.

## Requirements

- **Windows** 10 or 11
- **Python** 3.12+

## Installation

```bash
git clone <repo-url>
cd ScreenshotStretchTo16by9
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

The app starts as a system-tray icon. Right-click the icon and select **Quit** to stop.

No configuration needed — it works out of the box.

## Dependencies

| Package | Purpose |
|---------|---------|
| `Pillow` | Image processing and resizing |
| `pywin32` | Windows clipboard access (CF_DIB) |
| `pystray` | System tray icon |

## Architecture

Single-file application (`main.py`) with two threads:

- **Main thread** — runs the pystray event loop (tray icon)
- **Daemon thread** — polls the clipboard every 250ms, detects new images via MD5 fingerprinting, stretches non-16:9 images using Lanczos resampling, and writes the result back as Windows DIB (24bpp RGB or 32bpp BGRA with alpha support)

A debounce timer (600ms) prevents the app from re-processing its own clipboard writes.
