#!/usr/bin/env python3
"""Pruebas de tools/send_digest.py sin tocar Telegram.

Uso:  python tests/test_digest.py
"""
import io
import json
import os
import sys
import tempfile
import urllib.error
from datetime import datetime
from pathlib import Path
from unittest import mock

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))

import send_digest as sd  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FALLO'}  {name}{'  — ' + detail if detail and not cond else ''}")
    if not cond:
        FAILURES.append(name)


DIGEST = """Día dominado por las elecciones: oro arriba, IA abajo.

## 2026-11-07-PeterSchiff
Muy alcista en oro (4.070$) & plata; pide vender Bitcoin <ahora>.

## 2026-11-07-TradingLatino-HhKjAUuyuWo
Bitcoin lateral en 76.000$; espera ruptura.
"""

print("parse_digest")
intro, items = sd.parse_digest(DIGEST)
check("panorama", intro == "Día dominado por las elecciones: oro arriba, IA abajo.", intro)
check("dos vídeos", [n for n, _ in items] == ["2026-11-07-PeterSchiff", "2026-11-07-TradingLatino-HhKjAUuyuWo"], str(items))
check("canal sin id de vídeo", sd.channel_of("2026-11-07-TradingLatino-HhKjAUuyuWo") == "TradingLatino")

print("render")
msgs = sd.render("2026-11-07", DIGEST)
check("un solo mensaje", len(msgs) == 1, str(len(msgs)))
m = msgs[0]
check("encabezado con recuento", m.startswith("📈 <b>Resúmenes bolsa 2026-11-07</b> (2 vídeos)"), m[:80])
check("escapa & < >", "&amp; plata" in m and "&lt;ahora&gt;" in m and "<ahora>" not in m)
check("enlace al resumen", f'{sd.REPO_URL}/2026-11-07-PeterSchiff.md">resumen</a>' in m)
check("singular con un vídeo", "(1 vídeo)" in sd.render("2026-11-08", "## 2026-11-08-X\nalgo")[0])

long_digest = "\n".join(f"## 2026-11-07-Canal{i}\n" + "texto largo " * 30 for i in range(40))
long_msgs = sd.render("2026-11-07", long_digest)
check("parte digests largos", len(long_msgs) > 1, str(len(long_msgs)))
check("todos bajo el límite", all(len(x) <= sd.MAX_LEN for x in long_msgs), str([len(x) for x in long_msgs]))
check("no pierde vídeos al partir", sum(x.count("• <b>") for x in long_msgs) == 40)
huge = sd.render("2026-11-07", "## 2026-11-07-Enorme\n" + "<x> " * 3000)
check("bloque desmesurado acotado", all(len(x) <= sd.MAX_LEN for x in huge) and "<x>" not in huge[0])

print("franja de silencio (hora de Madrid)")
utc = sd.ZoneInfo("UTC")
cases = [
    ("22:59 Madrid en invierno", datetime(2026, 11, 7, 21, 59, tzinfo=utc), False),
    ("23:00 Madrid en invierno", datetime(2026, 11, 7, 22, 0, tzinfo=utc), True),
    ("06:59 Madrid en invierno", datetime(2026, 11, 8, 5, 59, tzinfo=utc), True),
    ("07:00 Madrid en invierno", datetime(2026, 11, 8, 6, 0, tzinfo=utc), False),
    ("23:30 Madrid en verano", datetime(2026, 7, 1, 21, 30, tzinfo=utc), True),
    ("16:00 Madrid en verano", datetime(2026, 7, 1, 14, 0, tzinfo=utc), False),
]
for name, when, expected in cases:
    check(name, sd.in_quiet_hours(when) is expected)

print("pendientes y marcador .sent")
with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp)
    (d / "2026-11-06.md").write_text("## 2026-11-06-A\nuno")
    (d / "2026-11-06.sent").write_text("ya")
    (d / "2026-11-07.md").write_text("## 2026-11-07-B\ndos")
    (d / "README.md").write_text("no es un digest")
    check("solo los no enviados", [p.name for p in sd.pending(d)] == ["2026-11-07.md"])
    check("sin carpeta, nada", sd.pending(d / "no-existe") == [])

    sent = []
    with mock.patch.object(sd, "DIGESTS", d), \
         mock.patch.object(sd, "send", lambda t, c, text: sent.append(text)), \
         mock.patch.object(sd, "in_quiet_hours", lambda now: False), \
         mock.patch.dict(os.environ, {"TG_TOKEN": "t", "TG_CHAT": "c"}), \
         mock.patch.object(sys, "argv", ["send_digest.py"]):
        rc = sd.main()
        check("envía el pendiente", rc == 0 and len(sent) == 1 and "2026-11-07" in sent[0])
        check("crea el marcador", (d / "2026-11-07.sent").exists())
        sent.clear()
        sd.main()
        check("un re-run no reenvía", sent == [])

    (d / "2026-11-09.md").write_text("## 2026-11-09-D\ncuatro")
    got = []
    with mock.patch.object(sd, "DIGESTS", d), \
         mock.patch.object(sd, "send", lambda t, c, text: got.append((t, c))), \
         mock.patch.object(sd, "in_quiet_hours", lambda now: False), \
         mock.patch.dict(os.environ, {"TG_TOKEN": "123:abc\n", "TG_CHAT": " 42\n"}), \
         mock.patch.object(sys, "argv", ["send_digest.py"]):
        sd.main()
        check("limpia saltos de línea de los secrets", got == [("123:abc", "42")], str(got))

    (d / "2026-11-08.md").write_text("## 2026-11-08-C\ntres")
    with mock.patch.object(sd, "DIGESTS", d), \
         mock.patch.object(sd, "send", lambda t, c, text: sent.append(text)), \
         mock.patch.object(sd, "in_quiet_hours", lambda now: True), \
         mock.patch.dict(os.environ, {"TG_TOKEN": "t", "TG_CHAT": "c"}), \
         mock.patch.object(sys, "argv", ["send_digest.py"]):
        sd.main()
        check("en silencio no envía ni marca", sent == [] and not (d / "2026-11-08.sent").exists())

print("errores de Telegram sin filtrar el token")
token = "123456:SECRETO-NO-IMPRIMIR"
err = urllib.error.HTTPError("https://api.telegram.org/bot" + token + "/sendMessage", 400, "Bad Request", {},
                             io.BytesIO(json.dumps({"ok": False, "description": "Bad Request: chat not found"}).encode()))
with mock.patch("urllib.request.urlopen", side_effect=err):
    try:
        sd.send(token, "c", "hola")
        msg = ""
    except RuntimeError as e:
        msg = str(e)
check("propaga la description", "chat not found" in msg, msg)
check("el error no contiene el token", token not in msg and "SECRETO" not in msg, msg)
ok_resp = mock.MagicMock()
ok_resp.__enter__.return_value = io.BytesIO(b'{"ok":true,"result":{}}')
with mock.patch("urllib.request.urlopen", return_value=ok_resp) as uo:
    sd.send(token, "42", "<b>hola</b>")
    req = uo.call_args[0][0]
    body = req.data.decode()
check("parse_mode HTML y sin preview", "parse_mode=HTML" in body and "disable_web_page_preview=true" in body)
check("usa sendMessage, nunca getUpdates", req.full_url.endswith("/sendMessage") and "getUpdates" not in req.full_url)

if FAILURES:
    print(f"\n{len(FAILURES)} fallo(s): {', '.join(FAILURES)}")
    sys.exit(1)
print("\nTodo ok")
