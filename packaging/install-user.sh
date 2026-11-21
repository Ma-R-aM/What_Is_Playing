#!/usr/bin/env bash
# Install WhatIsPlaying for the current user, without root.
set -euo pipefail

repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
prefix="${PREFIX:-$HOME/.local}"
data_dir="${XDG_DATA_HOME:-$prefix/share}"
bin_dir="$prefix/bin"
lib_dir="$prefix/lib/whatisplaying"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required." >&2
    exit 1
fi
if ! python3 -c 'import PySide6, PySide6.QtSvg' >/dev/null 2>&1; then
    echo "PySide6 and Qt 6 SVG support are required." >&2
    echo "On Arch Linux: sudo pacman -S pyside6 qt6-svg" >&2
    exit 1
fi
if ! python3 -c 'import dbus' >/dev/null 2>&1; then
    echo "python-dbus is required to read track metadata from MPRIS players." >&2
    echo "On Arch Linux: sudo pacman -S python-dbus" >&2
    echo "On Debian/Ubuntu: sudo apt install python3-dbus" >&2
    exit 1
fi

echo "Installing WhatIsPlaying into $prefix"
install -d "$bin_dir" "$lib_dir" "$data_dir/applications" \
    "$data_dir/icons/hicolor/scalable/apps"

rm -rf "$lib_dir/whatisplaying"
cp -a "$repo/desktop/whatisplaying" "$lib_dir/"
find "$lib_dir" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$lib_dir" -name '*.pyc' -delete

install -Dm755 "$repo/packaging/linux/whatisplaying-launcher" \
    "$bin_dir/whatisplaying"
install -Dm644 "$repo/desktop/whatisplaying/assets/whatisplaying.svg" \
    "$data_dir/icons/hicolor/scalable/apps/whatisplaying.svg"

# Point the menu entry at the absolute launcher path (handles ~/.local/bin not
# being on PATH, and paths containing spaces).
desktop_tmp="$(mktemp)"
sed "s|^Exec=.*|Exec=\"$bin_dir/whatisplaying\"|" \
    "$repo/packaging/linux/whatisplaying.desktop" > "$desktop_tmp"
install -Dm644 "$desktop_tmp" "$data_dir/applications/whatisplaying.desktop"
rm -f "$desktop_tmp"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$data_dir/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$data_dir/icons/hicolor" >/dev/null 2>&1 || true
fi

echo
echo "Installed."
echo "  Launch from your application menu, or run:"
echo "    $bin_dir/whatisplaying"
case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *) echo "  Note: $bin_dir is not on PATH; use the full path above or add it." ;;
esac
echo
echo "For a system-wide Arch package instead, run:"
echo "  ./packaging/arch/build-package.sh"
