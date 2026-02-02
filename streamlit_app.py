import io
import json
import time
from typing import Dict, Any, Optional, List

import pandas as pd
import requests
import streamlit as st


# RocketSource base URL per docs
BASE_URL = "https://app.rocketsource.io"  # :contentReference[oaicite:2]{index=2}


def rs_headers(api_key: str) -> Dict[str, str]:
    # Docs: Bearer token in Authorization header :contentReference[oaicite:3]{index=3}
    return {"Authorization": f"Bearer {api_key}"}


def upload_scan(api_key: str, file_bytes: bytes, filename: str, attributes: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST /api/v3/scans (multipart form: file + attributes JSON)
    """
    url = f"{BASE_URL}/api/v3/scans"  # :contentReference[oaicite:4]{index=4}
    files = {
        "file": (filename, file_bytes),
    }
    data = {
        "attributes": json.dumps(attributes)
    }
    resp = requests.post(url, headers=rs_headers(api_key), files=files, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def get_results(api_key: str, scan_id: str, page: int = 0, per_page: int = 100, table_type: str = "products") -> Dict[str, Any]:
    """
    POST /api/v3/scans/{scan_id} (JSON body)
    """
    url = f"{BASE_URL}/api/v3/scans/{scan_id}"  # :contentReference[oaicite:5]{index=5}
    payload = {"page": page, "per_page": per_page, "tableType": table_type}  # tableType: products|errors :contentReference[oaicite:6]{index=6}
    resp = requests.post(url, headers={**rs_headers(api_key), "Content-Type": "application/json"}, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def download_export(api_key: str, scan_id: str, export_type: str) -> bytes:
    """
    POST /api/v3/scans/{scan_id}/download?type=csv|xlsx|json
    """
    url = f"{BASE_URL}/api/v3/scans/{scan_id}/download"
    params = {"type": export_type}  # :contentReference[oaicite:7]{index=7}
    resp = requests.post(url, headers=rs_headers(api_key), params=params, timeout=300)
    resp.raise_for_status()
    return resp.content


def first_nonempty_id(obj: Dict[str, Any]) -> Optional[str]:
    """
    RocketSource upload response isn't documented in the public page, so we try common patterns safely.
    """
    for key in ["id", "scan_id", "scanId"]:
        if key in obj and obj[key]:
            return str(obj[key])
    # sometimes nested, e.g. { "scan": { "id": ... } }
    for key in ["scan", "data"]:
        if key in obj and isinstance(obj[key], dict):
            inner = obj[key]
            for k2 in ["id", "scan_id", "scanId"]:
                if k2 in inner and inner[k2]:
                    return str(inner[k2])
    return None


st.set_page_config(page_title="RocketSource CSV Scanner", layout="wide")
st.title("RocketSource • CSV Upload → Column Match → Export Output")

# ---- API KEY handling (Streamlit Secrets preferred) ----
default_key = ""
if "ROCKETSOURCE_API_KEY" in st.secrets:
    default_key = st.secrets["ROCKETSOURCE_API_KEY"]

api_key = st.text_input("RocketSource API Key", value=default_key, type="password", help="Stored in Streamlit secrets recommended.")
if not api_key:
    st.info("Enter your RocketSource API key to continue.")
    st.stop()

st.caption("RocketSource expects the mapping values to be **0-indexed column numbers**. "  # :contentReference[oaicite:8]{index=8}
           "This app builds that mapping from your selected column names.")

uploaded = st.file_uploader("Upload CSV (or XLSX)", type=["csv", "xlsx"])

if uploaded:
    # Read file for preview + columns
    file_bytes = uploaded.getvalue()
    filename = uploaded.name.lower()

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

    st.subheader("1) Preview")
    st.dataframe(df.head(25), use_container_width=True)

    cols: List[str] = list(df.columns)

    st.subheader("2) Match columns (RocketSource mapping)")

    left, right = st.columns(2)

    with left:
        id_col = st.selectbox("ID column (required) — UPC/EAN/ISBN/ASIN/etc.", options=cols, index=0)
        cost_col = st.selectbox("Cost column (required)", options=cols, index=1 if len(cols) > 1 else 0)

        supplier_sku_col = st.selectbox("Supplier SKU (optional)", options=["(none)"] + cols, index=0)
        supplier_image_col = st.selectbox("Supplier Image URL (optional)", options=["(none)"] + cols, index=0)
        supplier_pack_qty_col = st.selectbox("Supplier Pack Quantity (optional)", options=["(none)"] + cols, index=0)

    with right:
        map_col = st.selectbox("MAP (optional)", options=["(none)"] + cols, index=0)
        stock_qty_col = st.selectbox("Stock Quantity (optional)", options=["(none)"] + cols, index=0)
        discount_per_product_col = st.selectbox("Discount per product (optional)", options=["(none)"] + cols, index=0)

        custom_cols = st.multiselect(
            "Custom columns to pass-through (optional)",
            options=cols,
            help="RocketSource accepts custom_columns as column indices + optional custom column names in options."
        )

    st.subheader("3) Scan options")
    opt1, opt2, opt3 = st.columns(3)
    with opt1:
        marketplace_id = st.text_input("Marketplace ID", value="US", help='Example: "US", "CA", "DE", etc.')  # :contentReference[oaicite:9]{index=9}
    with opt2:
        scan_name = st.text_input("Scan name", value=f"Streamlit Scan - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    with opt3:
        header = st.checkbox("File has header row", value=True)

    # Build mapping (0-indexed column numbers) :contentReference[oaicite:10]{index=10}
    def idx(colname: str) -> int:
        return cols.index(colname)

    mapping: Dict[str, Any] = {
        "id": idx(id_col),
        "cost": idx(cost_col),
        "custom_columns": [idx(c) for c in custom_cols],
    }

    def set_optional(key: str, selected: str):
        if selected and selected != "(none)":
            mapping[key] = idx(selected)

    set_optional("supplier_sku", supplier_sku_col)
    set_optional("supplier_image", supplier_image_col)
    set_optional("supplier_pack_quantity", supplier_pack_qty_col)
    set_optional("map", map_col)
    set_optional("stock_quantity", stock_qty_col)
    set_optional("discount_per_product", discount_per_product_col)

    options: Dict[str, Any] = {
        "marketplace_id": marketplace_id,
        "name": scan_name,
        "header": header,
    }

    # If custom cols chosen, provide labels too (nice for downstream exports)
    if custom_cols:
        options["custom_columns"] = custom_cols

    attributes = {"mapping": mapping, "options": options}

    with st.expander("Show payload sent to RocketSource"):
        st.json(attributes)

    st.divider()

    if "scan_id" not in st.session_state:
        st.session_state["scan_id"] = None

    run = st.button("🚀 Upload to RocketSource & Start Scan", type="primary")
    if run:
        try:
            resp = upload_scan(api_key, file_bytes, uploaded.name, attributes)
            scan_id = first_nonempty_id(resp)
            st.session_state["scan_id"] = scan_id
            st.success(f"Uploaded! Response received. Scan ID: {scan_id if scan_id else '(not found in response)'}")
            st.json(resp)
        except requests.HTTPError as e:
            st.error(f"Upload failed: {e}\n\nDetails: {getattr(e.response, 'text', '')}")
        except Exception as e:
            st.error(f"Upload failed: {e}")

    scan_id = st.session_state.get("scan_id")

    if scan_id:
        st.subheader("4) Fetch results / Export output")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            table_type = st.selectbox("Table type", ["products", "errors"], index=0)
        with c2:
            per_page = st.number_input("Per page", min_value=1, max_value=100, value=100, step=1)
        with c3:
            page = st.number_input("Page", min_value=0, value=0, step=1)
        with c4:
            fetch = st.button("🔄 Fetch results now")

        if fetch:
            try:
                res = get_results(api_key, scan_id, page=int(page), per_page=int(per_page), table_type=table_type)
                st.json(res)

                # Try to display a table if we can find list-like data
                # (API response format not fully documented publicly, so we’re defensive.)
                rows = None
                for k in ["rows", "data", "items", "products", "errors"]:
                    if k in res and isinstance(res[k], list):
                        rows = res[k]
                        break
                if rows is None and isinstance(res, list):
                    rows = res

                if rows and isinstance(rows, list):
                    try:
                        out_df = pd.DataFrame(rows)
                        st.dataframe(out_df, use_container_width=True)
                    except Exception:
                        pass
            except requests.HTTPError as e:
                st.error(f"Fetch failed: {e}\n\nDetails: {getattr(e.response, 'text', '')}")
            except Exception as e:
                st.error(f"Fetch failed: {e}")

        st.markdown("### Export (recommended: download CSV from RocketSource)")
        e1, e2, e3 = st.columns(3)
        with e1:
            if st.button("⬇️ Download CSV"):
                try:
                    b = download_export(api_key, scan_id, "csv")  # :contentReference[oaicite:11]{index=11}
                    st.download_button("Save CSV", data=b, file_name=f"{scan_id}.csv", mime="text/csv")
                except Exception as e:
                    st.error(f"CSV download failed: {e}")
        with e2:
            if st.button("⬇️ Download XLSX"):
                try:
                    b = download_export(api_key, scan_id, "xlsx")  # :contentReference[oaicite:12]{index=12}
                    st.download_button("Save XLSX", data=b, file_name=f"{scan_id}.xlsx",
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except Exception as e:
                    st.error(f"XLSX download failed: {e}")
        with e3:
            if st.button("⬇️ Download JSON"):
                try:
                    b = download_export(api_key, scan_id, "json")  # :contentReference[oaicite:13]{index=13}
                    st.download_button("Save JSON", data=b, file_name=f"{scan_id}.json", mime="application/json")
                except Exception as e:
                    st.error(f"JSON download failed: {e}")
else:
    st.info("Upload a CSV/XLSX to begin.")
