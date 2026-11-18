"""Genera docs/index.html: vitrina estática del Hub para GitHub Pages (sin instalar nada para verla).

Uso: .venv\\Scripts\\python scripts\\build_showcase.py   (requiere la base DEMO: scripts\\setup_demo.py --reset)
"""
from __future__ import annotations

import datetime as dt
import html
import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.components import formatting as fmt  # noqa: E402
from src.analytics import commercial, metrics  # noqa: E402
from src.analytics.alerts import evaluate_alerts  # noqa: E402
from src.analytics.dataset import load_dataset  # noqa: E402

DOCS = ROOT / "docs"
AZUL, AMBAR = "#1F3A5F", "#F2A900"
CSS = """
:root{--fondo:#F6F7FB;--texto:#1D2939;--suave:#667085;--borde:#E4E7EC;--tarjeta:#fff}
@media (prefers-color-scheme: dark){:root{--fondo:#0F1520;--texto:#E6EAF0;--suave:#98A2B3;--borde:#2B3647;--tarjeta:#182131}}
*{box-sizing:border-box}body{margin:0;font-family:"Segoe UI",Roboto,Arial,sans-serif;background:var(--fondo);color:var(--texto)}
header{background:#1F3A5F;color:#fff;padding:28px 16px}header .c,main{max-width:1180px;margin:auto}main{padding:16px}
header h1{margin:0 0 6px;font-size:26px}header p{margin:0;opacity:.88}
.demo{background:#F2A900;color:#1D2939;font-weight:700;border-radius:6px;padding:2px 8px;font-size:12px;margin-left:8px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:8px 0 18px}
.kpi{background:var(--tarjeta);border:1px solid var(--borde);border-radius:12px;padding:14px}
.kpi .l{font-size:12px;color:var(--suave);text-transform:uppercase}.kpi .v{font-size:22px;font-weight:700;margin-top:4px}
h2{margin:26px 0 10px;font-size:20px;border-left:5px solid #F2A900;padding-left:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr));gap:14px}
.card{background:#fff;color:#1D2939;border:1px solid var(--borde);border-radius:12px;padding:12px;overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #E4E7EC}
th{background:#1F3A5F;color:#fff}.alta{color:#B42318;font-weight:700}.tabla{overflow-x:auto}
.links a{color:#fff;margin-right:14px}footer{color:var(--suave);font-size:12px;text-align:center;padding:30px 16px}
"""


def _base(fig: go.Figure, titulo: str, alto: int = 380) -> go.Figure:
    fig.update_layout(title=dict(text=titulo, x=0, font=dict(size=15)), height=alto, separators=",.",
                      margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=-0.2),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
    return fig


def _fig(fig: go.Figure, primero: bool = False) -> str:
    return '<div class="card">' + fig.to_html(full_html=False, include_plotlyjs="plotly.min.js" if primero else False,
                                              config={"displaylogo": False, "responsive": True}) + "</div>"


