#!/usr/bin/env bash
# Build an installable Arch Linux package without needing a Git remote.
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd -- "$here/../.." && pwd)"

pkgname="$(sed -n 's/^pkgname=//p' "$here/PKGBUILD")"
pkgver="$(sed -n 's/^pkgver=//p' "$here/PKGBUILD")"
tarball="$here/$pkgname-$pkgver.tar.gz"

if [[ -z "$pkgname" || -z "$pkgver" ]]; then
    echo "Could not read pkgname/pkgver from $here/PKGBUILD" >&2
    exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
staging="$work/$pkgname-$pkgver"
install -d "$staging"

cp -a "$repo/desktop/whatisplaying" "$staging/"
find "$staging" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$staging" -name '*.pyc' -delete

install -m755 "$repo/packaging/linux/whatisplaying-launcher" \
    "$staging/whatisplaying-launcher"
install -m644 "$repo/packaging/linux/whatisplaying.desktop" \
    "$staging/whatisplaying.desktop"
install -m644 "$repo/desktop/whatisplaying/assets/whatisplaying.svg" \
    "$staging/whatisplaying.svg"

tar -C "$work" -czf "$tarball" "$pkgname-$pkgver"

echo "Source tarball: $tarball"
cd "$here"
makepkg --force --noconfirm

pkgfile="$(find "$here" -maxdepth 1 -type f -name "$pkgname-$pkgver-*.pkg.tar.*" \
    -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d' ' -f2-)"
if [[ -z "$pkgfile" ]]; then
    echo "Package was not created." >&2
    exit 1
fi

echo
echo "Built: $pkgfile"
echo "Install with:"
echo "  sudo pacman -U \"$pkgfile\""
if [[ "${1:-}" == "--install" ]]; then
    sudo pacman -U "$pkgfile"
fi
