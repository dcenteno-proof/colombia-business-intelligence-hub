"""Componentes visuales reutilizables (tema corporativo, tarjetas KPI, tablas)."""
from __future__ import annotations

import html
from typing import Callable, Iterable

import pandas as pd
import streamlit as st

from app.components import formatting as fmt
from src.config import COMPANY_NAME

PALETTE = {
    "navy": "#0F2747", "teal": "#0E7C86", "teal_light": "#5FB3B9", "gold": "#C9A227", "slate": "#64748B",
    "grid": "#E2E8F0", "bg": "#F5F7FA", "red": "#B42318", "green": "#067647", "amber": "#B54708",
}
SERIES = ["#0F2747", "#0E7C86", "#C9A227", "#5B7DB1", "#7A9E7E", "#B4654A", "#8E7CC3", "#64748B"]

CSS = """
<style>
html, body, [class*="css"] { font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif; }
.block-container { padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1480px; }
[data-testid="stSidebar"] { background: #0F2747; }
[data-testid="stSidebar"] * { color: #E6ECF5 !important; }
[data-testid="stSidebar"] [data-baseweb="select"] * , [data-testid="stSidebar"] input { color: #1E293B !important; }
[data-testid="stSidebar"] [data-baseweb="tag"] { background: #0E7C86 !important; }
[data-testid="stSidebar"] [data-baseweb="tag"] * { color: #FFFFFF !important; }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: rgba(255,255,255,.12); border-radius: 6px; }
[data-testid="stSidebar"] button { background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.25); }
.cbh-header { display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; flex-wrap:wrap;
  border-bottom:1px solid #E2E8F0; padding-bottom:.8rem; margin-bottom:1.1rem; }
.cbh-title { font-size:1.65rem; font-weight:700; color:#0F2747; margin:0; line-height:1.2; }
.cbh-sub { color:#64748B; font-size:.92rem; margin-top:.25rem; }
.cbh-badges { display:flex; gap:.4rem; flex-wrap:wrap; }
.cbh-badge { font-size:.72rem; font-weight:600; letter-spacing:.04em; padding:.25rem .6rem; border-radius:999px;
  background:#E7F3F4; color:#0E7C86; border:1px solid #BFE0E3; white-space:nowrap; }
.cbh-badge.demo { background:#FEF6E7; color:#93370D; border-color:#F7D9A4; }
.kpi { background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:.8rem .9rem .75rem;
  box-shadow:0 1px 2px rgba(15,39,71,.04); height:100%; min-height:112px; }
.kpi-label { color:#64748B; font-size:.72rem; font-weight:600; text-transform:uppercase; letter-spacing:.03em;
  line-height:1.3; }
.kpi-value { color:#0F2747; font-size:clamp(1.05rem, 1.55vw, 1.45rem); font-weight:700; margin:.3rem 0 .2rem;
  line-height:1.25; word-break:break-word; }
.kpi-delta { font-size:.76rem; font-weight:600; line-height:1.3; }
.kpi-delta.up { color:#067647; } .kpi-delta.down { color:#B42318; } .kpi-delta.flat { color:#64748B; }
.kpi-foot { color:#94A3B8; font-size:.72rem; margin-top:.15rem; }
.cbh-section { font-size:1.05rem; font-weight:700; color:#0F2747; margin:1.2rem 0 .4rem; }
.cbh-note { color:#64748B; font-size:.8rem; }
.alert-card { background:#FFFFFF; border:1px solid #E2E8F0; border-left:5px solid #B54708; border-radius:8px;
  padding:.8rem 1rem; margin-bottom:.6rem; }
.alert-card.Alta { border-left-color:#B42318; } .alert-card.Media { border-left-color:#B54708; }
.alert-card.Baja { border-left-color:#0E7C86; }
.alert-title { font-weight:700; color:#0F2747; }
.alert-meta { color:#64748B; font-size:.78rem; margin:.15rem 0 .45rem; }
.alert-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap:.4rem .9rem;
  font-size:.84rem; }
.alert-grid b { color:#334155; display:block; font-size:.72rem; text-transform:uppercase; letter-spacing:.03em; }
.alert-reco { margin-top:.5rem; font-size:.86rem; background:#F5F7FA; border-radius:6px; padding:.45rem .6rem; }
.sev { font-size:.7rem; font-weight:700; padding:.12rem .5rem; border-radius:999px; margin-left:.4rem; }
.sev.Alta { background:#FEE4E2; color:#B42318; } .sev.Media { background:#FEF0C7; color:#93370D; }
.sev.Baja { background:#E7F3F4; color:#0E7C86; }
div[data-testid="stTabs"] button p { font-weight:600; }
@media (max-width: 640px) { .kpi { min-height:auto; } .kpi-value { font-size:1.2rem; } .cbh-title { font-size:1.3rem; } }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", period: str | None = None) -> None:
    badges = '<span class="cbh-badge demo">DATOS DEMO</span>'
    if period:
        badges += f'<span class="cbh-badge">{html.escape(period)}</span>'
    st.markdown(
        f'<div class="cbh-header"><div><div class="cbh-title">{html.escape(title)}</div>'
        f'<div class="cbh-sub">{html.escape(subtitle or COMPANY_NAME)}</div></div>'
        f'<div class="cbh-badges">{badges}</div></div>', unsafe_allow_html=True)


def section(title: str, note: str | None = None) -> None:
    st.markdown(f'<div class="cbh-section">{html.escape(title)}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="cbh-note">{html.escape(note)}</div>', unsafe_allow_html=True)


def _delta_html(delta: float | None, kind: str, inverse: bool, label: str) -> str:
    if delta is None or pd.isna(delta):
        return f'<div class="kpi-delta flat">— sin base comparable</div>'
    good = delta >= 0 if not inverse else delta <= 0
    cls = "flat" if abs(delta) < 1e-9 else ("up" if good else "down")
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "■")
    text = fmt.pp(delta) if kind == "pp" else fmt.pct(delta, signed=True)
    return f'<div class="kpi-delta {cls}">{arrow} {text} {html.escape(label)}</div>'


def kpi_card(label: str, value: str, delta: float | None = None, delta_kind: str = "pct", inverse: bool = False,
             delta_label: str = "vs periodo anterior", foot: str | None = None, show_delta: bool = True,
             help_text: str | None = None) -> None:
    delta_html = _delta_html(delta, delta_kind, inverse, delta_label) if show_delta else ""
    foot_html = f'<div class="kpi-foot">{html.escape(foot)}</div>' if foot else ""
    title_attr = f' title="{html.escape(help_text)}"' if help_text else ""
    st.markdown(f'<div class="kpi"{title_attr}><div class="kpi-label">{html.escape(label)}</div>'
                f'<div class="kpi-value">{html.escape(value)}</div>{delta_html}{foot_html}</div>',
                unsafe_allow_html=True)


def kpi_row(cards: list[dict], columns: int | None = None) -> None:
    cols = st.columns(columns or len(cards))
    for i, card in enumerate(cards):
        with cols[i % len(cols)]:
            kpi_card(**card)


def table(df: pd.DataFrame, money: Iterable[str] = (), percent: Iterable[str] = (), integers: Iterable[str] = (),
          decimals: Iterable[str] = (), dates: Iterable[str] = (), rename: dict[str, str] | None = None,
          height: int | None = None, pp_cols: Iterable[str] = ()) -> None:
    """Tabla interactiva (orden, búsqueda, pantalla completa) con formato colombiano.
    Se usa ``Styler`` para que el orden siga los valores numéricos y no el texto."""
    if df is None or df.empty:
        st.info("No hay registros para los filtros seleccionados.")
        return
    formatters: dict[str, Callable] = {}
    for c in money:
        formatters[c] = fmt.cop
    for c in percent:
        formatters[c] = fmt.pct
    for c in pp_cols:
        formatters[c] = fmt.pp
    for c in integers:
        formatters[c] = fmt.num
    for c in decimals:
        formatters[c] = lambda v: fmt.num(v, 1)
    for c in dates:
        formatters[c] = lambda v: "" if pd.isna(v) else pd.Timestamp(v).strftime("%Y-%m-%d")
    data = df.copy()
    formatters = {k: v for k, v in formatters.items() if k in data.columns}
    rename = rename or {}
    styled = data.rename(columns=rename).style.format(
        {rename.get(k, k): v for k, v in formatters.items()}, na_rep=fmt.NA)
    kwargs = {"hide_index": True}
    if height:
        kwargs["height"] = height
    st.dataframe(styled, **kwargs)


def empty_state(message: str) -> None:
    st.info(message, icon=":material/info:")


def alert_card(a: dict) -> None:
    e = {k: html.escape(str(v)) for k, v in a.items()}
    st.markdown(
        f'<div class="alert-card {e["severidad"]}"><div class="alert-title">{e["titulo"]}'
        f'<span class="sev {e["severidad"]}">{e["severidad"]}</span></div>'
        f'<div class="alert-meta">{e["modulo"]} · {e["regla"]} · Periodo {e["periodo"]}</div>'
        f'<div class="alert-grid"><div><b>Motivo</b>{e["motivo"]}</div><div><b>Indicador</b>{e["indicador"]}</div>'
        f'<div><b>Valor observado</b>{e["valor_observado"]}</div><div><b>Umbral</b>{e["umbral"]}</div></div>'
        f'<div class="alert-reco"><b>Recomendación:</b> {e["recomendacion"]}</div></div>', unsafe_allow_html=True)
