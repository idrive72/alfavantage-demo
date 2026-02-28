from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

BASE_URL = "https://www.alphavantage.co/query"
API_KEY_PATH = Path(__file__).resolve().parent.parent / "api_key.txt"


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
            "API key non trovata. Imposta `ALPHAVANTAGE_API_KEY` nei secrets "
            f"Streamlit o crea il file locale: {API_KEY_PATH}"
        )
    key = API_KEY_PATH.read_text(encoding="utf-8").strip()
    if not key:
        raise ValueError("Il file api_key.txt e' vuoto.")
    return key


def normalize_column_name(column: str) -> str:
    parts = column.split(". ", 1)
    value = parts[1] if len(parts) == 2 else column
    value = value.replace("(USD)", "USD").replace("(CNY)", "CNY")
    value = value.replace("/", "_").replace(" ", "_").replace("-", "_")
    return value.lower()


def format_human_number(value: Any) -> str:
    num = pd.to_numeric(value, errors="coerce")
    if pd.isna(num):
        return "-"
    num = float(num)
    if abs(num) >= 1_000_000_000_000:
        return f"{num / 1_000_000_000_000:.2f}T"
    if abs(num) >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f}B"
    if abs(num) >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    if abs(num) >= 1_000:
        return f"{num / 1_000:.2f}K"
    return f"{num:.2f}"


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
    df = df.dropna(axis=0, how="all").sort_index()
    return df


def technical_to_df(payload: dict[str, Any]) -> pd.DataFrame:
    ta_key = next((k for k in payload.keys() if "Technical Analysis" in k), None)
    if not ta_key:
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(payload[ta_key], orient="index")
    if df.empty:
        return df

    df = df.rename(columns={c: normalize_column_name(c) for c in df.columns})
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df.dropna(axis=0, how="all").sort_index()
    return df


def statement_payload_to_df(payload: dict[str, Any], report_scope: str) -> pd.DataFrame:
    key = "annualReports" if report_scope == "annual" else "quarterlyReports"
    df = pd.DataFrame(payload.get(key, []))
    if df.empty:
        return df

    if "fiscalDateEnding" in df.columns:
        df["fiscalDateEnding"] = pd.to_datetime(df["fiscalDateEnding"], errors="coerce")

    numeric_exclusions = {"fiscalDateEnding", "reportedCurrency"}
    for col in df.columns:
        if col in numeric_exclusions:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "fiscalDateEnding" in df.columns:
        df = df.sort_values("fiscalDateEnding", ascending=False)
    return df


def safe_query(function_name: str, **params: str) -> dict[str, Any] | None:
    try:
        return av_query(function_name, **params)
    except requests.RequestException as exc:
        st.error(f"Errore di rete verso Alpha Vantage: {exc}")
    except RuntimeError as exc:
        st.warning(
            "Alpha Vantage ha restituito un messaggio: "
            f"{exc}\n\nSuggerimento: prova piu' tardi o riduci le richieste."
        )
    except Exception as exc:
        st.error(f"Errore inatteso: {exc}")
    return None


