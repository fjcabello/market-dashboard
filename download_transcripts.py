#!/usr/bin/env python3
"""
Script diario para descargar transcripts de canales de YouTube.
Ejecutar una vez al día: python3 download_transcripts.py
Los archivos se guardan como YYYY-MM-DD-NombreCanal.txt
"""

import csv
import os
import re
import sys
import logging
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

# ── Configuración ────────────────────────────────────────────────────────────

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR   = os.path.join(BASE_DIR, "transcripts")
CHANNELS_CSV = os.path.join(BASE_DIR, "channels.csv")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_channels(csv_path: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if row.get("name") and row.get("url")]

# Cuántos vídeos recientes revisar por canal en cada ejecución.
# 3 cubre el caso de que no se ejecute el script un día.
VIDEOS_TO_CHECK = 3

PREFERRED_LANGS = ["es", "es-419", "en"]

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(OUTPUT_DIR, "download_transcripts.log")),
    ],
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
# Evita la pantalla de consentimiento GDPR que bloquea el parseo del HTML en la UE.
COOKIES = {"CONSENT": "YES+1", "SOCS": "CAI"}
ATOM_NS = "http://www.w3.org/2005/Atom"
YT_NS   = "http://www.youtube.com/xml/schemas/2015"

# ── Funciones ────────────────────────────────────────────────────────────────

def resolve_channel_id(channel_url: str) -> str | None:
    """Obtiene el channel_id (UC...) a partir de una URL de canal (handle, /c/ o /channel/)."""
    match = re.search(r"/channel/(UC[\w-]{22})", channel_url)
    if match:
        return match.group(1)

    try:
        resp = requests.get(channel_url, headers=HEADERS, cookies=COOKIES, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("  No se pudo resolver channel_id de %s: %s", channel_url, exc)
        return None

    match = re.search(r'"externalId":"(UC[\w-]{22})"', resp.text)
    return match.group(1) if match else None


def get_recent_videos(channel_url: str, n: int) -> list[tuple[str, str]]:
    """Devuelve lista de (fecha YYYY-MM-DD, video_id) para los n últimos vídeos.

    Usa el feed RSS público de YouTube en lugar de yt-dlp: los runners de
    GitHub Actions comparten IPs que YouTube bloquea con "Sign in to confirm
    you're not a bot" para el listado vía yt-dlp, mientras que el feed RSS
    no requiere autenticación ni pasa por esa detección.
    """
    channel_id = resolve_channel_id(channel_url)
    if not channel_id:
        return []

    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        resp = requests.get(feed_url, headers=HEADERS, cookies=COOKIES, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("  Error al leer feed RSS de %s: %s", channel_id, exc)
        return []

    root = ET.fromstring(resp.content)
    videos = []
    for entry in root.findall(f"{{{ATOM_NS}}}entry")[:n]:
        video_id = entry.findtext(f"{{{YT_NS}}}videoId")
        published = entry.findtext(f"{{{ATOM_NS}}}published")
        if video_id and published:
            videos.append((published[:10], video_id))
    return videos


def fetch_transcript(video_id: str) -> str:
    """Descarga el transcript de un vídeo y devuelve el texto plano."""
    api = YouTubeTranscriptApi()
    try:
        transcript = api.fetch(video_id, languages=PREFERRED_LANGS)
    except NoTranscriptFound:
        # Intenta con cualquier idioma disponible
        transcript_list = api.list(video_id)
        available = list(transcript_list)
        if not available:
            raise NoTranscriptFound(video_id, PREFERRED_LANGS, {})
        transcript = available[0].fetch()

    return "\n".join(entry.text for entry in transcript)


def target_path(date: str, channel_name: str, suffix: str = "") -> str:
    filename = f"{date}-{channel_name}{suffix}.txt"
    return os.path.join(OUTPUT_DIR, filename)


def process_channel(channel: dict) -> tuple[int, int]:
    """Procesa un canal y devuelve (descargados, errores)."""
    url  = channel["url"]
    name = channel["name"]
    log.info("Canal: %s", name)

    videos = get_recent_videos(url, VIDEOS_TO_CHECK)
    if not videos:
        log.warning("  No se obtuvieron vídeos para %s", name)
        return 0, 0

    downloaded = errors = 0

    for date, video_id in videos:
        path = target_path(date, name)

        # Si ya existe un archivo para esa fecha y canal, se omite
        if os.path.exists(path):
            log.info("  [SKIP] %s", os.path.basename(path))
            continue

        # Si hay más de un vídeo el mismo día, añade el ID como sufijo
        suffix = ""
        if any(os.path.exists(target_path(date, name, f"-{i}")) for i in range(1, 10)):
            suffix = f"-{video_id}"
        path = target_path(date, name, suffix)

        try:
            text = fetch_transcript(video_id)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            log.info("  [OK]   %s  (%d caracteres)", os.path.basename(path), len(text))
            downloaded += 1
        except TranscriptsDisabled:
            log.warning("  [SKIP] %s — transcripts desactivados", video_id)
        except NoTranscriptFound:
            log.warning("  [SKIP] %s — no hay transcript disponible", video_id)
        except Exception as exc:
            log.error("  [ERR]  %s — %s", video_id, exc)
            errors += 1

    return downloaded, errors


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=== Inicio descarga de transcripts (%s) ===", datetime.now().strftime("%Y-%m-%d"))

    channels = load_channels(CHANNELS_CSV)
    log.info("Canales cargados: %d", len(channels))

    total_ok = total_err = 0
    for channel in channels:
        ok, err = process_channel(channel)
        total_ok  += ok
        total_err += err

    log.info("=== Fin — descargados: %d  errores: %d ===", total_ok, total_err)


if __name__ == "__main__":
    main()
