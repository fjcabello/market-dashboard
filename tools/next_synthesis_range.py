#!/usr/bin/env python3
"""Calcula si toca generar una nueva síntesis en conclusiones/ y con qué rango.

No usa ningún modelo: solo mira los nombres de fichero ya existentes en
conclusiones/ (YYYY-MM-DD_a_YYYY-MM-DD.md) y decide si han pasado al menos
MIN_DAYS desde el final de la última síntesis.

Imprime "SKIP" si no toca, o "<start> <end>" (ISO) si hay que generar una.
"""
import glob
import re
import sys
from datetime import date, timedelta

MIN_DAYS = 15
PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})_a_(\d{4}-\d{2}-\d{2})\.md$")


def last_end_date() -> date | None:
    ends = [
        date.fromisoformat(m.group(2))
        for path in glob.glob("conclusiones/*.md")
        if (m := PATTERN.search(path))
    ]
    return max(ends) if ends else None


def main() -> None:
    today = date.today()
    last = last_end_date()
    start = last + timedelta(days=1) if last else today - timedelta(days=MIN_DAYS)

    if (today - start).days < MIN_DAYS:
        print("SKIP")
        return

    print(f"{start.isoformat()} {today.isoformat()}")


if __name__ == "__main__":
    sys.exit(main())
