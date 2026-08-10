#!/usr/bin/env python3
"""
Descarga diaria de liquidez global (FRED) + mercados (yfinance) y genera gráfica.

FRED (liquidez, se reescalan a trillones):
  WALCL      — Balance sheet Fed    (millones USD)
  WTREGEN    — TGA Tesoro EEUU      (millones USD)
  RRPONTSYD  — Reverse Repos        (billones USD)
  M2SL       — Oferta monetaria M2  (billones USD)

FRED (macro, en unidad nativa — ver FRED_MACRO):
  Curva      — DGS2, DGS10, DGS30, T10Y2Y, T10YIE, DFII10, DFF
  Inflación  — CPIAUCSL, PCEPILFE, CORESTICKM159SFRBATL
  Empleo     — PAYEMS, UNRATE, CIVPART, ICSA
  Otros      — DTWEXBGS, DEXJPUS, BAMLH0A0HYM2, DCOILWTICO
  Derivadas  — payems_chg, cpi_yoy, core_pce_yoy

yfinance:
  ^GSPC      — SP500
  GC=F       — Oro (futuros)
  BTC-USD    — Bitcoin

Net Liquidity (trillones) = WALCL/1e6 - WTREGEN/1e6 - RRPONTSYD/1e3

API key gratuita: https://fred.stlouisfed.org/docs/api/api_key.html
Añade al archivo .env:  FRED_API_KEY=tu_clave
"""

import os
import warnings
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import yfinance as yf
from fredapi import Fred
from datetime import datetime

warnings.filterwarnings("ignore")

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR      = os.path.join(BASE_DIR, "docs")
DATA_CSV      = os.path.join(BASE_DIR, "fred_data.csv")
CHART_PNG     = os.path.join(DOCS_DIR, "liquidity_chart.png")
CHART_3M_PNG  = os.path.join(DOCS_DIR, "liquidity_chart_3m.png")
MACRO_PNG     = os.path.join(DOCS_DIR, "macro_chart.png")
HTML_FILE     = os.path.join(DOCS_DIR, "index.html")
ENV_FILE      = os.path.join(BASE_DIR, ".env")
START_DATE    = "2020-01-01"
CHART_YEARS   = 3
CHART_MONTHS  = 3

os.makedirs(DOCS_DIR, exist_ok=True)

FRED_SERIES = {
    "WALCL":     "Fed Balance Sheet (M USD)",
    "WTREGEN":   "TGA Tesoro (M USD)",
    "RRPONTSYD": "Reverse Repos (B USD)",
    "M2SL":      "M2 (B USD)",
}

# Series macro adicionales. A diferencia de FRED_SERIES, estas NO se reescalan:
# FRED ya las entrega en su unidad natural (% para tipos, índice para precios).
# freq indica la frecuencia nativa y se usa para calcular derivadas (YoY, cambio
# mensual) sobre la serie original, antes de reindexar a diario.
FRED_MACRO = {
    # Curva de tipos
    "DGS2":                 ("Treasury 2Y (%)",            "D"),
    "DGS10":                ("Treasury 10Y (%)",           "D"),
    "DGS30":                ("Treasury 30Y (%)",           "D"),
    "T10Y2Y":               ("Spread 10Y-2Y (%)",          "D"),
    "T10YIE":               ("Breakeven 10Y (%)",          "D"),
    "DFII10":               ("Tipo real 10Y / TIPS (%)",   "D"),
    "DFF":                  ("Fed Funds efectivo (%)",     "D"),
    # Inflación
    "CPIAUCSL":             ("CPI general (índice)",       "M"),
    "PCEPILFE":             ("PCE subyacente (índice)",    "M"),
    "CORESTICKM159SFRBATL": ("Sticky CPI Atlanta (%)",     "M"),
    # Empleo
    "PAYEMS":               ("Nóminas no agrícolas (miles)", "M"),
    "UNRATE":               ("Tasa de paro (%)",           "M"),
    "CIVPART":              ("Tasa de participación (%)",  "M"),
    "ICSA":                 ("Peticiones de desempleo",    "W"),
    # Divisas, crédito y materias primas
    "DTWEXBGS":             ("Índice dólar amplio",        "D"),
    "DEXJPUS":              ("Dólar-Yen",                  "D"),
    "BAMLH0A0HYM2":         ("Spread High Yield (%)",      "D"),
    "DCOILWTICO":           ("WTI ($/barril)",             "D"),
}

# Fecha de la última observación real de cada serie macro, antes del ffill.
# La rellena fetch_fred_macro y la consume print_macro_summary.
LAST_OBS: dict[str, pd.Timestamp] = {}

# Derivadas que se calculan sobre la frecuencia nativa (ver fetch_fred_macro).
DERIVED_LABELS = {
    "payems_chg":   "Cambio mensual de nóminas (miles)",
    "cpi_yoy":      "CPI interanual (%)",
    "core_pce_yoy": "PCE subyacente interanual (%)",
}

MARKET_TICKERS = {
    "SP500":      "^GSPC",
    "MSCI_World": "URTH",    # iShares MSCI World ETF
    "Gold":       "GC=F",
    "Bitcoin":    "BTC-USD",
}

# ── API key ───────────────────────────────────────────────────────────────────

def load_api_key() -> str:
    key = os.environ.get("FRED_API_KEY", "")
    if key:
        return key
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE).readlines():
            if line.strip().startswith("FRED_API_KEY"):
                return line.split("=", 1)[-1].strip()
    raise SystemExit(
        "\n⚠️  No se encontró FRED_API_KEY.\n"
        "   Crea el archivo .env con:  FRED_API_KEY=tu_clave\n"
    )

