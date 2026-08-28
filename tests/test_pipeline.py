#!/usr/bin/env python3
"""Humo de la tubería sin tocar FRED, YouTube ni Yahoo.

No valida los datos: valida que el código no se rompa y que las reglas que sí
se pueden comprobar sin red se cumplan. Existe porque nada verificaba los
cambios antes de mergear, y un identificador de serie mal escrito o una columna
perdida no se detectaban hasta la ejecución del día siguiente.

Uso:  python tests/test_pipeline.py
"""
import os
import sys
import types
import tempfile

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FALLO'}  {name}{'  — ' + detail if detail and not cond else ''}")
    if not cond:
        FAILURES.append(name)


# ── Dobles de las fuentes externas ───────────────────────────────────────────

DAILY = pd.bdate_range("2020-01-01", "2026-08-10")
MONTHLY = pd.date_range("2020-01-01", "2026-08-01", freq="MS")


class FakeFred:
    """Devuelve series con la frecuencia real de cada identificador."""

    def __init__(self, api_key=None, broken: set[str] | None = None):
        self.broken = broken or set()

    def get_series(self, sid, observation_start=None):
        if sid in self.broken:
            raise RuntimeError(f"{sid} no disponible")
        if sid in ("CPIAUCSL", "PCEPILFE"):
            # +0,25% mensual => ~3,04% interanual
            return pd.Series(100 * (1.0025 ** np.arange(len(MONTHLY))), index=MONTHLY)
        if sid == "PAYEMS":
            v = np.full(len(MONTHLY), 150_000.0)
            v[-1] = v[-2] - 23.0
            return pd.Series(v, index=MONTHLY)
        if sid in ("UNRATE", "CIVPART", "CORESTICKM159SFRBATL"):
            return pd.Series(np.linspace(3.5, 4.1, len(MONTHLY)), index=MONTHLY)
        if sid == "ICSA":
            idx = pd.date_range("2020-01-04", "2026-08-08", freq="W-SAT")
            return pd.Series(np.full(len(idx), 197_000.0), index=idx)
        base = {"WALCL": 6.5e6, "WTREGEN": 6e5, "RRPONTSYD": 1.0, "M2SL": 23_160.0}
        if sid in base:
            return pd.Series(np.full(len(DAILY), base[sid]), index=DAILY)
        return pd.Series(np.linspace(1.0, 5.21, len(DAILY)), index=DAILY)


def install_stubs():
    """Sustituye las dependencias de red por dobles.

    Se stubean también las de download_transcripts para que el humo pueda correr
    sin instalar el conjunto completo: sin esto, comprobar una función pura como
    resolve_exit_code exigiría tener youtube-transcript-api disponible.
    """
    yf = types.ModuleType("yfinance")
    yf.download = lambda ticker, **kw: pd.DataFrame(
        {"Close": np.linspace(3000, 7757, len(DAILY))}, index=DAILY)
    sys.modules["yfinance"] = yf

    fa = types.ModuleType("fredapi")
    fa.Fred = FakeFred
    sys.modules["fredapi"] = fa

    if "requests" not in sys.modules:
        try:
            import requests  # noqa: F401
        except ImportError:
            rq = types.ModuleType("requests")
            rq.RequestException = type("RequestException", (Exception,), {})
            rq.HTTPError = type("HTTPError", (rq.RequestException,), {})
            rq.get = lambda *a, **k: (_ for _ in ()).throw(rq.RequestException("sin red"))
            sys.modules["requests"] = rq

    try:
        import youtube_transcript_api  # noqa: F401
    except ImportError:
        yta = types.ModuleType("youtube_transcript_api")
        yta.YouTubeTranscriptApi = object
        err = types.ModuleType("youtube_transcript_api._errors")
        err.NoTranscriptFound = type("NoTranscriptFound", (Exception,), {})
        err.TranscriptsDisabled = type("TranscriptsDisabled", (Exception,), {})
        prox = types.ModuleType("youtube_transcript_api.proxies")
        prox.GenericProxyConfig = object
        prox.WebshareProxyConfig = object
        yta._errors, yta.proxies = err, prox
        sys.modules["youtube_transcript_api"] = yta
        sys.modules["youtube_transcript_api._errors"] = err
        sys.modules["youtube_transcript_api.proxies"] = prox


# ── Comprobaciones ───────────────────────────────────────────────────────────

