#!/usr/bin/env python3
"""
Script diario para descargar transcripts de canales de YouTube.
Ejecutar una vez al día: python3 download_transcripts.py
Los archivos se guardan como YYYY-MM-DD-NombreCanal.txt
"""

import csv
import glob
import os
import re
import subprocess
import sys
import logging
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

# ── Configuración ────────────────────────────────────────────────────────────

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR   = os.path.join(BASE_DIR, "transcripts")
CHANNELS_CSV = os.path.join(BASE_DIR, "channels.csv")
ENV_FILE     = os.path.join(BASE_DIR, ".env")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _load_env_key(name: str) -> str:
    """Lee una variable del entorno o del fichero .env."""
    val = os.environ.get(name, "")
    if val:
        return val
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            if line.strip().startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return ""


def load_channels(csv_path: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if row.get("name") and row.get("url")]

# Cuántos vídeos recientes revisar por canal en cada ejecución.
# 3 cubre el caso de que no se ejecute el script un día.
# Se puede aumentar puntualmente con la env var VIDEOS_TO_CHECK para
# recuperar huecos (p.ej. tras una caída del workflow de varios días).
VIDEOS_TO_CHECK = int(os.environ.get("VIDEOS_TO_CHECK", "3"))

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

YTDLP   = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
BROWSER = "safari"   # cookies del navegador para esquivar bloqueos de IP
IN_CI   = os.environ.get("CI", "false").lower() == "true"

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

# ── Proxy Webshare ───────────────────────────────────────────────────────────

# Diccionario de proxies para requests (se rellena al inicio si hay clave).
_REQUESTS_PROXIES: dict = {}


WEBSHARE_HOST = "p.webshare.io"
WEBSHARE_PORT = 80
ROTATE_SUFFIX = "-rotate"


def rotating_username(user: str) -> str:
    """Usuario tal y como lo exige el gateway rotativo de Webshare.

    El endpoint p.webshare.io rechaza con 407 el usuario sin sufijo, aunque las
    credenciales sean correctas. Es idempotente porque la API puede devolverlo
    ya sufijado según la configuración de la cuenta, y duplicarlo también falla.
    """
    return user if user.endswith(ROTATE_SUFFIX) else user + ROTATE_SUFFIX


def verify_proxy(proxy_url: str) -> bool:
    """Comprueba de verdad que el túnel HTTPS funciona, y lo deja en el log.

    Sin esto, un proxy mal configurado sólo se manifiesta más abajo como
    decenas de errores por vídeo, mezclado con los bloqueos legítimos de
    YouTube. Una línea que diga si el proxy responde ahorra ese diagnóstico.

    Nunca aborta: si la sonda falla se sigue intentando la descarga, porque el
    fallo puede estar en el servicio de comprobación y no en el proxy.
    """
    try:
        resp = requests.get(
            "https://ipv4.webshare.io/",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=15,
        )
        resp.raise_for_status()
        log.info("  Proxy verificado — IP de salida: %s", resp.text.strip())
        return True
    except Exception as exc:
        log.error("  Proxy NO operativo: %s", exc)
        log.error("  La descarga continuará sin proxy y YouTube bloqueará "
                  "la IP del runner")
        return False


