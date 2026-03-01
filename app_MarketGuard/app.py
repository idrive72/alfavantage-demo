from __future__ import annotations

from datetime import date, datetime, timedelta
import os
from pathlib import Path
import random
from typing import Any

import pandas as pd
import requests
import streamlit as st

BASE_URL = "https://www.alphavantage.co/query"
API_KEY_PATH = Path(__file__).resolve().parent.parent / "api_key.txt"

PAIR_OPTIONS = ["EUR/USD", "GBP/USD", "USD/CHF", "USD/JPY", "EUR/GBP"]
COMMODITY_OPTIONS = ["BRENT", "WTI", "NATURAL_GAS", "GOLD", "SILVER"]


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Space+Grotesk:wght@400;500;700&display=swap');

        :root {
          --mg-bg: #060b16;
          --mg-bg-2: #0d1628;
          --mg-panel: rgba(13, 25, 42, 0.86);
          --mg-line: rgba(86, 227, 255, 0.25);
          --mg-cyan: #56e3ff;
          --mg-lime: #9af96f;
          --mg-amber: #ffc96b;
          --mg-red: #ff7a9c;
          --mg-text: #e8f5ff;
          --mg-sub: #9bb5ce;
        }

        .stApp {
          background:
            radial-gradient(circle at 12% 8%, rgba(86, 227, 255, 0.16), transparent 25%),
            radial-gradient(circle at 86% 12%, rgba(154, 249, 111, 0.1), transparent 22%),
            linear-gradient(170deg, var(--mg-bg), var(--mg-bg-2) 65%);
          color: var(--mg-text);
          font-family: "Space Grotesk", sans-serif;
        }

        h1, h2, h3 {
          font-family: "Orbitron", sans-serif;
          letter-spacing: 0.02em;
        }

        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #0a1324 0%, #0d1d34 100%);
          border-right: 1px solid var(--mg-line);
        }

        [data-testid="stMetric"] {
          background: var(--mg-panel);
          border: 1px solid var(--mg-line);
          border-radius: 14px;
          padding: 6px 10px;
        }

        .mg-panel {
          background: var(--mg-panel);
          border: 1px solid var(--mg-line);
          border-radius: 14px;
          padding: 12px 14px;
          margin-bottom: 10px;
        }

        .mg-chip {
          display: inline-block;
          padding: 3px 8px;
          margin-right: 6px;
          margin-bottom: 6px;
          border-radius: 999px;
          border: 1px solid var(--mg-line);
          color: var(--mg-sub);
          font-size: 12px;
        }

        .mg-alert {
          border-left: 4px solid var(--mg-cyan);
          background: rgba(13, 24, 39, 0.92);
          border-radius: 8px;
          padding: 8px 10px;
          margin-bottom: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_api_key() -> str:
    env_key = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
    if env_key:
        return env_key

    try:
        secret_key = str(st.secrets.get("ALPHAVANTAGE_API_KEY", "")).strip()
    except Exception:
        secret_key = ""
    if secret_key:
        return secret_key

    if not API_KEY_PATH.exists():
        raise FileNotFoundError(
            "API key non trovata. Imposta ALPHAVANTAGE_API_KEY nei secrets oppure crea "
            f"{API_KEY_PATH}"
        )
    key = API_KEY_PATH.read_text(encoding="utf-8").strip()
    if not key:
        raise ValueError("Il file api_key.txt e' vuoto.")
    return key


def normalize_column_name(column: str) -> str:
    parts = column.split(". ", 1)
    value = parts[1] if len(parts) == 2 else column
    return value.replace(" ", "_").replace("-", "_").replace("/", "_").lower()


@st.cache_data(ttl=900, show_spinner=False)
def av_query(function_name: str, **params: str) -> dict[str, Any]:
    query = {"function": function_name, "apikey": load_api_key(), **params}
    response = requests.get(BASE_URL, params=query, timeout=25)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict):
        if "Error Message" in data:
            raise RuntimeError(data["Error Message"])
        if "Information" in data:
            raise RuntimeError(data["Information"])
        if "Note" in data:
            raise RuntimeError(data["Note"])
    return data


