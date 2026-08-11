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
    python tools/query_metrics.py forward SP500 --cerca-maximo 1
"""
import argparse
import re
import os
import signal
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


def trading_days(s: pd.Series) -> pd.Series:
    """Quita el relleno hacia delante, dejando sólo sesiones con cotización.

    Sin esto los fines de semana cuentan como observaciones y '21 días' pasa a
    ser un mes de calendario en vez de un mes de mercado. Para una serie de
    precios el valor repetido es relleno; se pierde alguna sesión real que
    cerró plana, que es un coste despreciable frente a contar 8 sábados.
    """
    s = s.dropna()
    return s[s != s.shift()]


COND_RE = re.compile(r"^\s*([\w]+)\s*(<=|>=|<|>)\s*(-?[\d.]+)\s*$")


def build_condition(df: pd.DataFrame, s: pd.Series, a) -> tuple[pd.Series, str]:
    """Traduce los argumentos a una máscara booleana sobre el índice de s."""
    if a.cerca_maximo is not None:
        p = a.cerca_maximo
        return s >= s.cummax() * (1 - p / 100), f"a menos de {p:g}% del máximo histórico"
    if a.caida is not None:
        p = a.caida
        return s <= s.cummax() * (1 - p / 100), f"{p:g}% o más por debajo del máximo histórico"
    m = COND_RE.match(a.cuando)
    if not m:
        sys.exit("--cuando espera algo como 'T10Y2Y<0' o 'cpi_yoy>3'.")
    name, op, val = m.group(1), m.group(2), float(m.group(3))
    col = resolve(df, [name])[0]
    # ffill sobre la rejilla diaria completa antes de recortar: la condición usa
    # el valor vigente ese día, que para una serie mensual es el del último dato.
    other = df[col].ffill().reindex(s.index)
    mask = {"<": other < val, "<=": other <= val,
            ">": other > val, ">=": other >= val}[op]
    return mask.fillna(False), f"{label(col)} {op} {val:g}"


def cmd_forward(df, a):
    col = resolve(df, [a.serie])[0]
    s = trading_days(df[col])
    if len(s) < 150:
        sys.exit(f"{label(col)} sólo tiene {len(s)} sesiones: insuficiente.")

    mask, desc = build_condition(df, s, a)
    n_cond = int(mask.sum())
    if n_cond == 0:
        sys.exit(f"Ninguna sesión cumple '{desc}'.")

    horizontes = [int(h) for h in a.horizontes.split(",")]
    print(f"{label(col)} · condición: {desc}")
    print(f"histórico {s.index[0]:%Y-%m-%d} a {s.index[-1]:%Y-%m-%d} · "
          f"{len(s):,} sesiones con cotización")
    print(f"\n  {n_cond:,} sesiones la cumplen ({100 * n_cond / len(s):.0f}% del tiempo)\n")

    print(f"  {'horizonte':>12s} {'n':>6s} {'media':>8s} {'mediana':>8s} "
          f"{'positivo':>9s} {'peor':>8s}  │ {'base':>8s} {'positivo':>9s}")
    solape = []
    for h in horizontes:
        fwd = (s.shift(-h) / s - 1) * 100
        cond = fwd[mask].dropna()
        base = fwd.dropna()
        if cond.empty:
            print(f"  {h:>5d} sesiones {'—':>6s}  (sin ventanas completas)")
            continue
        print(f"  {h:>5d} sesiones {len(cond):>6,d} {cond.mean():>+7.1f}% "
              f"{cond.median():>+7.1f}% {100 * (cond > 0).mean():>8.0f}% "
              f"{cond.min():>+7.1f}%  │ {base.mean():>+7.1f}% "
              f"{100 * (base > 0).mean():>8.0f}%")
        solape.append((h, len(cond), len(cond) / h))

    # ---- Avisos. Van impresos siempre porque son justo lo que uno olvida
    # mencionar cuando la tabla de arriba le ha gustado.
    print("\n  Léelo con esto delante:")

    # 1. Ventanas solapadas. n=575 a 63 sesiones no son 575 datos independientes:
    #    cada uno comparte 62 días con el siguiente. Es el sesgo que más infla
    #    la sensación de solidez de una tabla como la de arriba.
    if solape:
        peor = max(solape, key=lambda t: t[0])
        print(f"  · Ventanas solapadas: a {peor[0]} sesiones, n={peor[1]:,} equivale a "
              f"~{peor[2]:.0f} periodos independientes, no a {peor[1]:,}.")

    # 2. Reparto por año: si la condición sólo se da en dos años alcistas, la
    #    estadística describe esos dos años, no una regularidad del mercado.
    por_año = mask[mask].groupby(mask[mask].index.year).size().sort_values(ascending=False)
    top = ", ".join(f"{y} ({c})" for y, c in por_año.head(3).items())
    print(f"  · Reparto por año, los tres mayores: {top}. "
          f"En total {len(por_año)} años distintos.")
    if por_año.iloc[0] > n_cond * 0.35:
        print(f"    ⚠ {por_año.index[0]} concentra el {100 * por_año.iloc[0] / n_cond:.0f}% "
              f"de los casos: esto describe ese año más que una regla general.")

    # 3. Longitud del histórico. Con pocos años no cabe un ciclo completo.
    años = (s.index[-1] - s.index[0]).days / 365.25
    if años < 15:
        print(f"  · El histórico son {años:.0f} años. No cabe un ciclo bajista largo, "
              f"así que estos números no dicen nada sobre uno.")


def main() -> int:
    # 'series | head' es el uso natural de esto, y sin esta línea corta la
    # tubería con un traceback de BrokenPipeError en vez de callarse.
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

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

    q = sub.add_parser(
        "forward", help="qué pasó después, históricamente, cuando se dio una condición",
        description="Frecuencia base: reparte las rentabilidades futuras entre las "
                    "sesiones que cumplen una condición y las compara con el conjunto. "
                    "Si las dos columnas se parecen, la condición no informa de nada.")
    q.add_argument("serie")
    cond = q.add_mutually_exclusive_group(required=True)
    cond.add_argument("--cerca-maximo", type=float, metavar="PCT",
                      help="sesiones a menos de PCT%% del máximo histórico")
    cond.add_argument("--caida", type=float, metavar="PCT",
                      help="sesiones PCT%% o más por debajo del máximo histórico")
    cond.add_argument("--cuando", metavar="EXPR",
                      help="condición sobre otra serie, p.ej. 'T10Y2Y<0'")
    q.add_argument("--horizontes", default="21,63,126",
                   help="sesiones hacia delante, separadas por comas (por defecto 21,63,126)")

    a = p.parse_args()
    df = load()
    {"series": cmd_series, "latest": cmd_latest, "on": cmd_on,
     "range": cmd_range, "compare": cmd_compare,
     "forward": cmd_forward}[a.cmd](df, a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