def build_proxy_config() -> GenericProxyConfig | None:
    """Obtiene credenciales de Webshare, configura el proxy global y devuelve
    un GenericProxyConfig para youtube-transcript-api, o None si falla."""
    global _REQUESTS_PROXIES
    api_key = _load_env_key("WEBSHARE_API_KEY")
    if not api_key:
        log.info("WEBSHARE_API_KEY no configurada — descarga sin proxy")
        return None
    try:
        resp = requests.get(
            "https://proxy.webshare.io/api/v2/proxy/config/",
            headers={"Authorization": f"Token {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data  = resp.json()
        user  = data["username"]
        pwd   = data["password"]

        # El gateway rotativo p.webshare.io exige el usuario con sufijo
        # "-rotate". Sin él la autenticación se rechaza con 407 aunque las
        # credenciales sean correctas, que es lo que rompió la descarga desde
        # el 2026-07-24: la llamada a la API funcionaba y el túnel no.
        rotate_user = rotating_username(user)
        proxy = f"http://{rotate_user}:{pwd}@{WEBSHARE_HOST}:{WEBSHARE_PORT}"
        _REQUESTS_PROXIES = {"http": proxy, "https": proxy}

        # WebshareProxyConfig añade el sufijo por su cuenta (se le pasa el
        # usuario crudo) y además desactiva keep-alive, necesario para que el
        # gateway entregue una IP distinta en cada petición.
        proxy_config = WebshareProxyConfig(proxy_username=user, proxy_password=pwd)

        log.info("Proxy Webshare configurado (%s@%s:%s)",
                 rotate_user, WEBSHARE_HOST, WEBSHARE_PORT)
        verify_proxy(proxy)
        return proxy_config
    except requests.HTTPError as exc:
        log.error("WEBSHARE_API_KEY inválida o expirada (HTTP %s) — abortando", exc.response.status_code)
        sys.exit(1)
    except Exception as exc:
        log.error("No se pudo contactar con Webshare: %s — abortando", exc)
        sys.exit(1)

# ── Funciones ────────────────────────────────────────────────────────────────

def resolve_channel_id(channel_url: str, cached_id: str = "") -> str | None:
    """Obtiene el channel_id (UC...) a partir de una URL de canal.

    Prioridad: 1) cached_id del CSV, 2) extracción directa de la URL,
    3) scraping del HTML (solo fuera de CI para no depender de IPs de GitHub).
    """
    if cached_id and re.match(r"UC[\w-]{22}", cached_id):
        return cached_id

    match = re.search(r"/channel/(UC[\w-]{22})", channel_url)
    if match:
        return match.group(1)

    if IN_CI:
        log.error("  No se puede resolver channel_id de %s en CI sin caché", channel_url)
        return None

    try:
        resp = requests.get(channel_url, headers=HEADERS, cookies=COOKIES, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("  No se pudo resolver channel_id de %s: %s", channel_url, exc)
        return None

    match = re.search(r'"externalId":"(UC[\w-]{22})"', resp.text)
    return match.group(1) if match else None


def get_recent_videos(channel_url: str, n: int, cached_id: str = "") -> list[tuple[str, str]]:
    """Devuelve lista de (fecha YYYY-MM-DD, video_id) para los n últimos vídeos.

    Usa el feed RSS público de YouTube en lugar de yt-dlp.
    """
    channel_id = resolve_channel_id(channel_url, cached_id)
    if not channel_id:
        return []

    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    # El feed se pide primero por el proxy y, si falla, directo. Antes iba solo
    # directo para esquivar el proxy roto, pero YouTube devuelve 404 a las IP de
    # los runners de forma intermitente. Con el proxy operativo, el orden
    # correcto es el inverso: proxy primero, directo como red de seguridad.
    attempts = [("proxy", _REQUESTS_PROXIES), ("directo", None)] if _REQUESTS_PROXIES \
        else [("directo", None)]

    for via, proxies in attempts:
        try:
            resp = requests.get(feed_url, headers=HEADERS, cookies=COOKIES,
                                timeout=15, proxies=proxies)
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            log.warning("  Feed RSS de %s vía %s: %s", channel_id, via, exc)
    else:
        log.error("  Error al leer feed RSS de %s por ninguna vía", channel_id)
        return []

    root = ET.fromstring(resp.content)
    videos = []
    for entry in root.findall(f"{{{ATOM_NS}}}entry")[:n]:
        video_id = entry.findtext(f"{{{YT_NS}}}videoId")
        published = entry.findtext(f"{{{ATOM_NS}}}published")
        if video_id and published:
            videos.append((published[:10], video_id))
    return videos


def _parse_srt(text: str) -> str:
    """Convierte texto SRT a texto plano eliminando marcas de tiempo y etiquetas HTML."""
    lines, prev = [], ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line)   # quitar etiquetas HTML/VTT
        if line and line != prev:              # deduplicar líneas consecutivas
            lines.append(line)
            prev = line
    return "\n".join(lines)


def fetch_transcript_ytdlp(video_id: str) -> str:
    """Descarga subtítulos automáticos via yt-dlp usando cookies del navegador."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmpdir:
        out_tmpl = os.path.join(tmpdir, "%(id)s")
        for lang in ("es", "es-419", "en", ".*"):
            subprocess.run(
                [
                    YTDLP,
                    "--skip-download",
                    "--write-auto-subs",
                    "--sub-langs", lang,
                    "--convert-subs", "srt",
                    "--cookies-from-browser", BROWSER,
                    "--no-warnings",
                    "--output", out_tmpl,
                    url,
                ],
                capture_output=True, text=True,
            )
            srt_files = glob.glob(os.path.join(tmpdir, "*.srt"))
            if srt_files:
                with open(srt_files[0], encoding="utf-8") as f:
                    text = f.read()
                parsed = _parse_srt(text)
                if parsed:
                    return parsed
    raise NoTranscriptFound(video_id, PREFERRED_LANGS, {})


def _fetch_with_api(video_id: str, proxy_config: GenericProxyConfig | None) -> str:
    api = YouTubeTranscriptApi(proxy_config=proxy_config)
    try:
        transcript = api.fetch(video_id, languages=PREFERRED_LANGS)
    except NoTranscriptFound:
        available = list(api.list(video_id))
        if not available:
            raise NoTranscriptFound(video_id, PREFERRED_LANGS, {})
        transcript = available[0].fetch()
    return "\n".join(entry.text for entry in transcript)


def fetch_transcript(video_id: str, proxy_config: GenericProxyConfig | None = None) -> str:
    """Descarga el transcript de un vídeo y devuelve el texto plano.

    Orden de intento:
      1. youtube-transcript-api con proxy Webshare (si está configurado)
      2. youtube-transcript-api sin proxy (fallback si el proxy falla)
      3. yt-dlp con cookies de Safari (solo fuera de CI)
    """
    configs = [proxy_config, None] if proxy_config else [None]
    last_exc: Exception | None = None

    for config in configs:
        label = "con proxy" if config else "sin proxy"
        try:
            return _fetch_with_api(video_id, config)
        except (TranscriptsDisabled, NoTranscriptFound):
            raise
        except Exception as exc:
            log.warning("  [transcript-api %s] %s — %s", label, video_id, exc)
            last_exc = exc

    if not IN_CI:
        log.warning("  Reintentando con yt-dlp %s", video_id)
        return fetch_transcript_ytdlp(video_id)
    raise last_exc  # type: ignore[misc]


def target_path(date: str, channel_name: str, suffix: str = "") -> str:
    filename = f"{date}-{channel_name}{suffix}.txt"
    return os.path.join(OUTPUT_DIR, filename)


def process_channel(
    channel: dict, proxy_config: GenericProxyConfig | None = None
) -> tuple[int, int, int, list[str], list[str]]:
    """Procesa un canal y devuelve (descargados, skips, errores, nuevos_ficheros, errores_ids)."""
    url  = channel["url"]
    name = channel["name"]
    log.info("Canal: %s", name)

    videos = get_recent_videos(url, VIDEOS_TO_CHECK, cached_id=channel.get("channel_id", ""))
    if not videos:
        # Cuenta como error, no como canal vacío. Un canal siempre tiene vídeos:
        # llegar aquí significa que falló el feed o la resolución del id. Sin
        # contarlo, once canales caídos sumaban 0 errores y la ejecución salía
        # en verde con cero descargas, que es el fallo silencioso que ya nos
        # costó 17 días.
        log.error("  No se obtuvieron vídeos para %s — feed o channel_id KO", name)
        return 0, 0, 1, [], [f"{name}: sin vídeos del feed"]

    downloaded = skips = errors = 0
    new_files: list[str] = []
    error_ids: list[str] = []

    for date, video_id in videos:
        path = target_path(date, name)

        if os.path.exists(path):
            log.info("  [SKIP] %s", os.path.basename(path))
            skips += 1
            continue

        suffix = ""
        if any(os.path.exists(target_path(date, name, f"-{i}")) for i in range(1, 10)):
            suffix = f"-{video_id}"
        path = target_path(date, name, suffix)

        try:
            text = fetch_transcript(video_id, proxy_config=proxy_config)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            log.info("  [OK]   %s  (%d caracteres)", os.path.basename(path), len(text))
            downloaded += 1
            new_files.append(f"{os.path.basename(path)} ({len(text):,} chars)")
        except TranscriptsDisabled:
            log.warning("  [SKIP] %s — transcripts desactivados", video_id)
            skips += 1
        except NoTranscriptFound:
            log.warning("  [SKIP] %s — no hay transcript disponible", video_id)
            skips += 1
        except Exception as exc:
            log.error("  [ERR]  %s — %s", video_id, exc)
            errors += 1
            error_ids.append(f"{video_id} — {exc}")

    return downloaded, skips, errors, new_files, error_ids


def write_github_summary(
    date: str,
    channels: list[dict],
    results: list[tuple],
    total_ok: int,
    total_skip: int,
    total_err: int,
) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = [
        f"## Transcripts — {date}",
        "",
        f"**{total_ok} nuevos · {total_skip} skip · {total_err} errores**",
        "",
        "| Canal | Nuevos | Skip | Errores |",
        "|-------|-------:|-----:|--------:|",
    ]
    for ch, (ok, skip, err, _, _) in zip(channels, results):
        lines.append(f"| {ch['name']} | {ok} | {skip} | {err} |")

    all_new = [f for _, _, _, files, _ in results for f in files]
    if all_new:
        lines += ["", "### Nuevos transcripts", ""]
        lines += [f"- `{f}`" for f in all_new]

    all_errs = [e for _, _, _, _, errs in results for e in errs]
    if all_errs:
        lines += ["", "### Errores", ""]
        lines += [f"- `{e}`" for e in all_errs]

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def resolve_exit_code(total_ok: int, total_skip: int, total_err: int) -> int:
    """Decide si la ejecución debe reportar éxito.

    La distinción clave es entre "hoy no había nada nuevo" y "lo intenté y falló
    todo". Sin ella, una tubería rota es indistinguible de un día tranquilo: es
    lo que permitió que la descarga estuviera 17 días terminando en verde con
    cero transcripts desde el 2026-07-24.

      - Algo descargado          -> éxito, aunque haya errores sueltos. Un fallo
                                    parcial no debe impedir publicar el resto.
      - Nada descargado, 0 errores -> éxito. Todos los vídeos ya estaban o no
                                    tenían subtítulos: es un día normal.
      - Nada descargado, con errores -> fallo. No se produjo ningún dato y hubo
                                    motivo para pensar que debería haberse
                                    producido.
    """
    if total_ok == 0 and total_err > 0:
        log.error(
            "Ningún transcript descargado y %d errores: la descarga está rota, "
            "no es un día sin novedades", total_err
        )
        return 1
    return 0


def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    log.info("=== Inicio descarga de transcripts (%s) ===", date_str)

    proxy_config = build_proxy_config()

    channels = load_channels(CHANNELS_CSV)
    log.info("Canales cargados: %d", len(channels))

    results = []
    total_ok = total_skip = total_err = 0
    for channel in channels:
        res = process_channel(channel, proxy_config=proxy_config)
        results.append(res)
        total_ok   += res[0]
        total_skip += res[1]
        total_err  += res[2]

    log.info("=== Fin — descargados: %d  skip: %d  errores: %d ===", total_ok, total_skip, total_err)
    write_github_summary(date_str, channels, results, total_ok, total_skip, total_err)
    return resolve_exit_code(total_ok, total_skip, total_err)


if __name__ == "__main__":
    sys.exit(main())
