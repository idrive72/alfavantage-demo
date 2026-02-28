# Demo Alpha Vantage

Questa app mostra in modo pratico cosa puoi fare con i dati Alpha Vantage:

- Home: spiegazione progetto, stato implementazione e roadmap Alpha Vantage/AI/MCP
- Azioni: overview societaria + serie storica prezzi/volumi
- Indicatori tecnici: SMA calcolata via API
- News & sentiment: feed notizie con score di sentiment
- Forex + macroeconomia: serie FX e US Real GDP
- Market movers: top gainers, top losers, most actively traded
- Fondamentali: income statement, balance sheet, cash flow ed earnings (EPS)

## Requisiti

- Python 3.10+
- File `../api_key.txt` con la tua API key Alpha Vantage

## Avvio

```bash
cd app_demo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run app.py
```

In alternativa, senza attivare la venv:

```bash
cd app_demo
.\.venv\Scripts\python -m streamlit run app.py
```

Se PowerShell blocca `Activate.ps1`, usa:

```bash
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Note

- La app usa cache (`st.cache_data`) per ridurre il numero di chiamate API.
- Se i dati sembrano fermi, usa il pulsante `Aggiorna dati (svuota cache)`.
- Con piano free Alpha Vantage potresti ricevere messaggi di limite chiamate.
- Non avviare con `python app.py`: genera molti warning Streamlit (`missing ScriptRunContext`).

## Deploy su Streamlit Community Cloud

- Repo: `https://github.com/idrive72/alfavantage-demo`
- Main file path: `app_demo/app.py`
- Python dependencies: `app_demo/requirements.txt`

Configura la chiave API in `Settings -> Secrets`:

```toml
ALPHAVANTAGE_API_KEY = "la_tua_chiave"
```

L'app usa questa priorita' per leggere la chiave:
1. Variabile ambiente `ALPHAVANTAGE_API_KEY`
2. `st.secrets["ALPHAVANTAGE_API_KEY"]` (cloud)
3. file locale `../api_key.txt`