# ── Fetch FRED ────────────────────────────────────────────────────────────────

def fetch_fred(fred: Fred) -> pd.DataFrame:
    frames = []
    for sid in FRED_SERIES:
        s = fred.get_series(sid, observation_start=START_DATE)
        s.name = sid
        frames.append(s)
    df = pd.concat(frames, axis=1).sort_index().ffill()
    # convertir a trillones USD
    df["WALCL"]     = df["WALCL"]     / 1_000_000
    df["WTREGEN"]   = df["WTREGEN"]   / 1_000_000
    df["RRPONTSYD"] = df["RRPONTSYD"] / 1_000
    df["M2SL"]      = df["M2SL"]      / 1_000
    df["net_liq"]   = df["WALCL"] - df["WTREGEN"] - df["RRPONTSYD"]
    return df

# ── Fetch FRED macro ──────────────────────────────────────────────────────────

def fetch_fred_macro(fred: Fred) -> pd.DataFrame:
    """Descarga tipos, inflación, empleo, divisas y crédito.

    Las derivadas (interanuales, cambio mensual) se calculan sobre la serie en
    su frecuencia nativa. Hacerlo después de reindexar a diario daría resultados
    sin sentido, porque el ffill repite el mismo valor durante todo el mes.

    Un fallo en una serie no aborta el resto: esto corre a diario en CI y es
    preferible publicar el dashboard incompleto a no publicarlo.
    """
    LAST_OBS.clear()
    raw: dict[str, pd.Series] = {}
    for sid in FRED_MACRO:
        try:
            s = fred.get_series(sid, observation_start=START_DATE).dropna()
            if s.empty:
                print(f"  [FRED] {sid}: sin datos")
                continue
            raw[sid] = s
            LAST_OBS[sid] = pd.Timestamp(s.index[-1])
        except Exception as exc:
            print(f"  [FRED] {sid} error: {exc}")

    if not raw:
        return pd.DataFrame()

    derived: dict[str, pd.Series] = {}
    if "PAYEMS" in raw:
        # El titular de nóminas es la variación mensual, no el nivel.
        derived["payems_chg"] = raw["PAYEMS"].diff()
    if "CPIAUCSL" in raw:
        derived["cpi_yoy"] = raw["CPIAUCSL"].pct_change(periods=12) * 100
    if "PCEPILFE" in raw:
        derived["core_pce_yoy"] = raw["PCEPILFE"].pct_change(periods=12) * 100

    for name, src in (("payems_chg", "PAYEMS"), ("cpi_yoy", "CPIAUCSL"),
                      ("core_pce_yoy", "PCEPILFE")):
        if name in derived:
            LAST_OBS[name] = LAST_OBS[src]

    frames = []
    for name, s in {**raw, **derived}.items():
        s = s.copy()
        s.name = name
        frames.append(s)

    df = pd.concat(frames, axis=1).sort_index()
    df.index = pd.to_datetime(df.index)
    return df.ffill()

# ── Fetch yfinance ────────────────────────────────────────────────────────────