def test_fetch_liquidity(tmp: str) -> None:
    print("\nfetch_liquidity")
    import fetch_liquidity as fl

    fl.DOCS_DIR = os.path.join(tmp, "docs")
    os.makedirs(fl.DOCS_DIR, exist_ok=True)
    fl.DATA_CSV = os.path.join(tmp, "data.csv")
    fl.CHART_PNG = os.path.join(fl.DOCS_DIR, "c.png")
    fl.CHART_3M_PNG = os.path.join(fl.DOCS_DIR, "c3m.png")
    fl.MACRO_PNG = os.path.join(fl.DOCS_DIR, "macro.png")
    fl.HTML_FILE = os.path.join(fl.DOCS_DIR, "index.html")
    fl.load_api_key = lambda: "fake"

    # Toda serie declarada debe tener etiqueta y frecuencia: evita entradas a medias.
    check("FRED_MACRO bien formado",
          all(isinstance(v, tuple) and len(v) == 2 for v in fl.FRED_MACRO.values()))

    # Ninguna serie macro puede colarse en el grupo que reescala a trillones.
    check("sin solape entre FRED_SERIES y FRED_MACRO",
          not (set(fl.FRED_SERIES) & set(fl.FRED_MACRO)))

    fred = FakeFred()
    macro = fl.fetch_fred_macro(fred)

    check("cpi_yoy sobre frecuencia nativa",
          abs(macro["cpi_yoy"].dropna().iloc[-1] - 3.04) < 0.05,
          f"obtenido {macro['cpi_yoy'].dropna().iloc[-1]:.2f}")
    check("payems_chg es la variación mensual",
          abs(macro["payems_chg"].dropna().iloc[-1] + 23) < 0.01)
    check("LAST_OBS guarda la fecha real de una mensual",
          fl.LAST_OBS.get("payems_chg") == MONTHLY[-1])

    # Una serie caída no puede tumbar las demás.
    macro_roto = fl.fetch_fred_macro(FakeFred(broken={"DGS10", "UNRATE"}))
    check("una serie caída no aborta el resto",
          "DGS10" not in macro_roto.columns and "DGS2" in macro_roto.columns)

    # Histórico previo con solo las columnas antiguas: no debe perderlas.
    viejo = pd.DataFrame(
        {c: 1.0 for c in ("WALCL", "WTREGEN", "RRPONTSYD", "M2SL", "net_liq", "SP500")},
        index=DAILY[:100])
    viejo.to_csv(fl.DATA_CSV)

    df_fred = fl.fetch_fred(fred).join(macro, how="outer")
    df = fl.update_csv(df_fred, fl.fetch_markets())

    check("no se pierden columnas del histórico previo",
          all(c in df.columns for c in viejo.columns))
    check("las columnas macro quedan pobladas",
          all(df[c].notna().any() for c in macro.columns))
    check("net_liq no se reescala por error",
          5.0 < df["net_liq"].dropna().iloc[-1] < 6.5)

    fl.plot(df)
    fl.plot_zoom(df)
    ok = fl.plot_macro(df)
    fl.generate_html(df, has_macro=ok)
    check("se generan ambas gráficas de liquidez",
          os.path.exists(fl.CHART_PNG) and os.path.exists(fl.CHART_3M_PNG))
    check("se genera la gráfica macro", ok and os.path.exists(fl.MACRO_PNG))

    # Sin columnas macro el HTML no puede enlazar una imagen inexistente.
    os.remove(fl.MACRO_PNG)
    solo_liq = df[["net_liq", "M2SL", "RRPONTSYD", "SP500"]]
    sin_macro = fl.plot_macro(solo_liq)
    fl.generate_html(solo_liq, has_macro=sin_macro)
    html = open(fl.HTML_FILE, encoding="utf-8").read()
    check("sin datos macro no se dibuja la gráfica", sin_macro is False)
    check("sin datos macro el HTML no enlaza la imagen",
          "macro_chart.png" not in html)


