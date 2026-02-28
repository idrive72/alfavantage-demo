from __future__ import annotations

from datetime import datetime, timedelta
import os
from pathlib import Path
import random
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
    normalized_params = "|".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"{function_name}|{normalized_params}"


def build_demo_daily_series(symbol: str, days: int, base_price: float, scale: float) -> dict[str, dict[str, str]]:
    seed = sum(ord(char) for char in symbol)
    rng = random.Random(seed)
    today = datetime.utcnow().date()
    current_price = base_price
    rows: dict[str, dict[str, str]] = {}

    for index in range(days):
        date_value = today - timedelta(days=(days - index))
        trend = ((index / max(days, 1)) - 0.5) * (0.5 * scale)
        open_price = max(0.01, current_price + rng.uniform(-0.8, 0.8) * scale)
        close_price = max(0.01, open_price + rng.uniform(-1.4, 1.4) * scale + trend)
        high_price = max(open_price, close_price) + abs(rng.uniform(0.2, 1.2) * scale)
        low_price = max(0.01, min(open_price, close_price) - abs(rng.uniform(0.2, 1.2) * scale))
        volume = int(900_000 + rng.random() * 3_500_000 + index * 2_000)

        rows[date_value.isoformat()] = {
            "1. open": f"{open_price:.4f}",
            "2. high": f"{high_price:.4f}",
            "3. low": f"{low_price:.4f}",
            "4. close": f"{close_price:.4f}",
            "5. volume": str(volume),
        }
        current_price = close_price
    return rows


def build_demo_report_dates(interval: str, count: int) -> list[str]:
    today = datetime.utcnow().date()
    if interval == "annual":
        return [f"{today.year - index}-12-31" for index in range(count)]
    return [(today - timedelta(days=(index * 90))).isoformat() for index in range(count)]