def is_rate_limit_message(message: str) -> bool:
    text = message.lower()
    patterns = [
        "rate limit",
        "requests per day",
        "call frequency",
        "please subscribe",
        "premium plans",
    ]
    return any(pattern in text for pattern in patterns)


def build_query_cache_key(function_name: str, params: dict[str, str]) -> str:
    normalized = "|".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"{function_name}|{normalized}"


def _build_demo_daily(seed_key: str, days: int, base: float, scale: float) -> dict[str, dict[str, str]]:
    seed = sum(ord(char) for char in seed_key)
    rng = random.Random(seed)
    rows: dict[str, dict[str, str]] = {}
    today = datetime.utcnow().date()
    value = base
    for idx in range(days):
        d = today - timedelta(days=(days - idx))
        drift = ((idx / max(days, 1)) - 0.5) * scale * 0.35
        op = max(0.0001, value + rng.uniform(-1.1, 1.1) * scale)
        cl = max(0.0001, op + rng.uniform(-1.4, 1.4) * scale + drift)
        hi = max(op, cl) + abs(rng.uniform(0.2, 1.1) * scale)
        lo = max(0.0001, min(op, cl) - abs(rng.uniform(0.2, 1.1) * scale))
        rows[d.isoformat()] = {
            "1. open": f"{op:.5f}",
            "2. high": f"{hi:.5f}",
            "3. low": f"{lo:.5f}",
            "4. close": f"{cl:.5f}",
            "5. volume": str(int(900000 + rng.random() * 3100000)),
        }
        value = cl
    return rows


def _build_demo_commodity(seed_key: str, points: int, base: float, step: float) -> list[dict[str, str]]:
    seed = sum(ord(char) for char in seed_key)
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    today = date.today()
    value = base
    for idx in range(points):
        month_date = today - timedelta(days=(points - idx) * 30)
        value = max(0.1, value + rng.uniform(-1.7, 1.7) * step + (0.04 * step))
        rows.append({"date": month_date.isoformat(), "value": f"{value:.2f}"})
    return rows


def build_demo_payload(function_name: str, params: dict[str, str]) -> dict[str, Any] | None:
    if function_name == "FX_DAILY":
        from_symbol = params.get("from_symbol", "EUR").upper()
        to_symbol = params.get("to_symbol", "USD").upper()
        pair = f"{from_symbol}{to_symbol}"
        return {"Time Series FX (Daily)": _build_demo_daily(pair, 220, 1.09, 0.012)}

    if function_name in {"BRENT", "WTI", "NATURAL_GAS", "GOLD", "SILVER"}:
        settings = {
            "BRENT": ("Brent Crude Oil", 82.0, 1.3, "USD per Barrel"),
            "WTI": ("WTI Crude Oil", 79.5, 1.25, "USD per Barrel"),
            "NATURAL_GAS": ("Natural Gas", 2.85, 0.11, "USD per MMBtu"),
            "GOLD": ("Gold", 2260.0, 9.8, "USD per Troy Ounce"),
            "SILVER": ("Silver", 27.4, 0.24, "USD per Troy Ounce"),
        }
        name, base, step, unit = settings[function_name]
        return {
            "name": name,
            "interval": "monthly",
            "unit": unit,
            "data": _build_demo_commodity(function_name, 72, base, step),
        }

    if function_name == "NEWS_SENTIMENT":
        tickers = params.get("tickers", "IBM").split(",")
        feed = []
        now = datetime.utcnow()
        for idx in range(15):
            ticker = tickers[idx % len(tickers)].strip().upper() or "IBM"
            score = round(random.Random(idx + len(ticker)).uniform(-0.72, 0.72), 3)
            label = "Bullish" if score > 0.2 else "Bearish" if score < -0.2 else "Neutral"
            feed.append(
                {
                    "time_published": (now - timedelta(hours=idx * 3)).strftime("%Y%m%dT%H%M%S"),
                    "source": "MarketGuard Demo Wire",
                    "title": f"{ticker} | evento demo #{idx + 1} per monitor rischio",
                    "overall_sentiment_label": label,
                    "overall_sentiment_score": str(score),
                    "url": "https://example.com/marketguard-demo",
                }
            )
        return {"feed": feed}
    return None


