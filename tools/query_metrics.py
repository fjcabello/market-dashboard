#!/usr/bin/env python3
"""Consulta fred_data.csv sin volcarlo entero.

El CSV tiene 30 columnas y 2.400 filas. Leerlo para responder "¿a cuánto está
el 10 años?" es tirar contexto a la basura, así que esto devuelve solo lo
pedido.

Aviso importante sobre las fechas: el CSV está rellenado hacia delante para
encajar series mensuales en un índice diario. Una serie mensual muestra el
mismo valor durante semanas. Por eso cada respuesta indica la fecha del último
cambio real, no la del índice: sin ese dato, un dato de empleo de hace tres
semanas parece de hoy.

    python tools/query_metrics.py series
    python tools/query_metrics.py latest DGS10 cpi_yoy
    python tools/query_metrics.py on 2026-07-30 DGS30 Gold
    python tools/query_metrics.py range 2026-07-01 2026-08-10 SP500 Gold
    python tools/query_metrics.py compare DGS10 Gold --desde 2026-01-01
"""
import argparse
import re
import os
import sys

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(BASE, "fred_data.csv")

# Etiqueta y unidad de cada columna. Sin esto la salida son siglas de FRED.
LABELS = {
    "net_liq":   ("Liquidez neta", "T$"),
    "WALCL":     ("Balance de la Fed", "T$"),
    "WTREGEN":   ("TGA del Tesoro", "T$"),
    "RRPONTSYD": ("Repos inversos", "T$"),
    "M2SL":      ("M2", "T$"),
    "SP500":     ("S&P 500", ""),
    "MSCI_World":("MSCI World (URTH)", "$"),
    "Gold":      ("Oro", "$/oz"),
    "Bitcoin":   ("Bitcoin", "$"),
    "DGS2":      ("Treasury 2 años", "%"),
    "DGS10":     ("Treasury 10 años", "%"),
    "DGS30":     ("Treasury 30 años", "%"),
    "T10Y2Y":    ("Spread 10Y-2Y", "%"),
    "T10YIE":    ("Breakeven 10 años", "%"),
    "DFII10":    ("Tipo real 10 años (TIPS)", "%"),
    "DFF":       ("Fed Funds efectivo", "%"),
    "CPIAUCSL":  ("CPI (índice)", ""),
    "PCEPILFE":  ("PCE subyacente (índice)", ""),
    "CORESTICKM159SFRBATL": ("Sticky CPI de Atlanta", "%"),
    "PAYEMS":    ("Nóminas no agrícolas (nivel)", "miles"),
    "UNRATE":    ("Tasa de paro", "%"),
    "CIVPART":   ("Tasa de participación", "%"),
    "ICSA":      ("Peticiones de desempleo", ""),
    "DTWEXBGS":  ("Índice dólar amplio", ""),
    "DEXJPUS":   ("Dólar-Yen", ""),
    "BAMLH0A0HYM2": ("Spread High Yield", "%"),
    "DCOILWTICO":("WTI", "$/barril"),
    "payems_chg":("Nóminas, cambio mensual", "miles"),
    "cpi_yoy":   ("CPI interanual", "%"),
    "core_pce_yoy": ("PCE subyacente interanual", "%"),
}


def load() -> pd.DataFrame:
    if not os.path.exists(CSV):
        sys.exit(f"No existe {CSV}. Ejecuta antes fetch_liquidity.py.")
    return pd.read_csv(CSV, index_col=0, parse_dates=True).sort_index()


def label(col: str) -> str:
    return LABELS.get(col, (col, ""))[0]


def unit(col: str) -> str:
    return LABELS.get(col, (col, ""))[1]


def fmt(col: str, v: float) -> str:
    u = unit(col)
    if u == "%":
        return f"{v:.2f}%"
    if u == "T$":
        return f"${v:.2f}T"
    if u.startswith("$"):
        return f"${v:,.2f}"
    if u == "miles":
        return f"{v:+,.0f}k"
    return f"{v:,.2f}"


def last_change(s: pd.Series) -> pd.Timestamp | None:
    """Fecha del último cambio de valor, proxy de la última observación real.

    Necesario porque el CSV viene rellenado hacia delante: el último índice no
    dice nada sobre cuándo se publicó el dato.
    """
    s = s.dropna()
    if s.empty:
        return None
    changed = s[s != s.shift()]
    return changed.index[-1] if len(changed) else s.index[0]