def build_demo_payload(function_name: str, params: dict[str, str]) -> dict[str, Any] | None:
    symbol = params.get("symbol", "DEMO").upper()

    if function_name == "OVERVIEW":
        return {
            "Symbol": symbol,
            "Name": f"{symbol} Demo Corporation",
            "Sector": "TECHNOLOGY",
            "MarketCapitalization": "145000000000",
            "Description": (
                f"{symbol} Demo Corporation (dati inventati) e' usata esclusivamente per "
                "dimostrazione del funzionamento dell'app quando il limite giornaliero API "
                "e' stato superato."
            ),
        }

    if function_name == "TIME_SERIES_DAILY":
        base = 80 + (sum(ord(char) for char in symbol) % 180)
        return {"Time Series (Daily)": build_demo_daily_series(symbol, days=220, base_price=base, scale=1.0)}

    if function_name == "SMA":
        period = max(int(params.get("time_period", "20")), 2)
        series = build_demo_daily_series(symbol, days=240, base_price=120, scale=1.0)
        df = pd.DataFrame.from_dict(series, orient="index")
        df["4. close"] = pd.to_numeric(df["4. close"], errors="coerce")
        df = df.dropna()
        sma = df["4. close"].rolling(period).mean().dropna()
        ta_rows = {str(index): {"SMA": f"{value:.4f}"} for index, value in sma.items()}
        return {"Technical Analysis: SMA": ta_rows}

    if function_name == "NEWS_SENTIMENT":
        seed = sum(ord(char) for char in symbol)
        rng = random.Random(seed)
        now = datetime.utcnow()
        total_items = min(max(int(params.get("limit", "20")), 1), 20)
        feed = []
        for index in range(total_items):
            score = round(rng.uniform(-0.75, 0.75), 3)
            if score > 0.2:
                label = "Bullish"
            elif score < -0.2:
                label = "Bearish"
            else:
                label = "Neutral"
            published = (now - timedelta(hours=index * 6)).strftime("%Y%m%dT%H%M%S")
            feed.append(
                {
                    "time_published": published,
                    "source": "Demo News Wire",
                    "title": f"{symbol}: notizia dimostrativa #{index + 1}",
                    "overall_sentiment_label": label,
                    "overall_sentiment_score": str(score),
                    "url": "https://example.com/demo-news",
                }
            )
        return {"feed": feed}

    if function_name == "FX_DAILY":
        from_symbol = params.get("from_symbol", "EUR").upper()
        to_symbol = params.get("to_symbol", "USD").upper()
        pair = f"{from_symbol}{to_symbol}"
        raw_rows = build_demo_daily_series(pair, days=220, base_price=1.08, scale=0.012)
        fx_rows = {
            date_key: {
                "1. open": row["1. open"],
                "2. high": row["2. high"],
                "3. low": row["3. low"],
                "4. close": row["4. close"],
            }
            for date_key, row in raw_rows.items()
        }
        return {"Time Series FX (Daily)": fx_rows}

    if function_name == "REAL_GDP":
        interval = params.get("interval", "annual")
        points = 40 if interval == "quarterly" else 25
        today = datetime.utcnow().date()
        data = []
        for index in range(points):
            if interval == "annual":
                date_value = f"{today.year - (points - index)}-01-01"
            else:
                date_value = (today - timedelta(days=(points - index) * 90)).isoformat()
            value = 5500 + (index * 370) + (index % 4) * 42
            data.append({"date": date_value, "value": f"{value:.2f}"})
        return {"data": data}

    if function_name == "TOP_GAINERS_LOSERS":
        return {
            "top_gainers": [
                {"ticker": "NVDA", "price": "1023.44", "change_amount": "61.22", "change_percentage": "6.36%", "volume": "58900231"},
                {"ticker": "SMCI", "price": "912.80", "change_amount": "42.65", "change_percentage": "4.90%", "volume": "22344112"},
                {"ticker": "TSLA", "price": "267.21", "change_amount": "10.14", "change_percentage": "3.95%", "volume": "86441022"},
            ],
            "top_losers": [
                {"ticker": "INTC", "price": "31.48", "change_amount": "-1.88", "change_percentage": "-5.64%", "volume": "97311220"},
                {"ticker": "PYPL", "price": "54.66", "change_amount": "-2.12", "change_percentage": "-3.73%", "volume": "33190880"},
                {"ticker": "BABA", "price": "74.39", "change_amount": "-2.44", "change_percentage": "-3.18%", "volume": "28874111"},
            ],
            "most_actively_traded": [
                {"ticker": "AAPL", "price": "213.25", "change_amount": "1.20", "change_percentage": "0.57%", "volume": "121331002"},
                {"ticker": "AMD", "price": "175.08", "change_amount": "2.51", "change_percentage": "1.45%", "volume": "104482719"},
                {"ticker": "AMZN", "price": "195.44", "change_amount": "0.96", "change_percentage": "0.49%", "volume": "91220177"},
            ],
        }

    if function_name in {"INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW"}:
        annual_dates = build_demo_report_dates("annual", 6)
        quarterly_dates = build_demo_report_dates("quarterly", 10)
        annual_reports: list[dict[str, str]] = []
        quarterly_reports: list[dict[str, str]] = []

        for index, date_value in enumerate(annual_dates):
            revenue = 95_000_000_000 - (index * 4_500_000_000)
            assets = 260_000_000_000 - (index * 7_500_000_000)
            cash_flow = 21_000_000_000 - (index * 1_200_000_000)
            if function_name == "INCOME_STATEMENT":
                annual_reports.append(
                    {
                        "fiscalDateEnding": date_value,
                        "reportedCurrency": "USD",
                        "totalRevenue": str(revenue),
                        "grossProfit": str(int(revenue * 0.53)),
                        "operatingIncome": str(int(revenue * 0.24)),
                        "netIncome": str(int(revenue * 0.18)),
                        "ebitda": str(int(revenue * 0.29)),
                    }
                )
            elif function_name == "BALANCE_SHEET":
                annual_reports.append(
                    {
                        "fiscalDateEnding": date_value,
                        "reportedCurrency": "USD",
                        "totalAssets": str(assets),
                        "totalLiabilities": str(int(assets * 0.58)),
                        "totalShareholderEquity": str(int(assets * 0.42)),
                        "cashAndCashEquivalentsAtCarryingValue": str(int(assets * 0.09)),
                        "shortLongTermDebtTotal": str(int(assets * 0.17)),
                    }
                )
            else:
                annual_reports.append(
                    {
                        "fiscalDateEnding": date_value,
                        "reportedCurrency": "USD",
                        "operatingCashflow": str(cash_flow),
                        "cashflowFromInvestment": str(int(-cash_flow * 0.38)),
                        "cashflowFromFinancing": str(int(-cash_flow * 0.27)),
                        "capitalExpenditures": str(int(-cash_flow * 0.22)),
                        "dividendPayout": str(int(cash_flow * 0.12)),
                    }
                )

        for index, date_value in enumerate(quarterly_dates):
            revenue = 24_000_000_000 - (index * 650_000_000)
            assets = 265_000_000_000 - (index * 2_100_000_000)
            cash_flow = 5_700_000_000 - (index * 180_000_000)
            if function_name == "INCOME_STATEMENT":
                quarterly_reports.append(
                    {
                        "fiscalDateEnding": date_value,
                        "reportedCurrency": "USD",
                        "totalRevenue": str(revenue),
                        "grossProfit": str(int(revenue * 0.52)),
                        "operatingIncome": str(int(revenue * 0.23)),
                        "netIncome": str(int(revenue * 0.17)),
                        "ebitda": str(int(revenue * 0.28)),
                    }
                )
            elif function_name == "BALANCE_SHEET":
                quarterly_reports.append(
                    {
                        "fiscalDateEnding": date_value,
                        "reportedCurrency": "USD",
                        "totalAssets": str(assets),
                        "totalLiabilities": str(int(assets * 0.57)),
                        "totalShareholderEquity": str(int(assets * 0.43)),
                        "cashAndCashEquivalentsAtCarryingValue": str(int(assets * 0.10)),
                        "shortLongTermDebtTotal": str(int(assets * 0.18)),
                    }
                )
            else:
                quarterly_reports.append(
                    {
                        "fiscalDateEnding": date_value,
                        "reportedCurrency": "USD",
                        "operatingCashflow": str(cash_flow),
                        "cashflowFromInvestment": str(int(-cash_flow * 0.36)),
                        "cashflowFromFinancing": str(int(-cash_flow * 0.25)),
                        "capitalExpenditures": str(int(-cash_flow * 0.20)),
                        "dividendPayout": str(int(cash_flow * 0.10)),
                    }
                )

        return {"symbol": symbol, "annualReports": annual_reports, "quarterlyReports": quarterly_reports}

    if function_name == "EARNINGS":
        annual_dates = build_demo_report_dates("annual", 8)
        quarterly_dates = build_demo_report_dates("quarterly", 12)
        annual = []
        quarterly = []
        for index, date_value in enumerate(annual_dates):
            annual.append({"fiscalDateEnding": date_value, "reportedEPS": f"{7.8 - index * 0.22:.2f}"})
        for index, date_value in enumerate(quarterly_dates):
            quarterly.append({"fiscalDateEnding": date_value, "reportedEPS": f"{2.1 - index * 0.06:.2f}"})
        return {"symbol": symbol, "annualEarnings": annual, "quarterlyEarnings": quarterly}

    return None


