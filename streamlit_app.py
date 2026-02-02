import io
import json
import pandas as pd
import requests
import streamlit as st

BASE_URL = "https://app.rocketsource.io"  # 


def headers(api_key: str):
    return {"Authorization": f"Bearer {api_key}"}  # 


def create_scan(api_key: str, file_bytes: bytes, filename: str, attributes: dict) -> dict:
    url = f"{BASE_URL}/api/v3/scans"  # 
    files = {"file": (filename, file_bytes)}
    data = {"attributes": json.dumps(attributes)}
    r = requests.post(url, headers=headers(api_key), files=files, data=data, timeout=120)
    r.raise_for_status()
    return r.json() if r.content else {}


def download_export(api_key: str, scan_id: str, export_type: str) -> bytes:
    url = f"{BASE_URL}/api/v3/scans/{scan_id}/download"  # 
    r = requests.post(url, headers=headers(api_key), params={"type": export_type}, timeout=300)  # 
    r.raise_for_status()
    return r.content


def extract_scan_id(resp: dict):
    # Defensive: response shape not fully documented publicly.
    for k in ("scan_id", "scanId", "id"):
        if k in resp and resp[k]:
            return str(resp[k])
    if isinstance(resp.get("scan"), dict):
        for k in ("scan_id", "scanId", "id"):
            if resp["scan"].get(k):
                return str(resp["scan"][k])
    return None


st.set_page_config(page_title="RocketSource Simple Scanner", layout="centered")
st.title("RocketSource • CSV Upload → Export")

api_key = st.text_input(
    "RocketSource API Key",
    value=st.secrets.get("ROCKETSOURCE_API_KEY", ""),
    type="password",
)

uploaded = st.file_uploader("Upload CSV", type=["csv"])

if not api_key:
    st.info("Enter API key.")
    st.stop()

if not uploaded:
    st.info("Upload a CSV to continue.")
    st.stop()

# Read CSV
file_bytes = uploaded.getvalue()
df = pd.read_csv(io.BytesIO(file_bytes))
cols = list(df.columns)

st.write("Preview")
st.dataframe(df.head(10), use_container_width=True)

id_col = st.selectbox("ID column (required)", cols, index=0)
cost_col = st.selectbox("Cost column (required)", cols, index=1 if len(cols) > 1 else 0)

marketplace_id = st.text_input("Marketplace ID", value="US")

if st.button("Run scan", type="primary"):
    mapping = {
        "id": cols.index(id_col),     # 0-indexed column numbers 
        "cost": cols.index(cost_col), # 0-indexed column numbers 
    }
    attributes = {"mapping": mapping, "options": {"marketplace_id": marketplace_id}}

    try:
        resp = create_scan(api_key, file_bytes, uploaded.name, attributes)
        scan_id = extract_scan_id(resp)

        st.success(f"Uploaded. Scan ID: {scan_id if scan_id else '(not found)'}")
        st.session_state["scan_id"] = scan_id
        st.session_state["raw_resp"] = resp
    except Exception as e:
        st.error(f"Upload failed: {e}")

scan_id = st.session_state.get("scan_id")

if scan_id:
    st.subheader("Download output")
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Download CSV"):
            b = download_export(api_key, scan_id, "csv")
            st.download_button("Save CSV", b, file_name=f"{scan_id}.csv", mime="text/csv")

    with c2:
        if st.button("Download XLSX"):
            b = download_export(api_key, scan_id, "xlsx")
            st.download_button(
                "Save XLSX",
                b,
                file_name=f"{scan_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with c3:
        if st.button("Download JSON"):
            b = download_export(api_key, scan_id, "json")
            st.download_button("Save JSON", b, file_name=f"{scan_id}.json", mime="application/json")

    with st.expander("Raw API response"):
        st.json(st.session_state.get("raw_resp", {}))