def fetch_markets() -> pd.DataFrame:
    frames = []
    for name, ticker in MARKET_TICKERS.items():
        try:
            raw = yf.download(ticker, start=START_DATE, auto_adjust=True, progress=False)
            if raw.empty:
                continue
            s = raw["Close"].squeeze()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            s.name = name
            frames.append(s)
            print(f"  [yfinance] {name:8s} último: {s.dropna().index[-1]:%Y-%m-%d}  {s.dropna().iloc[-1]:,.2f}")
        except Exception as e:
            print(f"  [yfinance] {name} error: {e}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1).sort_index()

# ── CSV ───────────────────────────────────────────────────────────────────────

def update_csv(df_fred: pd.DataFrame, df_mkt: pd.DataFrame) -> pd.DataFrame:
    # unir en un único DataFrame diario
    df_new = df_fred.join(df_mkt, how="outer").ffill()

    if os.path.exists(DATA_CSV):
        df_old = pd.read_csv(DATA_CSV, index_col=0, parse_dates=True)
        df = pd.concat([df_old, df_new[~df_new.index.isin(df_old.index)]]).sort_index()
        df.update(df_new)
    else:
        df = df_new

    df.to_csv(DATA_CSV)
    return df

# ── Gráfica ───────────────────────────────────────────────────────────────────

BG      = "#0f1117"
GRID    = "#1e1e2e"
LABEL   = "#888888"

COLORS = {
    "net_liq":   "#00d4ff",
    "SP500":     "#00e676",
    "MSCI_World":"#b388ff",
    "RRPONTSYD": "#ff6b6b",
    "M2SL":      "#f7b731",
    "Gold":      "#ffd700",
    "Bitcoin":   "#ff9500",
}

def style_ax(ax, show_xticks=False, locator=None, date_fmt="%b %Y"):
    ax.set_facecolor(BG)
    ax.tick_params(colors=LABEL, labelsize=8.5)
    for spine in ax.spines.values():
        spine.set_color("#2a2a3e")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.grid(axis="x", color=GRID, linewidth=0.3)
    ax.xaxis.set_major_locator(locator or mdates.MonthLocator(interval=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter(date_fmt))
    if show_xticks:
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", color=LABEL)
    else:
        ax.tick_params(labelbottom=False)

def fmt_T(x, _):
    return f"${x:.1f}T"

def annotate_last(ax, x, y, text, color, offset=(4, 0)):
    ax.annotate(text, xy=(x, y), xytext=offset,
                textcoords="offset points",
                color=color, fontsize=8.5, fontweight="bold", va="center")

def plot(df: pd.DataFrame):
    cutoff = pd.Timestamp.today() - pd.DateOffset(years=CHART_YEARS)
    d = df[df.index >= cutoff].copy()

    fig, axes = plt.subplots(
        4, 1, figsize=(15, 12),
        gridspec_kw={"height_ratios": [3, 1.8, 1.8, 2.2]},
        facecolor=BG,
    )
    fig.subplots_adjust(hspace=0.06, left=0.07, right=0.93, top=0.94, bottom=0.07)

    last_date = d.index[-1]

    # ── Panel 1: Net Liquidity + SP500 ──────────────────────────────────────
    ax0 = axes[0]
    style_ax(ax0)

    # Net Liquidity (izquierda)
    nl = d["net_liq"].dropna()
    ax0.plot(nl.index, nl, color=COLORS["net_liq"], linewidth=1.8, label="Net Liquidity", zorder=3)
    ax0.fill_between(nl.index, nl, alpha=0.12, color=COLORS["net_liq"])
    ax0.set_ylabel("Net Liquidity (T$)", color=LABEL, fontsize=9)
    ax0.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_T))
    annotate_last(ax0, nl.index[-1], nl.iloc[-1], f"${nl.iloc[-1]:.2f}T", COLORS["net_liq"])

    # SP500 + MSCI World normalizados a 100 (derecha)
    ax0r = ax0.twinx()
    ax0r.set_ylabel("Índice (base=100)", color=LABEL, fontsize=9)
    ax0r.tick_params(colors=LABEL, labelsize=8.5)
    ax0r.spines[:].set_color("#2a2a3e")
    ax0r.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}"))

    indices_legend = []
    for key, ls in [("SP500", "--"), ("MSCI_World", ":")]:
        if key not in d.columns:
            continue
        s = d[key].dropna()
        base = s.iloc[0]
        idx = (s / base) * 100
        pct = (s.iloc[-1] / base - 1) * 100
        label = f"{key.replace('_',' ')}  {s.iloc[-1]:,.0f}  ({pct:+.0f}%)"
        ax0r.plot(idx.index, idx, color=COLORS[key], linewidth=1.4,
                  alpha=0.85, linestyle=ls, label=label)
        annotate_last(ax0r, idx.index[-1], idx.iloc[-1],
                      f"  {idx.iloc[-1]:.0f}", COLORS[key])
        indices_legend.append(plt.Line2D([0],[0], color=COLORS[key], lw=1.5, ls=ls, label=label))

    # leyenda combinada
    lines0 = [plt.Line2D([0], [0], color=COLORS["net_liq"], lw=2, label="Net Liquidity")]
    ax0.legend(handles=lines0 + indices_legend, loc="upper left",
               facecolor="#1a1a2e", labelcolor="white", fontsize=8.5, framealpha=0.7)

    ax0.set_title(
        f"Liquidez Global & Mercados  ·  Actualizado {last_date:%d %b %Y}",
        color="white", fontsize=13, pad=10, loc="left", fontweight="bold",
    )

    # ── Panel 2: Reverse Repos ───────────────────────────────────────────────
    ax1 = axes[1]
    style_ax(ax1)
    rrp = d["RRPONTSYD"].dropna()
    ax1.plot(rrp.index, rrp, color=COLORS["RRPONTSYD"], linewidth=1.5, label="Reverse Repos (RRP)")
    ax1.fill_between(rrp.index, rrp, alpha=0.15, color=COLORS["RRPONTSYD"])
    ax1.set_ylabel("T$", color=LABEL, fontsize=9)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_T))
    annotate_last(ax1, rrp.index[-1], rrp.iloc[-1], f"${rrp.iloc[-1]:.3f}T", COLORS["RRPONTSYD"])
    ax1.legend(loc="upper right", facecolor="#1a1a2e", labelcolor="white", fontsize=8.5, framealpha=0.7)

    # ── Panel 3: M2 ──────────────────────────────────────────────────────────
    ax2 = axes[2]
    style_ax(ax2)
    m2 = d["M2SL"].dropna()
    ax2.plot(m2.index, m2, color=COLORS["M2SL"], linewidth=1.5, label="M2 (oferta monetaria)")
    ax2.fill_between(m2.index, m2, alpha=0.15, color=COLORS["M2SL"])
    ax2.set_ylabel("T$", color=LABEL, fontsize=9)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_T))
    annotate_last(ax2, m2.index[-1], m2.iloc[-1], f"${m2.iloc[-1]:.2f}T", COLORS["M2SL"])
    ax2.legend(loc="upper left", facecolor="#1a1a2e", labelcolor="white", fontsize=8.5, framealpha=0.7)

    # ── Panel 4: Oro + Bitcoin (indexados a 100) ──────────────────────────────
    ax3 = axes[3]
    style_ax(ax3, show_xticks=True)

    legends4 = []
    for asset, color in [("Gold", COLORS["Gold"]), ("Bitcoin", COLORS["Bitcoin"])]:
        if asset not in d.columns:
            continue
        s = d[asset].dropna()
        base = s.iloc[0]
        indexed = (s / base) * 100
        ax3.plot(indexed.index, indexed, color=color, linewidth=1.5, label=asset)
        ax3.fill_between(indexed.index, indexed, 100, alpha=0.08, color=color)
        val_last = s.iloc[-1]
        pct = (s.iloc[-1] / base - 1) * 100
        label = f"${val_last:,.0f}  ({pct:+.0f}%)"
        annotate_last(ax3, indexed.index[-1], indexed.iloc[-1], f"  {label}", color)
        legends4.append(plt.Line2D([0], [0], color=color, lw=1.5, label=f"{asset}  {label}"))

    ax3.axhline(100, color="#444455", linewidth=0.8, linestyle=":")
    ax3.set_ylabel("Índice (base=100)", color=LABEL, fontsize=9)
    ax3.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}"))
    if legends4:
        ax3.legend(handles=legends4, loc="upper left",
                   facecolor="#1a1a2e", labelcolor="white", fontsize=8.5, framealpha=0.7)

    fig.text(
        0.5, 0.01,
        "Net Liquidity = Fed Balance − TGA − RRP  ·  Fuente: FRED (St. Louis Fed) + Yahoo Finance",
        ha="center", color="#444455", fontsize=8,
    )

    plt.savefig(CHART_PNG, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"[OK] Gráfica guardada → {CHART_PNG}")


