scan_id = st.session_state.get("scan_id")

if scan_id:
    st.subheader("Stato scan")

    colA, colB, colC = st.columns([1,1,2])
    with colA:
        if st.button("🔎 Check results"):
            try:
                res = get_results(api_key, scan_id, per_page=1, table_type="products")
                st.session_state["last_results"] = res

                # euristica: se c'è una lista non vuota, consideriamo "pronta"
                ready = False
                for k in ("products", "rows", "items", "data"):
                    if isinstance(res.get(k), list) and len(res[k]) > 0:
                        ready = True
                        break

                st.session_state["ready"] = ready
                st.success("Risposta ricevuta. " + ("✅ Scan pronta" if ready else "⏳ Ancora in elaborazione"))
                st.json(res)
            except Exception as e:
                st.error(f"Check results fallito: {e}")

    with colB:
        if st.button("🛑 Cancel scan"):
            try:
                out = cancel_scan(api_key, scan_id)
                st.warning("Scan cancellata.")
                st.json(out)
            except Exception as e:
                st.error(f"Cancel fallito: {e}")

    ready = st.session_state.get("ready", False)

    st.subheader("Download output")
    st.caption("Il download si abilita solo quando la scan è pronta (evita che si blocchi).")

    export_type = st.selectbox("Formato", ["csv", "xlsx", "json"], index=0)

    if not ready:
        st.info("Prima premi **Check results** finché risulta pronta.")
    else:
        if st.button("⬇️ Scarica ora", type="primary"):
            try:
                b = download_export(api_key, scan_id, export_type)  # :contentReference[oaicite:5]{index=5}
                mime = {
                    "csv": "text/csv",
                    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "json": "application/json",
                }[export_type]
                st.download_button(
                    f"Save {export_type.upper()}",
                    data=b,
                    file_name=f"{scan_id}.{export_type}",
                    mime=mime,
                )
            except Exception as e:
                st.error(f"Download fallito: {e}")
