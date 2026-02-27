# Demo Alpha Vantage

Questa app mostra in modo pratico cosa puoi fare con i dati Alpha Vantage:

- Azioni: overview societaria + serie storica prezzi/volumi
- Indicatori tecnici: SMA calcolata via API
- News & sentiment: feed notizie con score di sentiment
- Forex + macroeconomia: serie FX e US Real GDP

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
