#!/usr/bin/env python3
"""
Descarga diaria de liquidez global (FRED) + mercados (yfinance) y genera gráfica.

FRED:
  WALCL      — Balance sheet Fed    (millones USD)
  WTREGEN    — TGA Tesoro EEUU      (millones USD)
  RRPONTSYD  — Reverse Repos        (billones USD)
  M2SL       — Oferta monetaria M2  (billones USD)

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
DOCS_DIR    = os.path.join(BASE_DIR, "docs")
DATA_CSV    = os.path.join(BASE_DIR, "fred_data.csv")
CHART_PNG   = os.path.join(DOCS_DIR, "liquidity_chart.png")
HTML_FILE   = os.path.join(DOCS_DIR, "index.html")
ENV_FILE    = os.path.join(BASE_DIR, ".env")
START_DATE  = "2020-01-01"
CHART_YEARS = 3

os.makedirs(DOCS_DIR, exist_ok=True)

FRED_SERIES = {
    "WALCL":     "Fed Balance Sheet (M USD)",
    "WTREGEN":   "TGA Tesoro (M USD)",
    "RRPONTSYD": "Reverse Repos (B USD)",
    "M2SL":      "M2 (B USD)",
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

def style_ax(ax, show_xticks=False):
    ax.set_facecolor(BG)
    ax.tick_params(colors=LABEL, labelsize=8.5)
    for spine in ax.spines.values():
        spine.set_color("#2a2a3e")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.grid(axis="x", color=GRID, linewidth=0.3)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
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

# ── HTML ─────────────────────────────────────────────────────────────────────

def generate_html(df: pd.DataFrame):
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
    .updated {{ color:#555; font-size:0.85rem; margin-top:.3rem; margin-bottom:1.8rem; }}
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
    <img class="chart" src="liquidity_chart.png" alt="Liquidity Chart">
    <div class="metrics">{cards}</div>
    <footer>
      Datos: <a href="https://fred.stlouisfed.org">FRED (St. Louis Fed)</a>
      &amp; <a href="https://finance.yahoo.com">Yahoo Finance</a>
      &nbsp;·&nbsp; Actualización diaria automática vía GitHub Actions
    </footer>
  </div>
</body>
</html>"""

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] HTML guardado → {HTML_FILE}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] Actualizando datos...")

    fred     = Fred(api_key=load_api_key())
    df_fred  = fetch_fred(fred)
    df_mkt   = fetch_markets()
    df       = update_csv(df_fred, df_mkt)

    last = df.index[-1]
    print(f"\n  Último dato   : {last:%Y-%m-%d}")
    print(f"  Net Liquidity : ${df['net_liq'].dropna().iloc[-1]:.2f}T")
    print(f"  M2            : ${df['M2SL'].dropna().iloc[-1]:.2f}T")
    print(f"  RRP           : ${df['RRPONTSYD'].dropna().iloc[-1]:.3f}T")
    for asset in MARKET_TICKERS:
        if asset in df.columns:
            v = df[asset].dropna().iloc[-1]
            print(f"  {asset:10s}  : {v:,.2f}")

    plot(df)
    generate_html(df)


if __name__ == "__main__":
    main()