def resolve(df: pd.DataFrame, cols: list[str]) -> list[str]:
    out = []
    for c in cols:
        if c in df.columns:
            out.append(c)
            continue
        # Búsqueda tolerante para no tener que recordar las siglas de FRED.
        # Por prioridad, porque la subcadena suelta produce colisiones absurdas:
        # "oro" aparece dentro de "Tesoro" y devolvía la TGA.
        low = c.lower()
        exact = [k for k in df.columns
                 if k.lower() == low or label(k).lower() == low]
        if exact:
            out.append(exact[0])
            continue
        # Palabra completa dentro de la etiqueta.
        word = [k for k in df.columns
                if low in re.findall(r"\w+", label(k).lower())]
        cand = word or [k for k in df.columns
                        if low in k.lower() or low in label(k).lower()]
        if len(cand) == 1:
            out.append(cand[0])
        elif cand:
            sys.exit(f"'{c}' es ambiguo: {', '.join(cand)}. Sé más específico.")
        else:
            sys.exit(f"'{c}' no existe. Usa 'series' para ver las disponibles.")
    return out


def cmd_series(df, _):
    print(f"{len(df.columns)} series · {df.index[0]:%Y-%m-%d} a {df.index[-1]:%Y-%m-%d}\n")
    for c in df.columns:
        when = last_change(df[c])
        s = df[c].dropna()
        val = fmt(c, s.iloc[-1]) if len(s) else "—"
        print(f"  {c:22s} {label(c):32s} {val:>14s}  (últ. cambio {when:%Y-%m-%d})")


def cmd_latest(df, a):
    for c in resolve(df, a.series):
        s = df[c].dropna()
        if s.empty:
            print(f"  {label(c)}: sin datos")
            continue
        when = last_change(df[c])
        stale = (df.index[-1] - when).days
        aviso = f"  [dato de hace {stale} días]" if stale > 7 else ""
        print(f"  {label(c):32s} {fmt(c, s.iloc[-1]):>14s}   ({when:%Y-%m-%d}){aviso}")


def cmd_on(df, a):
    fecha = pd.Timestamp(a.fecha)
    sub = df[df.index <= fecha]
    if sub.empty:
        sys.exit(f"No hay datos anteriores a {fecha:%Y-%m-%d}")
    print(f"Valores vigentes el {fecha:%Y-%m-%d} (fila {sub.index[-1]:%Y-%m-%d})\n")
    for c in resolve(df, a.series):
        s = sub[c].dropna()
        print(f"  {label(c):32s} {fmt(c, s.iloc[-1]) if len(s) else '—':>14s}")


def cmd_range(df, a):
    d = df[(df.index >= a.desde) & (df.index <= a.hasta)]
    if d.empty:
        sys.exit("Rango sin datos.")
    print(f"{d.index[0]:%Y-%m-%d} a {d.index[-1]:%Y-%m-%d}\n")
    for c in resolve(df, a.series):
        s = d[c].dropna()
        if s.empty:
            continue
        ini, fin = s.iloc[0], s.iloc[-1]
        pct = (fin / ini - 1) * 100 if ini else float("nan")
        print(f"  {label(c)}")
        print(f"     inicio {fmt(c, ini):>12s}   fin {fmt(c, fin):>12s}   "
              f"cambio {fin - ini:+.2f}" + (f" ({pct:+.1f}%)" if ini else ""))
        print(f"     mín    {fmt(c, s.min()):>12s} ({s.idxmin():%Y-%m-%d})   "
              f"máx {fmt(c, s.max()):>12s} ({s.idxmax():%Y-%m-%d})")


def cmd_compare(df, a):
    cols = resolve(df, [a.a, a.b])
    d = df[cols]
    if a.desde:
        d = d[d.index >= a.desde]
    d = d.dropna()
    if len(d) < 3:
        sys.exit("Datos insuficientes para comparar.")
    corr = d[cols[0]].corr(d[cols[1]])
    dcorr = d[cols[0]].diff().corr(d[cols[1]].diff())
    print(f"{label(cols[0])} vs {label(cols[1])}")
    print(f"  desde {d.index[0]:%Y-%m-%d} · {len(d)} observaciones\n")
    print(f"  correlación de niveles    : {corr:+.2f}")
    # La de variaciones es la que importa: dos series con tendencia siempre
    # correlacionan en niveles aunque no tengan relación alguna.
    print(f"  correlación de variaciones: {dcorr:+.2f}   <- la relevante")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("series", help="lista las series disponibles")

    q = sub.add_parser("latest", help="último valor de cada serie")
    q.add_argument("series", nargs="+")

    q = sub.add_parser("on", help="valor vigente en una fecha")
    q.add_argument("fecha")
    q.add_argument("series", nargs="+")

    q = sub.add_parser("range", help="recorrido entre dos fechas")
    q.add_argument("desde")
    q.add_argument("hasta")
    q.add_argument("series", nargs="+")

    q = sub.add_parser("compare", help="correlación entre dos series")
    q.add_argument("a")
    q.add_argument("b")
    q.add_argument("--desde", default=None)

    a = p.parse_args()
    df = load()
    {"series": cmd_series, "latest": cmd_latest, "on": cmd_on,
     "range": cmd_range, "compare": cmd_compare}[a.cmd](df, a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
