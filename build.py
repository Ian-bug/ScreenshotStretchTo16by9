import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "ScreenshotStretchTo16by9.spec"
ASSETS = ROOT / "assets"

APP_NAME = "ScreenshotStretchTo16by9"
ENTRY_POINT = ROOT / "main.py"
ICON_ICO = ASSETS / "icon.ico"
ICON_PATH = None


def install_pyinstaller():
    try:
        import importlib.util

        if not importlib.util.find_spec("PyInstaller"):
            raise ImportError
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"]
        )


def build():
    install_pyinstaller()

    global ICON_PATH
    if ICON_ICO.exists():
        ICON_PATH = ICON_ICO

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        APP_NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD_DIR),
    ]

    if ICON_PATH and ICON_PATH.exists():
        cmd.extend(["--icon", str(ICON_PATH)])

    hidden_imports = [
        "PIL._tkinter_finder",
        "pystray._util.win32",
        "win32clipboard",
        "win32con",
        "win32api",
    ]
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    cmd.append(str(ENTRY_POINT))

    print(f"Building {APP_NAME}...")
    subprocess.check_call(cmd)

    exe = DIST / f"{APP_NAME}.exe"
    if exe.exists():
        print(f"\nBuild successful: {exe}")
    else:
        print("\nBuild completed but exe not found in dist/")
        sys.exit(1)


def clean():
    import shutil

    for d in [DIST, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Removed {d}")
    if SPEC_FILE.exists():
        SPEC_FILE.unlink()
        print(f"Removed {SPEC_FILE}")
    print("Clean complete.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
    else:
        build()