def render_home_section() -> None:
    st.subheader("Home: obiettivo della demo")
    st.write(
        "Questa demo nasce per mostrare ai soci un caso concreto: usare Alpha Vantage come "
        "strato dati finanziario standard, combinabile con dashboard operative e componenti AI."
    )

    st.markdown("### Cosa e' implementato oggi")
    st.markdown(
        "- Azioni: overview aziendale, prezzo daily e volumi\n"
        "- Indicatori tecnici: SMA con periodo configurabile\n"
        "- News & sentiment: feed con punteggio sentiment\n"
        "- FX + macroeconomia: serie EUR/USD e US Real GDP\n"
        "- Market movers: top gainers, top losers, most actively traded\n"
        "- Fondamentali: income statement, balance sheet, cash flow + trend EPS\n"
        "- UX demo: ticker esempio a tendina + inserimento manuale"
    )

    st.markdown("### Cosa non e' ancora implementato (ma disponibile su Alpha Vantage)")
    st.markdown(
        "- Dati azionari avanzati: intraday, weekly/monthly, adjusted, bulk quotes\n"
        "- Opzioni USA: chain realtime e storico opzioni\n"
        "- Altri fondamentali: earnings calendar, IPO calendar, listing status\n"
        "- Macro estesa: CPI, inflazione, treasury yields, fed funds, unemployment\n"
        "- Commodities: energia, metalli, agricoli\n"
        "- Crypto completa: intraday + cross di conversione\n"
        "- Indicatori tecnici extra: RSI, MACD, BBANDS, ATR, OBV e molti altri"
    )

    st.markdown("### Potenziale AI + MCP")
    st.markdown(
        "- Alpha Vantage espone anche un MCP server ufficiale: un agente AI puo' interrogare "
        "direttamente dataset finanziari senza scrivere integrazioni custom endpoint per endpoint.\n"
        "- Possibile estensione: copilota interno che risponde a domande del management "
        "(trend ricavi, anomalia volumi, sentiment per ticker, scenario macro), con output "
        "tracciabile su dati aggiornati.\n"
        "- Possibile integrazione operativa: trigger automatici (news negative + rottura SMA + "
        "shock macro) per allerta in dashboard o canali collaboration."
    )

    st.info(
        "Questa app e' una base di studio: dimostra il flusso dati end-to-end e la scalabilita' "
        "verso use case AI/agentic."
    )