def safe_query(function_name: str, **params: str) -> dict[str, Any] | None:
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
                    "Limite giornaliero di richieste Alpha Vantage superato. "
                    "Verranno utilizzati, se presenti, i dati in cache."
                )
                return fallback_cache[cache_key]
            if st.session_state.get("use_demo_data_on_rate_limit", False):
                demo_payload = build_demo_payload(function_name, params)
                if demo_payload is not None:
                    fallback_cache[cache_key] = demo_payload
                    st.warning(
                        "Limite giornaliero di richieste Alpha Vantage superato. "
                        "Non essendoci cache, vengono usati dati demo inventati "
                        "solo per dimostrazione."
                    )
                    return demo_payload
            st.warning(
                "Limite giornaliero di richieste Alpha Vantage superato. "
                "Non ci sono dati in cache per questa richiesta. "
                "Puoi attivare l'opzione in sidebar per usare dati demo."
            )
        else:
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
        "Questa demo nasce per mostrare ai collaboratori un caso concreto: usare Alpha Vantage come "
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

    st.sidebar.checkbox(
        "Usa dati demo se limite superato",
        key="use_demo_data_on_rate_limit",
        help="Se superi il limite giornaliero e non ci sono dati in cache, "
        "l'app usera' dati inventati solo per dimostrazione.",
    )

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