def main() -> None:
    d = load_dataset()
    if d.is_empty:
        sys.exit("La base está vacía: ejecute scripts\\setup_demo.py --reset")
    meses = d.months[-12:]
    lines = d.lines[d.lines.mes.isin(meses)]
    opex = int(d.expenses[d.expenses.mes.isin(meses)]["monto"].sum()) if "monto" in d.expenses else None
    k = metrics.summarize(lines, opex)
    # Crecimiento comparable: últimos 3 meses vs. los mismos 3 meses del año anterior
    ult3 = d.months[-3:]
    aa3 = [f"{int(m[:4]) - 1}{m[4:]}" for m in ult3]
    base_aa = d.lines[d.lines.mes.isin(aa3)]
    crec = (metrics.growth_pct(d.lines[d.lines.mes.isin(ult3)].ventas_netas.sum(), base_aa.ventas_netas.sum())
            if base_aa.mes.nunique() == 3 else None)

    tarjetas = "".join(
        f'<div class="kpi"><div class="l">{l}</div><div class="v">{v}</div></div>' for l, v in [
            ("Ventas netas (12 meses)", fmt.cop_short(k["ventas_netas"])),
            (f"Crecimiento {ult3[0]} a {ult3[-1]} vs. año anterior", fmt.pct(crec, signed=True)),
            ("Margen bruto", fmt.pct(k["margen_bruto"])),
            ("Margen operacional", fmt.pct(k["margen_operacional"])),
            ("Ticket promedio", fmt.cop(k["ticket_promedio"])),
            ("Clientes activos", fmt.num(k["clientes_activos"])),
        ])

    mens = commercial.monthly(d.lines[d.lines.mes.isin(d.months[-24:])])
    f1 = go.Figure()
    f1.add_bar(x=mens.mes, y=mens.ventas_netas / 1e6, name="Ventas netas ($ M)", marker_color=AZUL)
    f1.add_scatter(x=mens.mes, y=mens.margen_bruto, name="Margen bruto (%)", yaxis="y2", line=dict(color=AMBAR))
    f1.update_layout(yaxis=dict(title="$ millones"), yaxis2=dict(overlaying="y", side="right", title="%"))
    reg = commercial.by_dimension(lines, "region")
    reg["ventas_netas"] = reg.ventas_netas / 1e6
    f2 = px.bar(reg, x="ventas_netas", y="region", orientation="h", color="margen_bruto",
                color_continuous_scale=["#C0392B", "#F7DC6F", "#2E8B57"],
                labels={"ventas_netas": "Ventas netas ($ millones)", "region": "", "margen_bruto": "Margen %"})
    cat = commercial.by_dimension(lines, "categoria")
    cat["ventas_netas"] = cat.ventas_netas / 1e6
    f3 = px.bar(cat, x="categoria", y="ventas_netas", color="margen_bruto",
                color_continuous_scale=["#C0392B", "#F7DC6F", "#2E8B57"],
                labels={"ventas_netas": "Ventas netas ($ millones)", "categoria": "", "margen_bruto": "Margen %"})
    canal = commercial.by_dimension(lines, "canal")
    f4 = px.pie(canal, names="canal", values="ventas_netas", hole=0.5,
                color_discrete_sequence=[AZUL, AMBAR, "#2E8B57", "#C0392B", "#6C5CE7"])

    alertas, _, mes_alerta = evaluate_alerts(d.lines, d.expenses, d.snapshots, d.costs)
    filas = "".join(
        f'<tr><td class="{"alta" if a.severidad == "Alta" else ""}">{a.severidad}</td><td>{html.escape(a.titulo)}</td>'
        f"<td>{html.escape(a.valor_observado)}</td><td>{html.escape(a.umbral)}</td>"
        f"<td>{html.escape(a.recomendacion)}</td></tr>" for a in alertas.itertuples())

    repo = "https://github.com/dcenteno-proof/colombia-business-intelligence-hub"
    cuerpo = f"""
<header><div class="c"><h1>Colombia Business Intelligence Hub <span class="demo">DATOS DEMO</span></h1>
<p>BI para una distribuidora ficticia de consumo masivo: ventas, rentabilidad, inventario, clientes y alertas.
Últimos 12 meses: {meses[0]} a {meses[-1]}.</p>
<p class="links" style="margin-top:10px"><a href="{repo}">Código en GitHub</a>
<a href="{repo}/blob/master/docs/metodologia_indicadores.md">Metodología</a>
<a href="https://danielcenteno.netlify.app">Autor: Daniel Centeno</a></p></div></header>
<main>
<div class="kpis">{tarjetas}</div>
<h2>Ventas y rentabilidad</h2>
<div class="grid">{_fig(_base(f1, "Ventas netas mensuales y margen bruto"), primero=True)}
{_fig(_base(f2, "Ventas y margen por región (12 meses)"))}</div>
<div class="grid">{_fig(_base(f3, "Ventas y margen por categoría"))}{_fig(_base(f4, "Participación por canal"))}</div>
<h2>Centro de alertas ({mes_alerta}): {len(alertas)} alertas</h2>
<div class="card tabla"><table><tr><th>Severidad</th><th>Alerta</th><th>Valor observado</th><th>Umbral</th>
<th>Recomendación</th></tr>{filas}</table></div>
<p style="color:var(--suave);font-size:13px">La aplicación completa (Streamlit) tiene además estado de resultados,
segmentación RFM de clientes, rotación de inventario, desempeño de proveedores, carga ETL de archivos y
reportes en Excel. Ver instrucciones en el repositorio.</p>
</main>
<footer>Datos 100 % sintéticos; empresas, clientes y productos son ficticios. Generado el {dt.date.today().isoformat()}
· Python · SQL · Plotly.</footer>
<script>window.addEventListener("load",function(){{document.querySelectorAll(".plotly-graph-div")
.forEach(function(x){{Plotly.Plots.resize(x);}});}});</script>"""
    DOCS.mkdir(exist_ok=True)
    js = DOCS / "plotly.min.js"
    if not js.exists():
        from plotly.offline import get_plotlyjs
        js.write_text(get_plotlyjs(), encoding="utf-8")
    (DOCS / "index.html").write_text(
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'><title>Colombia BI Hub</title>"
        f"<style>{CSS}</style></head><body>{cuerpo}</body></html>", encoding="utf-8")
    print(DOCS / "index.html")


if __name__ == "__main__":
    main()
