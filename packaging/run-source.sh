#!/bin/sh
# Run WhatIsPlaying directly from this checkout without installing it.
set -eu

repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
PYTHONPATH="$repo/desktop${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH
exec python3 -m whatisplaying "$@"
