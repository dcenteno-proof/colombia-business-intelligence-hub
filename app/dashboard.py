"""Punto de entrada de Colombia Business Intelligence Hub.

Ejecutar desde la raíz del proyecto:
    streamlit run app/dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.components import state, ui  # noqa: E402
from src.config import COMPANY_NAME  # noqa: E402

st.set_page_config(page_title="Colombia BI Hub", page_icon=":material/insights:", layout="wide",
                   initial_sidebar_state="expanded")
ui.inject_css()

PAGES = Path(__file__).parent / "pages"
navigation = st.navigation({
    "Resumen": [
        st.Page(PAGES / "ejecutivo.py", title="Dashboard ejecutivo", icon=":material/dashboard:", default=True),
    ],
    "Inteligencia": [
        st.Page(PAGES / "comercial.py", title="Comercial", icon=":material/storefront:"),
        st.Page(PAGES / "financiero.py", title="Financiera", icon=":material/account_balance:"),
        st.Page(PAGES / "operacional.py", title="Operacional", icon=":material/inventory_2:"),
        st.Page(PAGES / "clientes.py", title="Clientes", icon=":material/groups:"),
    ],
    "Gestión": [
        st.Page(PAGES / "alertas.py", title="Centro de alertas", icon=":material/notifications_active:"),
        st.Page(PAGES / "reportes.py", title="Reportes", icon=":material/download:"),
        st.Page(PAGES / "centro_datos.py", title="Centro de datos", icon=":material/database:"),
        st.Page(PAGES / "metodologia.py", title="Metodología", icon=":material/menu_book:"),
    ],
})

with st.sidebar:
    st.markdown("### Colombia BI Hub")
    st.caption(f"{COMPANY_NAME}  \nDatos sintéticos de demostración")

try:
    state.bootstrap()
    ds = state.dataset()
except Exception as exc:  # error de infraestructura: mensaje claro en vez de traza
    st.error(f"No fue posible conectar o preparar la base de datos: {exc}", icon=":material/error:")
    st.stop()

st.session_state["filters"] = state.sidebar_filters(ds)
with st.sidebar:
    st.divider()
    st.caption("v1.0 · Streamlit + SQLite · Montos en COP")

navigation.run()
