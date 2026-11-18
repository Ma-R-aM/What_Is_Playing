import sys

try:
    from .app import main
except ImportError as exc:
    text = str(exc)
    if "PySide6" in text or "Qt6Svg" in text:
        print(
            "WhatIsPlaying needs PySide6 (Qt 6) with SVG support.",
            file=sys.stderr,
        )
        if sys.platform == "win32":
            print(
                "On Windows install the dependencies with:\n"
                "  python -m pip install -r packaging/windows/requirements-windows.txt",
                file=sys.stderr,
            )
        else:
            print(
                "On Arch Linux install it with: sudo pacman -S pyside6 qt6-svg",
                file=sys.stderr,
            )
        raise SystemExit(1) from exc
    raise

if __name__ == "__main__":
    raise SystemExit(main())
