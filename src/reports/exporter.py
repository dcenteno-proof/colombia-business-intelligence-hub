"""Generación de reportes descargables (Excel multihoja y CSV).

Los reportes se construyen en memoria (``bytes``) para descargarse desde la
interfaz sin escribir archivos temporales. Cada Excel incluye una hoja
"Notas" que identifica los datos como DEMO y documenta las fórmulas.
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.analytics import commercial, customers, financial, operational
from src.analytics.alerts import evaluate_alerts
from src.analytics.dataset import Dataset
from src.analytics.filters import Filters, apply_dimensions, apply_expenses, apply_sales
from src.analytics.metrics import summarize
from src.config import COMPANY_NAME, NO_MOVEMENT_DAYS, ACTIVE_CUSTOMER_DAYS

MONEY_HINTS = ("ventas", "costo", "utilidad", "valor", "monto", "descuento", "devoluciones", "ticket", "gastos",
               "inventario_promedio", "precio", "periodo_anterior", "variacion")
PCT_HINTS = ("margen", "participacion", "crecimiento", "pct", "nivel_servicio", "entregas_a_tiempo", "acumulado",
             "sobre_ventas", "variacion_pct")
HEADER_FILL = PatternFill("solid", fgColor="0F2747")


def _is_pct(col: str) -> bool:
    return any(h in col for h in PCT_HINTS)


def _is_money(col: str) -> bool:
    return not _is_pct(col) and any(h in col for h in MONEY_HINTS)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.date
    return out


def to_excel(sheets: dict[str, pd.DataFrame], title: str, filters: Filters | None = None,
             notes: list[str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        meta = [("Reporte", title), ("Empresa", COMPANY_NAME), ("Tipo de datos", "DEMO - datos sintéticos de "
                                                                                 "demostración, no reales"),
                ("Generado", datetime.now().strftime("%Y-%m-%d %H:%M")),
                ("Periodo", filters.label() if filters else "Todo"),
                ("Regiones", ", ".join(filters.regions) if filters and filters.regions else "Todas"),
                ("Categorías", ", ".join(filters.categories) if filters and filters.categories else "Todas"),
                ("Productos", ", ".join(filters.products) if filters and filters.products else "Todos")]
        meta += [("Nota", n) for n in (notes or [])]
        pd.DataFrame(meta, columns=["Campo", "Valor"]).to_excel(writer, sheet_name="Notas", index=False)
        for name, df in sheets.items():
            _clean(df).to_excel(writer, sheet_name=name[:31], index=False)
        for ws in writer.book.worksheets:
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = HEADER_FILL
                cell.alignment = Alignment(vertical="center")
            ws.freeze_panes = "A2"
            headers = [c.value for c in ws[1]]
            for idx, header in enumerate(headers, start=1):
                letter = get_column_letter(idx)
                h = str(header or "")
                fmt = '"$" #,##0' if _is_money(h) else ('0.0"%"' if _is_pct(h) else None)
                max_len = len(h)
                for cell in ws[letter][1:]:
                    if fmt and isinstance(cell.value, (int, float)):
                        cell.number_format = fmt
                    max_len = max(max_len, min(len(str(cell.value or "")), 60))
                ws.column_dimensions[letter].width = max_len + 3
    return buffer.getvalue()


def to_csv(df: pd.DataFrame) -> bytes:
    """CSV UTF-8 con BOM y separador ';' (abre correctamente en Excel con configuración regional colombiana)."""
    return _clean(df).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


# ------------------------------------------------------------------ reportes
def _period_data(ds: Dataset, f: Filters):
    lines = apply_sales(ds.lines, f)
    exp = apply_expenses(ds.expenses, f)
    prev_f = f.previous_period()
    prev_lines = apply_sales(ds.lines, prev_f) if prev_f else None
    prev_exp = apply_expenses(ds.expenses, prev_f) if prev_f else None
    return lines, exp, prev_lines, prev_exp


def commercial_report(ds: Dataset, f: Filters) -> tuple[bytes, pd.DataFrame]:
    lines, _, prev_lines, _ = _period_data(ds, f)
    perf = commercial.product_performance(lines, prev_lines)
    sheets = {
        "Resumen mensual": commercial.monthly(lines),
        "Por categoria": commercial.by_dimension(lines, "categoria"),
        "Por region": commercial.by_dimension(lines, "region"),
        "Por vendedor": commercial.by_dimension(lines, "vendedor"),
        "Por producto": perf,
        "Top clientes": commercial.by_dimension(lines, "cliente").head(50),
        "Concentracion": commercial.concentration(lines, "cliente")["pareto"],
    }
    return to_excel(sheets, "Reporte comercial", f, ["Ventas netas = brutas - descuentos - devoluciones."]), perf


def financial_report(ds: Dataset, f: Filters) -> tuple[bytes, pd.DataFrame]:
    lines, exp, prev_lines, prev_exp = _period_data(ds, f)
    opex = int(exp["monto"].sum()) if exp is not None else None
    prev_opex = int(prev_exp["monto"].sum()) if prev_exp is not None and prev_lines is not None and \
        not prev_lines.empty else None
    pnl = financial.income_statement(lines, opex, prev_lines, prev_opex)
    sheets = {
        "Estado de resultados": pnl.drop(columns="clave"),
        "Mensual": financial.monthly_pnl(lines, exp),
        "Rentabilidad categoria": financial.profitability_by(lines, "categoria"),
        "Rentabilidad producto": financial.profitability_by(lines, "producto"),
        "Indicadores": pd.DataFrame(financial.financial_indicators(lines, opex)),
    }
    notes = ["Cifras de gestión calculadas a partir de transacciones; no reemplazan estados financieros contables.",
             "Con filtros de región/categoría/producto los gastos operativos no son atribuibles (N/D)."]
    return to_excel(sheets, "Reporte financiero", f, notes), pnl


def inventory_report(ds: Dataset, f: Filters) -> tuple[bytes, pd.DataFrame]:
    lines, _, _, _ = _period_data(ds, f)
    start, end = f.bounds()
    start = start or ds.lines["fecha"].min().date()
    end = end or ds.lines["fecha"].max().date()
    snaps = apply_dimensions(ds.snapshots, f)
    stock = operational.latest_stock(snaps[snaps["fecha_corte"] <= pd.Timestamp(end)], apply_dimensions(ds.lines, f))
    sheets = {
        "Existencias": stock,
        "Rotacion por producto": operational.turnover_by(lines, snaps, start, end, "producto"),
        "Rotacion por categoria": operational.turnover_by(lines, snaps, start, end, "categoria"),
        "Bajo minimo": operational.low_stock(snaps[snaps["fecha_corte"] <= pd.Timestamp(end)],
                                             apply_dimensions(ds.lines, f)),
        "Sin movimiento": operational.no_movement(apply_dimensions(ds.movements, f), snaps, end, NO_MOVEMENT_DAYS),
        "Proveedores": operational.supplier_performance(ds.purchases[
            (ds.purchases["fecha_orden"] >= pd.Timestamp(start)) & (ds.purchases["fecha_orden"] <= pd.Timestamp(end))]),
    }
    return to_excel(sheets, "Reporte de inventario", f, ["Rotación = costo de ventas / inventario promedio."]), stock


def customers_report(ds: Dataset, f: Filters) -> tuple[bytes, pd.DataFrame]:
    lines, _, _, _ = _period_data(ds, f)
    _, end = f.bounds()
    end = end or ds.lines["fecha"].max().date()
    ref = customers.reference_for_period(end)
    try:
        r = customers.rfm(lines, ref)
        seg = customers.segment_summary(r)
    except customers.InsufficientDataError as exc:
        r, seg = customers.customer_metrics(lines, ref), pd.DataFrame([{"mensaje": str(exc)}])
    status = customers.activity_status(apply_dimensions(ds.lines, f), ds.customers, ref, ACTIVE_CUSTOMER_DAYS)
    sheets = {"Segmentos RFM": seg, "Clientes RFM": r, "Actividad": status}
    return to_excel(sheets, "Reporte de clientes", f, ["Segmentación RFM por quintiles (ver docs)."]), r


def alerts_report(ds: Dataset, f: Filters) -> tuple[bytes, pd.DataFrame]:
    alerts, evaluations, month = evaluate_alerts(ds.lines, ds.expenses, ds.snapshots, ds.costs,
                                                 end_month=f.end_month)
    sheets = {"Alertas": alerts, "Reglas evaluadas": evaluations}
    return to_excel(sheets, "Reporte de alertas", f, [f"Mes evaluado: {month}", "Alertas a nivel compañía."]), alerts


def kpi_snapshot(ds: Dataset, f: Filters) -> dict:
    lines, exp, _, _ = _period_data(ds, f)
    return summarize(lines, int(exp["monto"].sum()) if exp is not None else None)
