#!/usr/bin/env python3
"""Genera los resúmenes que faltan en resumenes/ a partir de transcripts/.

Hacerlo a mano en una sesión no escala: los 77 pendientes suman 2,6 MB, unos
700.000 tokens de lectura. Esto los procesa uno a uno contra la API y escribe
el mismo formato que usa la skill analyze-transcripts, para que resúmenes
viejos y nuevos sean indistinguibles.

Sólo procesa los transcripts sin resumen, así que es idempotente: se puede
lanzar a diario sin regenerar nada ni gastar de más.

    python tools/summarize_transcripts.py --dry-run      # qué haría y cuánto cuesta
    python tools/summarize_transcripts.py --limit 10     # tanteo
    python tools/summarize_transcripts.py                # todos los pendientes
"""
import argparse
import concurrent.futures
import os
import re
import sys

# anthropic se importa dentro de main(): --dry-run sólo mira ficheros y debe
# funcionar sin el SDK instalado, que es justo cuando uno quiere ver el coste.

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSCRIPTS = os.path.join(BASE, "transcripts")
RESUMENES = os.path.join(BASE, "resumenes")

MODEL = "claude-opus-5"

# El formato lo fija la skill analyze-transcripts. Si cambia allí, cambia aquí:
# los resúmenes se leen mezclados y un formato distinto rompe el grep.
SYSTEM = """Resumes transcripciones automáticas de vídeos de YouTube de comentaristas
financieros en español. Vienen de subtítulos automáticos: sin puntuación fiable, con
errores de transcripción en nombres propios y cifras, y a veces con varios interlocutores.

Devuelves EXCLUSIVAMENTE un documento markdown con esta estructura, sin texto antes ni
después, sin envolverlo en ```:

# {fecha} — {canal}

**Tesis principal:** Una o dos frases con el argumento central del vídeo.

**Puntos clave:**
- Dato o afirmación, con cifras concretas cuando las haya
- (máximo 6 puntos)

**Activos mencionados:** Tickers, ETFs, materias primas, criptos o fondos, con precio
u objetivo si se dan. "Ninguno específico." si no hay.

**Tono:** alcista / bajista / neutro / educativo, con matiz si hace falta.

Reglas:
- Recoge sólo lo que dice el vídeo. No añadas contexto de mercado propio ni corrijas al
  ponente aunque se equivoque: esto es un registro de lo que opinó, no un análisis.
- Conserva las cifras exactas que se mencionen. Son lo que después se contrasta con los
  datos reales, así que redondearlas destruye el valor del resumen.
- Si una cifra está claramente corrompida por la transcripción, transcríbela igual y
  añade "(según transcripción)". No la arregles adivinando.
- Si el vídeo es un evento con varios ponentes, atribuye las tesis a quien las dice.
- Si no hay contenido de mercado (vídeo puramente educativo o personal), dilo en la
  tesis y deja "Ninguno específico." en activos. No inventes contenido para rellenar."""

NOMBRE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+?)(?:-[\w-]{11})?$")


def pendientes() -> list[tuple[str, str, str]]:
    """(ruta, fecha, canal) de cada transcript sin resumen."""
    out = []
    for fn in sorted(os.listdir(TRANSCRIPTS)):
        if not fn.endswith(".txt"):
            continue
        base = fn[:-4]
        if os.path.exists(os.path.join(RESUMENES, base + ".md")):
            continue
        m = NOMBRE.match(base)
        if not m:
            print(f"  [!] nombre no reconocido, se omite: {fn}")
            continue
        out.append((os.path.join(TRANSCRIPTS, fn), m.group(1), m.group(2)))
    return out


def resumir(client, ruta: str, fecha: str, canal: str) -> str:
    texto = open(ruta, encoding="utf-8").read()
    r = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM,
        # Tarea de extracción rutinaria: el esfuerzo alto no mejora el resumen y
        # multiplica los tokens de razonamiento por 77.
        output_config={"effort": "low"},
        messages=[{
            "role": "user",
            "content": f"Fecha: {fecha}\nCanal: {canal}\n\nTranscripción:\n\n{texto}",
        }],
    )
    if r.stop_reason == "refusal":
        raise RuntimeError("la API rechazó el contenido")
    md = next((b.text for b in r.content if b.type == "text"), "").strip()
    if not md.startswith("#"):
        raise RuntimeError(f"respuesta con formato inesperado: {md[:80]!r}")
    return md


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="no llama a la API")
    p.add_argument("--limit", type=int, help="procesa como mucho N")
    p.add_argument("--jobs", type=int, default=4, help="peticiones en paralelo (4)")
    # En CI el secreto puede no estar puesto todavía, y quedarse sin resúmenes no
    # es motivo para tumbar la publicación del dashboard. Es una bandera explícita
    # y no el comportamiento por defecto: en local, olvidar la clave debe fallar.
    p.add_argument("--sin-clave-salir-ok", action="store_true",
                   help="si no hay ANTHROPIC_API_KEY, avisa y termina bien")
    a = p.parse_args()

    faltan = pendientes()
    if a.limit:
        faltan = faltan[:a.limit]
    if not faltan:
        print("No falta ningún resumen.")
        return 0

    total = sum(os.path.getsize(r) for r, _, _ in faltan)
    # ~4 caracteres por token en español; sirve para decidir, no para facturar.
    tokens = total / 4
    print(f"{len(faltan)} transcripts sin resumen · {total / 1024:.0f} KB")
    print(f"Estimación: ~{tokens / 1000:.0f}k tokens de entrada, "
          f"~${tokens / 1e6 * 5 + len(faltan) * 400 / 1e6 * 25:.2f} con {MODEL}\n")

    if a.dry_run:
        for _, fecha, canal in faltan:
            print(f"  {fecha}  {canal}")
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        if a.sin_clave_salir_ok:
            print("Sin ANTHROPIC_API_KEY: no se generan resúmenes (no es un error).")
            return 0
        sys.exit("Falta ANTHROPIC_API_KEY.")

    import anthropic
    client = anthropic.Anthropic()
    os.makedirs(RESUMENES, exist_ok=True)
    ok, err = 0, []

    def trabajo(item):
        ruta, fecha, canal = item
        return item, resumir(client, ruta, fecha, canal)

    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        for fut in concurrent.futures.as_completed(
                pool.submit(trabajo, i) for i in faltan):
            try:
                (ruta, fecha, canal), md = fut.result()
            except Exception as exc:
                err.append(str(exc))
                print(f"  FALLO  {exc}")
                continue
            destino = os.path.join(RESUMENES,
                                   os.path.basename(ruta)[:-4] + ".md")
            with open(destino, "w", encoding="utf-8") as f:
                f.write(md.rstrip() + "\n")
            ok += 1
            print(f"  ok     {fecha}  {canal}")

    print(f"\n{ok} escritos · {len(err)} fallos")
    # Un fallo parcial no invalida lo escrito, pero tiene que verse en CI: si
    # falla en silencio, el backfill se queda a medias sin que nadie lo note.
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