def plot_zoom(df: pd.DataFrame):
    """Gráfica de alta resolución para los últimos CHART_MONTHS meses."""
    cutoff = pd.Timestamp.today() - pd.DateOffset(months=CHART_MONTHS)
    d = df[df.index >= cutoff].copy()

    biweekly = mdates.WeekdayLocator(byweekday=0, interval=2)  # cada 2 lunes
    date_fmt  = "%d %b"

    fig, axes = plt.subplots(
        4, 1, figsize=(15, 12),
        gridspec_kw={"height_ratios": [3, 1.8, 1.8, 2.2]},
        facecolor=BG,
    )
    fig.subplots_adjust(hspace=0.06, left=0.07, right=0.93, top=0.94, bottom=0.09)

    last_date = d.index[-1]

    # ── Panel 1: Net Liquidity + SP500 ──────────────────────────────────────
    ax0 = axes[0]
    style_ax(ax0, locator=biweekly, date_fmt=date_fmt)

    nl = d["net_liq"].dropna()
    ax0.plot(nl.index, nl, color=COLORS["net_liq"], linewidth=2, label="Net Liquidity", zorder=3)
    ax0.fill_between(nl.index, nl, alpha=0.15, color=COLORS["net_liq"])
    ax0.set_ylabel("Net Liquidity (T$)", color=LABEL, fontsize=9)
    ax0.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_T))
    annotate_last(ax0, nl.index[-1], nl.iloc[-1], f"${nl.iloc[-1]:.2f}T", COLORS["net_liq"])

    ax0r = ax0.twinx()
    ax0r.set_ylabel("Índice (base=100)", color=LABEL, fontsize=9)
    ax0r.tick_params(colors=LABEL, labelsize=8.5)
    ax0r.spines[:].set_color("#2a2a3e")
    ax0r.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}"))

    indices_legend = []
    for key, ls in [("SP500", "--"), ("MSCI_World", ":")]:
        if key not in d.columns:
            continue
        s = d[key].dropna()
        base = s.iloc[0]
        idx  = (s / base) * 100
        pct  = (s.iloc[-1] / base - 1) * 100
        label = f"{key.replace('_',' ')}  {s.iloc[-1]:,.0f}  ({pct:+.1f}%)"
        ax0r.plot(idx.index, idx, color=COLORS[key], linewidth=1.6,
                  alpha=0.9, linestyle=ls, label=label)
        annotate_last(ax0r, idx.index[-1], idx.iloc[-1],
                      f"  {idx.iloc[-1]:.0f}", COLORS[key])
        indices_legend.append(plt.Line2D([0], [0], color=COLORS[key], lw=1.5, ls=ls, label=label))

    lines0 = [plt.Line2D([0], [0], color=COLORS["net_liq"], lw=2, label="Net Liquidity")]
    ax0.legend(handles=lines0 + indices_legend, loc="upper left",
               facecolor="#1a1a2e", labelcolor="white", fontsize=8.5, framealpha=0.7)

    ax0.set_title(
        f"Liquidez Global & Mercados — Últimos {CHART_MONTHS} meses  ·  {last_date:%d %b %Y}",
        color="white", fontsize=13, pad=10, loc="left", fontweight="bold",
    )

    # ── Panel 2: Reverse Repos ───────────────────────────────────────────────
    ax1 = axes[1]
    style_ax(ax1, locator=biweekly, date_fmt=date_fmt)
    rrp = d["RRPONTSYD"].dropna()
    ax1.plot(rrp.index, rrp, color=COLORS["RRPONTSYD"], linewidth=1.8, label="Reverse Repos (RRP)")
    ax1.fill_between(rrp.index, rrp, alpha=0.18, color=COLORS["RRPONTSYD"])
    ax1.set_ylabel("T$", color=LABEL, fontsize=9)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_T))
    annotate_last(ax1, rrp.index[-1], rrp.iloc[-1], f"${rrp.iloc[-1]:.3f}T", COLORS["RRPONTSYD"])
    ax1.legend(loc="upper right", facecolor="#1a1a2e", labelcolor="white", fontsize=8.5, framealpha=0.7)

    # ── Panel 3: M2 ──────────────────────────────────────────────────────────
    ax2 = axes[2]
    style_ax(ax2, locator=biweekly, date_fmt=date_fmt)
    m2 = d["M2SL"].dropna()
    ax2.plot(m2.index, m2, color=COLORS["M2SL"], linewidth=1.8, label="M2 (oferta monetaria)")
    ax2.fill_between(m2.index, m2, alpha=0.18, color=COLORS["M2SL"])
    ax2.set_ylabel("T$", color=LABEL, fontsize=9)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_T))
    annotate_last(ax2, m2.index[-1], m2.iloc[-1], f"${m2.iloc[-1]:.2f}T", COLORS["M2SL"])
    ax2.legend(loc="upper left", facecolor="#1a1a2e", labelcolor="white", fontsize=8.5, framealpha=0.7)

    # ── Panel 4: Oro + Bitcoin (indexados a 100) ─────────────────────────────
    ax3 = axes[3]
    style_ax(ax3, show_xticks=True, locator=biweekly, date_fmt=date_fmt)

    legends4 = []
    for asset, color in [("Gold", COLORS["Gold"]), ("Bitcoin", COLORS["Bitcoin"])]:
        if asset not in d.columns:
            continue
        s = d[asset].dropna()
        base = s.iloc[0]
        indexed = (s / base) * 100
        ax3.plot(indexed.index, indexed, color=color, linewidth=1.8, label=asset)
        ax3.fill_between(indexed.index, indexed, 100, alpha=0.1, color=color)
        val_last = s.iloc[-1]
        pct = (s.iloc[-1] / base - 1) * 100
        label = f"${val_last:,.0f}  ({pct:+.1f}%)"
        annotate_last(ax3, indexed.index[-1], indexed.iloc[-1], f"  {label}", color)
        legends4.append(plt.Line2D([0], [0], color=color, lw=1.5, label=f"{asset}  {label}"))

    ax3.axhline(100, color="#444455", linewidth=0.8, linestyle=":")
    ax3.set_ylabel("Índice (base=100)", color=LABEL, fontsize=9)
    ax3.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}"))
    if legends4:
        ax3.legend(handles=legends4, loc="upper left",
                   facecolor="#1a1a2e", labelcolor="white", fontsize=8.5, framealpha=0.7)

    fig.text(
        0.5, 0.01,
        "Net Liquidity = Fed Balance − TGA − RRP  ·  Fuente: FRED (St. Louis Fed) + Yahoo Finance",
        ha="center", color="#444455", fontsize=8,
    )

    plt.savefig(CHART_3M_PNG, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"[OK] Gráfica 3m guardada → {CHART_3M_PNG}")

