# MarketGuard Demo

`MarketGuard` e' una demo in stile **Risk & Alert Desk**:

- monitoraggio FX e commodity
- alert operativi su soglie
- scenario planner per esposizione USD
- feed news con sentiment
- blueprint AI + MCP

## Requisiti

- Python 3.10+
- API key Alpha Vantage in uno di questi modi:
  - secret/var `ALPHAVANTAGE_API_KEY`
  - file `../api_key.txt`

## Avvio locale (PowerShell)

```bash
cd app_MarketGuard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run app.py
```

Senza attivazione venv:

```bash
cd app_MarketGuard
.\.venv\Scripts\python -m streamlit run app.py
```

## Note operative

- Se il limite giornaliero API viene superato:
  - MarketGuard usa cache se disponibile
  - in alternativa puo' usare dati demo sintetici (toggle in sidebar)
- Il modulo `AI + MCP` e' blueprint architetturale, non esecuzione ordini.

## Deploy Streamlit Community Cloud

- Main file path: `app_MarketGuard/app.py`
- Requirements: `app_MarketGuard/requirements.txt`
- Secret da configurare:

```toml
ALPHAVANTAGE_API_KEY = "la_tua_chiave"
```
