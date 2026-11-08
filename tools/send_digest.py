#!/usr/bin/env python3
"""Envía por Telegram los digests diarios de resúmenes que aún no se han enviado.

/daily-resumenes escribe digests/YYYY-MM-DD.md cuando genera resúmenes nuevos:

    Párrafo opcional con el panorama del día (temas comunes entre vídeos).

    ## 2026-11-07-PeterSchiff
    1-2 líneas con lo esencial del vídeo.

    ## 2026-11-07-TradingLatino
    ...

Cada sección ## lleva el nombre base del resumen en resumenes/. Este script
convierte cada digest sin marcador digests/YYYY-MM-DD.sent en uno o varios
mensajes HTML para el chat privado de Paco y, si Telegram los acepta todos,
crea el marcador (el workflow lo commitea), así que un re-run no reenvía nada.

Usa el bot @PaquitosAgent_bot solo para enviar (sendMessage). Nunca llamar a
getUpdates ni a setWebhook con ese token: la sesión de Durbar en el VPS es la
única que lo lee.

Entre las 23:00 y las 07:00 (hora de Madrid) no envía nada: el digest queda
pendiente para la siguiente ejecución.

Variables de entorno: TG_TOKEN y TG_CHAT (secrets TELEGRAM_BOT_TOKEN y
TELEGRAM_CHAT_ID). Con --dry-run imprime los mensajes y no necesita ninguna.

Uso:  python tools/send_digest.py [--dry-run]
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent.parent
DIGESTS = BASE / "digests"
REPO_URL = "https://github.com/fjcabello/market-dashboard/blob/main/resumenes"
MADRID = ZoneInfo("Europe/Madrid")
QUIET_START, QUIET_END = 23, 7
# Telegram corta a 4096 caracteres; margen para el encabezado de continuación.
MAX_LEN = 3500
DIGEST_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")


def in_quiet_hours(now: datetime) -> bool:
    hour = now.astimezone(MADRID).hour
    return hour >= QUIET_START or hour < QUIET_END


def parse_digest(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Devuelve (panorama, [(nombre_resumen, texto), ...])."""
    intro: list[str] = []
    items: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("## "):
            items.append((line[3:].strip(), []))
        elif items:
            items[-1][1].append(line)
        else:
            intro.append(line)
    clean = lambda lines: " ".join(l.strip() for l in lines if l.strip())
    return clean(intro), [(name, clean(body)) for name, body in items]


def channel_of(resumen: str) -> str:
    # 2026-11-07-TradingLatino-HhKjAUuyuWo -> TradingLatino
    parts = resumen.split("-")
    return parts[3] if len(parts) > 3 else resumen


def render(date: str, text: str) -> list[str]:
    """Convierte un digest en mensajes HTML de menos de MAX_LEN caracteres."""
    intro, items = parse_digest(text)
    header = f"📈 <b>Resúmenes bolsa {date}</b> ({len(items)} vídeo{'s' if len(items) != 1 else ''})"
    blocks = []
    if intro:
        blocks.append(html.escape(intro, quote=False))
    for name, body in items:
        link = f"{REPO_URL}/{urllib.parse.quote(name)}.md"
        block = f'• <b>{html.escape(channel_of(name), quote=False)}</b> — {html.escape(body, quote=False)} <a href="{html.escape(link)}">resumen</a>'
        blocks.append(block)

    messages, current = [], header
    for block in blocks:
        if len(block) > MAX_LEN - 100:
            # Un bloque desmesurado no debería pasar (son 1-2 líneas), pero no
            # puede tumbar el envío: se corta en texto plano, sin etiquetas ni
            # entidades a medias, hasta que escapado quepa.
            plain = html.unescape(re.sub(r"<[^>]+>", "", block))
            limit = MAX_LEN - 200
            while len(html.escape(plain[:limit], quote=False)) > MAX_LEN - 200:
                limit -= 100
            block = html.escape(plain[:limit], quote=False) + "…"
        if len(current) + 2 + len(block) > MAX_LEN:
            messages.append(current)
            current = f"📈 <b>Resúmenes bolsa {date}</b> (sigue)"
        current += "\n\n" + block
    messages.append(current)
    return messages


def send(token: str, chat: str, text: str) -> None:
    data = urllib.parse.urlencode({
        "chat_id": chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    # El token va en la URL de la API: no se imprime nunca, ni en los errores.
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            body = json.load(e)
        except ValueError:
            body = {"ok": False, "description": f"HTTP {e.code}"}
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"Telegram no responde: {getattr(e, 'reason', e)}") from None
    if not body.get("ok"):
        raise RuntimeError(f"Telegram rechazó el mensaje: {body.get('description', 'sin descripción')}")


def pending(digests: Path) -> list[Path]:
    if not digests.is_dir():
        return []
    return sorted(p for p in digests.iterdir()
                  if DIGEST_NAME.match(p.name) and not p.with_suffix(".sent").exists())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="imprime los mensajes en vez de enviarlos")
    args = ap.parse_args()

    todo = pending(DIGESTS)
    if not todo:
        print("No hay digests pendientes de enviar.")
        return 0

    if not args.dry_run and in_quiet_hours(datetime.now(MADRID)):
        print(f"Franja de silencio ({QUIET_START}:00-{QUIET_END}:00 Madrid): {len(todo)} digest(s) quedan para la siguiente ejecución.")
        return 0

    token, chat = os.environ.get("TG_TOKEN", ""), os.environ.get("TG_CHAT", "")
    if not args.dry_run and not (token and chat):
        print("ERROR: faltan TG_TOKEN o TG_CHAT (secrets TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).", file=sys.stderr)
        return 1

    for path in todo:
        date = path.stem
        messages = render(date, path.read_text(encoding="utf-8"))
        if args.dry_run:
            for m in messages:
                print(f"----- {date} ({len(m)} caracteres)\n{m}")
            continue
        for m in messages:
            send(token, chat, m)
        path.with_suffix(".sent").write_text(datetime.now(MADRID).isoformat(timespec="seconds") + "\n", encoding="utf-8")
        print(f"Enviado digest {date} ({len(messages)} mensaje(s)).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