# ── Gráfica macro ─────────────────────────────────────────────────────────────

MACRO_COLORS = {
    "DGS2": "#00e676", "DGS10": "#00d4ff", "DGS30": "#b388ff", "T10Y2Y": "#ff6b6b",
    "cpi_yoy": "#f7b731", "core_pce_yoy": "#ff9500", "CORESTICKM159SFRBATL": "#b388ff",
    "payems_chg": "#00e676", "UNRATE": "#ff6b6b",
    "DTWEXBGS": "#00e676", "DEXJPUS": "#b388ff",
    "BAMLH0A0HYM2": "#ff6b6b", "DCOILWTICO": "#f7b731",
}


def _has(d: pd.DataFrame, *cols: str) -> bool:
    return all(c in d.columns and d[c].notna().any() for c in cols)


def _legend(ax, loc="upper left"):
    ax.legend(loc=loc, facecolor="#1a1a2e", labelcolor="white",
              fontsize=8.5, framealpha=0.7)


def _p_curva(ax, d):
    for col, label in (("DGS2", "2 años"), ("DGS10", "10 años"), ("DGS30", "30 años")):
        if not _has(d, col):
            continue
        s = d[col].dropna()
        ax.plot(s.index, s, color=MACRO_COLORS[col], linewidth=1.5,
                label=f"{label}  {s.iloc[-1]:.2f}%")
    ax.set_ylabel("Rendimiento (%)", color=LABEL, fontsize=9)
    _legend(ax)

    if _has(d, "T10Y2Y"):
        # El signo del spread es la señal: por debajo de cero, curva invertida.
        axr = ax.twinx()
        s = d["T10Y2Y"].dropna()
        axr.fill_between(s.index, s, 0, alpha=0.07,
                         color=MACRO_COLORS["T10Y2Y"], zorder=0)
        axr.plot(s.index, s, color=MACRO_COLORS["T10Y2Y"], linewidth=1.2,
                 alpha=0.9, zorder=1)
        axr.axhline(0, color="#666677", linewidth=0.8, linestyle=":")
        axr.set_ylabel("Spread 10Y-2Y (%)", color=LABEL, fontsize=9)
        axr.tick_params(colors=LABEL, labelsize=8.5)
        axr.spines[:].set_color("#2a2a3e")
        axr.legend(handles=[plt.Line2D([0], [0], color=MACRO_COLORS["T10Y2Y"], lw=2,
                                       label=f"Spread 10Y-2Y  {s.iloc[-1]:+.2f}%")],
                   loc="lower right", facecolor="#1a1a2e", labelcolor="white",
                   fontsize=8.5, framealpha=0.7)


def _p_inflacion(ax, d):
    for col, label in (("cpi_yoy", "CPI interanual"),
                       ("core_pce_yoy", "PCE subyacente"),
                       ("CORESTICKM159SFRBATL", "Sticky CPI (Atlanta)")):
        if not _has(d, col):
            continue
        s = d[col].dropna()
        ax.plot(s.index, s, color=MACRO_COLORS[col], linewidth=1.5,
                label=f"{label}  {s.iloc[-1]:.2f}%")
    ax.axhline(2, color="#00e676", linewidth=1.0, linestyle="--", alpha=0.7)
    ax.annotate("objetivo 2%", xy=(d.index[0], 2), xytext=(4, 3),
                textcoords="offset points", color="#00e676", fontsize=7.5)
    ax.set_ylabel("Interanual (%)", color=LABEL, fontsize=9)
    _legend(ax)


