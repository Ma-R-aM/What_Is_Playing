#!/usr/bin/env bash
# Remove a user installation created by install-user.sh.
set -euo pipefail

prefix="${PREFIX:-$HOME/.local}"
data_dir="${XDG_DATA_HOME:-$prefix/share}"

rm -f "$prefix/bin/whatisplaying"
rm -rf "$prefix/lib/whatisplaying"
rm -f "$data_dir/applications/whatisplaying.desktop"
rm -f "$data_dir/icons/hicolor/scalable/apps/whatisplaying.svg"
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/whatisplaying.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$data_dir/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$data_dir/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Removed the user installation."
echo "Settings and the Discord token were left in:"
echo "  ${XDG_CONFIG_HOME:-$HOME/.config}/whatisplaying/config.json"
echo "Delete that file manually if you also want to erase the saved token."
