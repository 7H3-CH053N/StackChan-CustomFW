#!/usr/bin/env bash
# Build the custom StackChan firmware:
#   upstream xiaozhi-esp32 (pinned commit) + xiaozhi-esp32.patch + cyan eyes.
#
# Requires ESP-IDF (tested with v6.1) in the current shell:
#   . $HOME/esp/esp-idf/export.sh
#
# Options (environment variables):
#   LANG_CODE  UI/voice-prompt language   (default de-DE, e.g. en-US)
#   WAKE_WORD  esp-sr wake word model     (default wn9_jarvis_tts)
#   WORK       checkout/build directory   (default ./build-work)
set -euo pipefail

UPSTREAM=https://github.com/78/xiaozhi-esp32.git
UPSTREAM_COMMIT=4632dc51f0a5ad26e08542e131e6e48da41e4ff3
LANG_CODE=${LANG_CODE:-de-DE}
WAKE_WORD=${WAKE_WORD:-wn9_jarvis_tts}
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-$HERE/build-work}

if [ ! -d "$WORK/.git" ]; then
    git clone "$UPSTREAM" "$WORK"
    git -C "$WORK" checkout -q "$UPSTREAM_COMMIT"
    git -C "$WORK" apply "$HERE/xiaozhi-esp32.patch"
fi
cd "$WORK"

build() { python ./scripts/build.py m5stack/core-s3 --language "$LANG_CODE" --wake-word "$WAKE_WORD"; }

# The eye GIFs replace the otto-gif emoji set, which only exists after the
# component manager has fetched it, hence the first pass.
GIFS=managed_components/txp666__otto-emoji-gif-component/gifs
[ -d "$GIFS" ] || build
cp "$HERE"/eyes/gifs/*.gif "$GIFS"/
build

echo
echo "Done. Images in $WORK/build:"
echo "  app     0x20000   xiaozhi.bin"
echo "  assets  0xa00000  generated_assets.bin"