def _p_empleo(ax, d):
    if _has(d, "payems_chg"):
        # La serie viene ffilleada a diario; una barra por día repetiría el mismo
        # valor todo el mes. Se toma un punto por mes.
        s = d["payems_chg"].resample("MS").first().dropna()
        colors = ["#ff6b6b" if v < 0 else MACRO_COLORS["payems_chg"] for v in s]
        ax.bar(s.index, s, width=20, color=colors, alpha=0.85,
               label="Nóminas, cambio mensual (miles)")
        ax.axhline(0, color="#666677", linewidth=0.8)
        lo, hi = min(s.min(), 0), max(s.max(), 0)
        ax.set_ylim(lo - abs(lo) * 0.25 - 20, hi * 1.35 + 20)
        ax.set_ylabel("Nóminas (miles)", color=LABEL, fontsize=9)
        _legend(ax)
    if _has(d, "UNRATE"):
        axr = ax.twinx()
        s = d["UNRATE"].dropna()
        axr.plot(s.index, s, color=MACRO_COLORS["UNRATE"], linewidth=1.5)
        axr.set_ylabel("Paro (%)", color=LABEL, fontsize=9)
        axr.tick_params(colors=LABEL, labelsize=8.5)
        axr.spines[:].set_color("#2a2a3e")
        axr.legend(handles=[plt.Line2D([0], [0], color=MACRO_COLORS["UNRATE"], lw=2,
                                       label=f"Tasa de paro  {s.iloc[-1]:.1f}%")],
                   loc="upper right", facecolor="#1a1a2e", labelcolor="white",
                   fontsize=8.5, framealpha=0.7)


def _p_dolar(ax, d):
    if _has(d, "DTWEXBGS"):
        s = d["DTWEXBGS"].dropna()
        ax.plot(s.index, s, color=MACRO_COLORS["DTWEXBGS"], linewidth=1.5)
        ax.set_ylabel("Índice dólar amplio", color=LABEL, fontsize=9)
        ax.legend(handles=[plt.Line2D([0], [0], color=MACRO_COLORS["DTWEXBGS"], lw=2,
                                      label=f"Índice dólar  {s.iloc[-1]:.1f}")],
                  loc="upper left", facecolor="#1a1a2e", labelcolor="white",
                  fontsize=8.5, framealpha=0.7)
    if _has(d, "DEXJPUS"):
        axr = ax.twinx()
        s = d["DEXJPUS"].dropna()
        axr.plot(s.index, s, color=MACRO_COLORS["DEXJPUS"], linewidth=1.4, linestyle="--")
        axr.set_ylabel("Yen por dólar", color=LABEL, fontsize=9)
        axr.tick_params(colors=LABEL, labelsize=8.5)
        axr.spines[:].set_color("#2a2a3e")
        axr.legend(handles=[plt.Line2D([0], [0], color=MACRO_COLORS["DEXJPUS"], lw=2, ls="--",
                                       label=f"Dólar-Yen  {s.iloc[-1]:.1f}")],
                   loc="lower right", facecolor="#1a1a2e", labelcolor="white",
                   fontsize=8.5, framealpha=0.7)


def _p_riesgo(ax, d):
    if _has(d, "BAMLH0A0HYM2"):
        s = d["BAMLH0A0HYM2"].dropna()
        ax.plot(s.index, s, color=MACRO_COLORS["BAMLH0A0HYM2"], linewidth=1.5)
        ax.set_ylabel("Spread High Yield (%)", color=LABEL, fontsize=9)
        ax.legend(handles=[plt.Line2D([0], [0], color=MACRO_COLORS["BAMLH0A0HYM2"], lw=2,
                                      label=f"Spread High Yield  {s.iloc[-1]:.2f}%")],
                  loc="upper left", facecolor="#1a1a2e", labelcolor="white",
                  fontsize=8.5, framealpha=0.7)
    if _has(d, "DCOILWTICO"):
        axr = ax.twinx()
        s = d["DCOILWTICO"].dropna()
        axr.plot(s.index, s, color=MACRO_COLORS["DCOILWTICO"], linewidth=1.4)
        axr.set_ylabel("WTI ($/barril)", color=LABEL, fontsize=9)
        axr.tick_params(colors=LABEL, labelsize=8.5)
        axr.spines[:].set_color("#2a2a3e")
        axr.legend(handles=[plt.Line2D([0], [0], color=MACRO_COLORS["DCOILWTICO"], lw=2,
                                       label=f"WTI  ${s.iloc[-1]:.2f}")],
                   loc="lower right", facecolor="#1a1a2e", labelcolor="white",
                   fontsize=8.5, framealpha=0.7)


MACRO_PANELS = [
    ("Curva de tipos",            _p_curva,     ("DGS10",)),
    ("Inflación",                 _p_inflacion, ("cpi_yoy", "core_pce_yoy",
                                                 "CORESTICKM159SFRBATL")),
    ("Empleo",                    _p_empleo,    ("payems_chg", "UNRATE")),
    ("Dólar",                     _p_dolar,     ("DTWEXBGS", "DEXJPUS")),
    ("Crédito y crudo",           _p_riesgo,    ("BAMLH0A0HYM2", "DCOILWTICO")),
]