def safe_query(function_name: str, allow_demo: bool = True, **params: str) -> dict[str, Any] | None:
    fallback_cache = st.session_state.setdefault("query_fallback_cache", {})
    cache_key = build_query_cache_key(function_name, params)

    try:
        payload = av_query(function_name, **params)
        fallback_cache[cache_key] = payload
        return payload
    except requests.RequestException as exc:
        st.error(f"Errore di rete verso Alpha Vantage: {exc}")
    except RuntimeError as exc:
        if is_rate_limit_message(str(exc)):
            if cache_key in fallback_cache:
                st.warning(
                    "Limite giornaliero Alpha Vantage superato. "
                    "MarketGuard sta usando i dati gia presenti in cache."
                )
                return fallback_cache[cache_key]
            if allow_demo and st.session_state.get("use_demo_data_on_rate_limit", True):
                demo_payload = build_demo_payload(function_name, params)
                if demo_payload is not None:
                    fallback_cache[cache_key] = demo_payload
                    st.warning(
                        "Limite giornaliero Alpha Vantage superato. "
                        "Non essendoci cache, sono attivi dati demo sintetici."
                    )
                    return demo_payload
            st.warning(
                "Limite giornaliero Alpha Vantage superato e cache non disponibile "
                "per questa richiesta."
            )
        else:
            st.warning(f"Alpha Vantage ha restituito: {exc}")
    except Exception as exc:
        st.error(f"Errore inatteso: {exc}")
    return None


def timeseries_to_df(payload: dict[str, Any]) -> pd.DataFrame:
    ts_key = next((k for k in payload.keys() if "Time Series" in k), None)
    if not ts_key:
        return pd.DataFrame()
    df = pd.DataFrame.from_dict(payload[ts_key], orient="index")
    if df.empty:
        return df
    df = df.rename(columns={c: normalize_column_name(c) for c in df.columns})
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.index = pd.to_datetime(df.index, errors="coerce")
    return df.dropna(how="all").sort_index()


