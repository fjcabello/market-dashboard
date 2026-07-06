#!/bin/bash
# Ejecutado por launchd (ver ~/Library/LaunchAgents/com.fjcabello.youtube-transcripts.plist).
# Descarga transcripts nuevos y los sube al repo si hay cambios.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

./venv/bin/python3 download_transcripts.py

git add transcripts/
if ! git diff --staged --quiet -- transcripts/; then
    git commit -m "transcripts: update $(date -u +%Y-%m-%d)"
    git push
fi
