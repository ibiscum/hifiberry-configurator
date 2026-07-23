#!/bin/bash
set -e

cd "$(dirname "$0")"

# Extract version from changelog as single source of truth
CHANGELOG_VERSION=$(head -1 debian/changelog | sed 's/.*(\([^)]*\)).*/\1/')
echo "Using version from changelog: $CHANGELOG_VERSION"

# Check if DIST is set by environment variable
if [ -n "$DIST" ]; then
    # Common typo guard: Debian "trixie" is frequently mistyped as "trixy".
    if [ "$DIST" = "trixy" ]; then
        echo "DIST=trixy is not a valid Debian suite; using DIST=trixie instead"
        DIST="trixie"
    fi
    echo "Using distribution from DIST environment variable: $DIST"
    DIST_ARG="--dist=$DIST"
else
    echo "No DIST environment variable set, using sbuild default"
    DIST_ARG=""
fi

sbuild \
    --chroot-mode=unshare \
    --enable-network \
    "$DIST_ARG" \
    --verbose