def commodity_to_df(payload: dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(payload.get("data", []))
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().sort_values("date")


def parse_news_time(raw: str) -> str:
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw


def format_change(latest: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return ((latest - previous) / previous) * 100


def risk_level(change_pct: float) -> str:
    abs_v = abs(change_pct)
    if abs_v < 0.5:
        return "Low"
    if abs_v < 1.5:
        return "Medium"
    return "High"


def get_fx_df(pair: str) -> pd.DataFrame:
    base, quote = pair.split("/")
    payload = safe_query("FX_DAILY", from_symbol=base, to_symbol=quote, outputsize="compact")
    if not payload:
        return pd.DataFrame()
    return timeseries_to_df(payload)


def get_commodity_df(function_name: str) -> pd.DataFrame:
    payload = safe_query(function_name, interval="monthly")
    if not payload:
        return pd.DataFrame()
    return commodity_to_df(payload)


def render_home() -> None:
    st.subheader("MarketGuard | Risk & Alert Desk")
    st.markdown(
        """
        <div class="mg-panel">
          <b>Perche questa demo:</b> mostrare un servizio pronto da proporre a collaboratori o clienti
          che vogliono monitorare rischio operativo legato a FX, materie prime e notizie di mercato.
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Moduli implementati")
        st.markdown(
            "- Monitor live FX e commodity (trend + variazioni)\n"
            "- Alert operativi su soglie di movimento\n"
            "- Scenario planner per esposizione in USD\n"
            "- Feed News + Sentiment per watchlist ticker\n"
            "- Fallback cache/demo in caso di rate-limit"
        )
    with c2:
        st.markdown("### Evoluzioni possibili")
        st.markdown(
            "- Report PDF automatico settimanale\n"
            "- Invio alert su Telegram/Email/Slack\n"
            "- Regole avanzate con priorita e escalation\n"
            "- Multi-tenant per clienti diversi\n"
            "- Copilota AI via MCP per Q&A finanziario"
        )

    st.markdown(
        """
        <span class="mg-chip">Futuristic UI</span>
        <span class="mg-chip">PMI-ready</span>
        <span class="mg-chip">AI + MCP ready</span>
        <span class="mg-chip">Rate-limit resilient</span>
        """,
        unsafe_allow_html=True,
    )


def render_monitor(pairs: list[str], commodities: list[str]) -> None:
    st.subheader("Panoramica rischio e mercati in tempo reale")
    st.caption("Focus su segnali rapidi: movimento prezzo e stato rischio.")

    pair_rows: list[dict[str, Any]] = []
    pair_series: list[pd.Series] = []
    for pair in pairs:
        df = get_fx_df(pair)
        if df.empty or "close" not in df.columns or len(df) < 2:
            continue
        latest = float(df["close"].iloc[-1])
        previous = float(df["close"].iloc[-2])
        chg = format_change(latest, previous)
        pair_rows.append({"Instrument": pair, "Latest": latest, "Change%": chg, "Risk": risk_level(chg)})
        pair_series.append(df["close"].tail(180).rename(pair))

    if pair_rows:
        st.markdown("#### FX Monitor")
        cols = st.columns(min(4, len(pair_rows)))
        for idx, row in enumerate(pair_rows[:4]):
            cols[idx].metric(row["Instrument"], f"{row['Latest']:.5f}", f"{row['Change%']:+.2f}%")
        if pair_series:
            chart_df = pd.concat(pair_series, axis=1)
            st.line_chart(chart_df, height=290)
    else:
        st.info("Nessun dato FX disponibile.")

    commodity_rows: list[dict[str, Any]] = []
    commodity_series: list[pd.Series] = []
    for commodity in commodities:
        df = get_commodity_df(commodity)
        if df.empty or len(df) < 2:
            continue
        latest = float(df["value"].iloc[-1])
        previous = float(df["value"].iloc[-2])
        chg = format_change(latest, previous)
        commodity_rows.append(
            {"Instrument": commodity, "Latest": latest, "Change%": chg, "Risk": risk_level(chg)}
        )
        commodity_series.append(df.set_index("date")["value"].tail(60).rename(commodity))

    if commodity_rows:
        st.markdown("#### Commodity Stress")
        cols = st.columns(min(4, len(commodity_rows)))
        for idx, row in enumerate(commodity_rows[:4]):
            cols[idx].metric(row["Instrument"], f"{row['Latest']:.2f}", f"{row['Change%']:+.2f}%")
        if commodity_series:
            chart_df = pd.concat(commodity_series, axis=1)
            st.line_chart(chart_df, height=260)
    else:
        st.info("Nessun dato commodity disponibile.")

    risk_df = pd.DataFrame(pair_rows + commodity_rows)
    if not risk_df.empty:
        risk_df["AbsMove%"] = risk_df["Change%"].abs()
        risk_df = risk_df.sort_values("AbsMove%", ascending=False)
        st.markdown("#### Risk Board")
        st.dataframe(
            risk_df[["Instrument", "Latest", "Change%", "Risk"]],
            use_container_width=True,
            hide_index=True,
        )


def render_scenari(pair: str, monthly_usd_exposure: float) -> None:
    st.subheader("Scenario Impatto FX")
    st.caption("Stima rapida impatto su costi in EUR per esposizione in USD.")

    df = get_fx_df(pair)
    if df.empty or "close" not in df.columns:
        st.info("Dati FX non disponibili per questo scenario.")
        return

    current_fx = float(df["close"].iloc[-1])
    baseline_cost_eur = monthly_usd_exposure / current_fx

    scenario_moves = [-8, -5, -3, 0, 3, 5, 8]
    rows = []
    for move in scenario_moves:
        shocked_fx = current_fx * (1 + (move / 100))
        shocked_cost = monthly_usd_exposure / shocked_fx
        delta = shocked_cost - baseline_cost_eur
        rows.append(
            {
                "Shock FX (%)": move,
                "FX rate": round(shocked_fx, 5),
                "Costo EUR stimato": round(shocked_cost, 2),
                "Delta vs baseline": round(delta, 2),
            }
        )

    c1, c2 = st.columns(2)
    c1.metric("Pair corrente", pair, f"{current_fx:.5f}")
    c2.metric("Costo baseline (EUR)", f"{baseline_cost_eur:,.2f}".replace(",", "."))
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_alert_feed(
    pairs: list[str],
    commodities: list[str],
    fx_threshold: float,
    commodity_threshold: float,
    news_tickers: str,
) -> None:
    st.subheader("Alert Feed")
    st.caption("Regole semplici ma operative per intercettare eventi critici.")

    alerts: list[dict[str, str]] = []
    for pair in pairs:
        df = get_fx_df(pair)
        if df.empty or "close" not in df.columns or len(df) < 2:
            continue
        chg = format_change(float(df["close"].iloc[-1]), float(df["close"].iloc[-2]))
        if abs(chg) >= fx_threshold:
            sev = "HIGH" if abs(chg) >= (fx_threshold * 1.8) else "MEDIUM"
            alerts.append(
                {
                    "severity": sev,
                    "title": f"{pair} movimento {chg:+.2f}%",
                    "detail": f"Superata soglia FX {fx_threshold:.2f}%",
                }
            )

    for commodity in commodities:
        df = get_commodity_df(commodity)
        if df.empty or len(df) < 2:
            continue
        chg = format_change(float(df["value"].iloc[-1]), float(df["value"].iloc[-2]))
        if abs(chg) >= commodity_threshold:
            sev = "HIGH" if abs(chg) >= (commodity_threshold * 1.8) else "MEDIUM"
            alerts.append(
                {
                    "severity": sev,
                    "title": f"{commodity} movimento {chg:+.2f}%",
                    "detail": f"Superata soglia commodity {commodity_threshold:.2f}%",
                }
            )

    payload = safe_query("NEWS_SENTIMENT", tickers=news_tickers, sort="LATEST", limit="20")
    news_df = pd.DataFrame()
    if payload and payload.get("feed"):
        rows: list[dict[str, Any]] = []
        bearish_count = 0
        for item in payload["feed"]:
            score = pd.to_numeric(item.get("overall_sentiment_score", ""), errors="coerce")
            label = item.get("overall_sentiment_label", "")
            if (isinstance(label, str) and "bear" in label.lower()) or (not pd.isna(score) and score < -0.2):
                bearish_count += 1
            rows.append(
                {
                    "published": parse_news_time(item.get("time_published", "")),
                    "source": item.get("source", ""),
                    "title": item.get("title", ""),
                    "sentiment_label": label,
                    "sentiment_score": score,
                }
            )
        news_df = pd.DataFrame(rows)
        if bearish_count >= 4:
            alerts.append(
                {
                    "severity": "MEDIUM",
                    "title": f"News sentiment negativo su watchlist ({bearish_count} segnali)",
                    "detail": "Valuta revisione esposizioni o hedging tattico.",
                }
            )

    if alerts:
        for alert in alerts:
            color = "#ff7a9c" if alert["severity"] == "HIGH" else "#ffc96b"
            st.markdown(
                f"""
                <div class="mg-alert" style="border-left-color:{color}">
                  <b>[{alert['severity']}] {alert['title']}</b><br/>
                  <span>{alert['detail']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.success("Nessun alert attivo con le soglie correnti.")

    if not news_df.empty:
        st.markdown("#### News & Sentiment")
        st.dataframe(news_df.head(15), use_container_width=True, hide_index=True)


def render_ai_mcp() -> None:
    st.subheader("AI + MCP Integration Blueprint")
    st.markdown(
        """
        <div class="mg-panel">
          <b>Obiettivo:</b> affiancare al monitoraggio tradizionale un copilota AI che risponde
          con contesto operativo: cosa e cambiato, quale esposizione e impattata, quali azioni
          tattiche valutare.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        "1. Dati Alpha Vantage (FX, commodity, news, fundamentals)\n"
        "2. Rule Engine MarketGuard (soglie, priorita, escalation)\n"
        "3. MCP layer per esporre dataset e segnali ad agenti AI\n"
        "4. Copilota per Q&A, briefing e spiegazioni decisionali"
    )
    st.code(
        "Esempio prompt copilota:\n"
        "\"Sintetizza i 3 rischi maggiori oggi per il nostro procurement, "
        "con impatto stimato su margine e azioni consigliate entro 24h.\"",
        language="text",
    )
    st.info("Il modulo AI non invia ordini. E progettato come supporto decisionale, non trading automatico.")


def main() -> None:
    st.set_page_config(page_title="MarketGuard", layout="wide")
    inject_styles()

    st.title("MarketGuard")
    st.write(
        "Dashboard futuristico per monitoraggio rischi finanziari su FX, commodity e sentiment."
    )

    try:
        _ = load_api_key()
    except Exception as exc:
        st.error(f"Impossibile caricare API key: {exc}")
        st.stop()

    st.sidebar.header("Control Deck")
    section = st.sidebar.radio(
        "Modulo",
        ["Home", "Monitor Live", "Scenari", "Alert Feed", "AI + MCP"],
        index=0,
    )
    pairs = st.sidebar.multiselect("FX da monitorare", PAIR_OPTIONS, default=PAIR_OPTIONS[:3])
    commodities = st.sidebar.multiselect(
        "Commodity da monitorare", COMMODITY_OPTIONS, default=["BRENT", "GOLD", "NATURAL_GAS"]
    )
    scenario_pair = st.sidebar.selectbox("Pair per scenario", PAIR_OPTIONS, index=0)
    monthly_usd_exposure = st.sidebar.number_input(
        "Esposizione mensile USD", min_value=1000.0, value=50000.0, step=1000.0
    )
    fx_threshold = st.sidebar.slider("Soglia alert FX (%)", min_value=0.2, max_value=3.0, value=1.0, step=0.1)
    commodity_threshold = st.sidebar.slider(
        "Soglia alert commodity (%)", min_value=0.5, max_value=8.0, value=2.0, step=0.1
    )
    news_tickers = st.sidebar.text_input("Watchlist news (CSV)", value="AAPL,MSFT,NVDA")
    st.sidebar.checkbox(
        "Usa dati demo se limite superato",
        key="use_demo_data_on_rate_limit",
        value=True,
        help="Se il limite giornaliero e superato e non c'e cache, usa dati sintetici demo.",
    )
    if st.sidebar.button("Aggiorna dati (svuota cache)"):
        st.cache_data.clear()
        st.session_state["query_fallback_cache"] = {}
        st.rerun()

    if section == "Home":
        render_home()
    elif section == "Monitor Live":
        if not pairs and not commodities:
            st.warning("Seleziona almeno un mercato da monitorare.")
        else:
            render_monitor(pairs, commodities)
    elif section == "Scenari":
        render_scenari(scenario_pair, monthly_usd_exposure)
    elif section == "Alert Feed":
        if not pairs and not commodities:
            st.warning("Seleziona almeno un mercato per generare alert.")
        else:
            render_alert_feed(pairs, commodities, fx_threshold, commodity_threshold, news_tickers)
    else:
        render_ai_mcp()


if __name__ == "__main__":
    main()
