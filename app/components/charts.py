"""Gráficos Plotly con estilo corporativo y formato numérico colombiano."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components.ui import PALETTE, SERIES

CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"], "locale": "es"}


def style(fig: go.Figure, height: int = 360, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=48, b=10), paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#334155"),
        separators=",.", colorway=SERIES, showlegend=legend, hoverlabel=dict(bgcolor="white"),
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0, title=None),
        title=dict(font=dict(size=14, color=PALETTE["navy"]), x=0, xanchor="left"),
    )
    fig.update_xaxes(showgrid=False, linecolor=PALETTE["grid"], title=None)
    fig.update_yaxes(gridcolor=PALETTE["grid"], zeroline=False, title=None)
    return fig


def show(fig: go.Figure) -> None:
    st.plotly_chart(fig, theme=None, config=CONFIG)


def sales_trend(monthly: pd.DataFrame, title: str = "Ventas netas, utilidad bruta y margen") -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=monthly["mes"], y=monthly["ventas_netas"], name="Ventas netas", marker_color=PALETTE["navy"],
                hovertemplate="%{x}<br>Ventas netas: $%{y:,.0f}<extra></extra>")
    fig.add_bar(x=monthly["mes"], y=monthly["utilidad_bruta"], name="Utilidad bruta", marker_color=PALETTE["teal"],
                hovertemplate="%{x}<br>Utilidad bruta: $%{y:,.0f}<extra></extra>")
    fig.add_scatter(x=monthly["mes"], y=monthly["margen_bruto"], name="Margen bruto %", yaxis="y2", mode="lines+markers",
                    line=dict(color=PALETTE["gold"], width=3),
                    hovertemplate="%{x}<br>Margen bruto: %{y:.1f} %<extra></extra>")
    fig.update_layout(title=title, barmode="group", yaxis=dict(tickprefix="$", tickformat="~s"),
                      yaxis2=dict(overlaying="y", side="right", ticksuffix=" %", tickformat=".0f", showgrid=False,
                                  rangemode="tozero"))
    fig.update_xaxes(type="category")
    return style(fig)


def period_comparison(cur: pd.DataFrame, prev: pd.DataFrame, value: str = "ventas_netas",
                      title: str = "Comparación con el periodo anterior") -> go.Figure:
    fig = go.Figure()
    cur = cur.reset_index(drop=True)
    prev = prev.reset_index(drop=True)
    labels = [f"Mes {i + 1}" for i in range(max(len(cur), len(prev)))]
    if not prev.empty:
        fig.add_bar(x=labels[:len(prev)], y=prev[value], name="Periodo anterior", marker_color="#CBD5E1",
                    customdata=prev["mes"], hovertemplate="%{customdata}: $%{y:,.0f}<extra></extra>")
    fig.add_bar(x=labels[:len(cur)], y=cur[value], name="Periodo actual", marker_color=PALETTE["navy"],
                customdata=cur["mes"], hovertemplate="%{customdata}: $%{y:,.0f}<extra></extra>")
    fig.update_layout(title=title, barmode="group", yaxis=dict(tickprefix="$", tickformat="~s"))
    return style(fig)


def hbar(df: pd.DataFrame, x: str, y: str, title: str, money: bool = True, color: str | None = None,
         height: int = 360, text_pct: str | None = None) -> go.Figure:
    data = df.sort_values(x, ascending=True)
    fig = go.Figure(go.Bar(x=data[x], y=data[y], orientation="h", marker_color=color or PALETTE["teal"],
                           text=[f"{v:.1f} %".replace(".", ",") for v in data[text_pct]] if text_pct else None,
                           textposition="outside" if text_pct else None,
                           hovertemplate="%{y}: " + ("$%{x:,.0f}" if money else "%{x:,.1f}") + "<extra></extra>"))
    fig.update_layout(title=title)
    if money:
        fig.update_xaxes(tickprefix="$", tickformat="~s")
    return style(fig, height=height, legend=False)


def donut(df: pd.DataFrame, names: str, values: str, title: str, height: int = 340) -> go.Figure:
    fig = go.Figure(go.Pie(labels=df[names], values=df[values], hole=0.58, sort=True, marker=dict(colors=SERIES),
                           hovertemplate="%{label}<br>$%{value:,.0f} (%{percent})<extra></extra>",
                           textinfo="percent"))
    fig.update_layout(title=title)
    return style(fig, height=height)


def lines(df: pd.DataFrame, x: str, y: str, color: str, title: str, money: bool = True, suffix: str = "",
          height: int = 360) -> go.Figure:
    fig = px.line(df, x=x, y=y, color=color, markers=True, color_discrete_sequence=SERIES)
    fig.update_traces(hovertemplate="%{x}<br>" + ("$%{y:,.0f}" if money else "%{y:,.1f}" + suffix) + "<extra></extra>")
    fig.update_layout(title=title)
    if money:
        fig.update_yaxes(tickprefix="$", tickformat="~s")
    elif suffix:
        fig.update_yaxes(ticksuffix=suffix)
    fig.update_xaxes(type="category")
    return style(fig, height=height)


def stacked(df: pd.DataFrame, x: str, y: str, color: str, title: str, height: int = 360) -> go.Figure:
    fig = px.bar(df, x=x, y=y, color=color, color_discrete_sequence=SERIES)
    fig.update_traces(hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>")
    fig.update_layout(title=title, barmode="stack")
    fig.update_yaxes(tickprefix="$", tickformat="~s")
    fig.update_xaxes(type="category")
    return style(fig, height=height)


def pareto(df: pd.DataFrame, label: str, title: str = "Curva de Pareto de ingresos") -> go.Figure:
    data = df.head(40)
    fig = go.Figure()
    fig.add_bar(x=data[label], y=data["participacion"], name="Participación %", marker_color=PALETTE["navy"],
                hovertemplate="%{x}<br>%{y:.1f} %<extra></extra>")
    fig.add_scatter(x=data[label], y=data["acumulado"], name="Acumulado %", yaxis="y2", mode="lines",
                    line=dict(color=PALETTE["gold"], width=3), hovertemplate="Acumulado: %{y:.1f} %<extra></extra>")
    fig.update_layout(title=title, yaxis=dict(ticksuffix=" %"),
                      yaxis2=dict(overlaying="y", side="right", range=[0, 105], ticksuffix=" %", showgrid=False))
    fig.update_xaxes(showticklabels=False)
    return style(fig, height=380)


def waterfall(items: list[tuple[str, float, str]], title: str) -> go.Figure:
    """items: (etiqueta, valor, medida 'absolute'|'relative'|'total')."""
    fig = go.Figure(go.Waterfall(
        x=[i[0] for i in items], y=[i[1] for i in items], measure=[i[2] for i in items],
        connector=dict(line=dict(color="#CBD5E1")), increasing=dict(marker=dict(color=PALETTE["teal"])),
        decreasing=dict(marker=dict(color="#B4654A")), totals=dict(marker=dict(color=PALETTE["navy"])),
        hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
    fig.update_layout(title=title, yaxis=dict(tickprefix="$", tickformat="~s"))
    return style(fig, legend=False)


def scatter(df: pd.DataFrame, x: str, y: str, color: str, hover: str, title: str, size: str | None = None,
            labels: dict | None = None) -> go.Figure:
    fig = px.scatter(df, x=x, y=y, color=color, hover_name=hover, size=size, color_discrete_sequence=SERIES,
                     labels=labels or {}, log_y=True)
    fig.update_layout(title=title)
    fig.update_yaxes(dtick=1, tickprefix="$", tickformat="~s")
    return style(fig, height=420)


def treemap(df: pd.DataFrame, path: list[str], values: str, title: str) -> go.Figure:
    fig = px.treemap(df, path=path, values=values, color_discrete_sequence=SERIES)
    fig.update_traces(hovertemplate="%{label}<br>$%{value:,.0f}<extra></extra>", textinfo="label+percent root")
    fig.update_layout(title=title)
    return style(fig, height=380, legend=False)
