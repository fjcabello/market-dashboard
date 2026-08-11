#!/usr/bin/env python3
"""Verifica y re-resuelve los channel_id de channels.csv.

resolve_channel_id se fía del channel_id cacheado en el CSV en cuanto tiene
forma de identificador, sin comprobar que apunte a un canal real. Si esos ids
se resolvieron con el proxy devolviendo páginas erróneas, quedaron grabados
mal y el feed responde 404 para siempre sin que nada lo detecte.

Esta herramienta comprueba cada id contra el feed y, cuando falla, lo vuelve a
resolver desde la URL del canal y lo verifica de nuevo.

Pensada para ejecutarse en CI, porque desde un entorno con YouTube bloqueado no
se puede comprobar nada.

    python tools/verify_channels.py            # solo informa
    python tools/verify_channels.py --write    # además corrige channels.csv
"""
import csv
import os
import re
import sys

import requests

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import download_transcripts as dt  # noqa: E402

CSV_PATH = os.path.join(BASE, "channels.csv")
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
ID_RE = re.compile(r"UC[\w-]{22}")


def feed_ok(channel_id: str, proxies: dict | None) -> tuple[bool, str]:
    """¿Devuelve el feed de este id un XML con entradas?"""
    if not channel_id or not ID_RE.fullmatch(channel_id):
        return False, "id con formato inválido"
    try:
        r = requests.get(FEED.format(channel_id), headers=dt.HEADERS,
                         cookies=dt.COOKIES, timeout=20, proxies=proxies)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        # Un 200 no basta: YouTube puede devolver un feed vacío.
        if "<entry>" not in r.text and "videoId" not in r.text:
            return False, "feed sin vídeos"
        return True, "ok"
    except requests.RequestException as exc:
        return False, type(exc).__name__


def scrape_channel_id(url: str, proxies: dict | None) -> str | None:
    """Extrae el externalId de la página del canal.

    Se descartan las coincidencias que no sean la canónica: la página lista
    también canales recomendados, y quedarse con la primera del HTML es
    justamente lo que puede haber grabado ids ajenos en el CSV.
    """
    try:
        r = requests.get(url, headers=dt.HEADERS, cookies=dt.COOKIES,
                         timeout=20, proxies=proxies)
        r.raise_for_status()
    except requests.RequestException as exc:
        print(f"      no se pudo descargar la página: {exc}")
        return None

    # rel="canonical" apunta al propio canal; es la fuente más fiable.
    m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', r.text)
    if m:
        return m.group(1)
    m = re.search(r'"channelId":"(UC[\w-]{22})"', r.text)
    if m:
        return m.group(1)
    m = re.search(r'"externalId":"(UC[\w-]{22})"', r.text)
    return m.group(1) if m else None


def main() -> int:
    write = "--write" in sys.argv

    proxy_cfg = dt.build_proxy_config()
    proxies = dt._REQUESTS_PROXIES or None
    print(f"Proxy: {'activo' if proxies else 'no configurado'}\n")

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0].keys())

    changed, broken = [], []
    for row in rows:
        name, url, cached = row["name"], row["url"], row.get("channel_id", "")
        ok, why = feed_ok(cached, proxies)
        if ok:
            print(f"  ok     {name:20s} {cached}")
            continue

        print(f"  KO     {name:20s} {cached or '(vacío)'} — {why}")
        resolved = scrape_channel_id(url, proxies)
        if not resolved:
            print(f"      no se pudo resolver desde {url}")
            broken.append(name)
            continue
        if resolved == cached:
            print(f"      la página devuelve el mismo id: el canal no publica feed")
            broken.append(name)
            continue

        ok2, why2 = feed_ok(resolved, proxies)
        if ok2:
            print(f"      CORREGIDO -> {resolved}")
            row["channel_id"] = resolved
            changed.append((name, cached, resolved))
        else:
            print(f"      el id resuelto {resolved} tampoco sirve — {why2}")
            broken.append(name)

    print(f"\n  {len(rows) - len(changed) - len(broken)} correctos · "
          f"{len(changed)} corregidos · {len(broken)} sin solución")

    if changed and write:
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"  channels.csv actualizado")
    elif changed:
        print("  (ejecuta con --write para aplicar los cambios)")

    # Falla si queda algún canal sin feed utilizable, para que CI lo marque.
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