def render_stock_section(symbol: str) -> None:
    st.subheader("Azioni: overview + serie storica")
    overview = safe_query("OVERVIEW", symbol=symbol)
    if overview and overview.get("Symbol"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Symbol", overview.get("Symbol", "-"))
        c2.metric("Name", overview.get("Name", "-"))
        c3.metric("Sector", overview.get("Sector", "-"))
        c4.metric("Market Cap", format_human_number(overview.get("MarketCapitalization", "-")))
        st.caption(overview.get("Description", "")[:500] + "...")
    else:
        st.info("Overview non disponibile per questo simbolo.")

    daily = safe_query("TIME_SERIES_DAILY", symbol=symbol, outputsize="compact")
    if not daily:
        return
    df = timeseries_to_df(daily)
    if df.empty or "close" not in df.columns:
        st.info("Serie storica non disponibile.")
        return

    st.line_chart(df[["close"]].tail(120), height=300)
    if "volume" in df.columns:
        st.bar_chart(df[["volume"]].tail(60), height=250)


def render_indicator_section(symbol: str, period: int) -> None:
    st.subheader("Indicatori tecnici: SMA")
    daily = safe_query("TIME_SERIES_DAILY", symbol=symbol, outputsize="compact")
    sma = safe_query(
        "SMA",
        symbol=symbol,
        interval="daily",
        time_period=str(period),
        series_type="close",
    )
    if not daily or not sma:
        return

    price_df = timeseries_to_df(daily)
    sma_df = technical_to_df(sma)
    if price_df.empty or sma_df.empty or "close" not in price_df.columns:
        st.info("Dati insufficienti per calcolare la SMA.")
        return

    sma_col = "sma" if "sma" in sma_df.columns else sma_df.columns[0]
    merged = price_df[["close"]].join(sma_df[[sma_col]], how="inner")
    merged = merged.rename(columns={sma_col: f"sma_{period}"})
    if merged.empty:
        st.info("Nessuna sovrapposizione tra storico prezzi e SMA.")
        return

    st.line_chart(merged.tail(180), height=360)
    st.dataframe(merged.tail(15), use_container_width=True)


def format_news_time(raw_value: str) -> str:
    try:
        return datetime.strptime(raw_value, "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw_value


def render_news_section(symbol: str) -> None:
    st.subheader("Alpha Intelligence: News & Sentiment")
    payload = safe_query("NEWS_SENTIMENT", tickers=symbol, sort="LATEST", limit="20")
    if not payload:
        return

    feed = payload.get("feed", [])
    if not feed:
        st.info("Nessuna news trovata.")
        return

    rows: list[dict[str, Any]] = []
    for item in feed:
        rows.append(
            {
                "published": format_news_time(item.get("time_published", "")),
                "source": item.get("source", ""),
                "title": item.get("title", ""),
                "sentiment_label": item.get("overall_sentiment_label", ""),
                "sentiment_score": item.get("overall_sentiment_score", ""),
                "url": item.get("url", ""),
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_fx_macro_section(from_symbol: str, to_symbol: str, gdp_interval: str) -> None:
    st.subheader("Forex + Macroeconomia")
    fx_payload = safe_query(
        "FX_DAILY",
        from_symbol=from_symbol,
        to_symbol=to_symbol,
        outputsize="compact",
    )
    if fx_payload:
        fx_df = timeseries_to_df(fx_payload)
        if not fx_df.empty and "close" in fx_df.columns:
            st.markdown(f"**FX {from_symbol}/{to_symbol}**")
            st.line_chart(fx_df[["close"]].tail(120), height=260)
        else:
            st.info("Dati FX non disponibili.")

    gdp_payload = safe_query("REAL_GDP", interval=gdp_interval)
    if not gdp_payload:
        return

    values = gdp_payload.get("data", [])
    gdp_df = pd.DataFrame(values)
    if gdp_df.empty or "value" not in gdp_df.columns or "date" not in gdp_df.columns:
        st.info("Dati GDP non disponibili.")
        return

    gdp_df["value"] = pd.to_numeric(gdp_df["value"], errors="coerce")
    gdp_df["date"] = pd.to_datetime(gdp_df["date"], errors="coerce")
    gdp_df = gdp_df.dropna().sort_values("date")

    st.markdown(f"**US Real GDP ({gdp_interval})**")
    st.line_chart(gdp_df.set_index("date")[["value"]], height=260)
    latest = gdp_df.iloc[-1]
    st.caption(f"Ultimo valore: {latest['value']:.2f} ({latest['date'].date()})")


def render_market_movers_section() -> None:
    st.subheader("Market Movers: top gainers, losers e titoli attivi")
    payload = safe_query("TOP_GAINERS_LOSERS")
    if not payload:
        return

    blocks = [
        ("Top Gainers", "top_gainers"),
        ("Top Losers", "top_losers"),
        ("Most Actively Traded", "most_actively_traded"),
    ]
    preferred_cols = ["ticker", "price", "change_amount", "change_percentage", "volume"]

    for title, key in blocks:
        rows = payload.get(key, [])
        st.markdown(f"**{title}**")
        if not rows:
            st.info(f"{title}: dati non disponibili.")
            continue

        df = pd.DataFrame(rows)
        cols = [col for col in preferred_cols if col in df.columns]
        if cols:
            df = df[cols]
        st.dataframe(df.head(20), use_container_width=True, hide_index=True)


def render_statement_block(title: str, df: pd.DataFrame, metrics: list[str]) -> None:
    st.markdown(f"**{title}**")
    if df.empty:
        st.info(f"{title}: dati non disponibili.")
        return

    available_metrics = [metric for metric in metrics if metric in df.columns]
    latest = df.iloc[0]
    top_metrics = available_metrics[:4]
    if top_metrics:
        cols = st.columns(len(top_metrics))
        for idx, metric in enumerate(top_metrics):
            cols[idx].metric(metric, format_human_number(latest.get(metric)))

    table_cols = ["fiscalDateEnding"]
    if "reportedCurrency" in df.columns:
        table_cols.append("reportedCurrency")
    table_cols.extend(available_metrics[:6])
    table_cols = [col for col in table_cols if col in df.columns]
    st.dataframe(df[table_cols].head(8), use_container_width=True, hide_index=True)


def render_financials_section(symbol: str, report_scope: str) -> None:
    st.subheader("Fondamentali: Income Statement, Balance Sheet, Cash Flow, Earnings")
    income_payload = safe_query("INCOME_STATEMENT", symbol=symbol)
    balance_payload = safe_query("BALANCE_SHEET", symbol=symbol)
    cash_payload = safe_query("CASH_FLOW", symbol=symbol)
    earnings_payload = safe_query("EARNINGS", symbol=symbol)

    if earnings_payload:
        earnings_key = "annualEarnings" if report_scope == "annual" else "quarterlyEarnings"
        earnings_df = pd.DataFrame(earnings_payload.get(earnings_key, []))
        if (
            not earnings_df.empty
            and "fiscalDateEnding" in earnings_df.columns
            and "reportedEPS" in earnings_df.columns
        ):
            earnings_df["fiscalDateEnding"] = pd.to_datetime(
                earnings_df["fiscalDateEnding"], errors="coerce"
            )
            earnings_df["reportedEPS"] = pd.to_numeric(earnings_df["reportedEPS"], errors="coerce")
            earnings_df = earnings_df.dropna().sort_values("fiscalDateEnding")
            if not earnings_df.empty:
                st.markdown("**Earnings (EPS)**")
                st.line_chart(
                    earnings_df.set_index("fiscalDateEnding")[["reportedEPS"]].tail(20),
                    height=250,
                )

    income_df = (
        statement_payload_to_df(income_payload, report_scope) if income_payload else pd.DataFrame()
    )
    balance_df = (
        statement_payload_to_df(balance_payload, report_scope) if balance_payload else pd.DataFrame()
    )
    cash_df = statement_payload_to_df(cash_payload, report_scope) if cash_payload else pd.DataFrame()

    render_statement_block(
        "Income Statement",
        income_df,
        ["totalRevenue", "grossProfit", "operatingIncome", "netIncome", "ebitda"],
    )
    render_statement_block(
        "Balance Sheet",
        balance_df,
        [
            "totalAssets",
            "totalLiabilities",
            "totalShareholderEquity",
            "cashAndCashEquivalentsAtCarryingValue",
            "shortLongTermDebtTotal",
        ],
    )
    render_statement_block(
        "Cash Flow",
        cash_df,
        [
            "operatingCashflow",
            "cashflowFromInvestment",
            "cashflowFromFinancing",
            "capitalExpenditures",
            "dividendPayout",
        ],
    )


def main() -> None:
    st.set_page_config(page_title="Demo Alpha Vantage", layout="wide")
    st.title("Demo Alpha Vantage")
    st.write(
        "Progetto studio: panoramica pratica delle API Alpha Vantage e delle estensioni "
        "possibili con AI agentica e MCP."
    )
    st.caption(
        "Nota: il piano free di Alpha Vantage puo' avere limiti di chiamata giornalieri. "
        "Questa app usa cache per ridurre le richieste."
    )

    try:
        _ = load_api_key()
    except Exception as exc:
        st.error(f"Impossibile caricare API key: {exc}")
        st.stop()

    st.sidebar.header("Controlli")
    ticker_examples = ["IBM", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "Inserimento manuale"]
    selected_ticker = st.sidebar.selectbox("Ticker esempio", options=ticker_examples, index=0)
    manual_symbol = st.sidebar.text_input("Ticker azionario (manuale, opzionale)", value="")

    if manual_symbol.strip():
        symbol = manual_symbol.strip().upper()
    elif selected_ticker != "Inserimento manuale":
        symbol = selected_ticker
    else:
        symbol = ""

    period = st.sidebar.slider("SMA period", min_value=5, max_value=60, value=20, step=1)
    from_symbol = st.sidebar.text_input("FX from", value="EUR").strip().upper()
    to_symbol = st.sidebar.text_input("FX to", value="USD").strip().upper()
    gdp_interval = st.sidebar.selectbox("GDP interval", options=["annual", "quarterly"], index=0)
    report_scope = st.sidebar.selectbox("Bilancio interval", options=["annual", "quarterly"], index=0)
    section = st.sidebar.radio(
        "Sezione demo",
        options=[
            "Home",
            "Azioni",
            "Indicatori",
            "News",
            "FX + Macro",
            "Market Movers",
            "Bilancio",
        ],
        index=0,
    )

    if st.sidebar.button("Aggiorna dati (svuota cache)"):
        st.cache_data.clear()
        st.rerun()

    sections_requiring_symbol = {"Azioni", "Indicatori", "News", "Bilancio"}
    if section in sections_requiring_symbol and not symbol:
        st.warning("Inserisci un ticker valido o selezionane uno di esempio.")
        st.stop()

    if section == "Home":
        render_home_section()
    elif section == "Azioni":
        render_stock_section(symbol)
    elif section == "Indicatori":
        render_indicator_section(symbol, period)
    elif section == "News":
        render_news_section(symbol)
    elif section == "FX + Macro":
        render_fx_macro_section(from_symbol, to_symbol, gdp_interval)
    elif section == "Market Movers":
        render_market_movers_section()
    else:
        render_financials_section(symbol, report_scope)


if __name__ == "__main__":
    main()
