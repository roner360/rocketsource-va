# RocketSource Streamlit Uploader

Streamlit app to:
1) Upload CSV/XLSX
2) Map columns to RocketSource scan mapping
3) Create a scan via RocketSource API
4) Fetch results and download exports (CSV/XLSX/JSON)

## Local run
```bash
python -m venv .venv
source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
streamlit run streamlit_app.py