def plot_macro(df: pd.DataFrame) -> bool:
    """Gráfica de tipos, inflación, empleo, divisas y crédito.

    Sólo dibuja los paneles con datos: si FRED falla para un bloque entero, el
    resto de la gráfica sigue saliendo. Devuelve False si no hay nada que pintar,
    para que el HTML no enlace una imagen inexistente.
    """
    cutoff = pd.Timestamp.today() - pd.DateOffset(years=CHART_YEARS)
    d = df[df.index >= cutoff].copy()

    panels = [(t, fn) for t, fn, cols in MACRO_PANELS if any(_has(d, c) for c in cols)]
    if not panels:
        print("[--] Sin datos macro todavía: se omite macro_chart.png")
        return False

    fig, axes = plt.subplots(len(panels), 1, figsize=(15, 2.6 * len(panels) + 1),
                             facecolor=BG, squeeze=False)
    axes = axes[:, 0]
    fig.subplots_adjust(hspace=0.28, left=0.07, right=0.93, top=0.93, bottom=0.06)

    for i, ((title, fn), ax) in enumerate(zip(panels, axes)):
        style_ax(ax, show_xticks=(i == len(panels) - 1))
        fn(ax, d)
        ax.set_title(title, color="#cccccc", fontsize=10, loc="left",
                     pad=6, fontweight="bold")

    # suptitle y no set_title sobre el primer eje: eso borraría "Curva de tipos".
    fig.suptitle(
        f"Macro EEUU  ·  Actualizado {d.index[-1]:%d %b %Y}",
        color="white", fontsize=13, x=0.07, ha="left", fontweight="bold",
    )
    fig.text(0.5, 0.005, "Fuente: FRED (St. Louis Fed)",
             ha="center", color="#444455", fontsize=8)

    plt.savefig(MACRO_PNG, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"[OK] Gráfica macro guardada → {MACRO_PNG}")
    return True


# ── HTML ─────────────────────────────────────────────────────────────────────