def test_exit_code() -> None:
    print("\ndownload_transcripts")
    import download_transcripts as dt

    check("nada descargado con errores -> fallo",
          dt.resolve_exit_code(0, 0, 27) == 1)
    check("nada descargado sin errores -> éxito",
          dt.resolve_exit_code(0, 31, 0) == 0)
    check("descarga parcial con errores -> éxito",
          dt.resolve_exit_code(5, 10, 3) == 0)
    check("descarga limpia -> éxito",
          dt.resolve_exit_code(7, 20, 0) == 0)

    # El sufijo -rotate es lo que distingue el gateway rotativo del proxy
    # directo. Sin él, Webshare devuelve 407 con credenciales válidas.
    check("se añade el sufijo -rotate al usuario",
          dt.rotating_username("abc123") == "abc123-rotate")
    check("no se duplica si ya lo trae",
          dt.rotating_username("abc123-rotate") == "abc123-rotate")

    # Un canal cuyo feed falla debe contar como error. Si devuelve 0 errores,
    # once canales caídos suman 0 y la ejecución sale en verde sin datos.
    dt.get_recent_videos = lambda *a, **k: []
    ok, skip, err, _, errs = dt.process_channel({"name": "X", "url": "u"})
    check("un canal sin vídeos cuenta como error",
          (ok, skip, err) == (0, 0, 1) and len(errs) == 1,
          f"devolvió {(ok, skip, err)}")
    check("y por tanto la ejecución falla",
          dt.resolve_exit_code(0, 0, err) == 1)


def test_channels() -> None:
    print("\nchannels.csv")
    import download_transcripts as dt

    canales = dt.load_channels(os.path.join(BASE, "channels.csv"))
    check("se cargan canales", len(canales) > 0, f"{len(canales)} cargados")
    check("todos tienen nombre y URL",
          all(c.get("name") and c.get("url") for c in canales))
    check("nombres sin guiones",
          all("-" not in c["name"] for c in canales),
          "un guion rompería el parseo de fecha del nombre de fichero")
    check("nombres únicos",
          len({c["name"] for c in canales}) == len(canales))


def test_query_metrics() -> None:
    print("\nquery_metrics")
    import argparse

    sys.path.insert(0, os.path.join(BASE, "tools"))
    import query_metrics as qm

    # El CSV va rellenado hacia delante para meter series mensuales en un índice
    # diario. Si eso llega a los cálculos, los fines de semana cuentan como
    # sesiones y un horizonte de 21 pasa a ser mes de calendario, no de mercado.
    idx = pd.date_range("2026-01-01", periods=6, freq="D")
    s = pd.Series([100.0, 100.0, 101.0, 101.0, 101.0, 102.0], index=idx)
    check("trading_days quita el relleno hacia delante",
          list(qm.trading_days(s).values) == [100.0, 101.0, 102.0])
    check("trading_days conserva la primera observación",
          qm.trading_days(s).index[0] == idx[0])

    # last_change es lo que evita presentar un dato de hace seis semanas como
    # si fuera de hoy.
    check("last_change ignora la cola rellenada", qm.last_change(s) == idx[5])

    df = pd.DataFrame({
        "SP500": [10.0, 11.0, 12.0, 9.0, 13.0],
        "T10Y2Y": [0.5, -0.2, -0.3, 0.1, 0.4],
    }, index=pd.date_range("2026-01-01", periods=5, freq="D"))

    a = argparse.Namespace(cerca_maximo=1.0, caida=None, cuando=None)
    mask, _ = qm.build_condition(df, df["SP500"], a)
    # Máximo acumulado: 10, 11, 12, 12, 13. Sólo la fila de 9 queda a más del 1%.
    check("--cerca-maximo marca las sesiones en máximos",
          list(mask.values) == [True, True, True, False, True])

    a = argparse.Namespace(cerca_maximo=None, caida=20.0, cuando=None)
    mask, _ = qm.build_condition(df, df["SP500"], a)
    check("--caida marca sólo las que están un 20% abajo",
          list(mask.values) == [False, False, False, True, False])

    a = argparse.Namespace(cerca_maximo=None, caida=None, cuando="T10Y2Y<0")
    mask, _ = qm.build_condition(df, df["SP500"], a)
    check("--cuando aplica la condición de otra serie",
          list(mask.values) == [False, True, True, False, False])

    # Una expresión mal escrita tiene que parar, no colarse como "nada cumple"
    # y devolver una tabla vacía que parecería un resultado.
    a = argparse.Namespace(cerca_maximo=None, caida=None, cuando="chorrada")
    try:
        qm.build_condition(df, df["SP500"], a)
        ok = False
    except SystemExit:
        ok = True
    check("una condición inválida aborta en vez de no marcar nada", ok)


def main() -> int:
    install_stubs()
    with tempfile.TemporaryDirectory() as tmp:
        test_fetch_liquidity(tmp)
    test_exit_code()
    test_channels()
    test_query_metrics()

    print()
    if FAILURES:
        print(f"FALLARON {len(FAILURES)}: " + ", ".join(FAILURES))
        return 1
    print("Todo correcto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
