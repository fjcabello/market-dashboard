#!/bin/bash
# Ejecutado por launchd (ver ~/Library/LaunchAgents/com.fjcabello.youtube-transcripts.plist).
# Descarga transcripts nuevos y los sube al repo si hay cambios.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

./venv/bin/python3 download_transcripts.py

if ! git diff --quiet -- transcripts/ || ! git diff --cached --quiet -- transcripts/; then
    git add transcripts/
    git diff --staged --quiet || git commit -m "transcripts: update $(date -u +%Y-%m-%d)"
    git push
fi