def generate_html(df: pd.DataFrame, has_macro: bool = False):
    last  = df.index[-1]
    nl    = df["net_liq"].dropna().iloc[-1]
    m2    = df["M2SL"].dropna().iloc[-1]
    rrp   = df["RRPONTSYD"].dropna().iloc[-1]
    sp    = df["SP500"].dropna().iloc[-1]     if "SP500"      in df.columns else None
    msci  = df["MSCI_World"].dropna().iloc[-1] if "MSCI_World" in df.columns else None
    gold  = df["Gold"].dropna().iloc[-1]      if "Gold"       in df.columns else None
    btc   = df["Bitcoin"].dropna().iloc[-1]   if "Bitcoin"    in df.columns else None

    def card(label, value, sub=""):
        return f"""
        <div class="metric">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
          {"<div class='metric-sub'>" + sub + "</div>" if sub else ""}
        </div>"""

    cards = (
        card("Net Liquidity",   f"${nl:.2f}T",        "Fed Balance − TGA − RRP")
      + card("M2 (EEUU)",       f"${m2:.2f}T",        "Oferta monetaria")
      + card("Reverse Repos",   f"${rrp:.3f}T",       "Liquidez aparcada en Fed")
      + (card("SP500",          f"{sp:,.0f}",          "")         if sp   else "")
      + (card("MSCI World ETF", f"${msci:.2f}",        "URTH")     if msci else "")
      + (card("Oro",            f"${gold:,.0f}/oz",    "GC=F")     if gold else "")
      + (card("Bitcoin",        f"${btc:,.0f}",        "BTC-USD")  if btc  else "")
    )

    # Tarjetas macro: se omite en silencio cualquier serie que FRED no haya dado.
    def macro_card(col, label, fmt, sub=""):
        if col not in df.columns or not df[col].notna().any():
            return ""
        s = df[col].dropna()
        when = LAST_OBS.get(col, s.index[-1])
        return card(label, fmt.format(s.iloc[-1]), sub or f"{when:%d %b %Y}")

    macro_cards = (
        macro_card("DGS10",        "Treasury 10Y",   "{:.2f}%")
      + macro_card("DGS30",        "Treasury 30Y",   "{:.2f}%")
      + macro_card("T10Y2Y",       "Spread 10Y-2Y",  "{:+.2f}%")
      + macro_card("cpi_yoy",      "CPI interanual", "{:.2f}%")
      + macro_card("core_pce_yoy", "PCE subyacente", "{:.2f}%")
      + macro_card("payems_chg",   "Nóminas (mes)",  "{:+,.0f}k")
      + macro_card("UNRATE",       "Paro",           "{:.1f}%")
      + macro_card("DTWEXBGS",     "Índice dólar",   "{:.2f}")
      + macro_card("DEXJPUS",      "Dólar-Yen",      "{:.2f}")
      + macro_card("BAMLH0A0HYM2", "Spread High Yield", "{:.2f}%")
      + macro_card("DCOILWTICO",   "WTI",            "${:.2f}")
    )

    macro_tab   = ('<button class="tab" onclick="showTab(\'macro\', this)">Macro</button>'
                   if has_macro else "")
    macro_panel = ('<div id="panel-macro" class="chart-panel">'
                   '<img class="chart" src="macro_chart.png" alt="Macro EEUU">'
                   f'<div class="metrics">{macro_cards}</div>'
                   '</div>') if has_macro else ""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="3600">
  <title>Market Liquidity Dashboard</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0f1117; color:#e0e0e0;
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
    .container {{ max-width:1300px; margin:0 auto; padding:2rem; }}
    h1 {{ color:#fff; font-size:1.7rem; font-weight:700; }}
    .updated {{ color:#555; font-size:0.85rem; margin-top:.3rem; margin-bottom:1.4rem; }}
    .tabs {{ display:flex; gap:.5rem; margin-bottom:1rem; }}
    .tab {{ padding:.45rem 1.1rem; border-radius:6px; border:1px solid #2a2a3e;
            background:#1a1a2e; color:#888; font-size:.85rem; cursor:pointer;
            transition:all .15s; }}
    .tab.active {{ background:#00d4ff22; border-color:#00d4ff66; color:#00d4ff; font-weight:600; }}
    .chart-panel {{ display:none; }}
    .chart-panel.active {{ display:block; }}
    .chart {{ width:100%; border-radius:10px; display:block; }}
    .metrics {{ display:grid;
                grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
                gap:1rem; margin-top:1.8rem; }}
    .metric {{ background:#1a1a2e; border-radius:8px; padding:1.1rem 1.3rem; }}
    .metric-label {{ color:#666; font-size:.75rem; text-transform:uppercase;
                     letter-spacing:.06em; }}
    .metric-value {{ color:#fff; font-size:1.35rem; font-weight:600;
                     margin-top:.3rem; }}
    .metric-sub {{ color:#444; font-size:.72rem; margin-top:.2rem; }}
    footer {{ text-align:center; color:#333; font-size:.78rem;
              margin-top:2.5rem; padding-top:1rem;
              border-top:1px solid #1e1e2e; }}
    a {{ color:#555; text-decoration:none; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Market Liquidity Dashboard</h1>
    <p class="updated">Actualizado: {last:%d %b %Y} &nbsp;·&nbsp;
       Net Liquidity = Fed Balance Sheet − TGA − RRP</p>

    <div class="tabs">
      <button class="tab active" onclick="showTab('3y', this)">3 años</button>
      <button class="tab"        onclick="showTab('3m', this)">3 meses</button>
      {macro_tab}
    </div>

    <div id="panel-3y" class="chart-panel active">
      <img class="chart" src="liquidity_chart.png" alt="Liquidity Chart 3 años">
      <div class="metrics">{cards}</div>
    </div>
    <div id="panel-3m" class="chart-panel">
      <img class="chart" src="liquidity_chart_3m.png" alt="Liquidity Chart 3 meses">
      <div class="metrics">{cards}</div>
    </div>
    {macro_panel}
    <footer>
      Datos: <a href="https://fred.stlouisfed.org">FRED (St. Louis Fed)</a>
      &amp; <a href="https://finance.yahoo.com">Yahoo Finance</a>
      &nbsp;·&nbsp; Actualización diaria automática vía GitHub Actions
    </footer>
  </div>
  <script>
    function showTab(id, btn) {{
      document.querySelectorAll('.chart-panel').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      document.getElementById('panel-' + id).classList.add('active');
      btn.classList.add('active');
    }}
  </script>
</body>
</html>"""

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] HTML guardado → {HTML_FILE}")


# ── Resumen macro ─────────────────────────────────────────────────────────────

MACRO_SUMMARY = [
    ("Curva de tipos", [
        ("DGS2",   "2 años",          "{:.2f}%"),
        ("DGS10",  "10 años",         "{:.2f}%"),
        ("DGS30",  "30 años",         "{:.2f}%"),
        ("T10Y2Y", "Spread 10Y-2Y",   "{:+.2f}%"),
        ("DFII10", "Real 10Y (TIPS)", "{:.2f}%"),
        ("T10YIE", "Breakeven 10Y",   "{:.2f}%"),
        ("DFF",    "Fed Funds",       "{:.2f}%"),
    ]),
    ("Inflación", [
        ("cpi_yoy",              "CPI interanual",   "{:.2f}%"),
        ("core_pce_yoy",         "PCE subyacente",   "{:.2f}%"),
        ("CORESTICKM159SFRBATL", "Sticky CPI",       "{:.2f}%"),
    ]),
    ("Empleo", [
        ("payems_chg", "Nóminas (mes)",  "{:+,.0f}k"),
        ("UNRATE",     "Paro",           "{:.1f}%"),
        ("CIVPART",    "Participación",  "{:.1f}%"),
        ("ICSA",       "Peticiones",     "{:,.0f}"),
    ]),
    ("Divisas, crédito y crudo", [
        ("DTWEXBGS",     "Índice dólar",     "{:.2f}"),
        ("DEXJPUS",      "Dólar-Yen",        "{:.2f}"),
        ("BAMLH0A0HYM2", "Spread High Yield","{:.2f}%"),
        ("DCOILWTICO",   "WTI",              "${:.2f}"),
    ]),
]


def print_macro_summary(df: pd.DataFrame) -> None:
    """Imprime el último valor de cada serie macro.

    La fecha mostrada es la de la observación real (LAST_OBS), no la del índice
    diario: tras el ffill una serie mensual aparentaría ser un dato de hoy.
    """
    for title, rows in MACRO_SUMMARY:
        available = [(c, lbl, f) for c, lbl, f in rows if c in df.columns and df[c].notna().any()]
        if not available:
            continue
        print(f"\n  {title}")
        for col, label, fmt in available:
            s = df[col].dropna()
            when = LAST_OBS.get(col, s.index[-1])
            print(f"    {label:18s}: {fmt.format(s.iloc[-1]):>12s}   ({when:%Y-%m-%d})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] Actualizando datos...")

    fred     = Fred(api_key=load_api_key())
    df_fred  = fetch_fred(fred)
    df_macro = fetch_fred_macro(fred)
    df_mkt   = fetch_markets()

    if not df_macro.empty:
        df_fred = df_fred.join(df_macro, how="outer")
    df = update_csv(df_fred, df_mkt)

    last = df.index[-1]
    print(f"\n  Último dato   : {last:%Y-%m-%d}")
    print(f"  Net Liquidity : ${df['net_liq'].dropna().iloc[-1]:.2f}T")
    print(f"  M2            : ${df['M2SL'].dropna().iloc[-1]:.2f}T")
    print(f"  RRP           : ${df['RRPONTSYD'].dropna().iloc[-1]:.3f}T")
    for asset in MARKET_TICKERS:
        if asset in df.columns:
            v = df[asset].dropna().iloc[-1]
            print(f"  {asset:10s}  : {v:,.2f}")

    print_macro_summary(df)

    plot(df)
    plot_zoom(df)
    has_macro = plot_macro(df)
    generate_html(df, has_macro=has_macro)


if __name__ == "__main__":
    main()
