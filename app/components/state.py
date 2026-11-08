"""Estado compartido de la app: conexión, caché de datos y filtros globales."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.analytics.dataset import Dataset, load_dataset
from src.analytics.filters import Filters
from src.config import SAMPLE_DIR, database_url
from src.data.demo_generator import load_demo
from src.data.sample_files import write_samples
from src.database.connection import get_engine, init_db, is_populated

FILTER_KEYS = ("f_months", "f_regions", "f_categories", "f_products")


@st.cache_resource(show_spinner=False)
def engine():
    return get_engine(database_url())


def _db_version() -> float:
    """Cambia cuando la base se modifica (importaciones o regeneración) para invalidar la caché."""
    url = database_url()
    path = Path(url.replace("sqlite:///", "", 1)) if url.startswith("sqlite:///") else None
    stamp = path.stat().st_mtime if path and path.exists() else 0.0
    return stamp + st.session_state.get("data_version", 0)


@st.cache_data(show_spinner="Cargando datos…", max_entries=2)
def _dataset(_version: float) -> Dataset:
    return load_dataset(engine())


def bootstrap() -> None:
    """Crea la base y carga los datos DEMO la primera vez que se ejecuta la app."""
    eng = engine()
    init_db(eng)
    if not is_populated(eng):
        with st.spinner("Primera ejecución: generando base de datos DEMO (puede tardar unos segundos)…"):
            load_demo(eng)
            write_samples(SAMPLE_DIR)
        st.toast("Base de datos DEMO creada correctamente.", icon=":material/check_circle:")


def dataset() -> Dataset:
    return _dataset(_db_version())


def invalidate() -> None:
    st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
    _dataset.clear()


def reset_filters() -> None:
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def sidebar_filters(ds: Dataset) -> Filters:
    months = ds.months
    if not months:
        st.sidebar.warning("No hay ventas cargadas.")
        return Filters()
    lines = ds.lines
    with st.sidebar:
        st.markdown("#### Filtros")
        default = (months[max(0, len(months) - 6)], months[-1])
        if "f_months" in st.session_state and not set(st.session_state["f_months"]) <= set(months):
            st.session_state.pop("f_months")
        start, end = st.select_slider("Periodo (mes)", options=months, value=default, key="f_months")
        regions = st.multiselect("Región", sorted(lines["region"].unique()), key="f_regions",
                                 placeholder="Todas")
        categories = st.multiselect("Categoría", sorted(lines["categoria"].unique()), key="f_categories",
                                    placeholder="Todas")
        pool = lines[lines["categoria"].isin(categories)] if categories else lines
        product_options = sorted(pool["producto"].unique())
        if "f_products" in st.session_state:
            st.session_state["f_products"] = [p for p in st.session_state["f_products"] if p in product_options]
        products = st.multiselect("Producto", product_options, key="f_products", placeholder="Todos")
        st.button("Restablecer filtros", on_click=reset_filters, icon=":material/restart_alt:", width="stretch")
    return Filters(start_month=start, end_month=end, regions=tuple(regions), categories=tuple(categories),
                   products=tuple(products))


def current_filters() -> Filters:
    return st.session_state.get("filters", Filters())
